"""Safe subset from the exact candidate, no Git index, subprocesses or Solver."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import uuid

OUT=Path(__file__).resolve().parent;SOURCE=OUT.parents[2]
mode=sys.argv[1];assert mode in ('isolation','semantics')
report=OUT/(mode+'_TEST.xml');assert not report.exists(),'Do not overwrite previous results'
root=OUT/'local_verification'/uuid.uuid4().hex
snapshot=root/'source';snapshot.mkdir(parents=True)
rows=json.loads((OUT/'CANDIDATE_SNAPSHOT_WHITELIST.json').read_text(encoding='utf-8'))
copied=[]
for r in rows:
 name=r['path']
 if not (name.startswith(('abqjobpilot/','tests/')) or name in ('run_gui.py','requirements.txt')):continue
 src=SOURCE/name;dest=snapshot/name;assert hashlib.sha256(src.read_bytes()).hexdigest()==r['sha256']
 dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest);copied.append(name)
temp=root/'temp';temp.mkdir();(root/'home').mkdir()
os.environ.update(TEMP=str(temp),TMP=str(temp),HOME=str(root/'home'),USERPROFILE=str(root/'home'),
 PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',ABQJOBPILOT_UI_PREFS=str(root/'display.json'))
tempfile.tempdir=str(temp);os.chdir(snapshot)
sys.path.insert(0,str(snapshot));sys.path.insert(0,str(snapshot/'tests'))
def audit(event,args):
 if event in {'subprocess.Popen','os.system','os.startfile','abqjobpilot.managed_standard_create'}:raise AssertionError('No child process permitted in RC-G01 subset')
 if event=='open' and isinstance(args[0],(str,bytes)):
  p=Path(os.fsdecode(args[0])).absolute()
  if os.fsdecode(args[0]).lower()==os.devnull.lower():return
  if p.is_relative_to(SOURCE/'runtime') or p.is_relative_to(snapshot/'runtime'):raise AssertionError('Default Runtime forbidden')
  flags=args[2]
  if isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC):
   if not p.is_relative_to(root) and p!=report:raise AssertionError('Write outside isolated audit test root')
sys.addaudithook(audit)
import pytest
target='tests/test_execution_isolation.py' if mode=='isolation' else 'tests/test_cockpit_semantics.py'
result=pytest.main(['-q','-p','no:cacheprovider','--maxfail=1','--basetemp',str(temp/'cases'),'--log-file',str(root/'pytest.log'),'--junitxml',str(report),target])
# Record has no secret material. No recursive cleanup, no process cleanup needed.
(root/'RESULT.json').write_text(json.dumps({'mode':mode,'exit_code':result,'source_files':len(copied),'root':str(root),
 'external_process_calls':0,'Abaqus_calls':0,'directories_retained':True,'candidate_SHA_bound':True},indent=2),encoding='utf-8')
print('RETAINED_ROOT='+str(root));sys.exit(result)
