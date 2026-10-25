"""Thin client's failure boundaries; service policy is tested separately."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'examples/agent_first'))
import standard_client as cli
from abqjobpilot.execution.models import canonical_json,ExecutionError


@pytest.mark.parametrize('mode',['success','lost_a_response','lost_b_response','connection_lost','a_blocked','a_deadline'])
def test_public_sequencer_stops_on_loss_and_never_resubmits(tmp_path,monkeypatch,mode):
    requests=[{'plan_id':v,'plan_digest':v,'idempotency_key':v} for v in 'AB'];calls=[]
    class Client:
        def __init__(self,*args):pass
        def inspect_plan(self,pid,digest):return {'backend_id':'abaqus-standard-axial-2024-v1',
            'project_instance_id':'instance','standard_sequence':{'position':pid}}
        def submit(self,r):
            calls.append(r['idempotency_key'])
            if mode=='lost_'+r['plan_id'].lower()+'_response':raise ExecutionError('IPC_UNAVAILABLE','Response unknown')
            return {'receipt':{'run_id':r['plan_id'],'accepted_at':1000},'replayed':False}
        def run(self,rid):
            if mode=='connection_lost':raise ExecutionError('IPC_UNAVAILABLE','Read unavailable')
            return {'execution':'BLOCKED' if mode=='a_blocked' else ('RUNNING' if mode=='a_deadline' else 'FINISHED'),
                'managed_completion':'COMMITTED_EMPTY_SCOPE','solver_conclusion':'COMPLETED_TEXT_EVIDENCE',
                'numerical_validation':'PRIMARY_THREE_PASS','backend_outcome':'COMPLETED'}
    monkeypatch.setattr(cli,'FakeClient',Client)
    monkeypatch.setattr(cli.time,'time',lambda:1331 if mode=='a_deadline' else 1001)
    def no_sleep(n):raise AssertionError('No hidden reconnect or wait loop expected')
    monkeypatch.setattr(cli.time,'sleep',no_sleep)
    connection=tmp_path/'connection.json';offer=tmp_path/'offer.json'
    connection.write_text(canonical_json({'endpoint':{'project_instance_id':'instance'},'credential':'test-private'}))
    offer.write_text(canonical_json({'requests':requests}))
    if mode in ('success','a_deadline'):
        result=cli.run_pair(connection,offer,tmp_path)
        assert result['status']==('PAIR_OBSERVED' if mode=='success' else 'A_WAIT_ENDED_B_NOT_SUBMITTED')
    else:
        with pytest.raises(ExecutionError):cli.run_pair(connection,offer,tmp_path)
    assert calls==(['A','B'] if mode in ('success','lost_b_response') else ['A'])
    for saved in tmp_path.glob('*/receipt.json'):assert 'test-private' not in saved.read_text()
    connection.unlink();offer.unlink()


def test_legacy_export_compatibility_does_not_allow_extra_fields():
    import json
    from abqjobpilot.execution.diagnostics import report_bytes
    from abqjobpilot.execution.models import digest
    source=Path(__file__).resolve().parents[1]/'docs/agent_first/run_007/examples/historical_invalid_after.json'
    report=json.loads(source.read_text(encoding='utf-8'))
    assert json.loads(report_bytes(report))==report
    report['body']['facts']['run']['credential']='must-not-export'
    report['content_digest']=digest(report['body'])
    with pytest.raises(ExecutionError):report_bytes(report)
