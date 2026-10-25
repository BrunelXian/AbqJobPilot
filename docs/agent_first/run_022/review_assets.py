"""Candidate-content checks; records locations/categories, never secret values."""
import json
from pathlib import Path
import re
import subprocess
from collections import Counter

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[2]
paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
findings=[];groups=Counter();sizes=Counter()
for name in sorted(set(paths)-{''}):
    if name.startswith('docs/agent_first/run_022/'):continue
    p=ROOT/name
    if not p.is_file() or p.is_symlink() or p.is_junction():continue
    data=p.read_bytes();group='source' if name.startswith('abqjobpilot/') else 'tests' if name.startswith('tests/') else 'examples' if name.startswith('examples/') else 'run_docs' if name.startswith('docs/agent_first/') else 'other'
    groups[group]+=1;sizes[group]+=len(data)
    flags=[]
    if data.startswith(b'SQLite format 3\x00'):flags.append('DATABASE_MAGIC')
    if any(part.lower() in {'private','runtime','backups'} for part in p.relative_to(ROOT).parts):flags.append('PRIVATE_RUNTIME_DIRECTORY')
    try:text=data.decode('utf-8-sig')
    except UnicodeError:text=''
    if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{30,}|\bsk-[A-Za-z0-9_-]{35,}',text):flags.append('SECRET_SIGNATURE_REVIEW')
    keymatches=[]
    for n,line in enumerate(text.splitlines(),1):
        if re.search(r'[\"\x27](?:credential|operator_token|token|api_key|authkey|secret|password|ciphertext)[\"\x27]\s*:\s*[\"\x27][^\"\x27\s]{16,}[\"\x27]',line,re.I):keymatches.append(n)
    if keymatches:flags.append('SECRET_KEY_LITERAL_REVIEW')
    if flags:findings.append({'path':name,'flags':flags,'lines':keymatches})
result={'scope':'Git tracked + nonignored untracked, Dev only; excludes own output','group_counts':dict(groups),'group_bytes':dict(sizes),'findings':findings,
        'limitations':'Pattern and magic-byte screening, not proof of absence of all encoded or externally held secrets. No secret values emitted; no files deleted or staged.'}
(OUT/'CANDIDATE_CONTENT_REVIEW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
