"""One-time offline Plan registration in the user-named, still empty candidate.
No Grant/Run/service. Existing Run021 preparation and material bytes stay intact.
"""
import json
from pathlib import Path
import sys

SOURCE=Path(__file__).resolve().parents[3];sys.path.insert(0,str(SOURCE))
OUT=Path(__file__).resolve().parent
ROOT=Path(r'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run021_42b9754ee29b457d8c86b2e97a26ec4b')


def guard(event,args):
    if event in ('subprocess.Popen','os.system','os.startfile','abqjobpilot.managed_standard_create'):
        raise AssertionError('Preparation cannot create any external execution process')


def save(name,value):
    with (OUT/name).open('x',encoding='utf-8') as f:f.write(json.dumps(value,ensure_ascii=False,indent=2))


def main():
    sys.addaudithook(guard)
    from abqjobpilot.product_project import open_project
    from abqjobpilot.product_standard import prepare_product,inspect_preparation
    from abqjobpilot.service_lifecycle import ServiceLifecycleManager
    from abqjobpilot.execution.models import canonical_json,digest,now,CONTRACT
    from abqjobpilot.execution.standard_contract import StandardConfig,identity,ENTRY,CMD,PYTHON,INPUT_DIGEST
    from abqjobpilot.execution.store import open_existing_read_only
    assert not (OUT/'ACCEPTANCE_MANIFEST.json').exists(),'Never rebuild an existing candidate'
    previous=json.loads((SOURCE/'docs/agent_first/run_021/PREPARATION_MANIFEST.json').read_text())
    assert digest(previous['body'])=='sha256:c5b2ab1edd4d4c3c7d8ccc8803409b02bdde583a60ba8c7d6179fc887334736c'
    project=open_project(ROOT);assert project['project_id']=='p_fa698230f3e6499caf08517e3e82dbc2'
    manager=ServiceLifecycleManager(ROOT)
    def facts():
        with open_existing_read_only(manager.context).read() as conn:
            return {'counts':{t:conn.execute('SELECT COUNT(*) FROM '+t).fetchone()[0]
                for t in ('plans','grants','runs','receipts','consumption','events','management_grants','management_receipts')},
                'gate':dict(conn.execute('SELECT * FROM dispatch_gate').fetchone()),
                'supervisor_started':dict(conn.execute('SELECT * FROM meta'))['supervisor_started']}
    before=facts();assert all(v==0 for v in before['counts'].values())
    assert before['gate']['state']=='PAUSED' and before['supervisor_started']=='0'
    assert manager.inspect()['state']=='NOT_RUNNING'
    source=ROOT/'engineering/axial_bar.inp';assert identity(source)['digest']==INPUT_DIGEST
    original_files={str(p):identity(p) for p in (ROOT/'agent_project.json',Path(manager.context.root)/'experiment.json',
                                               source,manager.private/'lifecycle.json',manager.private/'operator.json')}
    installation=json.loads((SOURCE/'docs/agent_first/run_010/RUNTIME_STATIC_IDENTITIES.json').read_text())
    paths=[v['path'] for v in installation if v['path'] not in (ENTRY,CMD,PYTHON)]
    config=StandardConfig.fixed(paths,managed=True)
    # Only jobs/plans and two new encrypted preparation files are written.
    plan=prepare_product(ROOT,ROOT/'engineering','r021_bar_42b9754e',config,expires_at=now()+30*86400)
    checked=inspect_preparation(ROOT);assert checked['plan']==plan
    after=facts();assert after['counts']['plans']==1 and all(v==0 for k,v in after['counts'].items() if k!='plans')
    assert after['gate']==before['gate'] and after['supervisor_started']=='0' and manager.inspect()['state']=='NOT_RUNNING'
    assert all(identity(p)==v for p,v in original_files.items())
    save('PLAN.json',plan)
    keys={name:'run021-product-'+name+'-42b9754e' for name in ('authorize','submit','dispatch','stop')}
    request={'contract_version':CONTRACT,'operation':'submit','project_id':project['project_id'],
        'project_instance_id':project['project_instance_id'],'job_id':plan['job_id'],'job_revision':1,
        'plan_id':plan['plan_id'],'plan_digest':plan['plan_digest'],'grant_id':None,
        'idempotency_key':keys['submit'],'retry_of':None}
    code=list((SOURCE/'abqjobpilot').rglob('*.py'))+[SOURCE/'run_gui.py',SOURCE/'Open_Dev_GUI.vbs',
        SOURCE/'examples/agent_first/product_standard_acceptance.py',Path(__file__),source,
        ROOT/'agent_project.json',Path(manager.context.root)/'experiment.json',OUT/'PLAN.json']
    materials={str(p):identity(p) for p in code}
    for value in config.value()['materials']:materials[value['path']]=value
    body={'format':'product-standard-single-acceptance-v1',
        'experiment_id':'run021_42b9754ee29b457d8c86b2e97a26ec4b',
        'approval_state':'AWAITING_SEPARATE_REAL_GRANT_AND_ONE_ANALYSIS_AUTHORIZATION',
        'previous_incomplete_body_sha256':previous['body_sha256'],
        'project':project,'root':str(ROOT),'context':manager.context.to_dict(),'plan':plan,
        'entry':ENTRY,'input':identity(source),'cwd':plan['engineering'],'scratch':plan['scratch'],
        'outputs':plan['engineering'],'job':plan['job_name'],'resources':plan['resources'],
        'maximum_analysis_calls':1,'extra_abaqus_calls':0,'grant_seconds':600,'dispatch_seconds':25,
        'operation_keys':keys,'submission_template':request,
        'dispatch_policy':{'global_gate':'PAUSED_AT_ALL_TIMES','acceptance':'exact approved Plan only while PAUSED',
            'start':'exact owner/Run/Grant/revision; 25s from durable explicit dispatch request',
            'consume':'same transaction as START_INTENT and slot claim; no reusable permission',
            'failure':'preserve intent/slot/UNKNOWN; no automatic retry or new key',
            'disconnect':'accepted work continues independently; query original receipt, no resubmit with a new key'},
        'observation':{'upper_bound_seconds':300,'origin':'monotonic CreateProcess return; capped by claim time +300s',
            'expiry':'end observation only, no terminate/retry/delete/background observer'},
        'stop':'explicit idle lifecycle operation only after original committed managed completion and empty slot; never kill',
        'restart':'explicit lifecycle start; PAUSED, consumed Grant/history/receipts preserved; no replay',
        'numerical_checks':previous['body']['numerical_checks'],'odb_content_validation':'NOT_RUN',
        'scope':'root and inheriting CreateProcess descendants in one no-kill Job; external services/full physical set UNKNOWN',
        'host':'existing ServiceLifecycleManager, current-user DPAPI, independent file stdout/stderr; Windows session remains alive',
        'gui':'Open_Dev_GUI.vbs; select this explicit Project, Start Service, select original Run; GUI closure is disconnect only',
        'gui_timing':'If Solver finishes too quickly, mark NOT_OBSERVED; no second analysis',
        'not_verified':['actual Standard compatibility of product host','ODB contents','host-wide resource exclusion',
                        'logoff/reboot/session closure','external service lifecycle'],
        'materials':list(materials.values()),'material_digest_rule':'sha256 raw bytes; excludes mutable DB, credentials and future outputs'}
    value={'body':body,'body_sha256':digest(body).split(':',1)[1],
           'digest_rule':'SHA256 UTF8 canonical_json(body), sorted keys/compact JSON; not whole JSON file bytes'}
    save('ACCEPTANCE_MANIFEST.json',value)
    save('CANDIDATE_CHANGE.json',{'before':before,'after':after,'service':manager.inspect(),
        'original_bound_files_unchanged':True,'changes':['one Job and one Plan transaction','new DPAPI standard-profile.json','new DPAPI standard-operator.json'],
        'not_changed':['Project identity','input','base lifecycle credentials','dispatch gate','authorization','execution history'],
        'abaqus_calls':0,'external_processes_created':0})
    print(canonical_json({'plan_id':plan['plan_id'],'plan_digest':plan['plan_digest'],'body_sha256':value['body_sha256'],
                          'expires_at':plan['expires_at'],'facts':after}))


if __name__=='__main__':main()
