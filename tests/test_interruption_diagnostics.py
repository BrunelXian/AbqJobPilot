"""D02 simulated history and no-write assertions; no external execution."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from abqjobpilot.execution.interruption import inspect_interrupted_execution, build_interruption_report
from abqjobpilot.execution.models import ExecutionError, canonical_json, identifier
from abqjobpilot.execution.store import ReadOnlyStore, document, update_run
from execution_helpers import guard_environment, harness, inventory
from test_fake_reconciliation import uncertain


def inspect(h):
    return inspect_interrupted_execution(h.context, h.run_id)['body']


def view(owner='NOT_OBSERVED', member=None, boot='NOT_OBSERVED'):
    return {'source':'CURRENT_WINDOWS_READONLY', 'started_at':1, 'finished_at':2,
        'owner':{'state':owner}, 'members':[] if member is None else [{'state':member}],
        'boot':{'state':boot,'confidence':'ESTIMATE_NOT_SESSION_PROOF'},
        'lock':'NOT_ACQUIRED','scope_handle':'NOT_QUERIED'}


def projected(h, observation):
    raw=h.store._diagnostic_snapshot(h.context,h.run_id,interruption=True)
    return build_interruption_report(h.context,raw,observation)['body']


def test_pending_then_completed_without_any_observation_or_write(harness,monkeypatch):
    h=harness;_,_,receipt=h.accept();h.run_id=receipt['run_id']
    import abqjobpilot.execution.interruption_probe as probe
    monkeypatch.setattr(probe,'observe',lambda *a:pytest.fail('No implicit OS query'))
    before=inventory(h.root)
    a=inspect(h); b=inspect(h)
    assert a['diagnosis']['classification']=='NEVER_STARTED_RECORDED'
    assert a['decision_digest']==b['decision_digest'] and inventory(h.root)==before
    h.service.execute_pending(h.context,h.run_id)
    before=inventory(h.root);a=inspect(h)
    assert a['diagnosis']['classification']=='COMPLETION_RECORDED'
    assert a['facts']['run']['solver_conclusion']=='NOT_RUN'
    assert inventory(h.root)==before


@pytest.mark.parametrize('owner,member,boot,expected',[
    ('EXACT_IDENTITY_ALIVE','EXACT_IDENTITY_ALIVE','NOT_OBSERVED','EXECUTION_ACTIVITY_OBSERVED'),
    ('EXACT_IDENTITY_EXITED','EXACT_IDENTITY_ALIVE','NOT_OBSERVED','OWNER_LOST_WORKER_ACTIVE'),
    ('PROCESS_UNAVAILABLE',None,'LATER_BOOT_ESTIMATE','SUPERVISION_INTERRUPTION_SUSPECTED'),
    ('IDENTITY_MISMATCH',None,'NOT_OBSERVED','EXECUTION_STATE_UNKNOWN'),
    ('PROCESS_UNAVAILABLE',None,'ESTIMATE_ONLY','EXECUTION_STATE_UNKNOWN'),
    ('QUERY_FAILED',None,'LATER_BOOT_ESTIMATE','EXECUTION_STATE_UNKNOWN'),
    ('PROCESS_UNAVAILABLE',None,'CLOCK_UNSTABLE','EXECUTION_STATE_UNKNOWN'),
    ('IDENTITY_UNRECORDED',None,'LATER_BOOT_ESTIMATE','EXECUTION_STATE_UNKNOWN'),
    ('EXACT_IDENTITY_ALIVE',None,'LATER_BOOT_ESTIMATE','EXECUTION_ACTIVITY_OBSERVED'),
    ('PROCESS_UNAVAILABLE','EXACT_IDENTITY_ALIVE','LATER_BOOT_ESTIMATE','EXECUTION_ACTIVITY_OBSERVED'),
])
def test_simulated_observation_classification_no_state_change(uncertain,owner,member,boot,expected):
    h=uncertain;before=inventory(h.root)
    report=projected(h,view(owner,member,boot))
    assert report['diagnosis']['classification']==expected
    assert report['diagnosis']['display_projection']==('UNKNOWN_INTERRUPTED' if expected in {
        'OWNER_LOST_WORKER_ACTIVE','SUPERVISION_INTERRUPTION_SUSPECTED'} else expected)
    assert not report['recovery_preview']['apply_allowed']
    assert inventory(h.root)==before and h.effects==[h.run_id]


def test_owner_change_missing_scope_and_unrelated_files_do_not_prove_completion(uncertain):
    h=uncertain
    with h.store.transaction('isolated_negative_history') as db:
        db.execute("UPDATE meta SET value=? WHERE key='owner_id'",(identifier('owner'),))
    (h.root/'unbound.dat').write_text('ANALYSIS COMPLETE')
    (h.root/'unbound.odb').write_bytes(b'not trusted result')
    before=inventory(h.root);report=inspect(h)
    assert report['diagnosis']['classification']=='SUPERVISION_INTERRUPTION_SUSPECTED'
    assert report['facts']['run']['artifact_validation']=='UNKNOWN'
    assert report['resources']['slot_run_id']==h.run_id
    assert report['resources']['gate']['state']=='PAUSED'
    assert inventory(h.root)==before


@pytest.mark.parametrize('damage',['plan_digest','missing_start','missing_receipt','missing_consumption','owner_identity','backend_identity'])
def test_corrupt_history_fails_closed_without_repair(uncertain,damage):
    h=uncertain
    with h.store.transaction('isolated_corruption') as db:
        if damage=='plan_digest':
            run=document(db,'runs','run_id',h.run_id);run['plan_digest']='sha256:'+'a'*64
            db.execute('UPDATE runs SET body=? WHERE run_id=?',(canonical_json(run),h.run_id))
        if damage=='missing_start':db.execute("DELETE FROM events WHERE run_id=? AND json_extract(body,'$.type')='START_INTENT'",(h.run_id,))
        if damage=='missing_receipt':db.execute('DELETE FROM receipts WHERE run_id=?',(h.run_id,))
        if damage=='missing_consumption':db.execute('DELETE FROM consumption WHERE run_id=?',(h.run_id,))
        if damage in {'owner_identity','backend_identity'}:
            run=document(db,'runs','run_id',h.run_id)
            run['owner_id' if damage=='owner_identity' else 'backend_id']='invalid-secret-field'
            db.execute('UPDATE runs SET body=? WHERE run_id=?',(canonical_json(run),h.run_id))
    before=inventory(h.root)
    try: assert inspect(h)['diagnosis']['classification']=='EVIDENCE_CONFLICT'
    except ExecutionError as exc: assert exc.code=='STORE_UNAVAILABLE'
    assert inventory(h.root)==before


def test_wrong_project_format_and_invalid_flag_safe_rejection(harness):
    h=harness;_,_,receipt=h.accept();h.run_id=receipt['run_id'];before=inventory(h.root)
    for context in (replace(h.context,project_id=identifier('p')),replace(h.context,schema_version=99)):
        with pytest.raises(ExecutionError):inspect_interrupted_execution(context,h.run_id)
    with pytest.raises(ExecutionError):inspect_interrupted_execution(h.context,h.run_id,observe_os='yes')
    assert inventory(h.root)==before


def test_effect_traps_and_os_observation_after_snapshot_closed(uncertain,monkeypatch):
    h=uncertain;closed=[];before=inventory(h.root)
    def forbidden(*a,**k):pytest.fail('Diagnostic attempted a business side effect')
    monkeypatch.setattr(h.store,'transaction',forbidden)
    for name in ('execute_pending','apply_reconciliation','resume_dispatch','submit'):
        monkeypatch.setattr(h.service,name,forbidden)
    monkeypatch.setattr(ReadOnlyStore,'_diagnostic_checkpoint',lambda self,stage:closed.append(stage))
    def observe(*args):
        assert closed[-1]=='diagnostic:after_close'
        return view('EXACT_IDENTITY_ALIVE','EXACT_IDENTITY_ALIVE')
    monkeypatch.setattr('abqjobpilot.execution.interruption_probe.observe',observe)
    report=inspect_interrupted_execution(h.context,h.run_id,observe_os=True)
    assert report['body']['diagnosis']['classification']=='EXECUTION_ACTIVITY_OBSERVED'
    assert inventory(h.root)==before


def test_snapshot_limits_and_no_payload_leak(uncertain):
    h=uncertain
    raw=h.store._diagnostic_snapshot(h.context,h.run_id,interruption=True)
    run=json.loads(raw['run'][0][0]);run['private_secret']='never-export-this'
    raw['run']=[(canonical_json(run),raw['run'][0][1])]
    observation=view();observation['secret']='never-export-this';observation['owner']['image_path']='never-export-this'
    encoded=canonical_json(build_interruption_report(h.context,raw,observation))
    assert 'never-export-this' not in encoded and str(h.root) not in encoded
    with h.store.transaction('isolated_oversized_record') as db:
        run['private_secret']='x'*20000
        db.execute('UPDATE runs SET body=? WHERE run_id=?',(canonical_json(run),h.run_id))
    before=inventory(h.root)
    with pytest.raises(ExecutionError) as exc:inspect(h)
    assert exc.value.code=='LIMIT_EXCEEDED' and inventory(h.root)==before


def test_atomic_database_view_writer_progress_and_no_owned_lock(harness,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    h=harness;_,_,receipt=h.accept();h.run_id=receipt['run_id']
    read_started,write_staged,write_finished=threading.Event(),threading.Event(),threading.Event()
    def checkpoint(self,stage):
        if stage=='diagnostic:after_run':
            read_started.set();assert write_staged.wait(2)
        if stage=='diagnostic:after_close':assert write_finished.wait(2)
    monkeypatch.setattr(ReadOnlyStore,'_diagnostic_checkpoint',checkpoint)
    def writer():
        assert read_started.wait(2)
        with h.store.transaction('isolated_concurrent_writer') as db:
            update_run(db,document(db,'runs','run_id',h.run_id),'DISPATCH_BLOCKED',execution='BLOCKED',queue_state='BLOCKED')
            db.execute("UPDATE dispatch_gate SET state='PAUSED',version=version+1")
            write_staged.set()
        write_finished.set()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(writer);old=inspect(h);future.result(3)
    assert old['view']['run_revision']==1 and old['resources']['gate']['state']=='OPEN'
    monkeypatch.setattr(ReadOnlyStore,'_diagnostic_checkpoint',lambda *a:None)
    new=inspect(h)
    assert new['view']['run_revision']==2 and new['resources']['gate']['state']=='PAUSED'
    assert new['diagnosis']['classification']=='EVIDENCE_CONFLICT'  # no START_INTENT: do not invent history


def test_sidecar_refused_without_repair_or_probe(harness,monkeypatch):
    h=harness;_,_,receipt=h.accept();h.run_id=receipt['run_id']
    Path(h.context.execution_store+'-journal').write_bytes(b'isolated-not-sqlite-journal')
    before=inventory(h.root)
    monkeypatch.setattr('abqjobpilot.execution.interruption_probe.observe',lambda *a:pytest.fail('No probe after refused DB'))
    with pytest.raises(ExecutionError) as exc:inspect_interrupted_execution(h.context,h.run_id,observe_os=True)
    assert exc.value.code=='STORE_REQUIRES_MAINTENANCE' and inventory(h.root)==before


def test_incoherent_snapshot_never_probes_and_original_failed_validation_kept(harness,monkeypatch):
    h=harness;_,_,receipt=h.accept();h.run_id=receipt['run_id'];h.service.execute_pending(h.context,h.run_id)
    with h.store.transaction('isolated_missing_receipt') as db:db.execute('DELETE FROM receipts WHERE run_id=?',(h.run_id,))
    monkeypatch.setattr('abqjobpilot.execution.interruption_probe.observe',lambda *a:pytest.fail('Invalid binding must not probe'))
    r=inspect_interrupted_execution(h.context,h.run_id,observe_os=True)['body']
    assert r['diagnosis']['classification']=='EVIDENCE_CONFLICT'
    assert r['facts']['run']['artifact_validation']=='VALID'


def test_control_metadata_bound_checked_before_materialization(uncertain):
    h=uncertain
    with h.store.transaction('isolated_oversized_owner') as db:
        db.execute("UPDATE meta SET value=? WHERE key='owner_id'",('x'*100000,))
    before=inventory(h.root)
    with pytest.raises(ExecutionError) as exc:inspect(h)
    assert exc.value.code=='LIMIT_EXCEEDED' and inventory(h.root)==before
