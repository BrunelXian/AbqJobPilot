import hashlib,json,platform,subprocess,sys,tempfile
from pathlib import Path
from datetime import datetime
root=Path(__file__).resolve().parents[3];out=Path(__file__).resolve().parent
def git(*args):return subprocess.check_output(['git','--no-optional-locks','-c','core.quotepath=false',*args],cwd=root,text=True,encoding='utf-8').strip()
assert git('branch','--show-current')=='Develop' and not git('ls-files','-u')
excluded={'docs/agent_first/run_016/real_001/gui_A_reconnected/view.json','docs/agent_first/run_016/real_001/gui_B/view.json'}
files=[]
for name in git('ls-files','--cached','--others','--exclude-standard').splitlines():
    if name.startswith('docs/agent_first/run_019/') or name in excluded:continue
    p=root/name
    if p.is_file():files.append({'path':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
data={'at':datetime.now().astimezone().isoformat(),'root':str(root),'head':git('rev-parse','HEAD'),
      'branch':'Develop','status':git('status','--short','--untracked-files=all'),'files':files,
      'excluded_live_views':sorted(excluded),'python':sys.executable,'version':sys.version,'os':platform.platform(),
      'test_root':tempfile.mkdtemp(prefix='AbqJobPilot_Run019_')}
with (out/'BASELINE.json').open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
print(data['test_root'])
