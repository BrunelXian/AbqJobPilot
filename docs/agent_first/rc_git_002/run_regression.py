"""Audited RC selections; fresh isolated roots, fixed Python children only.

Not a general test runner. No default GUI or historical Project is opened.
The Standard Windows tests replace the native creator in their child owner.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

OUT=Path(__file__).resolve().parent/'test_results'
OUT.mkdir(exist_ok=True)
SOURCE=OUT.parent/'local_verification/source'
os.chdir(SOURCE)
sys.path.insert(0,str(SOURCE))
MODE=sys.argv[1]
BATCH=sys.argv[2] if len(sys.argv)>2 else MODE
if (OUT/(BATCH+'.xml')).exists():raise RuntimeError('Preserve prior report; use a separately reviewed new report location')
root=Path(tempfile.mkdtemp(prefix='RCG02_'+MODE+'_',dir=OUT.parent/'local_verification')).resolve()
os.environ.update(TEMP=str(root),TMP=str(root),PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONIOENCODING='utf-8')
tempfile.tempdir=str(root)
(root/'home').mkdir()
os.environ.update(USERPROFILE=str(root/'home'),HOME=str(root/'home'))
for stage in ('012','013','014','015','016','018','019','020','021B'):
    os.environ['RUN'+stage+'_EVIDENCE_DIR']=str(root/'evidence'/stage)
    (root/'evidence'/stage).mkdir(parents=True)
(OUT/(BATCH+'_ROOT.json')).write_text(json.dumps({'root':str(root),'interpreter':sys.executable},indent=2),encoding='utf-8')
print('ISOLATED_ROOT='+str(root),flush=True)

SELECTIONS={
 'fixtures':['release_fixtures','standard_backend','standard_managed','standard_pair_client','product_standard_control','product_project'],
 'legacy_single':['g2_task_workspace'],
 'native':['native_workspace'],
 'semantics':['cockpit_semantics'],
 # Import-isolation assertions require a fresh interpreter, separate from GUI imports.
 'focused':['execution_gui','project_view','run_diagnostics','diagnostic_supervisor','managed_scope','interrupted_recovery','mcp_readonly'],
 'cockpit':['cockpit_widgets'],
 'cockpit_windows':['cockpit_windows'],
 'visual':['native_visual'],
 'lifecycle_gui':['service_lifecycle','product_windows','product_standard_windows'],
 'recovery':['interruption_diagnostics','interruption_probe','interruption_windows','interrupted_recovery','recovery_windows'],
 'native_windows':['native_workspace_windows'],
 'core':['execution_contract','execution_store','execution_ownership','process_contract','process_fixture','fake_supervisor',
         'fake_reconciliation','recorded_exit_reconciliation','reconciliation_supervisor','run_diagnostics','diagnostic_supervisor',
         'public_workflow','public_client_example','standard_backend','standard_admission','standard_supervisor',
         'standard_closeout','closeout_windows','managed_scope','standard_managed','standard_managed_windows','standard_pair_client'],
 'product':['service_attachment','project_view','attachment_gui','execution_gui','service_lifecycle','lifecycle_boundaries',
            'product_project','product_windows','product_standard_control','product_standard_windows'],
 'isolation':['execution_isolation'],
 'legacy':['project_gui','gui_table_state','g2_task_workspace','project_model','project_database','project_file_ownership','queue_only_enqueue'],
 'api':['mcp_readonly'],
}
targets=['tests/test_'+x+'.py' for x in SELECTIONS[MODE]]
if MODE=='legacy_single':targets=['tests/test_g2_task_workspace.py::TaskWorkspaceGuiTests::test_workspace_gui_end_to_end']
if len(sys.argv)>3:
    import re
    assert MODE in {'native','cockpit'} and re.fullmatch(r'test_[A-Za-z0-9_]+(?:\[[A-Za-z0-9.-]+\])?',sys.argv[3])
    targets=[targets[0]+'::'+sys.argv[3]]
if MODE=='legacy': targets+=['tests/test_public_api.py::TestPublicApi','docs/agent_first/run_017/test_format_boundaries.py']
def audit(event,args):
    if event in {'subprocess.Popen','os.system','os.startfile','abqjobpilot.managed_standard_create'}:
        serialized=str(args).lower()
        if any(x in serialized for x in ('abq2024.bat','standard.exe','smapython.exe','abq2024.exe')):
            raise AssertionError('RC suite forbids real Abaqus entry')
        if MODE in {'legacy','legacy_single'}: raise AssertionError('No process creation in selected legacy tests')
    if event=='open':
        path,mode,flags=args
        if isinstance(path,(str,bytes)):
            p=Path(os.fsdecode(path)).absolute()
            # subprocess.DEVNULL opens the Windows null device O_RDWR even for
            # stdin. It is not a filesystem output or a solver invocation.
            if os.fsdecode(path).lower() == os.devnull.lower() or str(p).lower() in {r'\\.\nul',r'\\?\nul'}: return
            if p.is_relative_to(SOURCE/'runtime'):raise AssertionError('Default Runtime forbidden')
            if isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC):
                if not (p.is_relative_to(root) or p.is_relative_to(OUT)):
                    raise AssertionError('Test write escaped explicit test/report roots: '+str(p))
sys.addaudithook(audit)

def run():
    import pytest
    return pytest.main(['-q','-p','no:cacheprovider','--maxfail=1','--basetemp',str(root/'cases'),'--log-file',str(root/'pytest.log'),
        '--junitxml',str(OUT/(BATCH+'.xml')),'-o','tmp_path_retention_policy=all',*targets])
if MODE in {'legacy','legacy_single','api'}:
    original_file,original_dir=Path.is_file,Path.is_dir
    def absent(p,fn):return False if p.is_relative_to(SOURCE/'runtime') else fn(p)
    with patch.object(Path,'home',return_value=root/'home'),patch.object(Path,'is_file',lambda p:absent(p,original_file)),patch.object(Path,'is_dir',lambda p:absent(p,original_dir)):
        from abqjobpilot import config
        config.use_runtime_dir(root/'runtime');config.RUNTIME_DIR_PATH=root/'runtime'
        sys.exit(run())
sys.exit(run())
