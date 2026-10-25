"""Existing offline Standard substitutes; never real Solver evidence."""
import pytest
from execution_helpers import inventory
from test_standard_backend import case
from test_standard_closeout import finished
from test_standard_managed import pair,execute
from abqjobpilot.execution.interruption import inspect_interrupted_execution
from abqjobpilot.execution.models import canonical_json
from abqjobpilot.execution.store import document


def test_administrative_release_preserves_unknown_and_retention(finished):
    c=finished;c.service.apply_closeout(c.ctx,c.permission())
    before=inventory(c.root)
    r=inspect_interrupted_execution(c.ctx,c.rid)['body']
    assert r['diagnosis']['classification']=='ADMINISTRATIVE_DISPOSITION_RECORDED'
    assert r['resources']['administrative_release_committed']
    assert r['resources']['path_policy']=='RETAINED_NO_REUSE'
    assert r['resources']['slot_run_id'] is None and r['resources']['gate']['state']=='PAUSED'
    assert r['facts']['run']['overall_exit']=='UNKNOWN'
    assert inventory(c.root)==before and len(c.calls)==1


@pytest.mark.parametrize('damage',[None,'scope_id','missing_scope','missing_commit','validation_only'])
def test_managed_completion_validation_and_scope_loss_remain_distinct(pair,damage):
    c=pair;a=execute(c,0);rid=a['run_id']
    if damage:
        with c.store.transaction('isolated_negative_history') as db:
            r=document(db,'runs','run_id',rid)
            if damage=='scope_id':r['managed_scope']['run_id']='r_'+'0'*32
            if damage=='missing_scope':r['managed_scope']=None
            if damage=='missing_commit':r['managed_completion']='NOT_CONFIRMED'
            if damage=='validation_only':r['artifact_validation']='NOT_RUN';r['numerical_validation']='NOT_RUN'
            db.execute('UPDATE runs SET body=? WHERE run_id=?',(canonical_json(r),rid))
    before=inventory(c.root);r=inspect_interrupted_execution(c.ctx,rid)['body']
    assert r['managed_completion_checked'] == (damage in (None,'validation_only'))
    assert r['diagnosis']['classification']==('COMPLETION_RECORDED' if damage in (None,'validation_only') else 'EXECUTION_STATE_UNKNOWN')
    assert r['facts']['run']['solver_conclusion']=='COMPLETED_TEXT_EVIDENCE'
    assert r['facts']['run']['overall_exit']=='UNKNOWN'
    assert r['facts']['run']['odb_content_validation']=='NOT_RUN'
    assert inventory(c.root)==before and len(c.calls)==1
