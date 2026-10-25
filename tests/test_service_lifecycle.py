"""Product launcher and exact idle stop. Windows, new isolated stores only."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
import time

import pytest

from abqjobpilot.service_lifecycle import ServiceLifecycleManager, configure_lifecycle
from abqjobpilot.execution.models import ExecutionError, canonical_json
from abqjobpilot.execution.store import acquire_initial_preparation_store
from abqjobpilot.execution.service import ExecutionService
from abqjobpilot.execution.process_handles import ProcessReference
from supervisor_helpers import ProcessHarness, read_json, wait_until


def telemetry(path):
    try:return read_json(path)
    except (FileNotFoundError,PermissionError):return {} # GUI atomic file replacement only


@contextmanager
def prepared(root,scenarios=None):
    h=ProcessHarness(root,process_scenarios=scenarios,managed_scope=True)
    authority=read_json(h.bootstrap)['authority_instance']
    store=acquire_initial_preparation_store(h.context,authority)
    try:
        service=ExecutionService(h.context,store,client_namespace='stable-test-client',process_config=h.process_config)
        configure_lifecycle(service,process_config=h.process_config)
    finally:store.close()
    manager=ServiceLifecycleManager(h.context.root)
    try:yield h,manager
    finally:
        # Only the owner and worker created for this private test instance.
        # Fixed workers self-exit; release only this harness's own barriers.
        for release in Path(h.context.runtime_root).glob('process_runs/*/fixture.json'):
            (release.parent/'release.json').write_text('{}')
        try:
            client,ctx,health=manager.connect()
            ref=ProcessReference(health['process']['pid'],health['process'])
            try:
                deadline=time.monotonic()+65
                while time.monotonic()<deadline:
                    try:manager.stop(owner_id=client.endpoint['owner_id'],operation_key='cleanup');break
                    except ExecutionError as exc:
                        if exc.code in {'COMMUNICATION_UNKNOWN','PROCESS_IDENTITY_UNKNOWN','OWNER_NOT_RUNNING'}:break
                        time.sleep(.05)
                wait_until(lambda:ref.exit_evidence(),timeout=10)
            finally:ref.close()
        except ExecutionError:pass
        # Delete only credentials created by this test, after own service exit.
        removed=[]
        for name in ('lifecycle.json','operator.json','connection.json'):
            path=manager._path(name)
            if path.exists():path.unlink();removed.append(name)
        (root/'product_cleanup.json').write_text(canonical_json({'private_files_removed':removed,'abaqus_calls':0}))
        h.close()


def test_idle_start_reuse_stop_restart_and_permission(tmp_path):
    with prepared(tmp_path) as (h,m):
        assert m.inspect()['state']=='NOT_RUNNING'
        result=m.start();assert result['state']=='CONNECTED'
        client,_,health=m.connect();identity=health['process']
        ref=ProcessReference(identity['pid'],identity)
        try:
            assert m.start()['owner_id']==result['owner_id']
            assert m.disconnect()['state']=='DISCONNECTED' and ref.exit_evidence() is None
            with pytest.raises(ExecutionError) as rejected:
                client.stop_service(result['owner_id'],'denied',client._credential)
            assert rejected.value.code=='LIFECYCLE_PERMISSION_REQUIRED'
            receipt=m.stop(owner_id=result['owner_id'],operation_key='stop-once')['receipt']
            wait_until(lambda:ref.exit_evidence())
            wait_until(lambda:m.inspect()['state']=='NOT_RUNNING')
            assert m.stop(owner_id=result['owner_id'],operation_key='stop-once')['receipt']==receipt
            newer=m.start();assert newer['owner_id']!=result['owner_id']
            assert m.connect()[0].dispatch_gate()['state']=='PAUSED'
            with pytest.raises(ExecutionError):m.stop(owner_id=result['owner_id'],operation_key='stop-once')
        finally:ref.close()


def test_concurrent_start_single_reservation_and_owner(tmp_path):
    with prepared(tmp_path) as (h,m):
        def start(_):
            try:return ServiceLifecycleManager(h.context.root).start()
            except ExecutionError as exc:return {'error':exc.code}
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(start,range(2)))
        client,_,health=wait_until(lambda:m.connect())
        assert len(list(m.private.glob('start_*/created.json')))==1
        assert len(list(m.private.glob('start_*/claimed.json')))==1
        assert len({r['owner_id'] for r in results if 'owner_id' in r})<=1
        assert m.start()['owner_id']==client.endpoint['owner_id']


@pytest.mark.parametrize('point',['intent_persisted','created'])
def test_lost_start_reply_never_second_creation(tmp_path,monkeypatch,point):
    with prepared(tmp_path) as (h,m):
        def fail(name):
            if name==point:raise OSError('injected failure')
        monkeypatch.setattr(m,'_checkpoint',fail)
        with pytest.raises((OSError,ExecutionError)):m.start()
        monkeypatch.setattr(m,'_checkpoint',lambda name:None)
        if point=='created':
            wait_until(lambda:m.inspect()['state']=='CONNECTED')
            assert m.start()['created'] is False
        else:
            with pytest.raises(ExecutionError):m.start()
        assert len(list(m.private.glob('start_*/created.json'))) == (point=='created')


def test_handshake_timeout_inspect_no_retry(tmp_path):
    with prepared(tmp_path) as (h,m):
        assert m.start(wait_seconds=0)['state']=='STARTING'
        wait_until(lambda:m.inspect()['state']=='CONNECTED')
        assert m.start()['created'] is False


def test_old_lock_or_bad_credentials_never_replace(tmp_path):
    with prepared(tmp_path) as (h,m):
        from abqjobpilot.execution.ownership import LocalOwnerLock
        lock=LocalOwnerLock(h.context)
        try:
            with pytest.raises(ExecutionError) as rejected:m.start()
            assert rejected.value.code=='OWNER_BUSY'
            assert not m._path('lifecycle-current.json').exists()
        finally:lock.close()
        m.start();path=m._path('connection.json');original=path.read_bytes()
        value=read_json(path);value['credential']='wrong-'*10;path.write_text(canonical_json(value))
        try:
            assert m.inspect()['state']=='BLOCKED'
            with pytest.raises(ExecutionError):m.start()
            assert len(list(m.private.glob('start_*/created.json')))==1
        finally:path.write_bytes(original)


def test_product_gui_start_worker_survives_normal_gui_and_launcher_exit(tmp_path):
    from test_execution_gui import Gui
    from test_attachment_gui import action,choose
    guis=[];refs=[];evidence={'abaqus_calls':0,'python':sys.executable}
    with prepared(tmp_path,['result_wait']) as (h,m):
        try:
            gui=Gui(tmp_path,None,None,'gui_A',attachment=True,lifecycle=True);guis.append(gui)
            action(gui,'project',project=h.context.root)
            wait_until(lambda:'NOT_RUNNING' in telemetry(gui.root/'lifecycle.json').get('status',''))
            action(gui,'start')
            wait_until(lambda:m.inspect()['state']=='CONNECTED')
            gui.view(lambda v:v['connected'])
            client,_,health=m.connect();owner=health['process'];owner_id=client.endpoint['owner_id']
            owner_ref=ProcessReference(owner['pid'],owner);refs.append(owner_ref)
            action(gui,'start');assert m.start()['owner_id']==owner_id
            receipt=client.submit(h.requests[0])['receipt'];rid=receipt['run_id']
            run=wait_until(lambda:r if len((r:=client.run(rid))['process_records'])==4 else None)
            worker=next(p for p in run['process_records'] if p['role']=='worker')
            worker_ref=ProcessReference(worker['pid'],worker);refs.append(worker_ref)
            choose(gui,h,rid);shown=gui.view(lambda v:'WAITING' in v['progress_text'])
            action(gui,'disconnect');gui.view(lambda v:not v['connected'])
            action(gui,'reconnect')
            gui.view(lambda v:v['connected'] and dict(v['rows']).get('Run ID')==rid)
            with pytest.raises(ExecutionError) as rejected:m.stop(owner_id=owner_id,operation_key='active-refused')
            assert rejected.value.code=='SERVICE_NOT_IDLE'
            gate=client.dispatch_gate();before=client.run(rid)
            closed=gui.normal_close()
            assert owner_ref.exit_evidence() is None and worker_ref.exit_evidence() is None
            cursor=client.progress(rid)['next_sequence']
            wait_until(lambda:client.progress(rid)['next_sequence']>cursor)
            assert client.health()['process']==owner
            evidence['after_gui_chain_exit']={'owner_exit_evidence':owner_ref.exit_evidence(),
                'worker_exit_evidence':worker_ref.exit_evidence(),'progress_sequence_before':cursor,
                'progress_sequence_after':client.progress(rid)['next_sequence'],'owner_health_identity':client.health()['process'],
                'observed_at':int(time.time()),'basis':'retained identity-matched Windows handles, after both GUI exits'}
            gui2=Gui(tmp_path,None,None,'gui_B',attachment=True,lifecycle=True);guis.append(gui2)
            reopened=choose(gui2,h,rid)
            assert client.run(rid)==before and client.dispatch_gate()==gate
            assert client.submit(h.requests[0])['replayed']
            (Path(h.context.runtime_root)/'process_runs'/rid/'release.json').write_text('{}')
            finished=wait_until(lambda:r if (r:=client.run(rid))['execution']=='FINISHED' else None,timeout=30)
            assert finished['managed_completion']=='COMMITTED_EMPTY_SCOPE'
            gui2.view(lambda v:dict(v['rows']).get('Artifact 独立验证')=='VALID')
            assert len([e for e in client.events() if e['type']=='START_INTENT'])==1
            # Explicit GUI stop, not closing the window, invokes the one exact idle policy.
            action(gui2,'stop')
            wait_until(lambda:owner_ref.exit_evidence())
            wait_until(lambda:m.inspect()['state']=='NOT_RUNNING')
            stopped=m._stopped(m._current())
            evidence.update(owner=owner,worker=worker,gui=gui.identity,gui_exit=closed,
                owner_host=read_json(m._path(m._current()['start_id']+'/host.json')),
                before=shown,reopened=reopened,final=finished,stop=stopped,
                owner_exit=owner_ref.exit_evidence(),worker_exit=worker_ref.exit_evidence())
            gui2.normal_close()
            # Restart is explicit and remains PAUSED. No second test execution.
            newer=m.start();assert newer['owner_id']!=owner_id
            assert m.connect()[0].dispatch_gate()['state']=='PAUSED'
            (tmp_path/'windows_product_lifecycle.json').write_text(canonical_json(evidence),encoding='utf-8')
            target=os.environ.get('RUN019_EVIDENCE_DIR')
            if target:
                (Path(target)/'windows_product_lifecycle.json').write_text(canonical_json(evidence),encoding='utf-8')
        finally:
            for gui in guis:gui.close()
            for ref in refs:ref.close()
