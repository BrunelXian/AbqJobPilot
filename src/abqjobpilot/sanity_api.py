"""Sanity JSON 1.0. Local public facade onto native Plan, Grant, Receipt and Run."""
import json
from pathlib import Path

from .execution.models import CONTRACT, ExecutionError, fields, require
from .execution.paths import confined
from .execution.sanity_simulation import ACTION as SIMULATE
from .execution.sanity_model import SELECTOR, file_bytes, MODEL_TITLE
from .execution.standard_text import PARSER, bound_terminal_text, displacement, completion
from .execution.store import open_existing_read_only
from .local_credentials import read_private
from .sanity_admission import BACKEND, admission, prepare, recorded_plan, validate
from .service_lifecycle import ServiceLifecycleManager
from .build_metadata import current_build_metadata

VERSION='sanity-execution/1.0'
OPERATIONS=('capabilities','admission','prepare','inspect','grant','submit','dispatch','execution','evidence','verdict',
            'extraction_verdict')


def identify(manager, args):
    p=recorded_plan(manager)
    s=p['sanity']
    require(all(args[k]==v for k,v in {'research_project':s['research_project'],
            'admission_id':s['admission_id'],'plan_id':p['plan_id'],'plan_digest':p['plan_digest'],
            'request_key':s['request_key']}.items()),'GRANT_SCOPE_MISMATCH','Exact project, admission, plan and request required')
    return p


IDENTITY=('research_project','admission_id','plan_id','plan_digest','request_key')


def native_request(ctx,p,grant_id):
    return {'contract_version':CONTRACT,'operation':'submit','project_id':ctx.project_id,
            'project_instance_id':ctx.project_instance_id,'job_id':p['job_id'],'job_revision':p['job_revision'],
            'plan_id':p['plan_id'],'plan_digest':p['plan_digest'],'grant_id':grant_id,
            'idempotency_key':p['sanity']['request_key'],'retry_of':None}


def owner_control(service, action, args):
    require(action in ('grant','dispatch') and service.product_control is not None,'ADMISSION_REQUIRED','Prepared owner required')
    fields(args, IDENTITY+(('expires_at',) if action=='grant' else ('run_id','revision','gate_version','start_not_after')))
    m=ServiceLifecycleManager(service.context.test_root)
    p=identify(m,args)
    s=p['sanity']
    require(s['mode']=='TEST_ONLY', 'REAL_SANITY_DISABLED', 'REAL Sanity control is disabled')
    secret=read_private(service.context,m._path('standard-operator.json'))
    if action=='grant':
        native='authorize'
        arguments={'plan_id':p['plan_id'],'plan_digest':p['plan_digest'],'expires_at':args['expires_at'],
                   'subject':s['research_project'],'source':s['admission_digest']}
        suffix='.grant'
    else:
        native=SIMULATE
        arguments={k:args[k] for k in ('run_id','revision','gate_version','start_not_after')}
        suffix='.simulate'
    return service.product_control.invoke(service,{'action':native,'arguments':arguments,
        'operation_key':s['request_key']+suffix,'owner_id':service.store._session.owner_id,
        'operator_token':secret['operator_token']})


def execution(m,p):
    ctx=m.context
    store=open_existing_read_only(ctx)
    receipt=store.query_receipt(ctx,'product-client',p['sanity']['request_key'])
    run=store.query_run(ctx,receipt['run_id'])
    require(run['plan_id']==p['plan_id'] and run['plan_digest']==p['plan_digest'] and run['project_instance_id']==ctx.project_instance_id
            and run['project_id']==ctx.project_id and receipt['job_id']==p['job_id'] and run['backend_id']==BACKEND,
            'EVIDENCE_IDENTITY_MISMATCH','Receipt or Run differs')
    return receipt,run


def evidence(m,p,args):
    receipt,r=execution(m,p)
    require(r['run_id']==args['run_id'] and r['phase_attempt_id']==args['attempt_id'],
            'EVIDENCE_IDENTITY_MISMATCH','Wrong Run or attempt')
    require(r['backend_outcome']=='COMPLETED' and r['execution']=='FINISHED' and r['reconciliation']=='NONE' and
            r['launch_state']=='PROCESS_OBJECT_RETURNED' and r['managed_completion']=='COMMITTED_EMPTY_SCOPE' and
            r['solver_conclusion']=='COMPLETED_TEXT_EVIDENCE' and r['simulation'] is False,
            'EVIDENCE_INSUFFICIENT','Native terminal process, scope and Solver records required')
    ctx=m.context
    validate(ctx,p,live=False)
    s=p['sanity']
    require(s['mode']=='REAL','EVIDENCE_INSUFFICIENT','Test signature carries no Solver evidence')
    store=open_existing_read_only(ctx)
    observations=store.observations(ctx,r['run_id'])
    validations=store.validations(ctx,r['run_id'])
    require(len(observations)==len(validations)==1,'EVIDENCE_INSUFFICIENT','Exactly one observation and validation required')
    o,v=observations[0],validations[0]
    require(o['phase_attempt_id']==v['phase_attempt_id']==r['phase_attempt_id'] and
            v['evidence_refs']==[o['observation_id']] and v['verdict']=='PASS' and
            v['policy_id']==p['validation_policy'] and v['details']['observed_exit_success'] is True,
            'EVIDENCE_IDENTITY_MISMATCH','Native observation or validation differs')
    root=Path(p['engineering'])
    intent=json.loads(file_bytes(confined(ctx.test_root,root/('.'+p['job_name']+'.intent.json')),8192))
    require(intent==r['launch_intent'] and all(intent[k]==r[k] for k in
            ('phase_attempt_id','owner_id','run_id','plan_digest','project_instance_id')) and intent['output_key']==p['output_key'],
            'EVIDENCE_IDENTITY_MISMATCH','Durable launch intent differs')
    raw=bound_terminal_text(ctx,p,o,intent)
    result=displacement(raw['dat'],SELECTOR,terminal=True,model_title=MODEL_TITLE)
    require(result==v['details']['measurement'] and completion(raw['dat'],raw['sta'],raw['msg']),
            'EVIDENCE_CHANGED','Recomputed evidence differs')
    return {**{k:s[k] for k in ('research_project','admission_id','request_key','candidate_sha256','output')},
            'project_id':ctx.project_id,'project_instance_id':ctx.project_instance_id,'plan_id':p['plan_id'],
            'plan_digest':p['plan_digest'],'receipt_id':receipt['request_id'],'grant_id':r['grant_id'],
            'run_id':r['run_id'],'attempt_id':r['phase_attempt_id'],'attempt_no':r['attempt_no'],
            'solver_terminal':r['solver_conclusion'],'identity':'VERIFIED_FOR_CURRENT_RUN',
            'measurement':result,'dat_path':str(root/(p['job_name']+'.dat')),'goal_decision':'GD_CAE_OWNED'}


def _call(project, op, args):
    from .application_runtime import is_frozen_runtime
    frozen=is_frozen_runtime()
    if op=='capabilities':
        fields(args,())
        build=current_build_metadata()
        return {'contract':VERSION,'classic_surface':'1.0','backend':BACKEND,'operations':list(OPERATIONS),
                'product_version':build['version'],'candidate':build['candidate'],
                'frozen_standard_execution':'NOT_QUALIFIED' if frozen else 'SOURCE_CONTRACT_ONLY',
                'blocked_operations':['prepare','grant','submit','dispatch'] if frozen else [],
                'parallel_slots':1,'parser':PARSER,'odb':'NOT_IMPLEMENTED','authority':'native Agent-first service'}
    require(op in OPERATIONS,'INVALID_REQUEST','Unknown Sanity operation')
    if frozen and op in ('prepare','grant','submit','dispatch'):
        # No default execution capability; a protected exact admission must preexist.
        try:
            admission(ServiceLifecycleManager(project).context)
        except (ExecutionError,OSError,TypeError):
            require(False,'FROZEN_REAL_BACKEND_DISABLED','Trusted exact Sanity admission required')
    m=ServiceLifecycleManager(project)
    if op=='admission':
        fields(args,())
        return admission(m.context)
    if op=='prepare':
        return prepare(m.context,args)
    if op=='inspect':
        fields(args,IDENTITY)
        plan=identify(m,args)
        validate(m.context,plan,live=False)
        return plan
    extra={'submit':('grant_id',),'execution':(),'evidence':('run_id','attempt_id'),'verdict':('run_id','attempt_id'),
           'extraction_verdict':('run_id','attempt_id','receipt_id','operation_id'),
           'grant':('expires_at',),
           'dispatch':('run_id','revision','gate_version','start_not_after')}[op]
    fields(args,IDENTITY+extra)
    p=identify(m,args)
    if op=='execution':
        try:
            receipt,run=execution(m,p)
        except ExecutionError as exc:
            if exc.code!='NOT_FOUND':
                raise
            return {'acceptance':'ACCEPTANCE_UNKNOWN','request_key':args['request_key'],
                    'receipt':None,'run':None,'recovery':'QUERY_ORIGINAL_KEY'}
        return {'acceptance':'ACCEPTED','receipt':receipt,'run':run,'gate':open_existing_read_only(m.context).gate(),
                'consumed':1,'remaining':0,'scope':'one_native_submission_per_admission'}
    if op=='evidence':
        return evidence(m,p,args)
    if op=='verdict':
        from .execution.sanity_verdict import read_verdict
        receipt, run=execution(m,p)
        require(run['run_id']==args['run_id'] and run['phase_attempt_id']==args['attempt_id'],
                'EVIDENCE_IDENTITY_MISMATCH','Wrong Run or attempt')
        return read_verdict(m.context,p,receipt,run)
    if op=='extraction_verdict':
        from .execution.odb_verdict import read_verdict
        receipt, run=execution(m,p)
        require(run['run_id']==args['run_id'] and run['phase_attempt_id']==args['attempt_id']
                and receipt['request_id']==args['receipt_id'],
                'EVIDENCE_IDENTITY_MISMATCH','Wrong Run, Attempt or accepting Receipt')
        return read_verdict(m.context,p,receipt,run,args['operation_id'])
    require(p['sanity']['mode']=='TEST_ONLY', 'REAL_SANITY_DISABLED', 'REAL Sanity control is disabled')
    client,_,_=m.connect()
    if op=='submit':
        return client.submit(native_request(m.context,p,args['grant_id']))
    return client.call('sanity_control_v1',{'action':op,'args':args})


def call(project, op, args):
    """Allow an active native transaction to end. Never repair a sidecar or replay a write."""
    import time
    from .execution.models import ExecutionError
    if op not in ('execution','inspect','evidence','verdict','extraction_verdict'):
        return _call(project,op,args)
    delays=(0.035,0.1,0.25)
    for attempt in range(len(delays)+1):
        try:
            return _call(project,op,args)
        except ExecutionError as exc:
            if exc.code not in ('STORE_REQUIRES_MAINTENANCE','STORE_UNAVAILABLE') or attempt==len(delays):
                raise
            time.sleep(delays[attempt])
