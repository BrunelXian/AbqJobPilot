import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import uuid

import pytest

import engine
import frozen
import records
import windows_host
from printed_results import parse
from abqjobpilot.execution.process_handles import ProcessReference

HERE = Path(__file__).resolve().parent
PYTHON = r'D:\Program Files\Python312\python.exe'
ENV_PYTHON = r'D:\XianLab\envs\LangChainEnv\Scripts\python.exe'
TEXT = b'''ABAQUS 2024
ABAQUS/STANDARD
STEP 1 INCREMENT 1
TOTAL TIME COMPLETED 1.0000

NODE U1 U2 U3
1 0 0 0
2 1.0000E-2 0 0

NODE RF1 RF2 RF3
1 -1 0 0
2 0 0 0

ELEMENT PT S11
1 1 1.0000

THE ANALYSIS HAS BEEN COMPLETED
'''


def make_case(tmp_path):
    root = tmp_path / ('case_' + uuid.uuid4().hex[:8]); root.mkdir()
    for path in ('observations','engineering/scratch','extracted'):
        (root / path).mkdir(parents=True)
    spec = {'root':str(root),'job':'test_job','experiment_id':'fixture_only',
            'original_digest':'test-only','output_identity':'fixture-output','budget_seconds':1}
    return root, spec


def pass_host():
    return {'job_query_succeeded':True, 'in_any_job':False, 'test_only':True}


def forbidden(*a, **k):
    pytest.fail('External process must be unreachable')


def inventory(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def wait_for(predicate, seconds=12):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate(): return
        time.sleep(.01)
    raise AssertionError('Deterministic phase/exit condition not reached within fixture budget')


def persist_test(name, data):
    directory = Path(os.environ['R11_EVIDENCE_DIR'])
    directory.mkdir(exist_ok=True)
    with (directory / (name + '.json')).open('x', encoding='utf-8') as out:
        json.dump(data, out, indent=2)


class Launched:
    def __init__(self, root, script, args, *, interpreter=PYTHON):
        self.out = (root / ('stdout_' + uuid.uuid4().hex + '.txt')).open('xb')
        self.err = (root / ('stderr_' + uuid.uuid4().hex + '.txt')).open('xb')
        self.p = subprocess.Popen([interpreter, '-B', str(script), *args], cwd=root,
            env={'SystemRoot':r'C:\Windows','TEMP':str(root),'TMP':str(root),'PYTHONDONTWRITEBYTECODE':'1'},
            stdin=subprocess.DEVNULL, stdout=self.out, stderr=self.err,
            close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW)
        self.ref = ProcessReference(self.p.pid)

    def finish(self):
        wait_for(lambda:self.p.poll() is not None)
        evidence = self.ref.exit_evidence()
        assert evidence is not None
        value = {'identity':self.ref.identity,'exit':evidence,'stdout':str(self.out.name),
                 'stderr':str(self.err.name),'handles_closed':True}
        self.ref.close(); self.p._handle.Close(); self.p._child_created = False
        self.out.close(); self.err.close()
        assert self.ref.handle is None and self.p._handle.closed and self.out.closed and self.err.closed
        return value


@pytest.mark.parametrize('state', [False, None, 'unknown', 1])
def test_r11_02_query_failure_never_claims(tmp_path, state):
    root, spec = make_case(tmp_path)
    with pytest.raises(records.Refusal, match='HOST_JOB_BLOCKED'):
        engine.run_once(spec, 'v1', lambda:None,
            lambda:{'job_query_succeeded':state, 'in_any_job':False}, forbidden)
    assert inventory(root) == {}


@pytest.mark.parametrize('membership', [True, None, 'false', 0])
def test_r11_02_job_or_unknown_never_claims(tmp_path, membership):
    root, spec = make_case(tmp_path)
    with pytest.raises(records.Refusal, match='HOST_JOB_BLOCKED'):
        engine.run_once(spec, 'v1', lambda:None,
            lambda:{'job_query_succeeded':True,'in_any_job':membership}, forbidden)
    assert inventory(root) == {}


def test_r11_01_material_failure_before_intent(tmp_path):
    root, spec = make_case(tmp_path)
    def reject(): raise records.Refusal('MATERIAL_CHANGED')
    with pytest.raises(records.Refusal, match='MATERIAL_CHANGED'):
        engine.run_once(spec, 'v1', reject, pass_host, forbidden)
    assert inventory(root) == {}


@pytest.mark.parametrize('contents', [b'', b'{', b'{}', b'corrupt prior claim'])
def test_r11_03_any_existing_attempt_blocks_new_version(tmp_path, contents):
    root, spec = make_case(tmp_path)
    (root / 'observations/attempt.json').write_bytes(contents)
    before = inventory(root)
    with pytest.raises(records.Refusal, match='ATTEMPT_EXISTS'):
        engine.run_once(spec, 'different_candidate_version', lambda:None, pass_host, forbidden)
    assert inventory(root) == before


def test_r11_04_intent_fsync_failure_never_calls_and_preserves(tmp_path, monkeypatch):
    root, spec = make_case(tmp_path)
    monkeypatch.setattr(records.os, 'fsync', lambda fd: (_ for _ in ()).throw(OSError('injected')))
    with pytest.raises(OSError):
        engine.run_once(spec, 'v1', lambda:None, pass_host, forbidden)
    assert (root / 'observations/attempt.json').exists()
    with pytest.raises(records.Refusal, match='ATTEMPT_EXISTS'):
        engine.run_once(spec, 'v2', lambda:None, pass_host, forbidden)


def test_r11_04_creation_unknown_keeps_attempt_and_distinct_state(tmp_path):
    root, spec = make_case(tmp_path); called = []
    def unknown(out, err):
        assert records.read_json(root / 'observations/attempt.json')['state'] == 'START_INTENT'
        called.append(1); raise OSError('may have created before response was lost')
    report = engine.run_once(spec, 'v1', lambda:None, pass_host, unknown)
    assert called == [1] and report['creation'] == 'CALL_ENTERED_OUTCOME_UNKNOWN'
    assert report['outcome'] == 'UNKNOWN_NO_RETRY'
    with pytest.raises(records.Refusal): engine.run_once(spec, 'v2', lambda:None, pass_host, forbidden)


def test_r11_04_report_failure_is_unknown_not_success(tmp_path, monkeypatch):
    root, spec = make_case(tmp_path)
    original = engine.write_new
    def broken(path, value):
        if path.name == 'controller_report.json': raise OSError('injected')
        return original(path,value)
    monkeypatch.setattr(engine, 'write_new', broken)
    with pytest.raises(records.Refusal, match='REPORT_COMMIT_UNKNOWN'):
        engine.run_once(spec, 'v1', lambda:None, pass_host,
                        lambda out,err: (_ for _ in ()).throw(OSError('injected create failure')))
    assert engine.read_report(spec)['status'] == 'ATTEMPT_WITHOUT_CONFIRMED_REPORT'
    with pytest.raises(records.Refusal): engine.run_once(spec,'v2',lambda:None,pass_host,forbidden)


def test_r11_07_exact_text_rules_and_signed_reference():
    result = parse(TEXT)
    assert result['numerical'] == 'VALID_TEXT_SUBSET'
    refs = {c['quantity']:c for c in result['comparisons']}
    assert refs['2_U1']['expected'] == '0.01' and refs['1_RF1']['expected'] == '-1'
    assert refs['1_S11']['effective_tolerance'] == '0.0001'
    assert result['solver'] != 'SUCCESS' and result['odb_content_validation'] == 'NOT_RUN'


@pytest.mark.parametrize('old,new', [
    (b'1.0000E-2',b'0.010002'), (b'1 -1 0 0',b'1 1 0 0'),
    (b'1 1 1.0000',b'1 1 1.0002'), (b'2 0 0 0',b'2 0.001 0 0')])
def test_r11_07_outside_frozen_tolerance_is_failure(old,new):
    assert parse(TEXT.replace(old,new))['numerical'] == 'NUMERICAL_FAIL'


@pytest.mark.parametrize('data', [b'', TEXT[:-40], TEXT + TEXT,
    TEXT.replace(b'TOTAL TIME COMPLETED 1.0000',b'TOTAL TIME COMPLETED 0.0000'),
    TEXT.replace(b'1.0000E-2',b'NaN'), TEXT.replace(b'1.0000E-2',b'*****'),
    TEXT.replace(b'NODE U1 U2 U3', b'NODE U2 U1 U3'),
    TEXT.replace(b'2 1.0000E-2 0 0', b'3 1.0000E-2 0 0'),
    TEXT.replace(b'1 1 1.0000', b'1 2 1.0000'),
    TEXT.replace(b'STEP 1 INCREMENT 1',b'STEP 2 INCREMENT 1'),
    TEXT.replace(b'ABAQUS 2024', b'ABAQUS 2025'), TEXT + b'***ERROR\n'])
def test_r11_07_missing_conflicting_unsupported_text_never_passes(data):
    assert parse(data)['numerical'] == 'EVIDENCE_INSUFFICIENT'


@pytest.mark.parametrize('data', [TEXT.replace(b'ABAQUS/STANDARD',b'ABAQUS/EXPLICIT'),
    TEXT + b'INCOMPLETE NEXT BLOCK\n', TEXT.replace(b'NODE U1 U2 U3',b'OTHER OUTPUT\nNODE U1 U2 U3')])
def test_r11_07_wrong_product_or_unrecognized_blocks_refused(data):
    assert parse(data)['numerical'] == 'EVIDENCE_INSUFFICIENT'


def test_r11_02_host_query_exception_is_before_write(tmp_path):
    root, spec = make_case(tmp_path)
    def unknown(): raise OSError('injected API failure')
    with pytest.raises(OSError): engine.run_once(spec,'v1',lambda:None,unknown,forbidden)
    assert inventory(root) == {}


def test_r11_04_event_persistence_failure_prevents_creation(tmp_path, monkeypatch):
    root,spec=make_case(tmp_path)
    monkeypatch.setattr(engine.Journal,'append',lambda *a,**k:(_ for _ in ()).throw(OSError('injected')))
    report=engine.run_once(spec,'v1',lambda:None,pass_host,forbidden)
    assert report['creation'] == 'NOT_CALLED' and report['outcome'] == 'UNKNOWN_NO_RETRY'
    with pytest.raises(records.Refusal): engine.run_once(spec,'v2',lambda:None,pass_host,forbidden)


def test_r11_01_unsafe_cli_parameter_is_not_supported(tmp_path):
    root,_=make_case(tmp_path)
    child=Launched(root,HERE.parent/'controller/probe.py',['check','--skip-job-check'],interpreter=ENV_PYTHON)
    evidence=child.finish()
    assert evidence['exit']['exit_code'] == 2
    assert 'unrecognized arguments' in Path(evidence['stderr']).read_text()
    persist_test('unsafe_parameter', {'process':evidence,'no_real_execute_invoked':True})


def test_r11_07_report_read_does_not_probe_or_change(tmp_path, monkeypatch):
    root,spec=make_case(tmp_path)
    report=engine.run_once(spec,'v1',lambda:None,pass_host,
        lambda *a:(_ for _ in ()).throw(OSError('fixture call outcome unknown')))
    before=inventory(root)
    monkeypatch.setattr(windows_host,'current_host',forbidden)
    monkeypatch.setattr(engine,'collect_files',forbidden)
    value=engine.read_report(spec)
    assert value['report'] == report and inventory(root) == before


def test_r11_07_old_output_and_living_member_do_not_validate(tmp_path):
    root, spec = make_case(tmp_path)
    dat = root / 'engineering/test_job.dat'; dat.write_bytes(TEXT)
    with pytest.raises(records.Refusal, match='OUTPUT_EXISTS'):
        engine.run_once(spec, 'v1', lambda:None, pass_host, forbidden)
    with pytest.raises(records.Refusal, match='OLD_OR_UNATTRIBUTED_DAT'):
        engine.collect_files(spec, {'start_intent_at_ns':records.stamp()+1000000000},
                             {'all_observed_exited':True})
    result = engine.collect_files(spec, {'start_intent_at_ns':1}, {'all_observed_exited':False})
    assert result['numerical'] == 'EVIDENCE_INSUFFICIENT'


def test_r11_07_input_change_during_attempt_refuses_results(tmp_path):
    root,spec=make_case(tmp_path)
    source=root/'engineering/input.txt'; source.write_bytes(b'original')
    spec.update(input_path=str(source), input_digest='sha256:'+hashlib.sha256(b'original').hexdigest())
    source.write_bytes(b'changed')
    with pytest.raises(records.Refusal, match='INPUT_CHANGED_DURING_ATTEMPT'):
        engine.collect_files(spec,{'start_intent_at_ns':1},{'all_observed_exited':True})


@pytest.mark.parametrize('operation', ['default','help','check','report','import'])
def test_r11_01_public_readonly_entry_no_process_or_writes(tmp_path, operation):
    root, _ = make_case(tmp_path)
    before = inventory(frozen.ROOT / 'observations')
    args = {'default':[], 'help':['--help'], 'check':['check'], 'report':['report'], 'import':[]}[operation]
    script = HERE / 'readonly_driver.py' if operation == 'import' else HERE.parent / 'controller/probe.py'
    child = Launched(root, script, args, interpreter=ENV_PYTHON)
    exit_record = child.finish()
    text = Path(exit_record['stdout']).read_text()
    assert exit_record['exit']['exit_code'] in ({0,2} if operation in {'default','check'} else {0})
    if operation in {'default','check'}:
        assert json.loads(text)['status'] == 'CHECK_ONLY'
    assert inventory(frozen.ROOT / 'observations') == before
    persist_test('readonly_'+operation, {'process':exit_record, 'stdout':text,
                                        'real_root_unchanged':True})


def test_r11_08_candidate_digest_and_parameter_changes_rejected(monkeypatch):
    original, candidate = frozen.load_candidate()
    assert candidate['body']['original_digest'] == frozen.ORIGINAL_DIGEST
    with pytest.raises(records.Refusal, match='CANDIDATE_CHANGED'):
        frozen.load_candidate('sha256:' + '0'*64)
    changed = copy.deepcopy(candidate); changed['body']['windows_call']['command_line'] += ' extra=1'
    changed['content_digest'] = records.digest(changed['body'])
    real_read = frozen.read_json
    monkeypatch.setattr(frozen, 'read_json', lambda p:changed if p.name == 'CANDIDATE_MANIFEST.json' else real_read(p))
    with pytest.raises(records.Refusal, match='CANDIDATE_CONFIGURATION_CHANGED'):
        frozen.load_candidate(changed['content_digest'])


def test_r11_08_material_byte_change_rejected(tmp_path):
    root, _ = make_case(tmp_path); f = root/'source.py'; f.write_bytes(b'old')
    item={'path':str(f),'bytes':3,'sha256':hashlib.sha256(b'old').hexdigest()}
    f.write_bytes(b'new')
    with pytest.raises(records.Refusal, match='MATERIAL_CHANGED'): frozen.verify_materials([item])


def test_r11_01_frozen_invocation_forwarded_exactly_without_os_create(monkeypatch):
    seen=[]
    marker=object()
    def capture(args, **kwargs): seen.append((args,kwargs)); return marker
    monkeypatch.setattr(subprocess,'Popen',capture)
    out,err=object(),object()
    assert frozen.spawn_frozen(out,err) is marker
    body=frozen.original()['body']; args,kw=seen[0]
    assert len(seen) == 1 and args == body['windows_call']['command_line']
    assert isinstance(args,str) and kw['executable'] == body['windows_call']['application']
    assert kw['cwd'] == body['windows_call']['cwd'] and kw['env'] == body['environment_policy']['values']
    assert kw['shell'] is False and kw['close_fds'] is True
    assert kw['creationflags'] == subprocess.CREATE_NO_WINDOW
    assert kw['stdin'] == subprocess.DEVNULL and kw['stdout'] is out and kw['stderr'] is err


def test_r11_07_reference_matches_frozen_original():
    reference=frozen.original()['body']['acceptance_reference']
    items={c['quantity']:c for c in parse(TEXT)['comparisons']}
    for key, original_key in [('2_U1','node2_U1_mm'),('1_S11','element1_S11_MPa'),('1_RF1','node1_RF1_N')]:
        assert items[key]['expected'] == reference['expected_decimal'][original_key]
        assert items[key]['effective_tolerance'] == reference['tolerances'][original_key]['absolute']


def natural_worker_cleanup(root):
    wait_for(lambda:(root/'worker_ready.json').exists())
    identity = json.loads((root/'worker_ready.json').read_text())
    ref = ProcessReference(identity['pid'], identity)
    try:
        (root/'release').touch()
        wait_for(lambda:ref.exit_evidence() is not None)
        evidence = ref.exit_evidence()
        assert evidence['exit_code'] == 0 and (root/'worker_done.json').exists()
        return {'identity':identity, 'exit':evidence, 'method':'fixture release then natural exit',
                'handle_closed':True}
    finally:
        ref.close()
        assert ref.handle is None


@pytest.mark.parametrize('mode', ['worker','launcher'])
def test_r11_05_06_controller_returns_worker_continues_then_exits(tmp_path, mode):
    root, spec = make_case(tmp_path)
    child = Launched(root, HERE/'fixture_driver.py', [mode,str(root),'a'])
    controller_exit = child.finish()
    wait_for(lambda:(root/'worker_ready.json').exists())
    identity=json.loads((root/'worker_ready.json').read_text())
    ref=ProcessReference(identity['pid'], identity)
    try:
        assert ref.exit_evidence() is None
        size=(root/'heartbeat.txt').stat().st_size
        wait_for(lambda:(root/'heartbeat.txt').stat().st_size > size)
        assert ref.exit_evidence() is None
    finally: ref.close()
    report=json.loads((root/'reply_a.json').read_text())
    assert controller_exit['exit']['exit_code'] == 0
    assert report['deadline_reached'] and report['processes']['overall_exit'] == 'UNKNOWN'
    assert report['processes']['member_completeness'] == 'UNKNOWN'
    cleanup=natural_worker_cleanup(root)
    assert len(list(root.glob('physical_worker_*.json'))) == 1
    if mode == 'launcher':
        assert any(p['pid'] == report['launch_pid'] and p['exit_code'] == 0 for p in report['processes']['exits'])
    persist_test('survival_'+mode, {'controller':controller_exit,'report':report,
        'worker_alive_and_file_grew_after_controller_exit':True,'cleanup':cleanup,
        'physical_registrations':[json.loads(p.read_text()) for p in root.glob('physical_*.json')]})


def test_r11_03_four_process_concurrency_and_repeat(tmp_path):
    root, spec=make_case(tmp_path)
    children=[Launched(root,HERE/'fixture_driver.py',['race',str(root),tag]) for tag in 'abcd']
    wait_for(lambda:len(list(root.glob('driver_ready_*'))) == 4)
    (root/'race_go').touch()
    exits=[p.finish() for p in children]
    assert sorted(p['exit']['exit_code'] for p in exits) == [0,2,2,2]
    before=inventory(root/'observations')
    repeated=Launched(root,HERE/'fixture_driver.py',['worker',str(root),'d']).finish()
    assert repeated['exit']['exit_code'] == 2 and inventory(root/'observations') == before
    cleanup=natural_worker_cleanup(root)
    assert len(list(root.glob('physical_worker_*.json'))) == 1
    persist_test('concurrency', {'controllers':exits,'repeat':repeated,'cleanup':cleanup,
                                'physical_worker_starts':1,'candidate_versions':'a,b,c,d'})


@pytest.mark.parametrize('mode,code,worker', [('crash_intent',91,False),('crash_created',92,True)])
def test_r11_04_real_controller_exit_preserves_claim(tmp_path,mode,code,worker):
    root,spec=make_case(tmp_path)
    crashed=Launched(root,HERE/'fixture_driver.py',[mode,str(root),'a']).finish()
    assert crashed['exit']['exit_code'] == code
    assert engine.read_report(spec)['status'] == 'ATTEMPT_WITHOUT_CONFIRMED_REPORT'
    repeat=Launched(root,HERE/'fixture_driver.py',['worker',str(root),'b']).finish()
    assert repeat['exit']['exit_code'] == 2
    cleanup=natural_worker_cleanup(root) if worker else None
    assert len(list(root.glob('physical_worker_*.json'))) == int(worker)
    persist_test(mode, {'controller':crashed,'repeat':repeat,'cleanup':cleanup,
        'service_pid_record':'absent after intent / before identity persistence',
        'independent_fixture_registration_used_only_for_test_cleanup':worker})
