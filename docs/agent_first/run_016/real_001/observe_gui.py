"""Acceptance measurement only: public reads and identity-checked own GUI close.

Reuses the actual Dev GUI telemetry entry used by Run013. No submit, approval,
Backend call, database write, owner stop or process termination capability.
"""
import importlib.util
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[3]
sys.path.insert(0, str(SOURCE))
spec = importlib.util.spec_from_file_location('r13_measurement', SOURCE/'docs/agent_first/run_013/real_001/observe_gui.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
old.HERE = HERE
old.KEY = 'run016-A-once'
from abqjobpilot.execution.client import FakeClient
from abqjobpilot.execution.models import canonical_json, digest, ExecutionError
from abqjobpilot.execution.process_handles import ProcessReference


def main():
    value = old.read(SOURCE/'docs/agent_first/run_016/ACCEPTANCE_MANIFEST.json')
    assert digest(value['body']) == 'sha256:88ddae420d2fd73f0ecb7bace4171bb8f0eb6a6b2098b0d91e558c94338f3fd7'
    root = Path(value['body']['context']['test_root'])
    connection = old.read(root/'private/connection.json')
    client = FakeClient(connection['endpoint'], connection['credential'])
    refs, guis, receipts, finals = [], [], {}, {}
    result = {'started_at':old.stamp(), 'role':'read_only_acceptance_measurement',
              'submits':0, 'abaqus_calls':0, 'gui_close_running_solver':'NOT_OBSERVED'}
    owner = ProcessReference(connection['endpoint']['process']['pid'], connection['endpoint']['process'])
    refs.append(owner)
    solver = None
    closed = False
    log_after_close = None
    try:
        assert owner.exit_evidence() is None
        gui = old.Gui('gui_A_initial',root); guis.append(gui)
        first = old.wait(lambda:(v if (v:=gui.view()) and v['connected'] else None))
        assert dict(first['rows'])['Run ID'] == '未提交'
        old.save('READY.json',{'time':old.stamp(),'gui':gui.identity,'owner':owner.identity,
                              'health':client.health(),'gate':client.dispatch_gate(),'rendered':first})
        print('GUI_READY_NO_SUBMISSION',flush=True)
        deadline = time.monotonic()+180
        last_write = 0
        with (HERE/'PUBLIC_OBSERVATIONS.jsonl').open('x',encoding='utf-8') as log:
            while time.monotonic()<deadline:
                runs = {}
                for letter in 'AB':
                    if letter not in receipts:
                        try:
                            receipt = client.receipt(value['body']['request_keys'][letter])
                        except ExecutionError as e:
                            if e.code != 'NOT_FOUND': raise
                        else:
                            receipts[letter] = receipt
                            old.save(f'RECEIPT_{letter}.json',receipt)
                            if letter == 'A':
                                # Read-only measurement margin, not a grant/window extension.
                                deadline = time.monotonic()+640
                            else:
                                old.KEY = value['body']['request_keys']['B']
                                b_gui = old.Gui('gui_B',root); guis.append(b_gui)
                    if letter in receipts:
                        runs[letter] = client.run(receipts[letter]['run_id'])
                if time.monotonic()-last_write>=.5:
                    log.write(canonical_json({'time':old.stamp(),'runs':runs,
                        'progress':{k:client.progress(v['run_id']) for k,v in runs.items()},
                        'gate':client.dispatch_gate()})+'\n'); log.flush()
                    last_write = time.monotonic()
                run = runs.get('A')
                view = gui.view()
                if run and not closed and view and view['connected'] and dict(view['rows']).get('Run ID')==run['run_id']:
                    for member in run.get('process_records',[]):
                        if Path(member['image_path']).name.casefold()!='standard.exe': continue
                        candidate = ProcessReference(member['pid'],member)
                        if candidate.exit_evidence() is not None:
                            candidate.close(); continue
                        solver = candidate; refs.append(candidate)
                        old.save('BEFORE_GUI_CLOSE.json',{'time':old.stamp(),'solver':member,
                            'solver_exit':solver.exit_evidence(),'owner_exit':owner.exit_evidence(),
                            'health':client.health(),'view':view,'progress':client.progress(run['run_id']),
                            'receipt':client.receipt(value['body']['request_keys']['A'])})
                        exits = gui.close_normally(); closed = True
                        after = {'time':old.stamp(),'gui_exits':exits,'solver':solver.identity,
                            'solver_exit':solver.exit_evidence(),'owner_exit':owner.exit_evidence(),
                            'health':client.health(),'progress':client.progress(run['run_id']),
                            'receipt':client.receipt(value['body']['request_keys']['A'])}
                        old.save('AFTER_GUI_CLOSE.json',after)
                        result['gui_close_running_solver'] = 'OBSERVED' if after['solver_exit'] is None and after['owner_exit'] is None else 'NOT_OBSERVED_AFTER_CLOSE'
                        log_after_close = after['progress']
                        print('GUI_CLOSED '+result['gui_close_running_solver'],flush=True)
                        old.KEY = value['body']['request_keys']['A']
                        reconnect = old.Gui('gui_A_reconnected',root); guis.append(reconnect)
                        shown = old.wait(lambda:(v if (v:=reconnect.view()) and v['connected'] and dict(v['rows']).get('Run ID')==run['run_id'] else None))
                        old.save('GUI_RECONNECTED.json',{'time':old.stamp(),'gui':reconnect.identity,
                            'view':shown,'receipt':client.receipt(value['body']['request_keys']['A']),
                            'health':client.health(),'solver_exit':solver.exit_evidence()})
                        print('GUI_RECONNECTED_SAME_RUN',flush=True)
                        break
                if closed and run and 'log_growth_after_close' not in result:
                    progress = client.progress(run['run_id'])
                    before_bytes = {r['event']:r['bytes'] for r in log_after_close.get('records',[]) if 'bytes' in r}
                    after_bytes = {r['event']:r['bytes'] for r in progress.get('records',[]) if 'bytes' in r}
                    if any(n>before_bytes.get(k,0) for k,n in after_bytes.items()):
                        result['log_growth_after_close'] = {'time':old.stamp(),'progress':progress,
                            'solver_exit':solver.exit_evidence()}
                for letter,run in runs.items():
                    if letter not in finals and run['execution'] in ('FINISHED','BLOCKED'):
                        finals[letter] = run
                        old.save(f'FINAL_RUN_{letter}.json',run)
                        old.save(f'VALIDATIONS_{letter}.json',client.validations(run['run_id']))
                        report = client.diagnose(run['run_id'])
                        client.export_diagnostic(report,export_root=HERE,target=HERE/f'DIAGNOSTIC_{letter}.json')
                        print('FINAL '+letter+' '+run['execution'],flush=True)
                if len(finals)==2 or ('A' in finals and finals['A']['execution']=='BLOCKED'):
                    break
                time.sleep(.1)
            else: result['observation_end']='READ_ONLY_WAIT_ENDED_NO_TERMINATION'
        events=[]; cursor=0
        while True:
            page=client.events(cursor,64)
            if not page: break
            events.extend(page); cursor=max(e['project_sequence'] for e in page)
            if len(events)>2048: raise RuntimeError('EVENT_BOUND')
        old.save('FINAL_EVENTS.json',events)
        for g in guis:
            if g.actual.exit_evidence() is None:
                # Let the asynchronous reader render the committed final projection.
                old.wait(lambda:(v if (v:=g.view()) and v['connected'] and dict(v['rows']).get('执行阶段') in ('FINISHED','BLOCKED') else None),15)
                old.save(g.directory.name+'_FINAL_VIEW.json',g.view())
        result.update(ended_at=old.stamp(),receipts=receipts,finals=finals,
            gate=client.dispatch_gate(),owner=owner.identity,owner_exit=owner.exit_evidence(),
            solver_exit=solver.exit_evidence() if solver else None,
            remaining_gui=[g.identity for g in guis if g.actual.exit_evidence() is None],
            receipt_unchanged={k:client.receipt(value['body']['request_keys'][k])==v for k,v in receipts.items()})
        old.save('MEASUREMENT_RESULT.json',result)
        print('MEASUREMENT_FINISHED_OWNER_AND_VIEWS_PRESERVED',flush=True)
    except BaseException as exc:
        old.save('MEASUREMENT_ERROR.json',{'time':old.stamp(),'code':getattr(exc,'code',type(exc).__name__),
            'next':'Read-only queries only; no new submissions, owner stop or termination.'})
        raise
    finally:
        for ref in refs: ref.close()
        for g in guis: g.release_handles_only()


if __name__=='__main__': main()
