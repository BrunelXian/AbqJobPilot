"""Run023 design-only preservation check. No application imports or execution."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent

def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args]).decode('utf-8').strip()

def inventory():
    paths = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '-c', '-o', '--exclude-standard', '-z']).decode('utf-8').split('\0')
    result = {}
    for name in sorted(set(paths)):
        if not name or name.startswith('docs/agent_first/run_023/'):
            continue
        p = ROOT / name
        if p.is_file():
            result[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return result

def main():
    assert git('branch', '--show-current') == 'Develop'
    assert not git('ls-files', '-u')
    current = inventory()
    state = dict(root=str(ROOT), branch=git('branch','--show-current'), head=git('rev-parse','HEAD'),
                 interpreter=sys.executable, python=sys.version, version='0.3.0.dev0',
                 status=git('status','--porcelain=v1','--untracked-files=all').splitlines(), files=current)
    if sys.argv[1] == 'baseline':
        target=OUT/'BASELINE.json'
        with target.open('x',encoding='utf-8') as f:json.dump(state,f,ensure_ascii=False,indent=2)
    else:
        baseline=json.loads((OUT/'BASELINE.json').read_text(encoding='utf-8'))
        changed=[p for p,h in baseline['files'].items() if current.get(p)!=h]
        added=sorted(set(current)-set(baseline['files']))
        result=dict(branch=state['branch'],head=state['head'],baseline_files=len(baseline['files']),
                    changed_or_missing=changed,added_outside_run023=added,
                    pass_preservation=not changed and not added and baseline['head']==state['head'])
        (OUT/'PRESERVATION_CHECK.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result))
        assert result['pass_preservation']

if __name__=='__main__':main()
