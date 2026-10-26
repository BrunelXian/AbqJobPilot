"""Real isolated owner/managed Python fixture; no Abaqus, no historical owner."""
import json
from abqjobpilot.execution.interruption import inspect_interrupted_execution
from test_managed_scope import managed, bind, directory, terminal
from supervisor_helpers import wait_until, read_json


def live_read(context, run_id, refusals):
    # Existing read-only SQLite policy refuses transient journal files; a fresh
    # query may be requested later. Never open rw to repair or replay execution.
    from abqjobpilot.execution.models import ExecutionError
    def read():
        try:return inspect_interrupted_execution(context,run_id,observe_os=True)
        except ExecutionError as exc:
            assert exc.code in {'STORE_REQUIRES_MAINTENANCE','STORE_UNAVAILABLE'}
            refusals.append(exc.code)
    return wait_until(read)


def test_live_owner_worker_readonly_then_normal_completion(tmp_path):
    with managed(tmp_path,['result_wait']) as h:
        owner=h.owner();client=h.client();rid=client.submit(h.requests[0])['receipt']['run_id']
        worker=bind(h,rid,'worker')
        wait_until(lambda:client.run(rid).get('process_records'))
        refusals=[];report=live_read(h.context,rid,refusals)
        assert report['body']['diagnosis']['classification']=='EXECUTION_ACTIVITY_OBSERVED'
        assert report['body']['diagnosis']['known_member_active']
        assert report['body']['current_observation']['owner']['state']=='EXACT_IDENTITY_ALIVE'
        assert client.health()['process']==owner.identity and worker.exit_evidence() is None
        assert len(read_json(owner.control/'physical-launches.json'))==1
        (directory(h,rid)/'release.json').write_text('{}')
        completed=terminal(h,rid)
        final=inspect_interrupted_execution(h.context,rid)
        assert final['body']['managed_completion_checked'] and final['body']['diagnosis']['classification']=='COMPLETION_RECORDED'
        assert client.run(rid)==completed
        h.evidence.update(active_diagnostic=report,final_diagnostic=final,transient_read_refusals=refusals)


def test_owned_owner_exit_worker_alive_no_requeue_or_takeover(tmp_path):
    with managed(tmp_path,['result_wait','normal']) as h:
        owner=h.owner(barriers=['process:after_identity']);client=h.client();a,b=[client.submit(q)['receipt']['run_id'] for q in h.requests]
        owner.reached('process:after_identity');worker=bind(h,a,'worker')
        owner.terminate()  # This fixture's retained identity-checked handle only.
        assert worker.exit_evidence() is None
        from execution_helpers import inventory
        from pathlib import Path
        db=Path(h.context.execution_store);before=db.read_bytes()
        report=inspect_interrupted_execution(h.context,a,observe_os=True)
        # The fixture retained the original handle. A fresh public read may no
        # longer obtain the exited process image; it must NOT borrow our fact.
        owner_state=report['body']['current_observation']['owner']['state']
        assert owner_state in {'EXACT_IDENTITY_EXITED','PROCESS_UNAVAILABLE','QUERY_FAILED'}
        assert report['body']['diagnosis']['classification']==('OWNER_LOST_WORKER_ACTIVE'
            if owner_state=='EXACT_IDENTITY_EXITED' else 'EXECUTION_ACTIVITY_OBSERVED')
        assert report['body']['diagnosis']['known_member_active']
        assert report['body']['resources']['slot_run_id']==a and db.read_bytes()==before
        pending=inspect_interrupted_execution(h.context,b)
        assert pending['body']['diagnosis']['classification']=='NEVER_STARTED_RECORDED'
        assert len(read_json(owner.control/'physical-launches.json'))==1
        (directory(h,a)/'owner-bound.json').write_text('{}')
        (directory(h,a)/'release.json').write_text('{}');wait_until(worker.exit_evidence)
        h.evidence.update(owner_exited=owner.identity,worker_alive=worker.identity,
                          interrupted_diagnostic=report,pending_diagnostic=pending)
