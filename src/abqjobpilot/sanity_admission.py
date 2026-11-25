"""One sealed admission in one fresh Agent-first project. No grants or Run database here."""
import base64
import re
from pathlib import Path

from .application_runtime import validate_runtime
from .execution.models import digest, fields, identifier, now, require, integer
from .execution.paths import confined, local_path, no_reparse
from .execution.sanity_model import BASELINE, PROFILE, SELECTOR, candidate, file_bytes, force, sha
from .execution.standard_contract import CMD, RESOURCES, StandardConfig, identity, management_binding, HOST_POLICY
from .local_credentials import private_value, read_private
from .product_project import open_project
from .service_lifecycle import ServiceLifecycleManager, write_new

BACKEND = 'abaqus-standard-t3d2-sanity-v1'
FORMAT = 'trusted-t3d2-admission-v1'


def token(value):
    require(isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,96}', value), 'INVALID_IDENTIFIER','Bounded identity required')
    return value


def runtime(entry, materials):
    validate_runtime()
    from .application_runtime import is_frozen_runtime, owner_executable
    python = str(owner_executable() if is_frozen_runtime() else validate_runtime())
    path = local_path(entry)
    require(path.suffix.lower() == '.bat' and not any(c in str(path) for c in '"%!&|<>^\r\n'),
            'INVALID_RUNTIME','Qualified local Abaqus command file required')
    require(isinstance(materials,list) and 1 <= len(materials) <= 24, 'INVALID_RUNTIME','Explicit reviewed installation files required')
    paths = [str(path), CMD, python, *materials]
    require(len(set(map(str.casefold, paths))) == len(paths), 'INVALID_RUNTIME','Duplicate installation identity')
    return {'backend_id':BACKEND,'backend_version':1,'entry':str(path),'cmd':CMD,'interpreter':python,
            'host_policy':HOST_POLICY,'materials':[identity(p) for p in paths],'process_management':management_binding()}


def review_scope(release):
    return {'profile':PROFILE,'baseline_sha256':BASELINE,'units':'N/mm/MPa','analysis':'Standard/static',
              'material':'ELASTICBAR E=1000 MPa nu=0.3','section_area_mm2':'1','length_mm':'10',
              'boundary':'node1 U1-U3=0; node2 U1,U3=0','load':'node2 DOF2=-F N',
              'dependencies':[],'selector':SELECTOR,'release':release}


def admit(manager, spec):
    """Existing TEST_ONLY operator entry."""
    return _admit(manager, spec)


def prepare_hil(project, *, research_project, request_key, review_file, expires_at, external=False):
    """Stage one exact Plan for human review. No Owner start, Grant or permit."""
    from .application_runtime import is_frozen_runtime
    from .execution import sanity_hil
    from .execution.standard_contract import ENTRY

    require(not is_frozen_runtime(), 'FROZEN_REAL_BACKEND_DISABLED', 'HIL preparation is source-only')
    token(request_key)
    manager = ServiceLifecycleManager(project)
    require(Path(manager.context.test_root).drive.casefold() == 'd:',
            'OUTPUT_SCOPE_VIOLATION', 'This HIL profile requires an isolated D: Project')
    version = sanity_hil.external_version(manager.context.test_root) if external else sanity_hil.VERSION
    sanity_hil.check_request_key(version, request_key, project=manager.context.test_root)
    baseline = Path(__file__).resolve().parents[1] / 'docs/sanity/baseline.inp'
    a = _admit(manager, {
        'research_project': research_project, 'baseline': str(baseline), 'review_file': review_file,
        'release': '2024', 'entry': ENTRY, 'materials': sanity_hil.material_paths(version),
        'lower_N': '1', 'upper_N': '1', 'expires_at': expires_at, 'launch_budget': 1, 'mode': 'REAL',
    }, hil=sanity_hil.profile(version))
    raw = file_bytes(baseline, 8192)
    plan = _prepare(manager.context, {
        'admission_id': a['admission_id'], 'research_project': research_project,
        'request_key': request_key, 'F_N': '1', 'unit': 'N',
        'inp_base64': base64.b64encode(raw).decode('ascii'), 'sha256': sha(raw),
    }, hil=True)
    return sanity_hil.packet(plan)


def _admit(manager, spec, *, hil=None):
    from .application_runtime import is_frozen_runtime
    if is_frozen_runtime():
        from .application_runtime import owner_executable
        owner_executable()  # verified installed manifest and Owner role identity
    manager._operator()
    ctx = manager.context
    open_project(ctx.test_root)
    fields(spec, ('research_project','baseline','review_file','release','entry','materials','lower_N','upper_N',
                  'expires_at','launch_budget','mode'))
    token(spec['research_project'])
    token(spec['release'])
    require(spec['mode'] in ('TEST_ONLY','REAL') and type(spec['launch_budget']) is int and spec['launch_budget'] in (0,1),
            'INVALID_BUDGET','At most one candidate/attempt for this admission')
    require(spec['mode'] == ('REAL' if hil else 'TEST_ONLY'),
            'REAL_SANITY_DISABLED', 'Only dedicated HIL preparation can stage a REAL candidate')
    integer(spec['expires_at'])
    require(now() < spec['expires_at'] <= now()+86400 and force(spec['lower_N']) <= force(spec['upper_N']),
            'INVALID_ADMISSION','Invalid expiry or load range')
    require(sha(file_bytes(spec['baseline'],8192)) == BASELINE, 'MODEL_CONTRACT_MISMATCH','Frozen baseline differs')
    import json
    review_raw=file_bytes(spec['review_file'],65536)
    reviewed=json.loads(review_raw)
    expected=review_scope(spec['release'])
    fields(reviewed, (*expected,'reviewer','runtime_files'))
    require(all(reviewed[k]==v for k,v in expected.items()),'MODEL_REVIEW_MISMATCH','Independent engineering review differs')
    token(reviewed['reviewer'])
    review=sha(review_raw)
    config = runtime(spec['entry'],spec['materials'])
    require(reviewed['runtime_files']==config['materials'],'RUNTIME_REVIEW_MISMATCH','Reviewed installation pins differ')
    root = confined(ctx.test_root, Path(ctx.test_root)/'sanity-output')
    require(not root.exists() and not manager._path('standard-profile.json').exists(), 'OUTPUT_CONFLICT','Fresh project scope required')
    value = {'format':FORMAT,'admission_id':identifier('adm'),'profile':PROFILE,'baseline_sha256':BASELINE,
             'review_sha256':review,'project_id':ctx.project_id,'project_instance_id':ctx.project_instance_id,
             'context_digest':ctx.context_digest,'output':str(root),'selector':dict(SELECTOR),'resources':dict(RESOURCES),
             'runtime':config, **{k:spec[k] for k in ('research_project','release','lower_N','upper_N','expires_at','launch_budget','mode')}}
    if hil:
        value['hil'] = hil
    write_new(manager._path('sanity-admission.json'),private_value(ctx,value))
    return value


def admission(ctx):
    manager = ServiceLifecycleManager(ctx.test_root)
    path = manager._path('sanity-admission.json')
    require(path.is_file(), 'ADMISSION_REQUIRED','Trusted operator admission required')
    a = read_private(ctx,path)
    require(a['format']==FORMAT and a['context_digest']==ctx.context_digest and a['project_id']==ctx.project_id
            and a['project_instance_id']==ctx.project_instance_id and a['profile']==PROFILE and a['baseline_sha256']==BASELINE,
            'PROJECT_IDENTITY_MISMATCH','Sealed admission differs')
    return a


def binding(a, key, f, raw):
    value = {'admission_id':a['admission_id'],'admission_digest':digest(a),'project_id':a['project_id'],
            'research_project':a['research_project'],'request_key':token(key),'F_N':f,
            'candidate_sha256':candidate(raw,f,a['lower_N'],a['upper_N']),'launch_budget':a['launch_budget'],
            'mode':a['mode'],'selector':dict(SELECTOR),'output':a['output']}
    if 'hil' in a:
        value['hil'] = a['hil']
    return value


def validate(ctx, plan, *, live=True):
    a = admission(ctx)
    s = plan['sanity']
    from .execution import sanity_hil
    path = confined(ctx.test_root, Path(a['output'])/'axial_bar.inp', exists=True)
    raw = file_bytes(path, 8192)
    require(binding(a,s['request_key'],s['F_N'],raw)==s and plan['engineering']==a['output']
            and plan['runtime_binding']==a['runtime'] and plan['expires_at']==a['expires_at']
            and plan['input_manifest'][0]['digest']=='sha256:'+s['candidate_sha256'],
            'GRANT_SCOPE_MISMATCH','Final candidate, admission, runtime or output changed')
    if sanity_hil.external(plan):
        require(plan['input_manifest'] == [sanity_hil.input_identity(path)],
                'PLAN_STALE', 'Original HIL input file identity changed')
    if live:
        require(a['expires_at']>now(),'PLAN_EXPIRED','Admission expired')
    return a


def prepare(ctx, req):
    return _prepare(ctx, req)


def _prepare(ctx, req, *, hil=False):
    from . import product_standard
    from .execution.models import canonical_json
    a = admission(ctx)
    require(a['mode'] == ('REAL' if hil else 'TEST_ONLY') and ('hil' in a) == hil,
            'REAL_SANITY_DISABLED', 'Public Sanity preparation is TEST_ONLY')
    fields(req,('admission_id','research_project','request_key','F_N','unit','inp_base64','sha256'))
    require(req['admission_id']==a['admission_id'] and req['research_project']==a['research_project'],
            'PROJECT_IDENTITY_MISMATCH','Project or admission differs')
    require(a['expires_at']>now() and req['unit']=='N','CANDIDATE_SCOPE_MISMATCH','Expired scope or wrong units')
    require(isinstance(req['inp_base64'],str) and len(req['inp_base64'])<=12000,'INVALID_INPUT','Bounded INP required')
    raw=base64.b64decode(req['inp_base64'],validate=True)
    s=binding(a,req['request_key'],req['F_N'],raw)
    require(s['candidate_sha256']==req['sha256'],'INPUT_DIGEST_MISMATCH','Submitted digest differs')
    m=ServiceLifecycleManager(ctx.test_root)
    if m._path('standard-profile.json').exists():
        plan=recorded_plan(m)
        require(plan.get('sanity')==s,'IDEMPOTENCY_CONFLICT','Dedicated admission already has another candidate')
        validate(ctx,plan)
        return plan
    root=confined(ctx.test_root,a['output'])
    root.mkdir(exist_ok=True)
    scratch=confined(ctx.test_root,root/'scratch')
    scratch.mkdir(exist_ok=True)
    path=confined(ctx.test_root,root/'axial_bar.inp')
    try:
        with path.open('xb') as out:
            out.write(raw)
    except FileExistsError:
        require(file_bytes(path,8192)==raw,'IDEMPOTENCY_CONFLICT','Staged bytes differ')
    require(set(root.iterdir())=={scratch,path},'OUTPUT_CONFLICT','Unexpected output files')
    return product_standard.prepare_product(ctx.test_root,root,'sanity_'+sha(raw)[:8],
        StandardConfig(canonical_json(a['runtime'])),expires_at=a['expires_at'],sanity=s)


def recorded_plan(manager):
    from .execution.store import open_existing_read_only, document
    path=manager._path('standard-profile.json')
    require(path.is_file(),'PLAN_NOT_PREPARED','No committed Operator Plan')
    ext=read_private(manager.context,path)
    require(ext['context_digest']==manager.context.context_digest,'PROJECT_IDENTITY_MISMATCH','Profile belongs to another project')
    with open_existing_read_only(manager.context).read() as conn:
        plan=document(conn,'plans','plan_id',ext['binding']['plan_id'])
    require(plan['backend_id']==BACKEND and digest({k:v for k,v in plan.items() if k!='plan_digest'})==
            plan['plan_digest']==ext['binding']['plan_digest'],'PLAN_STALE','Recorded Plan differs')
    return plan

