"""Run022 read-only Dev inventory. Never follows links or opens external roots."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8', errors='strict')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name, data):
    (OUT/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def main():
    assert git('branch','--show-current').strip() == 'Develop'
    assert not git('ls-files','-u')
    tracked = set(git('ls-files','-z').split('\0'))-{''}
    other = set(git('ls-files','--others','--exclude-standard','-z').split('\0'))-{''}
    ignored = set(git('ls-files','--others','--ignored','--exclude-standard','-z').split('\0'))-{''}
    records=[]; findings=[]
    for name in sorted(tracked|other):
        if name.startswith('docs/agent_first/run_022/'): continue
        p=ROOT/name
        if not p.exists():
            records.append({'path':name,'missing':True});continue
        if any(q.is_symlink() or q.is_junction() for q in (p,*p.parents) if q!=ROOT.parent):
            records.append({'path':name,'link_not_read':True});continue
        data=p.read_bytes()
        item={'path':name,'tracked':name in tracked,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        records.append(item)
        flags=[]
        if p.suffix.lower() in {'.db','.sqlite','.sqlite3','.odb','.dat','.sta','.msg','.bin','.log','.zip','.exe','.dll'}: flags.append('binary_or_runtime_extension')
        if len(data)>1024*1024: flags.append('over_1_MiB')
        if re.search(r'(connection|credential|private|bootstrap|operator)\.(json|bin)$',name,re.I): flags.append('credential_filename_review')
        try: text=data.decode('utf-8')
        except UnicodeDecodeError: text=None
        if text is not None:
            # Do not save matched values. These are review candidates, not confirmed secrets.
            lines=[]
            for n,line in enumerate(text.splitlines(),1):
                if re.search(r'"(?:token|authkey|secret|credential|operator_token|connection_secret|password|api_key|ciphertext)"\s*:\s*"[^"\s]{12,}"',line,re.I): lines.append(n)
            if lines: flags.append('literal_sensitive_key_review');item['sensitive_key_lines']=lines
            if re.search(r'[A-Za-z]:[\\/]+Users[\\/]+',text): flags.append('personal_path_review')
        if flags:findings.append({'path':name,'bytes':len(data),'flags':flags,'sensitive_key_lines':item.get('sensitive_key_lines',[])})
    payload={'observed_at':datetime.now(timezone.utc).isoformat(),'root':str(ROOT),'branch':git('branch','--show-current').strip(),
      'head':git('rev-parse','HEAD').strip(),'status':git('status','--porcelain=v1','-uall').splitlines(),
      'numstat':git('diff','--numstat').splitlines(),'conflicts':[], 'tracked_count':len(tracked),'untracked_count':len(other),
      'ignored_count':len(ignored),'ignored_paths':sorted(ignored),'files':records,'review_findings':findings}
    if sys.argv[1:] == ['final']:
        baseline=json.loads((OUT/'BASELINE.json').read_text(encoding='utf-8'))
        old={r['path']:r for r in baseline['files']};new={r['path']:r for r in records}
        payload['changed_since_baseline']=[n for n in sorted(old) if old[n].get('sha256')!=new.get(n,{}).get('sha256')]
        save('FINAL_INVENTORY.json',payload)
    else:
        if (OUT/'BASELINE.json').exists():raise RuntimeError('Preserve existing baseline')
        save('BASELINE.json',payload)
    print(json.dumps({k:payload[k] for k in ('head','tracked_count','untracked_count','ignored_count')},indent=2))
    print('review_candidates',len(findings),'bytes',sum(r.get('bytes',0) for r in records))
if __name__=='__main__':main()
