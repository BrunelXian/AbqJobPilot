"""Read-only preservation/link checks; writes only this Run's audit result."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
b=json.loads((OUT/'BASELINE.json').read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True,encoding='utf-8').strip()
changed=[];missing=[]
for e in b['entries']:
    p=ROOT/e['path']
    if not p.exists():missing.append(e['path'])
    elif sha(p)!=e['sha256']:changed.append(e['path'])
protected_bad=[]
for e in b['protected']:
    p=Path(e['path'])
    if not p.exists() or sha(p)!=e['sha256']:protected_bad.append(e['path'])
links=[]
for p in [*OUT.glob('*.md'),ROOT/'README.md',ROOT/'README_CN.md']:
    for m in re.finditer(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
        target=m.group(1).strip('<>').split('#')[0]
        if not target or '://' in target:continue
        q=p.parent/target
        # No file resolution outside the explicitly allowed Dev workspace.
        if not q.resolve().is_relative_to(ROOT):continue
        if not q.exists():links.append({'file':str(p.relative_to(ROOT)),'target':target})
known={e['path'].replace('\\','/') for e in b['entries']}
new=[x for x in git('ls-files','--others','--exclude-standard').splitlines() if x.replace('\\','/') not in known]
volatile={'docs/agent_first/run_016/real_001/gui_A_reconnected/view.json',
          'docs/agent_first/run_016/real_001/gui_B/view.json'}
result={'branch':git('branch','--show-current'),'head':git('rev-parse','HEAD'),
        'conflicts':git('ls-files','-u'),'prior_nonignored_files':len(b['entries']),
        'changed_prior_files':changed,'missing_prior_files':missing,
        'retained_gui_volatile_views':[p for p in changed if p in volatile],
        'unexpected_changed_prior_files':[p for p in changed if p not in volatile|{'README.md','README_CN.md'}],
        'volatile_explanation':'tests/run012_gui.py write/view callback continues in retained Run016 GUIs; this audit never wrote or stopped these views',
        'protected_count':len(b['protected']),'protected_mismatch':protected_bad,
        'new_files':new,'new_outside_run017':[p for p in new if not p.startswith('docs/agent_first/run_017/')],
        'broken_local_links':links,
        'version_declaration':(ROOT/'abqjobpilot/__init__.py').read_text(encoding='utf-8').strip(),
        'scope':'No owner/GUI/OS query or database connection; hashes of already listed files only'}
(OUT/'FINAL_INTEGRITY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'GIT_AFTER.txt').write_text(git('status','--short','--untracked-files=all'),encoding='utf-8')
print(json.dumps({k:result[k] for k in ('branch','head','conflicts','changed_prior_files','missing_prior_files',
    'protected_count','protected_mismatch','new_outside_run017','broken_local_links')},ensure_ascii=False))
