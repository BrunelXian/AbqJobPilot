"""Narrow host/operator preparation and fixed-command contracts; no launch."""
from contextlib import closing
import json
from pathlib import Path
import sys

import pytest
from abqjobpilot.execution import ExecutionService
from abqjobpilot.execution.models import canonical_json,now
from abqjobpilot.execution.standard_contract import issue_execution,StandardConfig
from abqjobpilot.execution.store import acquire_initial_preparation_store,acquire_supervisor_store
from abqjobpilot.execution.standard_backend import call_data
from abqjobpilot.execution import standard_process
from test_standard_backend import case,assert_code,ROOT


def test_approval_provision_does_not_start_or_resume_owner(case):
    c=case;authority=c.store._session.authority_instance;c.store.close()
    with closing(acquire_initial_preparation_store(c.ctx,authority)) as store:
        service=ExecutionService(c.ctx,store,standard_config=c.config)
        grant=issue_execution(service,c.plan['plan_id'],expires_at=now()+50,approval_source='TEST_SUBSTITUTE_OPERATOR')
        assert grant['grant_kind']=='REAL_FIXED_STANDARD'
        with store.read() as db:
            assert db.execute('select count(*) from runs').fetchone()[0]==0
            assert db.execute('select count(*) from consumption').fetchone()[0]==0
            assert dict(db.execute('select key,value from meta'))['supervisor_started']=='0'
    with closing(acquire_supervisor_store(c.ctx,authority)) as store:assert store.gate()['state']=='OPEN'
    assert c.calls==[]


def test_command_is_frozen_windows_template_with_only_new_identity(case):
    c=case;original=json.loads((ROOT/'docs/agent_first/run_010/EXPERIMENT_MANIFEST.json').read_text())['body']
    expected=original['windows_call']['command_line'].replace(original['directories']['input_and_submission'],str(c.engineering)).replace('r010_bar_a19d17ea',c.plan['job_name'])
    call=call_data(c.ctx,c.plan,{'run_id':'r_'+'1'*32})
    assert call['command_line']==expected
    assert call['cwd']==str(c.engineering) and c.calls==[]
    assert not any(k in call['environment'] for k in ('CREDENTIAL','PYTHONPATH','ABAQUS_ARGS'))


@pytest.mark.parametrize('success,in_job,file_type,expected',[(True,True,1,True),(True,False,1,True),
    (False,False,1,False),(True,True,3,False),(True,False,0,False)])
def test_host_policy_requires_queries_identity_and_regular_outputs(monkeypatch,success,in_job,file_type,expected):
    class Kernel:
        def GetCurrentProcess(self):return 1
        def IsProcessInJob(self,process,job,result):result._obj.value=int(in_job);return int(success)
        def GetStdHandle(self,n):return 1
        def GetFileType(self,handle):return file_type
    monkeypatch.setattr(standard_process,'kernel',lambda:Kernel())
    config=StandardConfig(canonical_json({'interpreter':sys.executable,'host_policy':'independent-service-same-windows-session-v1'}))
    result=standard_process.check_host(config)
    assert result['eligible']==expected
    assert result['full_job_hierarchy']=='UNKNOWN' and result['abaqus_survival']=='NOT_VALIDATED'


def test_standard_has_no_existing_test_reconciliation_escape(case):
    c=case;rid=c.service.submit(c.ctx,c.request(c.approve()))['receipt']['run_id']
    c.service.execute_pending(c.ctx,rid)
    for preview in (c.service.preview_reconciliation(c.ctx,rid),c.service.preview_process_reconciliation(c.ctx,rid)):
        assert preview['candidate_action'] is None
        assert preview['reasons'][0]['code']=='UNSUPPORTED_EVIDENCE_POLICY'
    assert c.store.query_run(c.ctx,rid)['reconciliation']=='RECONCILIATION_REQUIRED'
    assert c.store.gate()['state']=='PAUSED'
