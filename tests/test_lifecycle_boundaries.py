"""Faults and authority boundaries of the existing owner-transaction lifecycle."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import json
import socket
from pathlib import Path

import pytest

from abqjobpilot.execution.client import FakeClient
from abqjobpilot.execution.lifecycle import LifecycleControl, STOP
from abqjobpilot.execution.models import ExecutionError, canonical_json, digest
from abqjobpilot.execution.store import open_existing_read_only
from abqjobpilot.execution.supervisor import FakeSupervisor
from abqjobpilot.service_lifecycle import ServiceLifecycleManager
from test_service_lifecycle import prepared
from supervisor_helpers import read_json,wait_until


@contextmanager
def local_owner(h,m):
    profile=m._profile();bootstrap={k:profile[k] for k in ('authority_instance','credential','client_namespace')}
    bootstrap['endpoint_file']=str(h.root/'local-endpoint.json')
    control=LifecycleControl(profile['operator_digest'],'local-boundary-test')
    owner=FakeSupervisor(h.context,bootstrap,process_config=h.process_config,lifecycle=control)
    try:yield owner,control
    finally:owner.listener.close();owner.store.close()


def request(owner,m,key='stop-key'):
    return {'owner_id':owner.endpoint['owner_id'],'operation_key':key,'operator_token':m._operator()}


def test_inspect_connect_disconnect_no_business_writes(tmp_path,monkeypatch):
    with prepared(tmp_path) as (h,m):
        before=Path(h.context.execution_store).read_bytes()
        def trap(*a,**kw):raise AssertionError('query launched a process')
        monkeypatch.setattr('subprocess.Popen',trap)
        for _ in range(3):assert m.inspect()['state']=='NOT_RUNNING';m.disconnect()
        assert not m._path('lifecycle-current.json').exists()
        assert Path(h.context.execution_store).read_bytes()==before


@pytest.mark.parametrize('damage',['protocol','project','stale_owner','unreachable','capability'])
def test_existing_owner_errors_never_replace(tmp_path,monkeypatch,damage):
    with prepared(tmp_path) as (h,m):
        m.start();path=m._path('connection.json');ownerpath=Path(h.context.root)/'owner.json'
        original=path.read_bytes();ownerbytes=ownerpath.read_bytes();value=read_json(path)
        health=FakeClient.health;realcall=FakeClient.call
        if damage=='protocol':value['endpoint']['protocol']='future'
        elif damage=='project':value['endpoint']['project_instance_id']='other'
        elif damage=='stale_owner':value['endpoint']['owner_id']='obsolete'
        elif damage=='unreachable':
            def unavailable(self,op,args):raise ExecutionError('COMMUNICATION_UNKNOWN','Injected lost owner response')
            monkeypatch.setattr(FakeClient,'call',unavailable)
        else:
            def old(self):
                result=health(self);result['operations'].remove('project_view');return result
            monkeypatch.setattr(FakeClient,'health',old)
        path.write_text(canonical_json(value),encoding='utf-8');ownerpath.write_text(canonical_json(value['endpoint']),encoding='utf-8')
        try:
            assert m.inspect()['state']=='BLOCKED'
            with pytest.raises(ExecutionError):m.start()
            assert len(list(m.private.glob('start_*/created.json')))==1
        finally:
            path.write_bytes(original);ownerpath.write_bytes(ownerbytes)
            monkeypatch.setattr(FakeClient,'health',health);monkeypatch.setattr(FakeClient,'call',realcall)


@pytest.mark.parametrize('failure',['PENDING','UNKNOWN','REAL_PLAN','HELD_SLOT'])
def test_unresolved_store_cannot_stop_or_start(tmp_path,failure):
    with prepared(tmp_path) as (h,m):
        with local_owner(h,m) as (owner,control):
            receipt=owner.service.submit(h.context,h.requests[0])['receipt']
            rid=receipt['run_id']
            # Negative-only storage fixtures, never used to prove execution success.
            with owner.store.transaction('negative_fixture') as c:
                if failure=='UNKNOWN':
                    r=owner.store.query_run(h.context,rid);r['execution']='BLOCKED';r['reconciliation']='REQUIRED'
                    c.execute('UPDATE runs SET body=? WHERE run_id=?',(canonical_json(r),rid))
                elif failure=='REAL_PLAN':
                    p=json.loads(c.execute('SELECT body FROM plans LIMIT 1').fetchone()[0]);p['backend_id']='abaqus-standard-axial-2024-v1'
                    c.execute('UPDATE plans SET body=? WHERE plan_id=?',(canonical_json(p),p['plan_id']))
                elif failure=='HELD_SLOT':c.execute('UPDATE slot SET run_id=? WHERE id=1',(rid,))
            before=Path(h.context.execution_store).read_bytes();gate=owner.store.gate()
            with pytest.raises(ExecutionError):control.stop(owner.service,request(owner,m))
            assert owner.store.gate()==gate and not control.stop_requested.is_set()
            assert Path(h.context.execution_store).read_bytes()==before
        # Old owner metadata prevents replacement regardless of the now released lock.
        with pytest.raises(ExecutionError):m.start()
        assert not m._path('lifecycle-current.json').exists()


def test_start_refuses_pending_without_owner_metadata(tmp_path):
    with prepared(tmp_path) as (h,m):
        from abqjobpilot.execution.store import acquire_initial_preparation_store
        from abqjobpilot.execution.service import ExecutionService
        store=acquire_initial_preparation_store(h.context,m._profile()['authority_instance'])
        try:
            # Corrupt/unsupported pre-existing acceptance fixture: fail closed
            # even without owner metadata; this is not a valid acceptance path.
            with store.transaction('negative_fixture') as c:
                req=h.requests[0]
                c.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)',('r_negative',req['job_id'],req['job_revision'],
                    req['plan_id'],req['grant_id'],1,None,canonical_json({
                    'backend_id':'fake-v1','execution':'PLANNED','queue_state':'PENDING','reconciliation':'NONE'})))
        finally:store.close()
        with pytest.raises(ExecutionError) as exc:m.start()
        assert exc.value.code=='SERVICE_NOT_IDLE' and not m._path('lifecycle-current.json').exists()


def test_stop_transaction_failure_does_not_pause_or_unlock(tmp_path,monkeypatch):
    with prepared(tmp_path) as (h,m):
        with local_owner(h,m) as (owner,control):
            gate=owner.store.gate()
            def fail(name):
                if name=='lifecycle_stop:before_commit':raise OSError('injected transaction failure')
            monkeypatch.setattr(owner.store,'_checkpoint',fail)
            with pytest.raises(ExecutionError):control.stop(owner.service,request(owner,m))
            assert owner.store.gate()==gate and not owner.store._session.stopping
            assert not control.stop_requested.is_set()
            from abqjobpilot.execution.ownership import LocalOwnerLock
            with pytest.raises(ExecutionError):LocalOwnerLock(h.context)
            with owner.store.read() as c:assert c.execute('SELECT COUNT(*) FROM management_receipts').fetchone()[0]==0


def test_concurrent_stop_one_commit_and_submit_race_blocked(tmp_path):
    with prepared(tmp_path) as (h,m):
        with local_owner(h,m) as (owner,control):
            req=request(owner,m)
            with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:control.stop(owner.service,req),range(2)))
            assert sum(not r['replayed'] for r in results)==1
            with owner.store.read() as c:
                assert c.execute('SELECT COUNT(*) FROM management_receipts').fetchone()[0]==1
                assert c.execute('SELECT COUNT(*) FROM control_events').fetchone()[0]==1
            with pytest.raises(ExecutionError):control.stop(owner.service,request(owner,m,'other'))
            with pytest.raises(ExecutionError):
                with owner.store.transaction('accept'):raise AssertionError('stop allowed a racing accept writer')
            with pytest.raises(ExecutionError):owner.service.submit(h.context,h.requests[0])
            assert owner.store.gate()['state']=='PAUSED'


def test_stop_response_lost_queries_original_receipt(tmp_path,monkeypatch):
    with prepared(tmp_path) as (h,m):
        result=m.start();client,_,_=m.connect();real=FakeClient.stop_service
        def lose(self,*args,**kwargs):
            real(self,*args,**kwargs)
            raise ExecutionError('COMMUNICATION_UNKNOWN','Injected loss after committed reply')
        monkeypatch.setattr(FakeClient,'stop_service',lose)
        with pytest.raises(ExecutionError):m.stop(owner_id=result['owner_id'],operation_key='lost')
        wait_until(lambda:m.inspect()['state']=='NOT_RUNNING')
        original=m.stop(owner_id=result['owner_id'],operation_key='lost')
        assert original['replayed'] and original['receipt']['operation_key']=='lost'
        with pytest.raises(ExecutionError):m.stop(owner_id=result['owner_id'],operation_key='replacement')


@pytest.mark.parametrize('damage',['partial_intent','bad_operator','host_unknown','intent_write_failure'])
def test_precreation_faults_fail_closed(tmp_path,monkeypatch,damage):
    with prepared(tmp_path) as (h,m):
        import abqjobpilot.service_lifecycle as module
        if damage=='partial_intent':m._path('lifecycle-current.json').write_text('{')
        elif damage=='bad_operator':
            doc=read_json(m._path('operator.json'));doc['operator_token']='CONNECTION_IS_NOT_OPERATOR'
            m._path('operator.json').write_text(canonical_json(doc))
        elif damage=='host_unknown':
            def unknown(**kw):raise ExecutionError('HOST_UNCONFIRMED','Injected failed IsProcessInJob')
            monkeypatch.setattr('abqjobpilot.service_host.observe_host',unknown)
        else:
            original=module.write_new
            def fail(path,value):
                if path.name=='intent.json':raise OSError('injected disk full')
                return original(path,value)
            monkeypatch.setattr(module,'write_new',fail)
        def trap(*a,**kw):raise AssertionError('Preflight allowed process creation')
        monkeypatch.setattr(module.subprocess,'Popen',trap)
        with pytest.raises((ExecutionError,OSError)):m.start()
        assert not list(m.private.glob('start_*/created.json'))


def test_unknown_stop_commit_replay_uses_durable_decision(tmp_path,monkeypatch):
    import sqlite3
    import abqjobpilot.execution.store as module
    with prepared(tmp_path) as (h,m):
        with local_owner(h,m) as (owner,control):
            original=module._connection
            class LostCommit:
                def __init__(self,c):self.c=c
                def __getattr__(self,name):return getattr(self.c,name)
                def commit(self):
                    self.c.commit();raise sqlite3.OperationalError('Injected response loss after durable commit')
            def connect(*a,**kw):
                c=original(*a,**kw)
                return c if kw.get('read_only') else LostCommit(c)
            monkeypatch.setattr(module,'_connection',connect)
            req=request(owner,m)
            with pytest.raises(ExecutionError) as exc:control.stop(owner.service,req)
            assert exc.value.code=='ACCEPTANCE_UNKNOWN' and owner.store._session.stopping
            assert not control.stop_requested.is_set()
            with pytest.raises(ExecutionError):
                with owner.store.transaction('accept'):raise AssertionError('Uncertain stop permitted a writer')
            monkeypatch.setattr(module,'_connection',original)
            receipt=owner.store.management_receipt(owner.service.client_namespace,STOP,req['operation_key'])
            replay=control.stop(owner.service,req)
            assert replay['replayed'] and replay['receipt']==receipt and control.stop_requested.is_set()
            with owner.store.read() as c:assert c.execute('SELECT COUNT(*) FROM control_events').fetchone()[0]==1


def test_real_owner_crash_not_automatically_replaced(tmp_path):
    import ctypes
    from abqjobpilot.execution.process_handles import ProcessReference
    with prepared(tmp_path) as (h,m):
        m.start();client,_,health=m.connect();identity=health['process']
        # New test-owned process only, bound to retained OS handle and creation identity.
        ref=ProcessReference(identity['pid'],identity,cleanup=True)
        try:
            ref.api.TerminateProcess.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
            assert ref.api.TerminateProcess(ref.handle,91)
            wait_until(lambda:ref.exit_evidence())
            assert m.inspect()['state']=='BLOCKED'
            with pytest.raises(ExecutionError):m.start()
            assert len(list(m.private.glob('start_*/created.json')))==1
            (tmp_path/'crash_evidence.json').write_text(canonical_json({'identity':identity,'exit':ref.exit_evidence(),
                'inspection':m.inspect(),'abaqus_calls':0}))
        finally:ref.close()


def test_first_explicit_start_preserves_preexisting_paused_gate(tmp_path):
    from abqjobpilot.execution.store import acquire_initial_preparation_store
    with prepared(tmp_path) as (h,m):
        store=acquire_initial_preparation_store(h.context,m._profile()['authority_instance'])
        try:store.pause_after_error()
        finally:store.close()
        m.start();client,_,_=m.connect()
        assert client.dispatch_gate()['state']=='PAUSED'
        with pytest.raises(ExecutionError) as exc:client.submit(h.requests[0])
        assert exc.value.code=='DISPATCH_PAUSED'
        assert client.project_view()['runs']==[]


def test_two_os_clients_race_same_original_owner_lock(tmp_path):
    import subprocess,sys
    from abqjobpilot.execution.process_handles import ProcessReference
    with prepared(tmp_path) as (h,m):
        children=[];refs=[]
        try:
            for i in range(2):
                control=tmp_path/('caller_'+str(i));control.mkdir()
                child=subprocess.Popen([sys.executable,'-B',str(Path(__file__).with_name('run019_client.py')),
                    h.context.root,str(control)],cwd=tmp_path,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,close_fds=True,shell=False,creationflags=subprocess.CREATE_NO_WINDOW)
                children.append(child);refs.append(ProcessReference(child.pid))
                wait_until((control/'identity.json').exists)
                identity=read_json(control/'identity.json');refs.append(ProcessReference(identity['pid'],identity))
            (tmp_path/'release.json').write_text('{}')
            for child in children:assert child.wait(timeout=20)==0
            assert all(ref.exit_evidence()['exit_code']==0 for ref in refs)
            wait_until(lambda:m.inspect()['state']=='CONNECTED')
            assert len(list(m.private.glob('start_*/created.json')))==1
            assert len(list(m.private.glob('start_*/claimed.json')))==1
            results=[read_json(tmp_path/('caller_'+str(i))/'result.json') for i in range(2)]
            assert sum(r.get('created',False) for r in results)==1
            (tmp_path/'cross_process_race.json').write_text(canonical_json({'results':results,
                'exits':[ref.exit_evidence() for ref in refs]}),encoding='utf-8')
        finally:
            (tmp_path/'release.json').write_text('{}')
            for child in children:child.wait(timeout=20)
            for ref in refs:ref.close()
