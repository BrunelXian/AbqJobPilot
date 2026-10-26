"""Materialize exact proposed path lists, never Git's index. Conservative raw-data exclusion."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[2]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(n,v):(OUT/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
base=read(OUT/'BASELINE.json')
modified=set(subprocess.check_output(['git','diff','--name-only','-z'],cwd=ROOT).decode().split('\0'))
fixtures={
 'tests/fixtures/Job_test.inp':('INCLUDE','76-byte synthetic queue-only input; explicitly marked fake, not a solver result'),
 'docs/agent_first/run_010/axial_bar.inp':('INCLUDE','420-byte self-contained analytical axial-bar model; no INCLUDE/user files; existing exact model hash required by Standard contract'),
 'docs/agent_first/run_010/EXPERIMENT_MANIFEST.json':('INCLUDE','Frozen prepare-only command-template test fixture, execution_authorized=false; absolute paths are historical declarations, no grant'),
 'docs/agent_first/run_010/RUNTIME_STATIC_IDENTITIES.json':('INCLUDE','Static installation identity metadata required by explicit historical package preparation; not dynamic credentials or a launch permission'),
 'docs/agent_first/run_011/result_review_001/ORIGINAL_DAT.bin':('REVIEW_REQUIRED','10334-byte actual Abaqus DAT copy, hash 23ac0cdd...; many Standard/recovery regressions read it. Forbidden raw-result category: needs approved sanitized replacement, not extension-based exception'),
 'docs/agent_first/run_007/examples/historical_invalid_after.json':('REVIEW_REQUIRED','Actual historical diagnostic/process record read by compatibility tests; replace with provenance-marked synthetic fixture before excluding raw evidence'),
}
design_prefixes=('docs/agent_first/run_023/design/','docs/agent_first/run_023/locales/')
rows=[]
for item in base['inventory']:
 name=item['path'];suffix=item.get('suffix','');row=dict(item)
 action,reason='LOCAL_ONLY','Historical raw evidence, per-machine capture, test result or one-off acceptance helper; preserve locally'
 if name in fixtures:action,reason=fixtures[name]
 elif name=='sample.png':action,reason='REVIEW_REQUIRED','Archived screenshot visibly contains real engineering directory/job names and results; public-use redaction/approval required, not a runtime dependency'
 elif name=='docs/agent_first/run_022/CLEANUP.json':action,reason='PROHIBITED','Contains one plaintext test credential plus 44 encrypted credential fields; already in HEAD history'
 elif item.get('sqlite_magic') or suffix in {'.db','.sqlite','.sqlite3','.odb','.dat','.sta','.msg','.bin','.jsonl','.ready'}:
  action,reason='PROHIBITED','Database, actual solver/console/process output or transient marker; no source-distribution inclusion'
 elif name.startswith('abqjobpilot/') and suffix in {'.py','.json'}:action,reason='INCLUDE','Product/core source or display-only localization resource; dependency closure required'
 elif name.startswith('tests/') and suffix=='.py':action,reason='INCLUDE','Reviewed test/helper source, not generated test data; runtime isolation is mandatory'
 elif name.startswith('examples/') and suffix=='.py':action,reason='INCLUDE','Controlled public-client/operator source, not permission to execute historical acceptance; excluded from ordinary end-user launch shortcuts'
 elif name.startswith('examples/') and suffix=='.vbs':action,reason='LOCAL_ONLY','Historical TEST/real acceptance shortcut; keep locally, do not expose as product launcher'
 elif 'old_tests_tmp' in name:action,reason='LOCAL_ONLY','Explicit retained legacy temporary artifact; never delete or publish automatically'
 elif suffix=='.md':action,reason='INCLUDE','Development contract/report; historical paths and evidence caveats retained; raw evidence links may be local-only'
 elif name in {'.gitignore','LICENSE','run_gui.py','Open_Dev_GUI.vbs','requirements.txt','requirements-mcp.txt','sample.png'}:
  action,reason='INCLUDE','Repository entry/dependency/legal asset; legacy screenshot explicitly identified as archived'
 elif name.startswith(design_prefixes) and suffix in {'.html','.json'}:action,reason='INCLUDE','Archived static design/localization draft; not the product GUI runtime'
 elif name=='docs/agent_first/run_017/test_format_boundaries.py':action,reason='INCLUDE','Regression source referenced by safe legacy selection'
 row.update(category=action,reason=reason,git_effect=('MODIFY' if name in modified else 'KEEP_HEAD') if item['tracked'] else 'ADD',release_runtime=name.startswith('abqjobpilot/') or name in {'run_gui.py','Open_Dev_GUI.vbs','requirements.txt','LICENSE'})
 rows.append(row)
save('FILE_CLASSIFICATION.json',rows)
included=[r for r in rows if r['category']=='INCLUDE']
excluded=[r for r in rows if r['category']!='INCLUDE']
save('CANDIDATE_SNAPSHOT_WHITELIST.json',included)
save('EXCLUSIONS.json',excluded)
save('FIXTURE_REVIEW.json',[r for r in rows if r['path'] in fixtures])
for name,values in [('ADD_MODIFY_WHITELIST.txt',[r['path'] for r in included if r['git_effect'] in {'ADD','MODIFY'}]),
 ('TRACKED_EXCLUSION_PROPOSAL.txt',[r['path'] for r in excluded if r['tracked']]),
 ('LOCAL_UNTRACKED_EXCLUSIONS.txt',[r['path'] for r in excluded if not r['tracked']]),
 ('MANUAL_DECISIONS.txt',[r['path'] for r in rows if r['category']=='REVIEW_REQUIRED'])]:
 (OUT/name).write_text('\n'.join(values)+'\n',encoding='utf-8')

names={r['path'] for r in included};allnames={r['path'] for r in rows}
missing_imports=[];imports_checked=0
for r in included:
 if not r['path'].startswith('abqjobpilot/') or not r['path'].endswith('.py'):continue
 p=ROOT/r['path'];tree=ast.parse(p.read_text(encoding='utf-8-sig'))
 for node in ast.walk(tree):
  if isinstance(node,ast.ImportFrom) and node.level:
   imports_checked+=1;parts=p.relative_to(ROOT).with_suffix('').parts[:-1];baseparts=parts[:len(parts)-node.level+1]
   module='/'.join((*baseparts,*(node.module.split('.') if node.module else [])))
   targets=([module+'.py',module+'/__init__.py'] if node.module else [module+'/'+alias.name+'.py' for alias in node.names])
   if node.module and not any(n in names for n in targets):missing_imports.append({'source':r['path'],'line':node.lineno,'targets':targets})
   if not node.module:
    initpath=ROOT/(module+'/__init__.py')
    exports=set()
    if initpath.exists():
     for n in ast.walk(ast.parse(initpath.read_text(encoding='utf-8-sig'))):
      if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store):exports.add(n.id)
    for target in targets:
     if target not in names and target[:-3]+'/__init__.py' not in names and Path(target).stem not in exports:missing_imports.append({'source':r['path'],'line':node.lineno,'targets':[target]})
links=[]
for r in included:
 if r.get('suffix')!='.md':continue
 for target in re.findall(r'\]\(([^)]+)\)',(ROOT/r['path']).read_text(encoding='utf-8-sig')):
  target=target.split('#')[0].split(' "')[0].strip('<>')
  if not target or re.match(r'(?:[a-zA-Z]+:|/|\\)',target):continue
  dest=(ROOT/r['path']).parent/unquote(target)
  # Normalize lexically; never follow a linked external path.
  import os
  dest=Path(os.path.abspath(dest))
  if not dest.is_relative_to(ROOT):continue
  rel=dest.relative_to(ROOT).as_posix()
  if rel not in names:
   links.append({'source':r['path'],'target':rel,'classification':'LOCAL_EVIDENCE_EXCLUDED' if rel in allnames else 'MISSING_OR_DIRECTORY'})
save('DEPENDENCY_AUDIT.json',{'product_relative_imports_checked':imports_checked,'missing_product_imports':missing_imports,
 'test_data_blockers':[n for n,(a,_) in fixtures.items() if a=='REVIEW_REQUIRED'],
 'document_links_outside_candidate':links,
 'scope':'Static product relative imports and literal documentation links; dynamic historical scripts may still require old local manifests. No script executed by link audit.'})
print(json.dumps({'categories':Counter(r['category'] for r in rows),'candidate':len(included),'add_modify':sum(r['git_effect'] in {'ADD','MODIFY'} for r in included),'tracked_exclusions':sum(r['tracked'] for r in excluded),'manual':sum(r['category']=='REVIEW_REQUIRED' for r in rows),'missing_product_imports':missing_imports,'local_evidence_links':len(links)},ensure_ascii=False))
