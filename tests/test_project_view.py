"""No backend execution: real read-only snapshots, bounds and format failures."""
import json
import sqlite3
import threading
from pathlib import Path

import pytest
from abqjobpilot.execution.models import ExecutionError, canonical_json
from execution_helpers import guard_environment, harness, inventory


def test_project_page_readonly_and_no_authorization_fields(harness, monkeypatch):
    h=harness
    _,_,receipt=h.accept()
    before=inventory(h.root)
    def forbidden(*a,**k):raise AssertionError('read attempted execution or mutation')
    monkeypatch.setattr(h.service,'execute_pending',forbidden)
    monkeypatch.setattr(h.store,'transaction',forbidden)
    page=h.service.project_view(h.context)
    assert page['runs'][0]['receipt']['request_id']==receipt['request_id']
    assert page['runs'][0]['run_id']==receipt['run_id']
    assert page['slot_run_id'] is None and page['gate']['state']=='OPEN'
    encoded=canonical_json(page)
    assert 'grant_id' not in encoded and 'authority' not in encoded and str(h.root) not in encoded
    assert inventory(h.root)==before


def test_project_page_namespace_and_public_projection(harness):
    h=harness;_,_,receipt=h.accept()
    with h.store.transaction('isolated_corruption_fixture') as c:
        r=json.loads(c.execute('SELECT body FROM runs').fetchone()[0])
        r['private_note']='SECRET_EVENT_PAYLOAD';r['grant_id']='SECRET_GRANT_REFERENCE'
        c.execute('UPDATE runs SET body=?',(canonical_json(r),))
    page=h.service.project_view(h.context)
    assert 'SECRET_' not in canonical_json(page)
    assert h.store.project_view(h.context,'different-namespace')['runs']==[]
    with h.store.transaction('isolated_corruption_fixture') as c:
        r['job_id']={'token':'SECRET_NESTED'};c.execute('UPDATE runs SET body=?',(canonical_json(r),))
    with pytest.raises(ExecutionError) as exc:h.service.project_view(h.context)
    assert 'SECRET_' not in str(exc.value)


def test_keyset_pages_with_many_runs(harness):
    h=harness
    # All rows created through original acceptance; no fabricated Run or permission.
    ids=[]
    for i in range(70):
        _,_,r=h.accept(key='key'+str(i),spec=h.spec(job_id='job'+str(i)))
        ids.append(r['run_id'])
    pages=[];cursor=0
    while cursor is not None:
        p=h.service.project_view(h.context,cursor,32)
        pages.extend(x['run_id'] for x in p['runs']);cursor=p['next_before_row']
    assert pages==list(reversed(ids)) and len(set(pages))==70


@pytest.mark.parametrize('args',[(0,33),(-1,1),(True,1),(0,0),(2**63,1)])
def test_project_page_argument_bounds(harness,args):
    with pytest.raises(ExecutionError):harness.service.project_view(harness.context,*args)


def test_project_page_single_snapshot_and_transaction_ends_before_projection(harness,monkeypatch):
    h=harness;_,_,receipt=h.accept();reached=threading.Event();release=threading.Event()
    original=h.store._diagnostic_checkpoint
    def checkpoint(name):
        if name=='project_view:after_runs':reached.set();assert release.wait(5)
        if name=='project_view:after_close':
            # Exclusive transaction can be acquired now, before projection/transport.
            c=sqlite3.connect(h.context.execution_store,timeout=.1)
            try:c.execute('BEGIN EXCLUSIVE');c.rollback()
            finally:c.close()
    monkeypatch.setattr(h.store,'_diagnostic_checkpoint',checkpoint)
    result=[];errors=[]
    def reader():
        try:result.append(h.service.project_view(h.context))
        except BaseException as exc:errors.append(exc)
    t=threading.Thread(target=reader);t.start();assert reached.wait(5)
    c=sqlite3.connect(h.context.execution_store,timeout=.1)
    try:
        c.execute('BEGIN IMMEDIATE')
        c.execute("UPDATE dispatch_gate SET state='PAUSED',version=version+1")
        c.execute('UPDATE slot SET run_id=?',(receipt['run_id'],))
        # DELETE-journal snapshot prevents writer commit while the read is active.
        with pytest.raises(sqlite3.OperationalError):c.commit()
        c.rollback()
    finally:c.close();release.set();t.join(5)
    assert not t.is_alive() and not errors
    assert result[0]['slot_run_id'] is None and result[0]['gate']['state']=='OPEN'


@pytest.mark.parametrize('failure',['missing','future','journal','busy','corrupt','huge'])
def test_project_page_failures_do_not_repair(harness,failure):
    h=harness;h.accept();db=Path(h.context.execution_store);lock=None
    if failure=='missing':db.unlink()
    elif failure=='future':
        with h.store.transaction('test') as c:c.execute("UPDATE meta SET value='999' WHERE key='schema'")
    elif failure=='journal':Path(str(db)+'-journal').write_bytes(b'needs-maintenance')
    elif failure=='busy':
        lock=sqlite3.connect(db);lock.execute('BEGIN EXCLUSIVE')
    elif failure=='corrupt':db.write_bytes(b'not sqlite')
    elif failure=='huge':
        with h.store.transaction('test') as c:
            run=json.loads(c.execute('SELECT body FROM runs').fetchone()[0]);run['unused']='x'*70000
            c.execute('UPDATE runs SET body=?',(canonical_json(run),))
    before=inventory(h.root)
    try:
        with pytest.raises(ExecutionError):h.service.project_view(h.context)
        assert inventory(h.root)==before
    finally:
        if lock:lock.rollback();lock.close()
