"""Fixed revised candidate. Default check is no-Solver; execute needs NEW prior human approval."""
import argparse
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'controller'))
sys.path.insert(0,str(HERE.parents[3]))
from records import Refusal
import frozen
import package
import host_policy
from engine_adapter import run_once, check_empty, read_report


def check(expected=None):
    candidate,history=package.verify(expected)
    check_empty(frozen.execution_spec())
    host=host_policy.observe()
    decision=host_policy.evaluate(host)
    return {'status':'SELF_CHECK_PASS' if decision['eligible'] else 'SELF_CHECK_BLOCKED',
        'candidate_digest':candidate['content_digest'],'materials':'MATCH','host':host,
        'host_policy':decision,'historical_fixture':history,
        'attempt_written':False,'abaqus_calls':0,'execution_authorization':'NOT_GRANTED',
        'warning':'limited conditional host policy only; execute rechecks, requires separate NEW approval'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',nargs='?',default='check',choices=['check','report','execute'])
    parser.add_argument('--candidate-digest',help='reviewed content identity, not approval')
    args=parser.parse_args(argv)
    if args.operation=='execute' and not args.candidate_digest:
        parser.error('execute requires the new reviewed candidate digest and separate prior approval')
    if args.operation!='execute':
        def readonly(event, values):
            if event in {'subprocess.Popen','os.system','os.startfile','sqlite3.connect','socket.connect'}:
                raise Refusal('READONLY_EXECUTION_BLOCKED')
        sys.addaudithook(readonly)
    try:
        if args.operation=='check': result=check(args.candidate_digest)
        elif args.operation=='report':
            package.load(args.candidate_digest)
            result=read_report(frozen.execution_spec())
        else:
            result=run_once(frozen.execution_spec(),args.candidate_digest,
                lambda:package.verify(args.candidate_digest), host_policy.observe, frozen.spawn_frozen)
        print(json.dumps(result,ensure_ascii=True,sort_keys=True))
        return 2 if result.get('status')=='SELF_CHECK_BLOCKED' else 0
    except Exception as exc:
        print(json.dumps({'status':'SELF_CHECK_BLOCKED_OR_UNKNOWN','code':getattr(exc,'code','LOCAL_IO_OR_FORMAT_FAILURE'),
            'execution_authorization':'NOT_GRANTED','action':'preserve evidence; do not retry execute after any intent or uncertainty'}))
        return 2


if __name__=='__main__': raise SystemExit(main())
