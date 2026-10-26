"""Explicit isolated no-process CI selection; no real backend or default Runtime."""
import argparse
import ast
import os
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);args=parser.parse_args()
target=Path(args.root).resolve()
if target.exists():raise SystemExit('Use a new explicit test directory')
target.mkdir(parents=True)
(target/'home').mkdir()
os.environ.update(TEMP=str(target),TMP=str(target),HOME=str(target/'home'),USERPROFILE=str(target/'home'),
                  PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
tempfile.tempdir=str(target)
sys.path.insert(0,str(ROOT));os.chdir(ROOT)
for source in [*ROOT.glob('*.py'),*(ROOT/'abqjobpilot').rglob('*.py')]:ast.parse(source.read_bytes(),filename=str(source))

def guard(event,args):
    if event in {'subprocess.Popen','os.system','os.startfile','abqjobpilot.managed_standard_create'}:
        raise AssertionError('CI selection forbids ALL external processes')
    if event=='open':
        path,mode,flags=args
        if isinstance(path,(str,bytes)) and isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC):
            if os.fsdecode(path).lower()==os.devnull.lower():return
            if not Path(os.fsdecode(path)).absolute().is_relative_to(target):raise AssertionError('CI write outside isolated root')
sys.addaudithook(guard)
import pytest
raise SystemExit(pytest.main(['-q','-p','no:cacheprovider','--tb=short','--show-capture=no','--basetemp',str(target/'cases'),
                             '--log-file',str(target/'pytest.log'),
                             '--junitxml',str(target/'safe.xml'),'tests/test_execution_contract.py','tests/test_release_fixtures.py']))
