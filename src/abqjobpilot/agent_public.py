"""Agent-first public v1 client: authenticated owner; no executor or database writes."""
import argparse,json
from .product_project import open_project
from .service_lifecycle import ServiceLifecycleManager

def call(project,action,key='installed-test-only-v1',run_id=None):
    identity=open_project(project)
    if action=='project':return {'version':'af-public-v1','project':identity}
    client,ctx,health=ServiceLifecycleManager(project).connect()
    if action in {'task','submit','tasks'}:
        return client.call('installed_test_task_v1',{'request':{'version':'af-public-v1','action':action,'project_id':identity['project_id'],'key':key}})
    if action=='runs':return client.project_view()
    if action=='receipt':return client.receipt(key)
    if action=='run':return client.run(run_id)
    if action=='evidence':
        run=client.run(run_id)
        progress={'status':'NOT_APPLICABLE','reason':'FakeBackend has no Solver STA or process progress','records':[]} if run['backend_id']=='fake-v1' else client.progress(run_id)
        return {'version':'af-public-v1','run':run,'validations':client.validations(run_id),'progress':progress,'scope':'simulation' if run.get('simulation') else 'execution'}
    if action=='events':return client.events()
    raise ValueError('Unknown action')

def main():
    p=argparse.ArgumentParser(description='Agent-first public v1; TEST_ONLY task budget: one per Project')
    p.add_argument('action',choices=['project','task','tasks','submit','runs','receipt','run','evidence','events'])
    p.add_argument('--project',required=True);p.add_argument('--key',default='installed-test-only-v1');p.add_argument('--run-id')
    a=p.parse_args();print(json.dumps(call(a.project,a.action,a.key,a.run_id),ensure_ascii=True));return 0
