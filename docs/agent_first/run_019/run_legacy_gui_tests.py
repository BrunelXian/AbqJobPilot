"""Separate legacy regression process; explicit fresh home/Runtime/Recent, no launch."""
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

source=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(source))
root=Path(tempfile.mkdtemp(prefix='legacy_',dir=os.environ['TEMP'])).resolve()
os.environ.update(TEMP=str(root),TMP=str(root),PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
tempfile.tempdir=str(root);(root/'home').mkdir()
print('ISOLATED_ROOT='+str(root),flush=True)

def audit(event,args):
    if event in {'subprocess.Popen','os.system','os.startfile'}:
        raise AssertionError('No external process is allowed in these legacy UI regressions')
    if event=='open':
        path,mode,flags=args
        if isinstance(path,(str,bytes)):
            target=Path(os.fsdecode(path)).resolve()
            if target.is_relative_to(source/'runtime'):
                raise AssertionError('Do not access repository legacy Runtime')
            if isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC):
                assert target.is_relative_to(root),('write escaped new test root',target)
sys.addaudithook(audit)
original_file,original_dir=Path.is_file,Path.is_dir
def absent_legacy(path,fn):
    if path.is_relative_to(source/'runtime'):return False
    return fn(path)
with patch.object(Path,'home',return_value=root/'home'), \
     patch.object(Path,'is_file',lambda p:absent_legacy(p,original_file)), \
     patch.object(Path,'is_dir',lambda p:absent_legacy(p,original_dir)):
    from abqjobpilot import config
    config.use_runtime_dir(root/'runtime')
    config.RUNTIME_DIR_PATH=root/'runtime'
    import pytest
    sys.exit(pytest.main(['-q','-p','no:cacheprovider','--basetemp',str(root/'cases'),'--log-file',str(root/'pytest.log'),
        '--junitxml',str(root/'legacy.xml'),'tests/test_project_gui.py',
        'tests/test_gui_table_state.py','tests/test_g2_task_workspace.py',
        'docs/agent_first/run_017/test_format_boundaries.py']))
