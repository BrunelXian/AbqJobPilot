"""Read-only Git/content audit. Writes only this audit's reports; never stages."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def paths(*args):return [x.decode('utf-8') for x in git(*args).split(b'\0') if x]
def save(name,obj):(OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(raw):return hashlib.sha256(raw).hexdigest()
tracked=set(paths('ls-files','-z'));new=set(paths('ls-files','--others','--exclude-standard','-z'))
ignored=paths('ls-files','--others','--ignored','--exclude-standard','-z')
status=git('status','--porcelain=v1','-z','--untracked-files=all')
head=git('rev-parse','HEAD').decode().strip();branch=git('branch','--show-current').decode().strip()
assert branch=='Develop' and not git('ls-files','-u')
index=ROOT/'.git/index';index_hash=sha(index.read_bytes())
inventory=[];findings=[];syntax=[];absolute=[];json_secrets=[];imports=[]
sensitive={'credential','authkey','secret','token','operator_token','lifecycle_token','ciphertext'}
def inspect_json(value,path,where='$'):
 if isinstance(value,dict):
  for key,v in value.items():
   if key.lower() in sensitive and isinstance(v,str) and v:
    json_secrets.append({'path':path,'location':where+'.'+key,'length':len(v),'value_exported':False})
   inspect_json(v,path,where+'.'+key)
 elif isinstance(value,list):
  for n,v in enumerate(value):inspect_json(v,path,f'{where}[{n}]')
for name in sorted(tracked|new):
 if name.startswith('docs/agent_first/rc_git_001/'):continue
 p=ROOT/name;row={'path':name,'tracked':name in tracked,'exists':p.exists()}
 if not p.exists():inventory.append(row);continue
 if p.lstat().st_file_attributes&1024:row['reparse_skipped']=True;inventory.append(row);continue
 raw=p.read_bytes();row.update(bytes=len(raw),sha256=sha(raw),suffix=p.suffix.lower())
 row['sqlite_magic']=raw.startswith(b'SQLite format 3\0')
 try:text=raw.decode('utf-8-sig');row['encoding']='utf-8'
 except UnicodeError:
  try:text=raw.decode('cp936');row['encoding']='cp936'
  except UnicodeError:text=None;row['encoding']='binary'
 if raw.startswith(b'\x89PNG'):row['encoding']='png'
 if len(raw)>1_000_000:findings.append({'path':name,'kind':'large_file','bytes':len(raw)})
 for marker,pattern in [('private_key',rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),('known_token_shape',rb'(?:ghp_[A-Za-z0-9]{30,}|sk-proj-[A-Za-z0-9_-]{30,})')]:
  if re.search(pattern,raw):findings.append({'path':name,'kind':marker,'contents_exported':False})
 if text is not None:
  for n,line in enumerate(text.splitlines(),1):
   if re.search(r'[A-Z]:[\\/]',line):absolute.append({'path':name,'line':n})
  if p.suffix=='.json':
   try:inspect_json(json.loads(text),name)
   except ValueError:findings.append({'path':name,'kind':'invalid_json'})
  if p.suffix=='.py':
   try:
    tree=ast.parse(text,filename=name)
    for node in ast.walk(tree):
     if isinstance(node,ast.Import):imports.extend({'path':name,'line':node.lineno,'module':a.name,'level':0} for a in node.names)
     elif isinstance(node,ast.ImportFrom):imports.append({'path':name,'line':node.lineno,'module':node.module,'level':node.level,'names':[a.name for a in node.names]})
    syntax.append({'path':name,'result':'PASS'})
   except SyntaxError as e:syntax.append({'path':name,'result':'FAIL','line':e.lineno,'message':e.msg})
 inventory.append(row)
save('BASELINE.json',{'head':head,'branch':branch,'index_sha256':index_hash,'status_porcelain':status.decode('utf-8').split('\0'),
 'staged_numstat':git('diff','--cached','--numstat').decode(),'unstaged_numstat':git('diff','--numstat').decode(),
 'tracked_count':len(tracked),'untracked_count_excluding_audit':sum(not n.startswith('docs/agent_first/rc_git_001/') for n in new),
 'ignored_paths_only_not_opened':ignored,'inventory':inventory})
save('CONTENT_SCAN.json',{'findings':findings,'json_secret_field_candidates':json_secrets,'absolute_path_locations':absolute,
 'limits':'No secret values exported. Pattern scan is not a proof against arbitrary encoded secrets. Ignored paths not opened. No network, owner or Project access.'})
save('STATIC_PYTHON.json',{'files':syntax,'imports':imports})
(OUT/'GIT_DIFF_CHECK.txt').write_bytes(git('diff','--check') if not subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True).returncode else subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True).stdout)
print(json.dumps({'head':head,'tracked':len(tracked),'untracked':len(new),'inventory':len(inventory),'syntax':Counter(x['result'] for x in syntax),
 'scan_findings':findings,'json_secret_fields':len(json_secrets),'ignored':len(ignored),'suffix':Counter(x.get('suffix') for x in inventory)},ensure_ascii=False))
