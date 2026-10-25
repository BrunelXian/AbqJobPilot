"""Fixed product acceptance operator example. No automatic approval/dispatch.

check/report are read-only. Other actions are explicit trusted local operator
steps and require separate human authorization; a matching digest is not one.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

SOURCE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(SOURCE))
from abqjobpilot.execution.models import canonical_json,digest,require,ExecutionError,now
from abqjobpilot.service_lifecycle import ServiceLifecycleManager,write_new
from abqjobpilot.product_standard import StandardOperator,inspect_preparation


def verify(path, expected):
    require(path.stat().st_size<=262144,'LIMIT_EXCEEDED','Manifest too large')
    value=json.loads(path.read_text(encoding='utf-8'))
    body=value['body']
    require(value['body_sha256']==expected==digest(body).split(':',1)[1],
            'PLAN_STALE','Actual normalized body differs from the reviewed object')
    require(body['format']=='product-standard-single-acceptance-v1','UNSUPPORTED_FORMAT','Unsupported acceptance manifest')
    for material in body['materials']:
        p=Path(material['path'])
        from abqjobpilot.execution.standard_contract import identity
        actual=identity(p)
        require(actual['digest']==material['digest'] and actual['size']==material['size'],
                'PLAN_STALE','Referenced material changed')
    return body


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--body-sha256',required=True)
    p.add_argument('--action',choices=('check','start','authorize','submit','dispatch','report','stop','restart'),default='check')
    p.add_argument('--subject');p.add_argument('--source')
    args=p.parse_args();body=verify(args.manifest,args.body_sha256)
    manager=ServiceLifecycleManager(body['root']);operator=StandardOperator(body['root'])
    plan=body['plan'];keys=body['operation_keys']
    if args.action=='check':
        prepared=inspect_preparation(body['root'])
        require(prepared['plan']==plan,'PLAN_STALE','Stored Plan differs')
        return {'preparation':prepared,'service':manager.inspect(),'abaqus_calls_this_check':0}
    if args.action in ('start','restart'):return manager.start()
    client,ctx,_=manager.connect()
    require(ctx.project_id==body['project']['project_id'] and ctx.project_instance_id==body['project']['project_instance_id'],
            'PROJECT_IDENTITY_MISMATCH','Selected Project differs')
    if args.action in ('authorize','dispatch'):
        # Durable request arguments make loss/replay retain the ORIGINAL deadline
        # and owner. This is an operation record, not a new approval protocol.
        target=manager._path('acceptance-'+args.action+'.json')
        action='authorize' if args.action=='authorize' else 'dispatch_once'
        key=keys[args.action]
        if target.exists():
            from abqjobpilot.service_discovery import read_document
            request=read_document(target)
            require(request['manifest_digest']==args.body_sha256 and request['operation_key']==key,
                    'IDEMPOTENCY_CONFLICT','Existing operation belongs to another acceptance object')
            if args.action=='authorize':
                require(args.subject==request['arguments']['subject'] and args.source==request['arguments']['source'],
                        'IDEMPOTENCY_CONFLICT','Actual authorization reference differs; do not reset')
        else:
            if args.action=='authorize':
                require(bool(args.subject) and bool(args.source),'REAL_OPERATOR_REQUIRED','Actual separate authorization reference required')
                arguments={'plan_id':plan['plan_id'],'plan_digest':plan['plan_digest'],
                    'expires_at':min(now()+body['grant_seconds'],plan['expires_at']),'subject':args.subject,'source':args.source}
            else:
                receipt=client.receipt(keys['submit']);run=client.run(receipt['run_id'])
                arguments={'run_id':run['run_id'],'revision':run['revision'],'gate_version':client.dispatch_gate()['version'],
                           'start_not_after':now()+body['dispatch_seconds']}
            request={'manifest_digest':args.body_sha256,'owner_id':client.endpoint['owner_id'],
                     'operation_key':key,'arguments':arguments}
            write_new(target,request)
        return operator.request(action,request['arguments'],operation_key=key,owner_id=request['owner_id'])
    if args.action=='submit':
        grant=client.management_receipt('product_standard_authorize',keys['authorize'])
        request={**body['submission_template'],'grant_id':grant['grant_id']}
        return client.submit(request)
    if args.action=='stop':return manager.stop(owner_id=client.endpoint['owner_id'],operation_key=keys['stop'])
    receipt=client.receipt(keys['submit']);rid=receipt['run_id']
    return {'receipt':receipt,'run':client.run(rid),'gate':client.dispatch_gate(),'diagnostic':client.diagnose(rid)}


if __name__=='__main__':
    try:print(canonical_json(main()))
    except ExecutionError as exc:
        print(canonical_json({'error':exc.code,'state':'STOP_AND_INSPECT_ORIGINAL_KEY_NO_NEW_ATTEMPT'}));sys.exit(2)
