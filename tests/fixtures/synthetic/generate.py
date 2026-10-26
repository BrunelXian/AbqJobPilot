"""Explicit deterministic fixture authoring, never run by pytest or product code.

No historical file is read. Values below are invented contract examples.
Run from repository root with the registered interpreter to reproduce both files.
The report's absent managed fields intentionally exercise legacy v2 reading.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
OUT = Path(__file__).resolve().parent

DAT = """SYNTHETIC PARSER FIXTURE - NOT SOLVER OUTPUT
Abaqus 2024 Date 01-01月-2026 Time 00:00:00
R010 axial bar a19d17ea - N mm MPa STEP 1 INCREMENT 1
S T E P 1 S T A T I C A N A L Y S I S
INCREMENT 1 SUMMARY
TIME INCREMENT COMPLETED 1.000 , FRACTION OF STEP COMPLETED 1.000
STEP TIME COMPLETED 1.000 , TOTAL TIME COMPLETED 1.000

THE FOLLOWING TABLE IS PRINTED AT THE INTEGRATION POINTS FOR ELEMENT TYPE T3D2 AND ELEMENT SET
BAR
ELEMENT PT FOOT- S11
NOTE
1 1 1.0000

THE FOLLOWING TABLE IS PRINTED FOR ALL NODES
NODE FOOT- U1 U2 U3
NOTE
1 0.0000 0.0000 0.0000
2 1.0000E-02 0.0000 0.0000

THE FOLLOWING TABLE IS PRINTED FOR ALL NODES
NODE FOOT- RF1 RF2 RF3
NOTE
1 -1.0000 0.0000 0.0000

THE ANALYSIS HAS BEEN COMPLETED
ANALYSIS COMPLETE
JOB TIME SUMMARY
USER TIME (SEC) = 1.0
SYSTEM TIME (SEC) = 0.0
TOTAL CPU TIME (SEC) = 1.0
WALLCLOCK TIME (SEC) = 1.0
"""

def report():
    from abqjobpilot.execution.diagnostics import BODY_V2, project, report_bytes
    from abqjobpilot.execution.models import digest
    def ident(prefix): return prefix+'_'+'1'*32
    rid=ident('r'); pid=ident('plan'); hid='sha256:'+'2'*64
    body=project({
        'report_version':'af-run-diagnostic-v2', 'rules_version':'process-diagnostic-rules-v2',
        'identity':{'project_id':ident('p'),'project_instance_id':ident('pi'),
            'storage_generation':ident('generation'),'context_digest':hid,'schema_version':1,
            'run_id':rid,'job_ref':hid,'plan_id':pid,'historical_plan_digest':hid},
        'view':{'source':'experiment_sqlite_read_transaction','read_at':1000,'run_revision':4,
            'project_event_upper_bound':0,'run_event_sequences':[],'project_event_sequences':[],
            'all_run_records_within_limits':True,'atomic_scope':'database_records_only'},
        'facts':{'run':{'run_id':rid,'plan_id':pid,'plan_digest':hid,'revision':4,'attempt_no':1,
            'phase_attempt_id':ident('phase'),'backend_id':'python-process-fixture-v1',
            'execution':'BLOCKED','backend_outcome':'UNKNOWN','simulation':True,
            'solver_conclusion':'NOT_RUN','artifact_validation':'INVALID','reconciliation':'RECONCILIATION_REQUIRED',
            'process_records':[],'process_exits':[]},
            'plan':{'plan_id':pid,'plan_digest':hid,'backend_id':'python-process-fixture-v1','backend_version':1},
            'events':[],'observations':[],'reconciliations':[],
            'validations':[{'validation_id':ident('val'),'run_id':rid,'phase_attempt_id':ident('phase'),
                'scope':'simulation','policy_id':'process-fixture-result-v1','policy_version':1,
                'validator_id':'process-fixture-validator','validator_version':1,'verdict':'FAIL',
                'recorded_at':1000,'evidence_refs':[],'source':'explicit_client_validation'}],
            'dispatch_gate':{'owner_id':ident('owner'),'version':1,'state':'PAUSED'}},
        'diagnostics':[],'unknowns':['LIVE_PROCESS_NOT_OBSERVED'],
        'coverage':{'events':0,'observations':0,'validations':1,'reconciliations':0},
        'disclosure':{'omitted':[],'artifact_bytes_included':False,'artifacts_revalidated_now':False,
            'executable_authorization':False,'anonymization':'field_whitelist_not_general_anonymization',
            'digest_scope':'canonical_public_body_only_not_original_records_or_signature'}}, BODY_V2)
    for key in ('managed_scope','managed_completion','managed_completion_recorded_at'):
        body['facts']['run'].pop(key)
    result={'body':body,'content_digest':digest(body)}
    report_bytes(result)
    return result

if __name__ == '__main__':
    (OUT/'standard_axial_cp936.txt').write_bytes(DAT.encode('cp936'))
    (OUT/'diagnostic_v2.json').write_text(json.dumps(report(),ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
