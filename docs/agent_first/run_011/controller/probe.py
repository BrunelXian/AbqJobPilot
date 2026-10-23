"""Fixed Run010 controller candidate. Default=check. No real execution approved by this package."""
import argparse
import json
import sys

from records import Refusal, require
from windows_host import current_host, admit
from frozen import (load_candidate, verify_before_attempt, execution_spec, spawn_frozen,
                    BASE_INTERPRETER)
from engine import check_empty, run_once, read_report


def host_for_launch():
    from pathlib import Path
    value = current_host()
    require(Path(value['identity']['image_path']) == BASE_INTERPRETER, 'ACTUAL_INTERPRETER_MISMATCH')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', nargs='?', default='check', choices=['check','execute','report'])
    parser.add_argument('--candidate-digest', help='Reviewed candidate identity, not an authorization token')
    args = parser.parse_args(argv)
    if args.operation == 'execute' and not args.candidate_digest:
        parser.error('execute requires --candidate-digest and separate prior human approval of this candidate')
    if args.operation != 'execute':
        def readonly(event, values):
            if event in {'subprocess.Popen','os.system','os.startfile','sqlite3.connect','socket.connect'}:
                raise Refusal('READONLY_EXECUTION_BLOCKED')
        sys.addaudithook(readonly)
    try:
        if args.operation == 'report':
            load_candidate(args.candidate_digest)
            result = read_report(execution_spec())
        elif args.operation == 'check':
            _, candidate = verify_before_attempt(args.candidate_digest)
            check_empty(execution_spec())
            host = host_for_launch()
            result = {'status':'CHECK_ONLY', 'candidate_digest':candidate['content_digest'],
                      'materials':'MATCH', 'host':host, 'attempt_written':False,
                      'external_processes_created':0, 'execution_authorization':'NOT_ASSERTED',
                      'host_condition': 'PASS_AT_THIS_OBSERVATION_ONLY' if
                          host['job_query_succeeded'] and host['in_any_job'] is False else 'BLOCKED',
                      'warning':'execute rechecks in its own process; prior check cannot admit execution'}
        else:
            # No arbitrary executable, root, duration, host override or backend parameter.
            result = run_once(execution_spec(), args.candidate_digest,
                lambda: verify_before_attempt(args.candidate_digest), host_for_launch, spawn_frozen)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 2 if result.get('host_condition') == 'BLOCKED' else 0
    except Exception as exc:
        print(json.dumps({'status':'BLOCKED_OR_UNKNOWN',
            'code':getattr(exc, 'code', 'LOCAL_IO_OR_FORMAT_FAILURE'),
            'action':'Read existing attempt/report; never retry a launch after intent or uncertainty',
            'execution_authorization':'NOT_ASSERTED'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
