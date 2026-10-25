"""Run015 Windows Job-list scope, existing owner/client/GUI and isolated data."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import time

import pytest

from abqjobpilot.execution.models import canonical_json
from abqjobpilot.execution.process_handles import ProcessReference
from supervisor_helpers import ProcessHarness, read_json, wait_until


@contextmanager
def managed(root,scenarios):
    h=ProcessHarness(root,process_scenarios=scenarios,managed_scope=True)
    h.evidence={'os':sys.platform,'python':sys.executable,'abaqus_calls':0,'root':str(root)}
    h.refs=[]
    try:yield h
    finally:
        for child in h.children:
            for path in child.control.glob('*.reached.json'):
                path.with_name(path.name.replace('.reached.json','.release.json')).write_text('{}',encoding='utf-8')
        runs=Path(h.context.runtime_root)/'process_runs'
        if runs.exists():
            for directory in runs.iterdir():
                if directory.is_dir():
                    for name in ('owner-bound.json','release.json','branch-release.json','leaf-release.json'):
                        (directory/name).write_text('{}',encoding='utf-8')
        for ref in h.refs:
            wait_until(lambda:ref.exit_evidence(),timeout=50)
            h.evidence.setdefault('cleanup_exits',[]).append(ref.exit_evidence())
            ref.close()
        h.close()
        h.evidence['owner_cleanup']=read_json(root/'lifecycle.json')
        h.evidence['private_credentials_removed']=not h.bootstrap.exists() and all(not (c.control/'private-process.json').exists() for c in h.children)
        if os.environ.get('RUN015_EVIDENCE_DIR'):
            with (Path(os.environ['RUN015_EVIDENCE_DIR'])/(root.name+'.json')).open('x',encoding='utf-8') as stream:
                stream.write(canonical_json(h.evidence))


def directory(h,rid):return Path(h.context.runtime_root)/'process_runs'/rid


def bind(h,rid,role):
    path=directory(h,rid)/(role+'.json')
    wait_until(path.exists)
    candidate=read_json(path)
    ref=ProcessReference(candidate['pid'],candidate)
    h.refs.append(ref)
    return ref


def terminal(h,rid):
    def read():
        r=h.client().run(rid)
        if r['execution']=='BLOCKED':raise AssertionError(r)
        return r if r['execution']=='FINISHED' else None
    return wait_until(read,timeout=15)


def all_events(client):
    events=[];cursor=0
    while True:
        page=client.events(after_sequence=cursor,limit=64)
        if not page:return events
        events.extend(page);cursor=page[-1]['project_sequence']


def test_managed_two_normal_tasks_are_transactionally_sequential(tmp_path):
    with managed(tmp_path,['normal','normal']) as h:
        owner=h.owner();client=h.client()
        receipts=[client.submit(req)['receipt'] for req in h.requests]
        final=[terminal(h,r['run_id']) for r in receipts]
        events=all_events(client)
        first,second=[r['run_id'] for r in receipts]
        finish=next(e for e in events if e['run_id']==first and e['type']=='VALIDATION_RECORDED')
        start=next(e for e in events if e['run_id']==second and e['type']=='START_INTENT')
        assert finish['project_sequence']<start['project_sequence']
        for r in final:
            assert r['managed_completion']=='COMMITTED_EMPTY_SCOPE'
            assert r['managed_scope']['active_processes']==0 and r['managed_scope']['total_processes']>=4
            assert r['backend_outcome']=='COMPLETED' and r['artifact_validation']=='VALID' and r['solver_conclusion']=='NOT_RUN'
        assert len(read_json(owner.control/'physical-launches.json'))==2
        assert all(client.submit(req)['replayed'] for req in h.requests)
        h.evidence.update(final=final,events=events,receipts=receipts,physical_launches=read_json(owner.control/'physical-launches.json'))


def test_managed_delayed_grandchild_holds_slot_without_pid_list_completion(tmp_path):
    with managed(tmp_path,['managed_tree','normal']) as h:
        owner=h.owner();c=h.client();a=c.submit(h.requests[0])['receipt']['run_id'];b=c.submit(h.requests[1])['receipt']['run_id']
        branch=bind(h,a,'branch')
        partial=wait_until(lambda:r if len((r:=c.run(a))['process_exits'])==4 else None)
        assert branch.exit_evidence() is None and partial['managed_scope']['active_processes']>0
        assert c.run(b)['queue_state']=='PENDING'
        (directory(h,a)/'branch-release.json').write_text('{}',encoding='utf-8')
        leaf=bind(h,a,'leaf');wait_until(branch.exit_evidence)
        assert leaf.exit_evidence() is None and c.run(b)['queue_state']=='PENDING'
        (directory(h,a)/'leaf-release.json').write_text('{}',encoding='utf-8')
        final=terminal(h,a);second=terminal(h,b)
        assert final['managed_scope']['total_processes']>=6
        assert len(final['process_records'])==4  # scope proof is NOT the enumerated key-role count
        h.evidence.update(partial=partial,branch=branch.identity,leaf=leaf.identity,final=final,second=second,
                          events=all_events(c),physical_launches=read_json(owner.control/'physical-launches.json'))


def test_managed_transient_children_counted_without_individual_pid_poll(tmp_path):
    with managed(tmp_path,['managed_burst','normal']) as h:
        owner=h.owner();c=h.client();ids=[c.submit(q)['receipt']['run_id'] for q in h.requests]
        results=[terminal(h,rid) for rid in ids]
        count=results[0]['managed_scope']['total_processes']
        assert 10<=count<=32  # includes actual venv transport processes, not only named roles
        assert len(results[0]['process_records'])==4 and results[0]['managed_scope']['active_processes']==0
        report=c.diagnose(ids[0]);assert report['body']['rules_version']=='process-diagnostic-rules-v4'
        assert 'MANAGED_SCOPE_ENDED' in [x['reason_code'] for x in report['body']['diagnostics']]
        h.evidence.update(results=results,diagnostic=report,events=all_events(c),physical_launches=read_json(owner.control/'physical-launches.json'))


@pytest.mark.parametrize('scenario',['nonzero','invalid_result'])
def test_managed_empty_scope_does_not_turn_failure_into_success_or_continue(tmp_path,scenario):
    with managed(tmp_path,[scenario,'normal']) as h:
        owner=h.owner();c=h.client();a,b=[c.submit(q)['receipt']['run_id'] for q in h.requests]
        result=terminal(h,a)
        assert result['managed_completion']=='COMMITTED_EMPTY_SCOPE'
        assert result['backend_outcome']==('FAILED' if scenario=='nonzero' else 'COMPLETED')
        assert result['artifact_validation']==('VALID' if scenario=='nonzero' else 'INVALID')
        assert c.dispatch_gate()['state']=='PAUSED' and c.run(b)['queue_state']=='PENDING'
        assert len(read_json(owner.control/'physical-launches.json'))==1
        h.evidence.update(first=result,second=c.run(b),gate=c.dispatch_gate())


def test_managed_paused_gate_survives_first_terminal_commit(tmp_path):
    with managed(tmp_path,['result_wait','normal']) as h:
        owner=h.owner(managed_control=True);c=h.client();a,b=[c.submit(q)['receipt']['run_id'] for q in h.requests]
        worker=bind(h,a,'worker')
        wait_until(lambda:(directory(h,a)/'result.json').exists())
        (owner.control/'pause.json').write_text('{}',encoding='utf-8')
        wait_until(lambda:c.dispatch_gate()['state']=='PAUSED')
        (directory(h,a)/'release.json').write_text('{}',encoding='utf-8')
        result=terminal(h,a)
        assert worker.exit_evidence() and c.dispatch_gate()['state']=='PAUSED'
        assert c.run(b)['queue_state']=='PENDING' and len(read_json(owner.control/'physical-launches.json'))==1
        h.evidence.update(first=result,second=c.run(b),gate=c.dispatch_gate())


@pytest.mark.parametrize('fault',['managed:before_scope','managed:before_create','managed:after_create','managed:before_query','terminal:before_commit'])
def test_managed_fault_never_releases_slot_or_restarts(tmp_path,fault):
    from abqjobpilot.execution.store import ReadOnlyStore
    with managed(tmp_path,['normal','normal']) as h:
        owner=h.owner(faults=[fault]);c=h.client();a,b=[c.submit(q)['receipt']['run_id'] for q in h.requests]
        blocked=wait_until(lambda:r if (r:=c.run(a))['reconciliation']=='RECONCILIATION_REQUIRED' else None)
        wait_until(lambda:c.dispatch_gate()['state']=='PAUSED')
        assert c.submit(h.requests[0])['replayed'] and c.run(b)['queue_state']=='PENDING'
        with ReadOnlyStore(h.context).read() as db:assert db.execute('SELECT run_id FROM slot').fetchone()[0]==a
        launches=read_json(owner.control/'physical-launches.json') if (owner.control/'physical-launches.json').exists() else []
        assert len(launches)==(0 if fault in ('managed:before_scope','managed:before_create') else 1)
        assert blocked.get('managed_completion')!='COMMITTED_EMPTY_SCOPE'
        preview=c.preview_process_reconciliation(a)
        assert preview['candidate_action'] is None
        h.evidence.update(fault=fault,blocked=blocked,second=c.run(b),physical_launches=launches,preview=preview)


def test_managed_owner_crash_leaves_worker_alive_and_restart_blocked(tmp_path):
    with managed(tmp_path,['result_wait','normal']) as h:
        owner=h.owner();c=h.client();a,b=[c.submit(q)['receipt']['run_id'] for q in h.requests]
        worker=bind(h,a,'worker');wait_until(lambda:(directory(h,a)/'result.json').exists())
        observed=c.run(a);assert observed['managed_scope']['active_processes']>0
        owner.terminate()  # only the harness-owned identity-verified owner, truly exits
        assert worker.exit_evidence() is None
        restarted=h.owner();c=h.client()
        assert c.dispatch_gate()['state']=='PAUSED' and c.run(a)['reconciliation_requirement']=='RECONCILIATION_REQUIRED'
        assert c.run(b)['queue_state']=='PENDING' and not (restarted.control/'physical-launches.json').exists()
        assert worker.exit_evidence() is None
        h.evidence.update(before_crash=observed,worker_alive_after_owner_exit=worker.identity,
                          restarted_run=c.run(a),restarted_gate=c.dispatch_gate(),restarted_identity=restarted.identity)
        (directory(h,a)/'release.json').write_text('{}',encoding='utf-8')
        wait_until(worker.exit_evidence)
        assert c.run(a)['reconciliation_requirement']=='RECONCILIATION_REQUIRED' # cleanup is not reconciliation


def test_managed_true_crash_after_empty_before_commit_does_not_release(tmp_path):
    with managed(tmp_path,['normal','normal']) as h:
        owner=h.owner(barriers=['managed:after_empty']);c=h.client();a,b=[c.submit(q)['receipt']['run_id'] for q in h.requests]
        owner.reached('managed:after_empty');before=c.run(a)
        assert before['managed_scope']['state']=='EMPTY_CONFIRMED' and before['managed_completion']=='NOT_CONFIRMED'
        owner.terminate();h.owner();c=h.client()
        assert c.dispatch_gate()['state']=='PAUSED' and c.run(a)['reconciliation_requirement']=='RECONCILIATION_REQUIRED'
        assert c.run(b)['queue_state']=='PENDING'
        h.evidence.update(before=before,after=c.run(a),events=all_events(c))


def test_managed_actual_gui_close_and_reconnect_does_not_own_job_handle(tmp_path):
    from test_execution_gui import Gui,connection
    with managed(tmp_path,['result_wait','normal']) as h:
        guis=[];conn=None
        try:
            owner=h.owner();c=h.client();a,b=[c.submit(q)['receipt']['run_id'] for q in h.requests]
            worker=bind(h,a,'worker');wait_until(lambda:(directory(h,a)/'result.json').exists())
            conn=connection(h);gui=Gui(tmp_path,conn,'key-0','gui_A');guis.append(gui)
            first=gui.view(lambda v:v['connected'] and '受管进程范围' in dict(v['rows']) and 'WAITING' in v['progress_text'])
            before=c.run(a);exits=gui.normal_close()
            assert worker.exit_evidence() is None and c.health()['process']==owner.identity
            seq=c.progress(a)['next_sequence'];wait_until(lambda:c.progress(a)['next_sequence']>seq)
            gui2=Gui(tmp_path,conn,'key-0','gui_B');guis.append(gui2)
            reopened=gui2.view(lambda v:v['connected'] and a in json.dumps(v['rows']))
            assert c.run(a)['managed_scope']['scope_id']==before['managed_scope']['scope_id']
            (directory(h,a)/'release.json').write_text('{}',encoding='utf-8')
            final=terminal(h,a);terminal(h,b)
            shown=gui2.view(lambda v:dict(v['rows']).get('范围收尾')=='COMMITTED_EMPTY_SCOPE')
            exits2=gui2.normal_close()
            assert len(read_json(owner.control/'physical-launches.json'))==2
            h.evidence.update(gui_A=first,gui_A_exits=exits,worker_alive_after_gui=worker.identity,
                gui_B=reopened,gui_B_final=shown,gui_B_exits=exits2,final=final,events=all_events(c))
        finally:
            for gui in guis:gui.close()
            if conn:conn.unlink(missing_ok=True)


def test_empty_unstarted_job_and_association_query_failures_are_not_success(monkeypatch):
    from abqjobpilot.execution.managed_process import ManagedScope,check_completion
    from abqjobpilot.execution.models import ExecutionError
    run={k:'fixed-test-binding' for k in ('project_instance_id','run_id','plan_digest','phase_attempt_id','owner_id')};run['owner_epoch']=1
    scope=ManagedScope(run)
    try:
        assert scope.query()['state']=='NOT_COMPLETE'
        with pytest.raises(ExecutionError):check_completion(scope.query(),run)
        monkeypatch.setattr(scope.api,'UpdateProcThreadAttribute',lambda *a:0)
        def forbidden(*a):raise AssertionError('Must reject association before external create')
        monkeypatch.setattr(scope.api,'CreateProcessW',forbidden)
        with pytest.raises(ExecutionError,match='no fallback'):
            scope.create([sys.executable],cwd=str(Path.cwd()),env={})
        monkeypatch.setattr(scope.api,'QueryInformationJobObject',lambda *a:0)
        with pytest.raises(ExecutionError):scope.query()
    finally:scope.close()
