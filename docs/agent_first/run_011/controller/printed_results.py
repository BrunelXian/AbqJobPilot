"""Conservative, bounded DAT text subset; not an ODB or general DAT reader.

Only explicit step/increment/time + exact component tables are accepted. Actual
2024 formatting is unverified: unsupported layout stays evidence-insufficient.
No fuzzy number search, last-row guessing, missing=zero, or tolerance adjustment.
"""
from decimal import Decimal, InvalidOperation
import re

from records import Refusal, require

NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d{1,3})?'


def number(text):
    require(re.fullmatch(NUMBER, text) is not None and len(text) <= 40, 'INVALID_NUMBER')
    value = Decimal(text.replace('D', 'E').replace('d', 'e'))
    require(value.is_finite(), 'INVALID_NUMBER')
    return value


def parse(data):
    """Return historical TEXT evidence, never process/Solver success by implication."""
    result = {'solver': 'EVIDENCE_INSUFFICIENT', 'numerical': 'EVIDENCE_INSUFFICIENT',
              'odb_content_validation': 'NOT_RUN', 'layout': 'r011-explicit-dat-tables-v1',
              'actual_2024_layout_validated': False}
    try:
        require(len(data) <= 16 * 1024 * 1024, 'TEXT_LIMIT')
        text = data.decode('ascii')
        lines = [re.sub(r'\s+', ' ', s.strip()).upper() for s in text.splitlines()]
        require(len(lines) <= 100000 and all(len(s) <= 4096 for s in lines), 'TEXT_LIMIT')
        if any('***ERROR' in s or 'ANALYSIS HAS NOT BEEN COMPLETED' in s for s in lines):
            result['solver'] = 'FAILURE_TEXT_OBSERVED'
            raise Refusal('FAILURE_TEXT')
        require(sum(s == 'ABAQUS 2024' for s in lines) == 1, 'VERSION_TEXT_UNCONFIRMED')
        require(sum(s == 'ABAQUS/STANDARD' for s in lines) == 1, 'PRODUCT_TEXT_UNCONFIRMED')
        require(sum(s == 'THE ANALYSIS HAS BEEN COMPLETED' for s in lines) == 1, 'COMPLETION_TEXT_MISSING_OR_DUPLICATE')
        require(sum(s == 'STEP 1 INCREMENT 1' for s in lines) == 1, 'STEP_AMBIGUOUS')
        require(not any(re.match(r'STEP\s+\d', s) and s != 'STEP 1 INCREMENT 1' for s in lines), 'STEP_AMBIGUOUS')
        start = lines.index('STEP 1 INCREMENT 1')
        finish = lines.index('THE ANALYSIS HAS BEEN COMPLETED')
        require(start < finish, 'INCOMPLETE_ORDER')
        require(not any(lines[finish+1:]), 'TRAILING_OR_INCOMPLETE_TEXT')
        times = [(i, s.split()[-1]) for i, s in enumerate(lines) if s.startswith('TOTAL TIME COMPLETED ')]
        require(len(times) == 1 and start < times[0][0] < finish and number(times[0][1]) == 1,
                'FINAL_TIME_AMBIGUOUS')
        values, refs = {}, {}
        consumed = {start, times[0][0]}
        for header, labels, ids in [
            ('NODE U1 U2 U3', ('U1','U2','U3'), ('1','2')),
            ('NODE RF1 RF2 RF3', ('RF1','RF2','RF3'), ('1','2')),
            ('ELEMENT PT S11', ('S11',), ('1',))]:
            hits = [i for i, s in enumerate(lines) if s == header]
            require(len(hits) == 1 and times[0][0] < hits[0] < finish, 'TABLE_MISSING_OR_DUPLICATE')
            consumed.add(hits[0])
            i = hits[0] + 1
            seen = set()
            while i < finish and lines[i]:
                fields = lines[i].split()
                offset = 2 if labels == ('S11',) else 1
                require(len(fields) == offset + len(labels) and fields[0] in ids
                        and fields[0] not in seen, 'ROW_AMBIGUOUS')
                if offset == 2:
                    require(fields[1] == '1', 'INTEGRATION_POINT_AMBIGUOUS')
                seen.add(fields[0])
                consumed.add(i)
                for label, raw in zip(labels, fields[offset:]):
                    key = fields[0] + '_' + label
                    values[key], refs[key] = number(raw), {'line': i + 1, 'header_line': hits[0] + 1, 'raw': raw}
                i += 1
            require(seen == set(ids), 'ENTITY_MISSING')
        require(all(not lines[i] or i in consumed for i in range(start, finish)),
                'UNSUPPORTED_DAT_LAYOUT')
        comparisons = []
        for key, expected, tolerance, unit in [
            ('2_U1', '0.01', '0.000001', 'mm'), ('1_S11', '1', '0.0001', 'MPa'),
            ('1_RF1', '-1', '0.0001', 'N'),
            *[(k, '0', '0.00000001', 'mm') for k in ('1_U1','1_U2','1_U3','2_U2','2_U3')],
            *[(k, '0', '0.0001', 'N') for k in ('2_RF1','2_RF2','2_RF3')]]:
            error = abs(values[key] - Decimal(expected))
            comparisons.append({'quantity': key, 'actual': str(values[key]), 'expected': expected,
                'absolute_error': str(error), 'effective_tolerance': tolerance, 'units': unit,
                'pass': error <= Decimal(tolerance), 'source': refs[key]})
        balance = abs(1 + values['1_RF1'] + values['2_RF1'])
        comparisons.append({'quantity':'X_force_balance', 'absolute_error':str(balance),
                            'effective_tolerance':'0.0002', 'pass':balance <= Decimal('0.0002')})
        result.update(solver='COMPLETION_TEXT_OBSERVED_NOT_PROCESS_PROOF',
                      numerical='VALID_TEXT_SUBSET' if all(c['pass'] for c in comparisons) else 'NUMERICAL_FAIL',
                      comparisons=comparisons, step=1, increment=1, final_time='1',
                      runtime_text={'product':'Abaqus/Standard','version':'2024','source':'DAT_only',
                                    'runtime_acceptance':False})
    except (Refusal, UnicodeError, InvalidOperation) as exc:
        result['reason'] = getattr(exc, 'code', 'UNSUPPORTED_TEXT')
    return result
