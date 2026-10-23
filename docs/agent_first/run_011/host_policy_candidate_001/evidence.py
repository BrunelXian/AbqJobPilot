"""Cross-check archived historical records; never probe old PIDs or run a fixture."""
from datetime import datetime
from pathlib import Path

from records import require, read_json, stable_read


def review(root):
    root = Path(root)
    report = read_json(root/'HOST_REPORT.json')
    ready = read_json(root/'controller_ready.json')
    returned = read_json(root/'function_returned.json')
    run = read_json(root/'observations/controller_report.json')
    context = read_json(root/'observer_context.json')
    launch = read_json(root/'worker_launcher.json')
    worker = read_json(root/'worker_ready.json')
    done = read_json(root/'worker_done.json')
    require(report['status'] == 'PASS_OBSERVED_FIXED_PYTHON_CHAIN_ONLY'
            and report['abaqus_calls'] == 0 and report['real_execute_calls'] == 0,
            'HISTORICAL_FIXTURE_NOT_PASSED')
    chain = report['controller_chain_OS_evidence']
    require(chain == ready['chain'] and report['controller_host'] == ready['host']
            and context['powershell'] == chain['powershell']
            and context['launcher'] == chain['venv_launcher'], 'EVIDENCE_CHAIN_CONFLICT')
    require(ready['host']['job_query_succeeded'] is True
            and type(ready['host']['in_any_job']) is bool, 'EVIDENCE_QUERY_UNKNOWN')
    identities = {'actual_controller':chain['controller'], 'controller_venv_launcher':chain['venv_launcher'],
                  'actual_worker':worker, 'worker_venv_launcher':launch['identity']}
    for name, identity in identities.items():
        require(type(identity['pid']) is int and identity['pid'] > 0
                and type(identity['creation_time_100ns']) is int
                and identity['creation_time_100ns'] > 0 and identity['image_path'], 'EVIDENCE_IDENTITY_MISSING')
    require(len({i['pid'] for i in identities.values()}) == 4, 'EVIDENCE_IDENTITY_CONFLICT')
    require(returned['report'] == run and returned['controller_identity'] == chain['controller']
            and returned['not_OS_exit_evidence'] is True and run['deadline_reached'] is True
            and run['creation'] == 'PROCESS_OBJECT_RETURNED' and 'failure' not in run,
            'EVIDENCE_FUNCTION_RETURN_CONFLICT')
    require(report['function_return']['at_ns'] == returned['observed_at_ns'], 'EVIDENCE_TIME_CONFLICT')
    require(worker == report['worker_verified_OS_identity'] == report['worker_candidate_self_report']
            == done['identity'] and done['natural_exit'] is True, 'EVIDENCE_WORKER_CONFLICT')
    require(run['processes']['direct_identity'] == launch['identity']
            and worker in run['processes']['candidate_identities'], 'EVIDENCE_CREATION_CONFLICT')
    roles = [('controller_exit','actual_controller'),('controller_venv_exit','controller_venv_launcher'),
             ('worker_exit','actual_worker'),('worker_venv_exit','worker_venv_launcher')]
    for field, role in roles:
        record = report[field]
        require(record['identity'] == identities[role] and record['exited'] is True
                and type(record['exit_code']) is int and record['exit_code'] == 0
                and record['source'] == 'PowerShell_retained_OS_process_reference', 'EVIDENCE_EXIT_MISSING')
    for field in ('worker_after_entire_controller_chain_exit','worker_after_growth'):
        record=report[field]
        require(record['identity'] == worker and record['exited'] is False and record['exit_code'] is None
                and record['source'] == 'PowerShell_retained_OS_process_reference', 'EVIDENCE_SURVIVAL_MISSING')
    dt = lambda field: datetime.fromisoformat(report[field]['observed_at'])
    require(max(dt('controller_exit'),dt('controller_venv_exit')) < dt('worker_after_entire_controller_chain_exit')
            <= dt('post_exit_growth') <= dt('worker_after_growth') < dt('worker_exit'), 'EVIDENCE_ORDER_CONFLICT')
    growth=report['post_exit_growth']
    data,_=stable_read(root/'heartbeat.txt')
    require(0 < growth['before_bytes'] < growth['after_bytes'] <= len(data)
            and data.endswith(b'finished\n') and not (root/'release').exists(), 'EVIDENCE_GROWTH_MISSING')
    cleanup=report['cleanup']
    require(len(cleanup)==4 and {c['role'] for c in cleanup}==set(identities), 'EVIDENCE_CLEANUP_MISSING')
    for c in cleanup:
        require(c['observation']['identity']==identities[c['role']] and c['observation']['exited'] is True
                and c['observation']['exit_code']==0, 'EVIDENCE_CLEANUP_CONFLICT')
    import json
    raw,_=stable_read(root/'observations/controller_events.jsonl')
    events=[json.loads(line) for line in raw.splitlines()]
    require([e['sequence'] for e in events] == list(range(1,len(events)+1))
            and [e['kind'] for e in events].count('PROCESS_OBJECT_RETURNED')==1
            and events[-1]['kind']=='OBSERVATION_ENDED'
            and events[-1]['processes']==run['processes'], 'EVIDENCE_EVENT_CONFLICT')
    return {'historical_fixture':'VERIFIED_RECORDED_CHAIN', 'operator_provenance':'user identified this terminal invocation',
            'controller_exits':[report[k] for k,_ in roles[:2]], 'worker_exit':report['worker_exit'],
            'scope':'terminal/session remained alive; fixed Python only; no Job hierarchy or Abaqus proof',
            'authorization':'NONE', 'current_processes_probed':False}
