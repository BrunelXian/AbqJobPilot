"""Read-only public/retained-handle evidence recorder. Never launches/stops work."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, r'D:\Projects\abqjobpilot_dev')
from abqjobpilot.service_lifecycle import ServiceLifecycleManager
from abqjobpilot.execution.process_handles import ProcessReference
from abqjobpilot.execution.models import ExecutionError

out = Path(__file__).parent
body = json.loads((out.parent/'ACCEPTANCE_MANIFEST.json').read_text())['body']
manager = ServiceLifecycleManager(body['root'])
client, ctx, health = manager.connect()
owner = manager.inspect()['process']
refs = {}
for label, pid, expected in [('gui',12056,None),('gui_venv',22576,None),('owner',owner['pid'],owner),('owner_venv',owner['parent_pid'],None)]:
    refs[label] = ProcessReference(pid, expected)
start = time.monotonic()
with (out/'OBSERVATIONS.jsonl').open('x',encoding='utf-8') as log:
    try:
        while time.monotonic()-start < 300 and not (out/'observer_stop').exists():
            row={'observed_at':time.time(),'owner_id':client.endpoint['owner_id']}
            try:
                receipt=client.receipt(body['operation_keys']['submit'])
                run=client.run(receipt['run_id'])
                row.update(receipt=receipt,run=run,gate=client.dispatch_gate())
                for i,record in enumerate(run.get('process_records',[])):
                    label='record_'+str(i)
                    if label not in refs:
                        try: refs[label]=ProcessReference(record['pid'],record)
                        except ExecutionError as e: row.setdefault('identity_errors',[]).append({'index':i,'code':e.code})
            except ExecutionError as e: row['query_error']=e.code
            except Exception as e: row['query_error']=type(e).__name__
            row['os']={}
            for label,ref in refs.items():
                try: row['os'][label]={'identity':ref.identity,'exit':ref.exit_evidence()}
                except ExecutionError as e: row['os'][label]={'error':e.code}
            row['files']={p.name:p.stat().st_size for p in Path(body['root'],'engineering').glob(body['plan']['job_name']+'.*') if p.is_file()}
            log.write(json.dumps(row,ensure_ascii=False)+'\n');log.flush()
            (out/'LATEST.json').write_text(json.dumps(row,ensure_ascii=False),encoding='utf-8')
            if not (out/'OBSERVER_READY.json').exists():
                (out/'OBSERVER_READY.json').write_text(json.dumps({'owner':owner,'os':row['os'],'at':row['observed_at']}),encoding='utf-8')
                print('OBSERVER_READY',flush=True)
            time.sleep(.5)
    finally:
        for ref in refs.values(): ref.close()
        (out/'OBSERVER_CLOSED.json').write_text(json.dumps({'at':time.time(),'handles_closed':len(refs),'termination_calls':0}),encoding='utf-8')
