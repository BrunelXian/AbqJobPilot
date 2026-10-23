import builtins
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dat_review
import collect_review

DATA = (HERE/'ORIGINAL_DAT.bin').read_bytes()
HASH = '23ac0cdd7714ef956f481fdf1ec97530cd0cf44a160ae286cd689400efc3f045'


def test_actual_unmodified_bytes_and_original_failure():
    assert hashlib.sha256(DATA).hexdigest() == HASH
    with pytest.raises(UnicodeDecodeError) as error:
        DATA.decode('ascii')
    assert error.value.start == 63
    assert DATA[63:65] == b'\xd4\xc2'
    sys.path.insert(0, str(HERE.parent/'controller'))
    import printed_results
    assert printed_results.parse(DATA)['reason'] == 'UNSUPPORTED_TEXT'


def test_real_tables_final_context_and_fixed_three():
    value = dat_review.parse(DATA)
    assert value['numerical'] == 'PRIMARY_THREE_PASS'
    assert (value['step'], value['increment'], value['final_time']) == (1, 1, '1')
    records = {c['quantity']: c for c in value['comparisons']}
    for name, actual, line in [('2_U1', '0.010000000', 218), ('1_S11', '1.000', 203), ('1_RF1', '-1.0000000', 227)]:
        assert dat_review.number(records[name]['actual']) == dat_review.number(actual)
        assert dat_review.number(records[name]['absolute_error']) == 0
        assert records[name]['source']['line'] == line
        assert records[name]['status'] == 'PASS'
    assert value['context']['final_time_line'] == 187  # not initial page time=0
    assert value['odb_content_validation'] == 'NOT_RUN'


def test_missing_node1_displacement_not_filled_or_all_passed():
    value = dat_review.parse(DATA)
    rows = {c['quantity']: c for c in value['comparisons']}
    for key in ('1_U1', '1_U2', '1_U3'):
        assert rows[key]['status'] == 'NOT_RECORDED'
        assert rows[key]['actual'] is None
    assert value['full_frozen_checks'] == 'NOT_ALL_ESTABLISHED'


def test_reference_and_tolerance_not_retuned():
    manifest = json.loads((HERE.parents[1]/'run_010/EXPERIMENT_MANIFEST.json').read_bytes())
    ref = manifest['body']['acceptance_reference']
    rows = {c['quantity']:c for c in dat_review.parse(DATA)['comparisons']}
    for key, frozen in [('2_U1','node2_U1_mm'),('1_S11','element1_S11_MPa'),('1_RF1','node1_RF1_N')]:
        assert dat_review.number(rows[key]['expected']) == dat_review.number(ref['expected_decimal'][frozen])
        assert dat_review.number(rows[key]['effective_tolerance']) == max(
            dat_review.number(ref['tolerances'][frozen]['absolute']),
            dat_review.number(ref['tolerances'][frozen]['relative'])*abs(dat_review.number(rows[key]['expected'])))


@pytest.mark.parametrize('before,after', [
    (b'1.0000000E-02', b'1.0002000E-02'),
    (b'1   1          1.000', b'1   1          1.001'),
    (b'-1.0000000E+00', b'1.0000000E+00'),
])
def test_real_rows_outside_frozen_tolerances_fail(before, after):
    assert before in DATA
    assert dat_review.parse(DATA.replace(before, after))['numerical'] == 'NUMERICAL_FAIL'


@pytest.mark.parametrize('before,after', [
    (b'STEP    1  INCREMENT    1', b'STEP    2  INCREMENT    1'),
    (b'INCREMENT     1 SUMMARY', b'INCREMENT     2 SUMMARY'),
    (b'TOTAL TIME COMPLETED         1.00', b'TOTAL TIME COMPLETED         0.00'),
    (b'ELEMENT TYPE T3D2', b'ELEMENT TYPE C3D8'),
    (b'   BAR\r\n', b'   OTHER\r\n'),
    (b'1   1          1.000', b'1   2          1.000'),
    (b'NODE FOOT-  U1             U2', b'NODE FOOT-  U2             U1'),
    (b'2      1.0000000E-02', b'3      1.0000000E-02'),
    (b'1.0000000E-02', b'NaN'),
    (b'1.0000000E-02', b'*************'),
    (b'1.0000000E-02', b'\xd4\xc2'),
    (b'Abaqus 2024', b'Abaqus 2025'),
])
def test_changed_context_ambiguous_or_invalid_data_refused(before, after):
    assert before in DATA
    assert dat_review.parse(DATA.replace(before, after))['numerical'] == 'EVIDENCE_INSUFFICIENT'


@pytest.mark.parametrize('data', [b'', DATA[:9000], DATA+DATA, DATA+b'***ERROR\n', DATA+b'UNFINISHED TABLE', b'x'*(1024*1024+1)],
                         ids=['empty','truncated','duplicated','error','unfinished','oversize'])
def test_missing_conflicting_incomplete_or_oversize_refused(data):
    assert dat_review.parse(data)['numerical'] == 'EVIDENCE_INSUFFICIENT'


def test_duplicate_same_entity_refused():
    line = next(s for s in DATA.splitlines(keepends=True) if b'2      1.0000000E-02' in s)
    assert dat_review.parse(DATA.replace(line, line+line))['numerical'] == 'EVIDENCE_INSUFFICIENT'


def test_missing_primary_does_not_become_success():
    lines = [s for s in DATA.splitlines(keepends=True) if b'1     -1.0000000E+00' not in s]
    result = dat_review.parse(b''.join(lines))
    assert result['numerical'] == 'EVIDENCE_INSUFFICIENT'
    assert next(c for c in result['comparisons'] if c['quantity']=='1_RF1')['status'] == 'NOT_RECORDED'


def test_parser_has_no_external_read_or_execution(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError('No external action allowed during interpretation')
    with monkeypatch.context() as patch:
        patch.setattr(builtins, 'open', blocked)
        patch.setattr(Path, 'open', blocked)
        patch.setattr(subprocess, 'Popen', blocked)
        assert dat_review.parse(DATA)['numerical'] == 'PRIMARY_THREE_PASS'


def test_review_trap_blocks_start_and_original_write():
    for event in ('subprocess.Popen','os.system','os.startfile','sqlite3.connect','socket.connect'):
        with pytest.raises(RuntimeError): collect_review.guard(event, ())
    with pytest.raises(RuntimeError):
        collect_review.guard('open', (str(collect_review.ROOT/'observations/attempt.json'), 'w', 0))


def test_review_linkage_to_old_report_is_separate_and_hashed():
    value = json.loads((HERE/'VALIDATION.json').read_bytes())
    assert value['dat_sha256'] == HASH
    assert value['old_result_preserved']['numerical'] == 'EVIDENCE_INSUFFICIENT'
    assert value['numeric_review']['numerical'] == 'PRIMARY_THREE_PASS'
    assert value['overall'] == 'PARTIAL'
    assert value['processes']['member_completeness'] == 'UNKNOWN'
    assert value['processes']['overall_exit'] == 'UNKNOWN'
    assert value['wrapper_calls_recorded'] == 1 and value['new_abaqus_calls_this_review'] == 0
    assert value['host_admission_from_record']['eligible'] is True
    assert value['input_sha256'] == 'e2f91730b68f3af72b8054bc168d31b72a3f21ae186e899d64ab4b6b761523a3'
    for name, digest in value['implementation_sha256'].items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest() == digest
