"""New candidate identity; delegates original experiment/attempt data unchanged."""
from pathlib import Path

from records import digest, require, read_json
import frozen
from host_policy import POLICY, POWERSHELL
from evidence import review

HERE=Path(__file__).resolve().parent
OLD_DIGEST='sha256:645389d8f25942e908f04dca25fbefed820d6f63b35fcfb6c308977b6c016824'
FILES=['candidate.py','package.py','host_policy.py','evidence.py','engine_adapter.py',
       'self_check.ps1','SELF_CHECK.cmd','OPERATOR_EVIDENCE_INDEX.json']


def paths():
    index=read_json(HERE/'OPERATOR_EVIDENCE_INDEX.json')
    return [HERE/p for p in FILES]+[HERE/'operator_evidence'/i['relative_path'] for i in index['items']]+[
        frozen.PACKAGE/'CANDIDATE_MANIFEST.json',POWERSHELL,
        frozen.PACKAGE/'host_compatibility_001/BUNDLE.json',
        frozen.PACKAGE/'host_compatibility_001/fixture_controller.py',
        frozen.PACKAGE/'host_compatibility_001/run_host_check.ps1',
        frozen.PACKAGE/'tests/fixture_process.py']


def configuration(old):
    return {'schema':'r011-fixed-controller-operator-policy-v1','supersedes_candidate_digest':OLD_DIGEST,
        'original_digest':frozen.ORIGINAL_DIGEST,'experiment_id':old['experiment_id'],
        'controller':str(HERE/'candidate.py'),'interpreter':str(frozen.INTERPRETER),
        'host_policy':POLICY,'policy_contract':{
            'job_membership':'must query successfully; membership allowed only under the fixed limited operator policy',
            'current_chain':'actual base Python <- registered venv launcher <- pinned Windows PowerShell',
            'console_session':'same live nonzero Windows session and PowerShell attached to controller console',
            'historical_basis':'archived operator fixed Python chain, not a current Job hierarchy proof',
            'operator_obligation':'keep terminal and Windows session alive; no Ctrl+C/closure/logout',
            'weaker_than_original':'does not exclude unknown ancestor Job termination; conditional lifetime only',
            'authorization':'separate NEW approval required; fixture PASS and digests grant no permission'},
        'fixed_execution':{k:old[k] for k in ['windows_call','environment_policy','actions','additional_abaqus_calls',
            'budget_seconds','attempt_path','attempt_scope','output_identity','records','stop_policy','numeric_reference']},
        'same_attempt_record':True,'additional_attempt_budget':0,'execution_authorization':'NOT_GRANTED',
        'report_scope':'external controller observations only; no formal Project Run; ODB not verified'}


def load(expected=None):
    _,old=frozen.load_candidate(OLD_DIGEST)
    candidate=read_json(HERE/'CANDIDATE_MANIFEST.json')
    require(set(candidate)=={'body','content_digest'} and digest(candidate['body'])==candidate['content_digest']
            and (expected is None or expected==candidate['content_digest']), 'CANDIDATE_CHANGED')
    body=candidate['body']
    require({k:v for k,v in body.items() if k!='materials'}==configuration(old['body']), 'CANDIDATE_CONFIGURATION_CHANGED')
    require([i['path'] for i in body['materials']]==[str(p) for p in paths()], 'CANDIDATE_MATERIAL_SET_CHANGED')
    frozen.verify_materials(body['materials'])
    history=review(HERE/'operator_evidence')
    return candidate,history


def verify(expected=None):
    candidate,history=load(expected)
    frozen.verify_before_attempt(OLD_DIGEST)
    return candidate,history
