"""Finalize read-only audit receipts. No index writes, deletion, auth or owner access."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
from string import Formatter
import subprocess
import xml.etree.ElementTree as ET

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[2]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,o):(OUT/n).write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf-8')
base=read(OUT/'BASELINE.json');rows=read(OUT/'FILE_CLASSIFICATION.json')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==base['head']
assert sha(ROOT/'.git/index')==base['index_sha256']
changed=[r['path'] for r in base['inventory'] if r.get('sha256') and (not (ROOT/r['path']).exists() or sha(ROOT/r['path'])!=r['sha256'])]
assert not changed,changed
save('PRESERVATION.json',{'HEAD':base['head'],'branch':'Develop','index_sha256':base['index_sha256'],'index_unchanged':True,
 'preexisting_files_checked':len(base['inventory']),'preexisting_files_changed':changed,'Abaqus_calls':0,'owner_operations':0,'git_mutations':0})

languages={k:read(ROOT/'abqjobpilot/locales'/f'{k}.json') for k in ('en','zh-CN','fr-FR','de-DE')}
params=lambda s:{f for _,f,_,_ in Formatter().parse(s) if f is not None}
differences=[]
for lang,values in languages.items():
 for key,value in languages['en'].items():
  if key not in values or params(value)!=params(values[key]):differences.append({'locale':lang,'key':key})
save('LANGUAGE_REVIEW.json',{'keys':{k:len(v) for k,v in languages.items()},'missing_or_parameter_differences':differences,
 'default':'en','preview_languages':['fr-FR','de-DE'],'native_review_not_repeated':True})

old=read(ROOT/'docs/agent_first/run_024r/integration_001/CLEANUP_BEFORE.json')['roots']
assert len(old)==45
assert all(not str(p).lower().replace('\\','/').startswith(str(ROOT).lower().replace('\\','/')+'/') for p in old)
save('RETAINED_45_EXCLUSION.json',{'source':'docs/agent_first/run_024r/integration_001/CLEANUP_BEFORE.json',
 'source_sha256':sha(ROOT/'docs/agent_first/run_024r/integration_001/CLEANUP_BEFORE.json'),
 'exact_roots':old,'all_outside_worktree':True,'Git_candidate_count':0,'release_candidate_count':0,
 'current_OS_query':False,'content_or_lifecycle_changed':False,'recursive_deletion_attempted':False,
 'prior_content_audit':'docs/agent_first/run_024r/final_acceptance_001/RETAINED_TEST_DATA_AUDIT.md'})

tests={};iterations=[]
for p in OUT.glob('*_TEST.xml'):
 for case in ET.parse(p).findall('.//testcase'):
  tests[case.attrib.get('classname','')+'::'+case.attrib['name']]='FAIL' if case.find('failure') is not None or case.find('error') is not None else 'SKIP' if case.find('skipped') is not None else 'PASS'
for p in (OUT/'local_verification').glob('*/RESULT.json'):iterations.append(read(p))
save('TEST_RESULTS.json',{'unique_cases':len(tests),'final':dict(Counter(tests.values())),'cases':tests,'iterations':iterations,
 'first_failure':'Two runner configure errors before collection: pytest default log path NUL was rejected by the local write confinement hook. Corrected by explicit isolated --log-file, not by relaxing the write scope. Both exit_code=3 records retained.',
 'external_processes':0,'Solver_calls':0,'retained_test_roots':len(iterations),
 'not_run':['Full regression requiring excluded historical DAT/diagnostic fixture','Abaqus','GUI background lifetime rerun','remote Git/owner checks'],
 'historical_only':'Final Acceptance 225 and Integration 768 were prior results, not added to this run count.'})

functional=[r for r in rows if r['category']=='INCLUDE' and r['git_effect'] in {'ADD','MODIFY'} and r['path'].startswith(('abqjobpilot/','tests/'))]
docs=[r for r in rows if r['category']=='INCLUDE' and r['git_effect'] in {'ADD','MODIFY'} and r['path'].startswith('docs/')]
groups=[{'id':'1','message':'feat(dev): integrate authorised recovery and compact native cockpit','depends_on':base['head'],'files':functional},
 {'id':'2','message':'docs(dev): record recovery and cockpit acceptance boundaries','depends_on':'1','files':docs}]
save('COMMIT_GROUPS.json',{'status':'DRAFT_BLOCKED_NOT_AUTHORIZATION','groups':groups,
 'hygiene':'TRACKED_EXCLUSION_PROPOSAL.txt is a separate review, not an approved deletion list. Two required fixtures must be replaced first. Index-only exclusion does not purge existing history.'})
for g in groups:(OUT/('GROUP_'+g['id']+'_PATHS.txt')).write_text('\n'.join(x['path'] for x in g['files'])+'\n',encoding='utf-8')
save('CHANGE_ESTIMATE.json',{'tracked_modified':sum(x['git_effect']=='MODIFY' for x in functional+docs),
 'untracked_additions':sum(x['git_effect']=='ADD' for x in functional+docs),'groups':{g['id']:len(g['files']) for g in groups},
 'new_file_lines':sum(len((ROOT/r['path']).read_text(encoding='utf-8-sig').splitlines()) for r in functional+docs if r['git_effect']=='ADD'),
 'existing_tracked_numstat':base['unstaged_numstat'],'tracked_exclusion_proposals':sum(r['tracked'] and r['category']!='INCLUDE' for r in rows),
 'does_not_include_future_fixture_changes_or_this_audit_reports':True})

local=[]
for p in sorted((OUT/'local_verification').rglob('*')):
 if p.is_file():local.append({'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'category':'LOCAL_VERIFICATION_COPY_OR_TEST_OUTPUT_DO_NOT_STAGE'})
save('AUDIT_LOCAL_EXCLUSIONS.json',local)
print(json.dumps({'preserved':len(base['inventory']),'index_unchanged':True,'tests':Counter(tests.values()),'groups':{g['id']:len(g['files']) for g in groups},'own_local_excluded_files':len(local)},ensure_ascii=False))
