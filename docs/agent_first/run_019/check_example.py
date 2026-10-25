"""Exercise the shipped example from a non-repository cwd, with a new TEST store."""
import json,os,subprocess,sys,time
from pathlib import Path
SOURCE=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(SOURCE))
from abqjobpilot.service_lifecycle import ServiceLifecycleManager
from abqjobpilot.execution.process_handles import ProcessReference
base=Path(json.loads((Path(__file__).with_name('BASELINE.json')).read_text(encoding='utf-8'))['test_root'])
root=base/'public_example';script=SOURCE/'examples/agent_first/lifecycle_demo.py'
def call(operation,**extra):
    command=[sys.executable,'-B',str(script),operation,'--root',str(root)]
    for k,v in extra.items():command.extend(['--'+k,v])
    result=subprocess.run(command,cwd=base,capture_output=True,text=True,encoding='utf-8',timeout=20,
                          env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','TEMP':str(base),'TMP':str(base)})
    assert result.returncode==0,result.stderr
    return json.loads(result.stdout)
data={'prepare':call('prepare'),'cwd':str(base),'abaqus_calls':0}
data['inspect_before']=call('inspect');data['start']=call('start')
manager=ServiceLifecycleManager(root/'project');client,_,health=manager.connect()
reference=ProcessReference(health['process']['pid'],health['process'])
try:
    data['submit']=call('submit');rid=data['submit']['receipt']['run_id']
    end=time.monotonic()+45
    while time.monotonic()<end:
        r=client.run(rid)
        if r['execution']=='FINISHED':break
        time.sleep(.05)
    assert r['execution']=='FINISHED' and r['artifact_validation']=='VALID' and r['solver_conclusion']=='NOT_RUN'
    data['run']=r;data['replay']=call('submit');assert data['replay']['replayed']
    data['stop']=call('stop',owner=client.endpoint['owner_id'])
    end=time.monotonic()+10
    while reference.exit_evidence() is None and time.monotonic()<end:time.sleep(.05)
    data['exit']=reference.exit_evidence();assert data['exit']['exit_code']==0
finally:reference.close()
data['private_removed']=[]
for name in ('offer.json','lifecycle.json','operator.json','connection.json'):
    (root/'private'/name).unlink();data['private_removed'].append(name)
with Path(__file__).with_name('PUBLIC_EXAMPLE.json').open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
print('PUBLIC_EXAMPLE_PASS')
