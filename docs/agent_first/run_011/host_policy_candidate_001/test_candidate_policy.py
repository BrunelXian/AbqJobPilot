"""Tests of the new seam, no real execute and no Solver subprocess."""
import copy
import json
from pathlib import Path
import shutil
import sys

import pytest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(HERE.parent/'controller'))
sys.path.insert(0,str(HERE.parents[3]))
import host_policy as policy
import package
import evidence
import candidate
import engine_adapter as engine
import frozen
from records import Refusal


def host():
    return {'policy':policy.POLICY,'job_query_succeeded':True,'in_any_job':True,
        'interpreter':str(policy.VENV),'python':'3.12.10',
        'identity':{'pid':10,'creation_time_100ns':30,'image_path':str(policy.BASE)},
        'chain_verified':True,'session_id':1,'powershell_attached_to_same_console':True,
        'chain':{role:{'identity':{'pid':pid,'creation_time_100ns':created,'image_path':str(image)},
            'observed_alive':True,'session_id':1,'job_query_succeeded':True,'in_any_job':True}
            for role,pid,created,image in [('venv_launcher',11,20,policy.VENV),('powershell',12,10,policy.POWERSHELL)]}}


def case(tmp_path):
    root=tmp_path/'case';root.mkdir()
    for name in ('observations','engineering/scratch','extracted'):(root/name).mkdir(parents=True)
    return {'root':str(root),'job':'test_job','experiment_id':'test','original_digest':'test',
            'output_identity':'test-output','budget_seconds':.1}


def never(*args,**kwargs):
    pytest.fail('No external create was allowed')


def test_operator_archive_cross_checked_without_current_process_probe(monkeypatch):
    monkeypatch.setattr(policy,'observe',never)
    result=evidence.review(HERE/'operator_evidence')
    assert result['historical_fixture']=='VERIFIED_RECORDED_CHAIN'
    assert result['authorization']=='NONE' and result['current_processes_probed'] is False


@pytest.mark.parametrize('mutation', ['missing_exit','wrong_worker','no_growth','wrong_order','bad_cleanup','missing_member'])
def test_pass_label_cannot_override_missing_or_conflicting_evidence(tmp_path,mutation):
    root=tmp_path/'archive';shutil.copytree(HERE/'operator_evidence',root)
    path=root/'HOST_REPORT.json';r=json.loads(path.read_text())
    if mutation=='missing_exit': r['controller_venv_exit']['exit_code']=None
    elif mutation=='wrong_worker':r['worker_after_growth']['identity']['creation_time_100ns']+=1
    elif mutation=='no_growth':r['post_exit_growth']['after_bytes']=r['post_exit_growth']['before_bytes']
    elif mutation=='wrong_order':r['worker_exit']['observed_at']=r['controller_exit']['observed_at']
    elif mutation=='bad_cleanup':r['cleanup'][0]['observation']['exited']=False
    else:r['controller_chain_OS_evidence']['venv_launcher']['pid']=1
    path.write_text(json.dumps(r))
    with pytest.raises(Refusal):evidence.review(root)


def test_membership_is_not_erased_or_called_safe():
    value=host();before=copy.deepcopy(value)
    decision=policy.evaluate(value);policy.admit(value)
    assert decision['eligible'] and value==before and value['in_any_job'] is True
    assert decision['full_job_hierarchy']=='UNKNOWN' and decision['authorization']=='NOT_GRANTED'


@pytest.mark.parametrize('key,value', [('job_query_succeeded',False),('job_query_succeeded',None),
    ('in_any_job',None),('in_any_job',1),('policy','skip'),('chain_verified',False),
    ('powershell_attached_to_same_console',False),('session_id',0),('interpreter',str(policy.BASE))])
def test_check_and_admit_share_refusal_before_intent(tmp_path,monkeypatch,key,value):
    observed=host();observed[key]=value
    spec=case(tmp_path)
    monkeypatch.setattr(package,'verify',lambda expected:({'content_digest':'test'},{}))
    monkeypatch.setattr(frozen,'execution_spec',lambda:spec)
    monkeypatch.setattr(policy,'observe',lambda:observed)
    result=candidate.check()
    assert result['host_policy']==policy.evaluate(observed)
    assert result['status']=='SELF_CHECK_BLOCKED'
    with pytest.raises(Refusal):engine.run_once(spec,'new',lambda:None,lambda:observed,never)
    assert list(Path(spec['root']).rglob('*.json'))==[]


@pytest.mark.parametrize('field,value', [('observed_alive',False),('job_query_succeeded',False),
    ('in_any_job',None),('session_id',2)])
def test_parent_query_liveness_and_session_fail_closed(field,value):
    observed=host();observed['chain']['powershell'][field]=value
    with pytest.raises(Refusal):policy.admit(observed)


def test_direct_job_limit_flag_does_not_admit_wrong_parent():
    value=host();value['kill_on_job_close']=False
    value['chain']['powershell']['identity']['image_path']='different.exe'
    assert not policy.evaluate(value)['eligible']
    with pytest.raises(Refusal):policy.admit(value)


@pytest.mark.parametrize('data',[b'',b'{',b'unknown'])
def test_same_attempt_record_blocks_new_candidate(tmp_path,data):
    spec=case(tmp_path)
    (Path(spec['root'])/'observations/attempt.json').write_bytes(data)
    with pytest.raises(Refusal,match='ATTEMPT_EXISTS'):
        engine.run_once(spec,'different-candidate',lambda:None,host,never)


def test_output_conflict_blocks_before_create(tmp_path):
    spec=case(tmp_path);p=Path(spec['root'])/'engineering/test_job.dat';p.write_text('old')
    with pytest.raises(Refusal,match='OUTPUT_EXISTS'):engine.run_once(spec,'new',lambda:None,host,never)
    assert p.read_text()=='old'


def test_uncertain_create_keeps_intent_and_forbids_retry(tmp_path):
    spec=case(tmp_path);calls=[]
    def uncertain(out,err):
        assert (Path(spec['root'])/'observations/attempt.json').exists()
        calls.append(1);raise OSError('injected response loss; no OS process in this test')
    result=engine.run_once(spec,'new',lambda:None,host,uncertain)
    assert calls==[1] and result['creation']=='CALL_ENTERED_OUTCOME_UNKNOWN'
    with pytest.raises(Refusal):engine.run_once(spec,'newer',lambda:None,host,never)


def test_adapter_changes_only_policy_import():
    old=(HERE.parent/'controller/engine.py').read_text()
    expected=old.replace('from windows_host import admit, ObservedProcesses, close_child_reference',
        'from windows_host import ObservedProcesses, close_child_reference\nfrom host_policy import admit')
    assert (HERE/'engine_adapter.py').read_text()==expected


def test_new_package_keeps_original_action_attempt_and_authorization_boundaries():
    new,_=package.load()
    _,old=frozen.load_candidate(package.OLD_DIGEST)
    fixed=new['body']['fixed_execution']
    for key,value in fixed.items():assert value==old['body'][key]
    assert new['body']['additional_attempt_budget']==0
    assert new['body']['execution_authorization']=='NOT_GRANTED'
    with pytest.raises(Refusal,match='CANDIDATE_CHANGED'):package.load(package.OLD_DIGEST)


def test_one_click_routes_only_fixed_check_no_argument_forwarding():
    batch=(HERE/'SELF_CHECK.cmd').read_text()
    script=(HERE/'self_check.ps1').read_text()
    assert '%*' not in batch and '-NoExit -File' in batch and 'self_check.ps1' in batch
    assert '$entry check' in script and '$entry execute' not in script
    assert 'ExecutionPolicy' not in batch and 'Start-Process' not in script


@pytest.mark.parametrize('operation',[[],['check'],['report'],['--help']])
def test_public_readonly_actions_do_not_create_attempt_or_external_process(monkeypatch,capsys,operation):
    root=Path(frozen.execution_spec()['root'])/'observations'
    before={p.name:p.read_bytes() for p in root.iterdir() if p.is_file()}
    monkeypatch.setattr(frozen,'spawn_frozen',never)
    monkeypatch.setattr(policy,'observe',host)
    if operation==['--help']:
        with pytest.raises(SystemExit) as caught:candidate.main(operation)
        assert caught.value.code==0
    else:
        assert candidate.main(operation)==0
        result=json.loads(capsys.readouterr().out)
        if operation!=['report']:
            assert result['execution_authorization']=='NOT_GRANTED' and result['attempt_written'] is False
    assert before=={p.name:p.read_bytes() for p in root.iterdir() if p.is_file()}


def test_modified_new_candidate_body_is_refused(monkeypatch):
    real=package.read_json
    manifest=real(HERE/'CANDIDATE_MANIFEST.json')
    manifest['body']['fixed_execution']['additional_abaqus_calls']=1
    monkeypatch.setattr(package,'read_json',lambda p:manifest if p==HERE/'CANDIDATE_MANIFEST.json' else real(p))
    with pytest.raises(Refusal,match='CANDIDATE_CHANGED'):package.load()


@pytest.mark.parametrize('failure',['session_query','chain_drift','parent_exit'])
def test_fresh_OS_collection_refuses_failure_and_closes_refs(monkeypatch,failure):
    import abqjobpilot.execution.process_handles as handles
    pid=policy.os.getpid();counter=[];refs=[]
    value=host();value['identity']['creation_time_100ns']=30
    monkeypatch.setattr(policy,'current_host',lambda:value)
    def rows():
        counter.append(1)
        return [(pid,11),(11,99 if failure=='chain_drift' and len(counter)>1 else 12)]
    monkeypatch.setattr(policy,'process_rows',rows)
    class Fn:
        def __init__(self,call):self.call=call
        def __call__(self,*args):return self.call(*args)
    class API:
        ProcessIdToSessionId=Fn(lambda *a:False if failure=='session_query' else (setattr(a[1]._obj,'value',1) or True))
        GetConsoleProcessList=Fn(lambda values,count:(values.__setitem__(0,12) or 1))
        IsProcessInJob=Fn(lambda *a:(setattr(a[2]._obj,'value',True) or True))
    monkeypatch.setattr(policy,'api',lambda:API())
    class Reference:
        def __init__(self,p):
            self.identity={'pid':p,'creation_time_100ns':20 if p==11 else 10,
                           'image_path':str(policy.VENV if p==11 else policy.POWERSHELL)}
            self.handle=1;self.closed=False;self.calls=0;refs.append(self)
        def exit_evidence(self):
            self.calls+=1
            return {} if failure=='parent_exit' and self.calls>1 else None
        def close(self):self.closed=True
    monkeypatch.setattr(handles,'ProcessReference',Reference)
    with pytest.raises(Refusal):policy.observe()
    assert all(r.closed for r in refs)
