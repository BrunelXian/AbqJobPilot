"""One fixed A->B acceptance policy, not a user-defined workflow engine."""
import json
from .models import fields,identifier,now,require
from .store import document

POLICY={'contract':'fixed-standard-pair-v1','a_start_after_approval_seconds':600,
        'b_start_after_a_accept_seconds':330,'batch_after_a_accept_seconds':630,
        'observation_seconds_each':300,'total_launch_budget':2}


def check_shape(plan):
    seq=plan.get('standard_sequence')
    fields(seq,(*POLICY,'batch_id','position','predecessor'))
    require(all(type(seq[k]) is type(v) and seq[k]==v for k,v in POLICY.items()) and
            type(seq['batch_id']) is str and seq['batch_id'].startswith('batch_') and seq['position'] in ('A','B'),
            'PLAN_STALE','Fixed sequence policy differs')
    if seq['position']=='A':require(seq['predecessor'] is None,'PLAN_STALE','A has no predecessor')
    else:fields(seq['predecessor'],('plan_id','plan_digest'))


def prepare_pair(service,engineering_a,job_a,engineering_b,job_b,*,expires_at):
    from .standard_contract import prepare
    require(str(engineering_a)!=str(engineering_b),'OUTPUT_CONFLICT','Separate engineering roots required')
    base={**POLICY,'batch_id':identifier('batch')}
    a=prepare(service,engineering_a,job_a,expires_at=expires_at,sequence={**base,'position':'A','predecessor':None}).to_dict()
    b=prepare(service,engineering_b,job_b,expires_at=expires_at,sequence={**base,'position':'B',
        'predecessor':{k:a[k] for k in ('plan_id','plan_digest')}}).to_dict()
    return [a,b]


def issue_pair(service,plan_ids,*,approval_source):
    from .standard_contract import check_plan,_issue
    require(type(approval_source) is str and 1<=len(approval_source)<=128,'GRANT_REQUIRED','Actual explicit approval source required')
    require(type(plan_ids) is list and len(plan_ids)==2,'GRANT_SCOPE_MISMATCH','Exactly A and B required')
    with service.store.transaction('grant_standard_pair') as conn:
        a,b=[document(conn,'plans','plan_id',pid) for pid in plan_ids]
        for plan in (a,b):check_plan(service,plan)
        require(a['standard_sequence']['position']=='A' and b['standard_sequence']['position']=='B' and
                a['standard_sequence']['batch_id']==b['standard_sequence']['batch_id'] and
                b['standard_sequence']['predecessor']=={k:a[k] for k in ('plan_id','plan_digest')} and
                a['engineering']!=b['engineering'] and a['output_key']!=b['output_key'],
                'GRANT_SCOPE_MISMATCH','Exact independent pair required')
        stamp=now();scope={'batch_id':a['standard_sequence']['batch_id'],'registered_at':stamp,
            'plan_ids':plan_ids,'a_start_not_after':stamp+600,'b_absolute_not_after':stamp+930}
        return [_issue(service,conn,p,min(p['expires_at'],stamp+(600 if i==0 else 930)),approval_source,scope)
                for i,p in enumerate((a,b))]


def predecessor(conn,plan):
    seq=plan['standard_sequence'];expected=seq['predecessor']
    prior=document(conn,'plans','plan_id',expected['plan_id'])
    require(prior['plan_digest']==expected['plan_digest'] and prior.get('process_management')==plan['process_management'] and
            prior['standard_sequence']['batch_id']==seq['batch_id'] and prior['standard_sequence']['position']=='A',
            'PREDECESSOR_NOT_QUALIFIED','Predecessor plan does not match this approved pair')
    rows=conn.execute('SELECT body FROM runs WHERE plan_id=?',(prior['plan_id'],)).fetchall()
    require(len(rows)==1,'PREDECESSOR_NOT_QUALIFIED','Exactly one accepted A required')
    return json.loads(rows[0][0])


def check_start(service,conn,plan,grant,run_id=None):
    if 'standard_sequence' not in plan:return
    require(conn.execute('SELECT state FROM dispatch_gate WHERE id=1').fetchone()[0]=='OPEN',
            'DISPATCH_PAUSED','Fixed pair requires the existing dispatch gate to remain OPEN')
    check_shape(plan);seq=plan['standard_sequence'];scope=grant.get('sequence_grant',{})
    fields(scope,('batch_id','registered_at','plan_ids','a_start_not_after','b_absolute_not_after'))
    require(scope['batch_id']==seq['batch_id'] and len(scope['plan_ids'])==2 and
            scope['plan_ids'][0 if seq['position']=='A' else 1]==plan['plan_id'] and
            scope['a_start_not_after']==scope['registered_at']+600 and scope['b_absolute_not_after']==scope['registered_at']+930,
            'REAL_GRANT_REQUIRED','Exact pair grant required')
    if seq['position']=='A':
        require(now()<scope['a_start_not_after'],'START_WINDOW_EXPIRED','A start window elapsed')
        return
    a=predecessor(conn,plan)
    prior_grant=document(conn,'grants','grant_id',a['grant_id'])
    require(prior_grant.get('sequence_grant')==scope and scope['plan_ids'][0]==a['plan_id'],
            'REAL_GRANT_REQUIRED','A and B must belong to the same registered pair')
    require(now()<min(scope['b_absolute_not_after'],a['created_at']+330),'START_WINDOW_EXPIRED','B start window elapsed; no deferred launch')
    require(a.get('managed_completion')=='COMMITTED_EMPTY_SCOPE' and a['execution']=='FINISHED' and
            a['reconciliation']=='NONE' and a.get('launch_state')=='PROCESS_OBJECT_RETURNED' and
            not a.get('administrative_closeout') and a['owner_id']==service.store._session.owner_id and
            a.get('solver_conclusion')=='COMPLETED_TEXT_EVIDENCE' and a.get('numerical_validation')=='PRIMARY_THREE_PASS' and
            a.get('artifact_validation')=='VALID' and a.get('backend_outcome')=='COMPLETED',
            'PREDECESSOR_NOT_QUALIFIED','A needs committed managed completion, Solver and all three DAT checks; administrative release is insufficient')
    from .managed_process import check_completion
    check_completion(a.get('managed_scope'),a)
    require(conn.execute('SELECT run_id FROM slot WHERE id=1').fetchone()[0]!=a['run_id'],
            'PREDECESSOR_NOT_QUALIFIED','A still owns the slot')
    require(conn.execute("SELECT 1 FROM events WHERE run_id=? AND json_extract(body,'$.type')='STANDARD_MANAGED_COMPLETED'",(a['run_id'],)).fetchone() is not None,
            'PREDECESSOR_NOT_QUALIFIED','Normal completion evidence missing')


def batch_deadline(conn,plan,run):
    if plan['standard_sequence']['position']=='A':return run['created_at']+630
    return predecessor(conn,plan)['created_at']+630


def start_deadline(conn,plan,grant):
    scope=grant['sequence_grant']
    if plan['standard_sequence']['position']=='A':return min(grant['expires_at'],scope['a_start_not_after'])
    return min(grant['expires_at'],scope['b_absolute_not_after'],predecessor(conn,plan)['created_at']+330)
