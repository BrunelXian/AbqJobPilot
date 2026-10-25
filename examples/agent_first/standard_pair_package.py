"""Preparation-only extension of standard_service's one manifest mechanism.

No execution, grants, IPC, process creation, or owner startup in this module.
"""
from contextlib import closing
from pathlib import Path
import secrets
import tempfile
import uuid


def prepare_package(manifest):
    from standard_service import SOURCE,read,write
    from abqjobpilot.execution import create_experiment,ExperimentStore,ExecutionService
    from abqjobpilot.execution.models import digest,now,require
    from abqjobpilot.execution.standard_contract import StandardConfig,identity,ENTRY,CMD,PYTHON
    from abqjobpilot.execution.standard_sequence import prepare_pair,POLICY
    require(not manifest.exists(),'STATE_CONFLICT','Existing acceptance package must not be replaced')
    token=uuid.uuid4().hex;root=Path(tempfile.gettempdir())/('AbqJobPilot_Run016_'+token);root.mkdir()
    for name in ('engineering_a/scratch','engineering_b/scratch','private','control','logs','session','non_repository_cwd'):
        (root/name).mkdir(parents=True)
    for name in ('engineering_a','engineering_b'):
        (root/name/'axial_bar.inp').write_bytes((SOURCE/'docs/agent_first/run_010/axial_bar.inp').read_bytes())
    paths=[v['path'] for v in read(SOURCE/'docs/agent_first/run_010/RUNTIME_STATIC_IDENTITIES.json') if v['path'] not in (ENTRY,CMD,PYTHON)]
    config=StandardConfig.fixed(paths,managed=True);ctx=create_experiment(root,root/'project')
    with closing(ExperimentStore(ctx)) as store:
        service=ExecutionService(ctx,store,client_namespace='run016-standard-pair',standard_config=config)
        plans=prepare_pair(service,root/'engineering_a','r016_bar_a_'+token[:8],root/'engineering_b','r016_bar_b_'+token[8:16],expires_at=now()+30*86400)
        write(root/'private/bootstrap.json',{'context':ctx.to_dict(),'authority_instance':store._session.authority_instance,
            'credential':secrets.token_urlsafe(36),'client_namespace':'run016-standard-pair','endpoint_file':str(root/'endpoint.json')})
    files=list((SOURCE/'abqjobpilot/execution').glob('*.py'))+[SOURCE/'abqjobpilot/execution_gui.py',SOURCE/'abqjobpilot/gui_app.py',
        SOURCE/'abqjobpilot/__init__.py',SOURCE/'examples/agent_first/standard_service.py',SOURCE/'examples/agent_first/standard_client.py',
        SOURCE/'examples/agent_first/dev_gui_demo.py',Path(__file__).resolve(),root/'engineering_a/axial_bar.inp',root/'engineering_b/axial_bar.inp']
    files+=list((SOURCE/'examples/agent_first').glob('R16_*.vbs'))
    body={'schema':'standard-managed-pair-acceptance-v1','experiment_id':'run016_'+token,'context':ctx.to_dict(),
        'standard_config':config._json,'plans':plans,'request_keys':{'A':'run016-A-once','B':'run016-B-once'},
        'authority':'NOT_ISSUED','run_ids':'CREATED_ONLY_BY_PUBLIC_ACCEPTANCE_TRANSACTION',
        'materials':[identity(p) for p in files],'entry':ENTRY,'resources_each':plans[0]['resources'],
        'sequence_policy':POLICY,'maximum_analysis_calls':2,'extra_abaqus_calls':0,
        'b_conditions':['same_approved_managed_path','A_committed_empty_scope','A_slot_released','A_Solver_complete',
            'A_three_DAT_pass','B_valid_grant_inputs_output_gate','B_no_attempt_and_start_window_open'],
        'timing':{'origin':'A accepted_at from durable receipt','A_start':'within 600s of atomic pair grant registration',
            'B_start':'before min(grant_registered_at+930, A_accepted_at+330)',
            'each_observation':'300s monotonic from CreateProcess return, capped by A_accepted_at+630',
            'batch_observation_end':'A_accepted_at+630; no delayed B, no terminate/retry/delete'},
        'disconnect':'Before B accepted: client stops sequencing. After B accepted: query original key, no cancellation/no new key. Server still enforces deadline at native creation.',
        'host_scope':'same Windows session; outer Job restrictions unknown; no breakaway or kill-on-close',
        'scope':'root cmd and inheriting CreateProcess descendants; external services/brokers excluded; key off-scope execution makes acceptance incomplete',
        'numerics':{'node2_U1':['0.01','0.000001'],'element1_IP1_S11':['1','0.0001'],'node1_RF1':['-1','0.0001']},
        'odb_content_validation':'NOT_RUN','approval_status':'AWAITING_EXPLICIT_TWO_ANALYSIS_AUTHORIZATION'}
    value={'body':body,'content_digest':digest(body)};write(manifest,value)
    return {'status':'PREPARED_TWO_PLANS_NO_GRANTS_NO_RUNS','digest':value['content_digest'],'root':str(root),'plan_ids':[p['plan_id'] for p in plans]}
