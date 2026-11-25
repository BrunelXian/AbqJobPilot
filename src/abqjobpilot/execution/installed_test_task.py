"""Bounded installed TEST_ONLY task operation on the existing owner/store."""
import json
from pathlib import Path
from .models import *
from .store import gate_view
from .authorization import check_grant, check_management_grant

def invoke(service, request):
    from ..application_runtime import is_test_only_build, executable_role
    from ..product_project import validate_product
    fields(request, ('version','action','project_id','key'))
    require(request['version']=='af-public-v1' and request['project_id']==service.context.project_id,
            'PROJECT_IDENTITY_MISMATCH','Explicit public contract and Project required')
    require(request['action'] in {'task','submit','tasks'},'INVALID_REQUEST','Unsupported fixed action')
    text(request['key'])
    validate_product(service.context)
    require(is_test_only_build() and executable_role()=='owner' and service._standard_backend is None
            and service._process_backend is None and service.product_control is None,
            'CAPABILITY_UNAVAILABLE','Only installed TEST_ONLY Fake Owner is eligible')
    ctx=service.context
    with service.store.read() as c:
        plans=[json.loads(r[0]) for r in c.execute('SELECT body FROM plans')]
    if request['action']=='tasks': return {'version':'af-public-v1','tasks':[p['job_spec'] for p in plans]}
    require(len(plans)<=1 and all(p['backend_id']=='fake-v1' and p['job_spec']['metadata']=={'purpose':'installed-test-only-v1','key':request['key']} for p in plans),
            'TEST_SCOPE_EXHAUSTED','One fixed TEST_ONLY task per Project; original key required')
    if not plans:
        require(request['action']=='task','NOT_FOUND','Create the fixed TEST_ONLY task first')
        inp=Path(ctx.root)/'installed-test-only.txt'
        content=b'AbqJobPilot installed TEST_ONLY simulation; no Solver\n'
        if inp.exists(): require(inp.read_bytes()==content,'INPUT_CHANGED','Unexpected fixture content')
        else:
            with inp.open('xb') as f: f.write(content)
        spec=JobSpec.from_dict({'job_id':identifier('job'),'revision':1,'project_id':ctx.project_id,
           'project_instance_id':ctx.project_instance_id,'input_refs':[str(inp)],'resources':dict(RESOURCES),
           'metadata':{'purpose':'installed-test-only-v1','key':request['key']}})
        plan=service.prepare(ctx,spec,ConfigSnapshot.from_dict({'config_revision':1,'values':{'label':'installed-test-only-v1'}}),expires_at=now()+86400).to_dict()
    else: plan=plans[0]
    if request['action']=='task': return {'version':'af-public-v1','scope':'TEST_ONLY','task':plan['job_spec'],'plan_id':plan['plan_id']}
    # Query before any authority issuance: a lost response never starts a second Run.
    try:
        receipt=service.store.query_receipt(ctx,service.client_namespace,request['key'])
        return {'receipt':receipt,'replayed':True}
    except ExecutionError as exc:
        if exc.code!='NOT_FOUND': raise
    session=service.store._session
    with service.store.transaction('installed_test_only_grant') as c:
        require(c.execute('SELECT COUNT(*) FROM runs').fetchone()[0]==0,'TEST_SCOPE_EXHAUSTED','Budget is one simulated Run')
        grants=[json.loads(r[0]) for r in c.execute('SELECT body FROM grants')]
        require(len(grants)<=1,'TEST_SCOPE_EXHAUSTED','Unexpected grants')
        grant=grants[0] if grants else {'grant_id':identifier('grant'),'issuer':'FakeGrantFixture','grant_kind':'TEST_ONLY',
           'authority_instance':session.authority_instance,'project_instance_id':ctx.project_instance_id,
           'plan_id':plan['plan_id'],'plan_digest':plan['plan_digest'],'job_id':plan['job_id'],'job_revision':1,
           'allowed_action':'emit_fixture_result','resource_limits':dict(RESOURCES),'output_scope':ctx.runtime_root,
           'expires_at':now()+300,'max_runs':1}
        check_grant(ctx,plan,grant,session.authority_instance,None)
        if not grants:c.execute('INSERT INTO grants VALUES(?,?,?)',(grant['grant_id'],plan['plan_id'],canonical_json(grant)))
        gate=gate_view(c)
        mg=None
        if gate['state']=='PAUSED':
            scope={'expected_gate_version':gate['version']}
            mg={'grant_id':identifier('mg'),'issuer':'FakeManagementFixture','grant_kind':'TEST_ONLY_MANAGEMENT',
                'authority_instance':session.authority_instance,'project_instance_id':ctx.project_instance_id,
                'context_digest':ctx.context_digest,'owner_id':session.owner_id,'action':'resume_dispatch',
                'scope':scope,'expires_at':now()+120,'max_uses':1}
            check_management_grant(ctx,mg,session.authority_instance,session.owner_id,'resume_dispatch',scope,False)
            c.execute('INSERT INTO management_grants VALUES(?,?)',(mg['grant_id'],canonical_json(mg)))
    if mg:
        service.resume_dispatch(ctx,{'contract_version':'af-management-v1','operation':'resume_dispatch',
            'project_id':ctx.project_id,'project_instance_id':ctx.project_instance_id,'owner_id':session.owner_id,
            'management_grant_id':mg['grant_id'],'idempotency_key':identifier('resume'),**mg['scope']})
    return service.submit(ctx,{'contract_version':CONTRACT,'operation':'submit','project_id':ctx.project_id,
        'project_instance_id':ctx.project_instance_id,'job_id':plan['job_id'],'job_revision':1,'plan_id':plan['plan_id'],
        'plan_digest':plan['plan_digest'],'grant_id':grant['grant_id'],'idempotency_key':request['key'],'retry_of':None})
