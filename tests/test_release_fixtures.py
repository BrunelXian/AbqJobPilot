"""Publication fixtures: independent immutable inputs, no solver or credentials."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import pytest
from abqjobpilot.execution.models import ExecutionError,digest
from abqjobpilot.execution.standard_dat import parse
from abqjobpilot.execution.diagnostics import report_bytes

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/'tests/fixtures/synthetic'

def test_deterministic_authoring_and_missing_rows():
    spec=importlib.util.spec_from_file_location('fixture_author',FIXTURES/'generate.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    raw=(FIXTURES/'standard_axial_cp936.txt').read_bytes()
    assert raw==module.DAT.encode('cp936')
    assert json.loads((FIXTURES/'diagnostic_v2.json').read_text())==module.report()
    result=parse(raw)
    assert result['numerical']=='PRIMARY_THREE_PASS'
    assert result['full_frozen_checks']=='NOT_ALL_ESTABLISHED'
    assert next(c for c in result['comparisons'] if c['quantity']=='2_RF1')['status']=='NOT_RECORDED'

@pytest.mark.parametrize('old,new',[
    ('1.0000E-02','1.1E-02'),('1 1 1.0000','1 1 1.1'),('1 -1.0000','1 -1.1')])
def test_numeric_failures_are_not_relaxed(old,new):
    raw=(FIXTURES/'standard_axial_cp936.txt').read_bytes()
    assert parse(raw.replace(old.encode(),new.encode()))['numerical']=='NUMERICAL_FAIL'

@pytest.mark.parametrize('old,new',[
    ('STEP 1 INCREMENT 1','STEP 1 INCREMENT 2'),('1 1 1.0000','1 2 1.0000'),
    ('2 1.0000E-02','3 1.0000E-02'),('ANALYSIS COMPLETE','INCOMPLETE'),
    ('1 1 1.0000','1 1 1.0000\n1 1 1.0000')])
def test_bad_context_and_duplicates_refused(old,new):
    raw=(FIXTURES/'standard_axial_cp936.txt').read_bytes()
    assert parse(raw.replace(old.encode(),new.encode()))['numerical']=='EVIDENCE_INSUFFICIENT'

@pytest.mark.parametrize('field',['credential','managed_scope_extra','image_path'])
def test_v2_extra_fields_rejected(field):
    report=json.loads((FIXTURES/'diagnostic_v2.json').read_text())
    assert 'managed_scope' not in report['body']['facts']['run']
    assert json.loads(report_bytes(report))==report
    report['body']['facts']['run'][field]='NON_AUTHENTICATING_SENTINEL'
    report['content_digest']=digest(report['body'])
    with pytest.raises(ExecutionError):report_bytes(report)

def test_audit_redaction_nested_idempotent_and_preserves_facts():
    spec=importlib.util.spec_from_file_location('audit_redaction',ROOT/'docs/agent_first/run_022/audit_redaction.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    source={'record':[{'credential':'DUMMY_UNUSABLE','ciphertext':'DUMMY_CIPHER','operator_token':'DUMMY_OPERATOR',
                       'exit_code':0,'pid':123,'note':'preserve'}]}
    before=deepcopy(source);clean=module.redact(source)
    assert source==before and module.redact(clean)==clean
    text=json.dumps(clean)
    assert not any(s in text for s in ('DUMMY_UNUSABLE','DUMMY_CIPHER','DUMMY_OPERATOR'))
    assert clean['record'][0]['exit_code']==0 and clean['record'][0]['note']=='preserve'
