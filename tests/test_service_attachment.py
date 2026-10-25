"""Real loopback owner, read-only discovery. No test backend is dispatched."""
from pathlib import Path

import pytest
from abqjobpilot.execution.models import ExecutionError, canonical_json
from abqjobpilot.service_discovery import discover, project_identity
from execution_helpers import inventory
from supervisor_helpers import ProcessHarness, read_json


def connection(h):
    folder=h.root/'private';folder.mkdir(exist_ok=True)
    path=folder/'connection.json'
    path.write_text(canonical_json({'endpoint':read_json(h.endpoint_file),'credential':h.credential}),encoding='utf-8')
    return path


def test_discovery_authenticates_existing_owner_and_reads_without_mutation(tmp_path):
    h=ProcessHarness(tmp_path);private=None
    try:
        owner=h.owner();private=connection(h)
        before=inventory(Path(h.context.root))
        for _ in range(3):
            c,ctx,health=discover(h.context.root)
            assert ctx==h.context and health['process']==owner.identity
            assert c.project_view()['runs']==[]
            assert c.project_view()['gate']['state']=='OPEN'
        assert inventory(Path(h.context.root))==before
        assert len(h.children)==1
        for arguments in ({'before_row':0,'limit':33},{'before_row':0,'limit':1,'path':'SECRET'},
                          {'before_row':0,'limit':1,'approved':True}):
            with pytest.raises(ExecutionError):c.call('project_view',arguments)
        assert inventory(Path(h.context.root))==before
    finally:
        if private:private.unlink()
        h.close()


@pytest.mark.parametrize('failure,code',[
    ('credential','AUTHENTICATION_FAILED'),('protocol','PROTOCOL_MISMATCH'),
    ('project','PROJECT_IDENTITY_MISMATCH'),('process','PROCESS_IDENTITY_MISMATCH'),
    ('stale','ENDPOINT_IDENTITY_MISMATCH'),('owner','ENDPOINT_IDENTITY_MISMATCH')])
def test_discovery_rejects_wrong_or_stale_identity(tmp_path,failure,code):
    h=ProcessHarness(tmp_path);private=None
    try:
        h.owner();private=connection(h);doc=read_json(private)
        if failure=='credential':doc['credential']='SECRET_INVALID_CONNECTION'
        if failure=='protocol':doc['endpoint']['protocol']='unsupported'
        if failure=='project':doc['endpoint']['project_instance_id']='other_project'
        if failure=='process':doc['endpoint']['process']['creation_time_100ns']+=1
        if failure=='stale':doc['endpoint']['owner_id']='stale'
        if failure=='owner':doc['endpoint']['owner_id']='nonmatching_real_owner'
        private.write_text(canonical_json(doc),encoding='utf-8')
        # Matching candidate metadata does not replace OS/authenticated checks.
        if failure not in {'credential','stale'}:
            (Path(h.context.root)/'owner.json').write_text(canonical_json(doc['endpoint']),encoding='utf-8')
        before=inventory(Path(h.context.root))
        with pytest.raises(ExecutionError) as exc:discover(h.context.root)
        assert exc.value.code==code
        assert 'SECRET_INVALID_CONNECTION' not in str(exc.value)
        assert inventory(Path(h.context.root))==before
    finally:
        if private:private.unlink()
        h.close()


def test_missing_owner_and_future_project_do_not_initialize(tmp_path,monkeypatch):
    h=ProcessHarness(tmp_path)
    try:
        import socket,subprocess
        def forbidden(*args,**kwargs):raise AssertionError('Missing discovery must not scan ports or launch')
        monkeypatch.setattr(socket,'socket',forbidden);monkeypatch.setattr(subprocess,'Popen',forbidden)
        before=inventory(tmp_path)
        with pytest.raises(ExecutionError):discover(h.context.root)
        assert inventory(tmp_path)==before and not h.children
        manifest=Path(h.context.root)/'experiment.json';data=read_json(manifest)
        data['schema_version']=999;manifest.write_text(canonical_json(data),encoding='utf-8')
        before=inventory(tmp_path)
        with pytest.raises(ExecutionError) as exc:discover(h.context.root)
        assert exc.value.code=='UNSUPPORTED_FORMAT' and inventory(tmp_path)==before
    finally:h.close()


def test_legacy_directory_rejected(tmp_path):
    legacy=tmp_path/'legacy';legacy.mkdir();(legacy/'project.json').write_text('{}')
    before=inventory(tmp_path)
    with pytest.raises(ExecutionError):project_identity(legacy)
    assert inventory(tmp_path)==before


def test_owner_without_new_capability_is_not_restarted(tmp_path,monkeypatch):
    h=ProcessHarness(tmp_path);private=None
    try:
        owner=h.owner();private=connection(h)
        from abqjobpilot.execution.client import FakeClient
        health=FakeClient.health
        def old(client):
            value=health(client);value['operations'].remove('project_view');return value
        monkeypatch.setattr(FakeClient,'health',old)
        with pytest.raises(ExecutionError) as exc:discover(h.context.root)
        assert exc.value.code=='CAPABILITY_UNAVAILABLE' and owner.process.poll() is None
        assert len(h.children)==1
    finally:
        if private:private.unlink()
        h.close()
