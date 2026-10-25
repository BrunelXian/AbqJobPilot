"""Trusted local operator entry, reusing the existing owner/store/service contract.

preview is read-only. review-and-decide explicitly takes an exclusive management
lease, keeps dispatch PAUSED, and asks for one exact disposition. No worker,
listener, Backend launch, process probe or automatic resume is created here.
"""
import argparse
import json
from pathlib import Path
import sys

SOURCE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(SOURCE))

from abqjobpilot.execution import ExecutionService
from abqjobpilot.execution.closeout import ACTIONS,issue,preview_store
from abqjobpilot.execution.models import canonical_json,now,ExecutionError,require
from abqjobpilot.execution.store import ReadOnlyStore,acquire_supervisor_store
from abqjobpilot.execution.supervisor import load_bootstrap


def main():
    parser=argparse.ArgumentParser(description='Recorded Standard closeout; never starts or stops Solver')
    parser.add_argument('operation',choices=('preview','review-and-decide'))
    parser.add_argument('--test-root',required=True)
    parser.add_argument('--bootstrap',required=True,help='Existing trusted bootstrap, not a new approval file')
    parser.add_argument('--run-id',required=True)
    args=parser.parse_args()
    store=None
    try:
        context,bootstrap=load_bootstrap(args.test_root,args.bootstrap)
        if args.operation=='preview':
            assessment=preview_store(ReadOnlyStore(context),context,args.run_id)
            print(canonical_json({'source':'offline_read_only_no_current_owner_admission','assessment':assessment}))
            return 0
        require(sys.stdin.isatty(),'TRUSTED_TERMINAL_REQUIRED','Review and decision require the operator terminal')
        # Cannot coexist with another supported owner, irrespective of endpoint
        # reachability. This operation is explicit ownership handoff, not a read.
        store=acquire_supervisor_store(context,bootstrap['authority_instance'])
        store.pause_after_error()
        service=ExecutionService(context,store,client_namespace=bootstrap['client_namespace'])
        assessment=service.preview_closeout(context,args.run_id)
        print(json.dumps(assessment,ensure_ascii=False,indent=2))
        print('Unknown process membership remains UNKNOWN. Engineering/output stay quarantined. Dispatch stays PAUSED.')
        print('Type one exact eligible action, or press Enter to leave records unchanged: '+', '.join(ACTIONS))
        action=input().strip()
        if not action:return 0
        require(action in ACTIONS,'INVALID_REQUEST','No supported disposition selected')
        reason=input('Reason and accepted residual uncertainty: ').strip()
        source=input('Actual human authorization source/reference: ').strip()
        request=issue(service,assessment,action,reason=reason,approval_source=source,expires_at=now()+300)
        # Printed before mutation: recover by this key if the response is lost.
        print(canonical_json({'operation':action,'idempotency_key':request['idempotency_key'],
                              'run_id':args.run_id,'owner_id':assessment['owner_id']}),flush=True)
        result=service.apply_closeout(context,request)
        print(canonical_json(result),flush=True)
        return 0
    except ExecutionError as exc:
        print(canonical_json({'status':'REFUSED','code':exc.code,
            'next_step':'Query the original operation key after uncertain commit; no new key or automatic retry'}))
        return 2
    finally:
        if store is not None:
            # No child process or active dispatcher exists in this entry.
            store.pause_after_error()
            store.close()


if __name__=='__main__':raise SystemExit(main())
