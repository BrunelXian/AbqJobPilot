"""Bounded read-only Win32 queries; clock/reboot tests are injected estimates."""
import json
from pathlib import Path
import pytest
from abqjobpilot.execution import interruption_probe as probe
from abqjobpilot.execution.models import ExecutionError, canonical_json, now
from abqjobpilot.execution.ownership import current_process_identity
from execution_helpers import guard_environment, harness, inventory


def metadata(h, identity):
    data={'project_id':h.context.project_id,'project_instance_id':h.context.project_instance_id,
        'context_digest':h.context.context_digest,'execution_store':h.context.execution_store,
        'owner_id':h.store._session.owner_id,'process':identity}
    (Path(h.context.root)/'owner.json').write_text(canonical_json(data),encoding='utf-8')
    return {'owner_id':h.store._session.owner_id,'process_records':[identity]}


def test_actual_current_process_identity_and_handle_cleanup(monkeypatch):
    from abqjobpilot.execution.process_handles import ProcessReference
    handles=[];original=ProcessReference.close
    def close(self):
        original(self);handles.append(self.handle)
    monkeypatch.setattr(ProcessReference,'close',close)
    identity=current_process_identity()
    for _ in range(12):
        observed=probe._observe_identity(identity)
        assert observed['state']=='EXACT_IDENTITY_ALIVE'
        assert observed['expected']['creation_time_100ns']==identity['creation_time_100ns']
        assert 'image_path' not in canonical_json(observed)
    assert handles==[None]*12
    mismatch=probe._observe_identity({**identity,'creation_time_100ns':identity['creation_time_100ns']+1})
    assert mismatch['state']=='IDENTITY_MISMATCH' and handles[-1] is None


@pytest.mark.parametrize('code,state',[('PROCESS_IDENTITY_UNKNOWN','PROCESS_UNAVAILABLE'),
    ('PROCESS_EXIT_UNKNOWN','QUERY_FAILED'),('PROCESS_IDENTITY_MISMATCH','IDENTITY_MISMATCH')])
def test_query_failure_never_exit_or_payload(code,state,monkeypatch):
    def fail(*a,**k):raise ExecutionError(code,'secret-payload')
    monkeypatch.setattr('abqjobpilot.execution.process_handles.ProcessReference',fail)
    result=probe._observe_identity(current_process_identity())
    assert result['state']==state and 'secret' not in canonical_json(result) and 'exit_code' not in result


@pytest.mark.parametrize('problem',['wrong_project','wrong_owner','oversize','malformed','missing'])
def test_owner_metadata_is_bounded_bound_and_no_repair(harness,problem):
    h=harness;run=metadata(h,current_process_identity());path=Path(h.context.root)/'owner.json'
    if problem=='missing':path.unlink()
    elif problem=='oversize':path.write_bytes(b'x'*16385)
    elif problem=='malformed':path.write_text('{')
    else:
        data=json.loads(path.read_text());data['project_id' if problem=='wrong_project' else 'owner_id']='wrong'
        path.write_text(canonical_json(data))
    before=inventory(h.root)
    assert probe._owner_identity(h.context,run) is None and inventory(h.root)==before


@pytest.mark.parametrize('later',[False,True])
def test_boot_estimate_combines_recorded_creation_but_is_not_session_proof(harness,monkeypatch,later):
    h=harness;identity=current_process_identity();run=metadata(h,identity)
    creation_ms=identity['creation_time_100ns']//10000-11644473600000
    monkeypatch.setattr(probe,'_boot_observation',lambda:{'state':'ESTIMATE_ONLY','confidence':'ESTIMATE_NOT_SESSION_PROOF',
        'estimated_boot_unix_ms':creation_ms+(10000 if later else 500),'sampling_uncertainty_ms':1000,
        'clock_history':'NOT_VERIFIABLE','source':'WALL_CLOCK_MINUS_GETTICKCOUNT64'})
    before=inventory(h.root);result=probe.observe(h.context,run)
    assert result['boot']['state']==('LATER_BOOT_ESTIMATE' if later else 'ESTIMATE_ONLY')
    assert result['owner']['state']=='EXACT_IDENTITY_ALIVE'  # contradicts restart: classifier must not assert it
    assert result['boot']['clock_history']=='NOT_VERIFIABLE' and inventory(h.root)==before


def test_real_boot_api_is_estimate_only():
    result=probe._boot_observation()
    assert result['state']=='ESTIMATE_ONLY' and result['uptime_ms']>0
    assert result['confidence']=='ESTIMATE_NOT_SESSION_PROOF'


def test_probe_limits_and_budget(harness,monkeypatch):
    h=harness;identity=current_process_identity();run=metadata(h,identity)
    with pytest.raises(ExecutionError):probe.observe(h.context,{**run,'process_records':[identity]*33})
    times=iter([0,3]);monkeypatch.setattr(probe.time,'monotonic',lambda:next(times))
    result=probe.observe(h.context,run)
    assert result['members'][0]['state']=='BUDGET_EXHAUSTED' and result['scope_handle']=='NOT_QUERIED'


def test_clock_jump_during_sampling_and_os_api_failure(monkeypatch):
    wall=iter([1000000000,100000000]);mono=iter([1,2])
    monkeypatch.setattr(probe.time,'time_ns',lambda:next(wall))
    monkeypatch.setattr(probe.time,'monotonic_ns',lambda:next(mono))
    monkeypatch.setattr(probe,'now',lambda:1)
    assert probe._boot_observation()['state']=='CLOCK_UNSTABLE'
    def fail(*a,**k):raise OSError('secret-error')
    monkeypatch.setattr(probe.ctypes,'WinDLL',fail)
    result=probe._boot_observation()
    assert result['state']=='QUERY_FAILED' and 'secret' not in canonical_json(result)
