"""Local human-only provisioning console. No general grant or process entry point."""
import json
import sys
from pathlib import Path
from abqjobpilot.execution.models import require, now
from abqjobpilot.execution.sanity_model import file_bytes, BASELINE, SELECTOR
from abqjobpilot.execution.standard_contract import RESOURCES
from abqjobpilot.product_project import create_project
from abqjobpilot.sanity_admission import admit, runtime, review_scope
from abqjobpilot.service_lifecycle import ServiceLifecycleManager

def main():
    op,root=sys.argv[1:3]
    if op in ('test-review','test-admit','test-start','test-stop'):
        from abqjobpilot.application_runtime import is_test_only_build
        require(is_test_only_build(),'CAPABILITY_UNAVAILABLE','Installed TEST_ONLY build required')
        m=ServiceLifecycleManager(root)
        if op in ('test-review','test-admit'):
            spec=json.loads(file_bytes(Path(sys.argv[3]),65536))
            require(spec['mode']=='TEST_ONLY','REAL_OPERATOR_REQUIRED','Test adapter cannot admit REAL')
            if op=='test-review':return {**review_scope(spec['release']), 'reviewer':'INSTALL_TEST_ONLY', 'runtime_files':runtime(spec['entry'],spec['materials'])['materials']}
            return admit(m,spec)
        if op=='test-start':return m.start()
        client,_,_=m.connect()
        return m.stop(owner_id=client.endpoint['owner_id'],operation_key='sanity-stop-'+client.endpoint['owner_id'])
    require(sys.stdin.isatty() and sys.stdout.isatty(),'OPERATOR_REQUIRED','Interactive local terminal required')
    if op=='create' and len(sys.argv)==3:
        return create_project(root,'Trusted T3D2 Sanity')
    m=ServiceLifecycleManager(root)
    if op=='review' and len(sys.argv)==4:
        spec=json.loads(file_bytes(Path(sys.argv[3]),65536))
        return {**review_scope(spec['release']), 'reviewer':'', 'runtime_files':runtime(spec['entry'],spec['materials'])['materials']}
    if op=='admit' and len(sys.argv)==4:
        spec=json.loads(file_bytes(Path(sys.argv[3]),65536))
        print(json.dumps({'project':root,'scope':spec,'baseline_sha256':BASELINE,'measurement':SELECTOR,
                          'resources':RESOURCES,'output':str(Path(root)/'sanity-output')},indent=2))
        expected=spec['mode']+' '+m.context.project_instance_id
        require(input('Review the model, signed load, license and output scope. Type '+expected+' to admit: ')==expected,
                'OPERATOR_REQUIRED','Admission declined')
        return admit(m,spec)
    if op=='start' and len(sys.argv)==3:
        return m.start()
    if op=='stop' and len(sys.argv)==3:
        client,_,_=m.connect()
        return m.stop(owner_id=client.endpoint['owner_id'],operation_key='sanity-stop-'+str(now()))
    raise ValueError('create | admit <scope.json> | start | stop')

if __name__=='__main__':
    try:
        print(json.dumps(main(),ensure_ascii=True))
    except Exception as exc:
        print(getattr(exc,'code','OPERATOR_ERROR'),str(exc),file=sys.stderr)
        sys.exit(1)

