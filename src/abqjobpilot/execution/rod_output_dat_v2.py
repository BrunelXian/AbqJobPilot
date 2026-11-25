"""Independent AF v2 candidate-layout parser. REAL_OUTPUT_FORMAT_NOT_YET_OBSERVED.

Missing rows are rejected. Offline fixtures do not qualify real Solver output.
"""
from decimal import Decimal, InvalidOperation
import hashlib
import re

VERSION = 'rod-combined-output-dat-v2'
NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d{1,3})?'
TITLE = 'R010 axial bar a19d17ea - N mm MPa'


class Refusal(ValueError):
    pass


def require(ok, code):
    if not ok:
        raise Refusal(code)


def number(value):
    require(len(value) <= 40 and re.fullmatch(NUMBER, value), 'INVALID_NUMBER')
    result = Decimal(value.replace('D', 'E').replace('d', 'e'))
    require(result.is_finite(), 'INVALID_NUMBER')
    return result


def lines_of(data):
    from .standard_text import lines, HEADER
    from .models import ExecutionError
    try:
        rows=lines(data)
    except (ExecutionError, ValueError) as exc:
        raise Refusal('INVALID_TEXT') from exc
    require(len(rows)<=4096,'TEXT_LIMIT')
    require(all(r.isascii() or HEADER.fullmatch(r) for r in rows),'UNSUPPORTED_NONASCII_LOCATION')
    return rows


def parse(data, load_n):
    result = {'schema': VERSION, 'dat_sha256': hashlib.sha256(data).hexdigest(),
              'scope': 'bounded fixed-model printed values; attribution supplied by service; no OS/ODB probing',
              'solver': 'EVIDENCE_INSUFFICIENT', 'numerical': 'EVIDENCE_INSUFFICIENT',
              'odb_content_validation': 'NOT_RUN'}
    try:
        lines = lines_of(data)
        require(not any('***ERROR' in s or 'HAS NOT BEEN COMPLETED' in s for s in lines), 'FAILURE_TEXT')
        def one(pattern):
            hits = [(i, re.fullmatch(pattern, s)) for i, s in enumerate(lines)]
            hits = [(i, m) for i, m in hits if m]
            require(len(hits) == 1, 'MISSING_OR_DUPLICATE_MARKER:' + pattern)
            return hits[0]
        heading, _ = one(re.escape(TITLE) + r' STEP 1 INCREMENT 1')
        require(sum(bool(re.search(r'STEP \d+ INCREMENT \d+', s)) for s in lines) == 1, 'STEP_AMBIGUOUS')
        static, _ = one(r'S T E P 1 S T A T I C A N A L Y S I S')
        summary, _ = one(r'INCREMENT 1 SUMMARY')
        require(sum(bool(re.fullmatch(r'INCREMENT \d+ SUMMARY', s)) for s in lines) == 1, 'INCREMENT_AMBIGUOUS')
        time_line, times = one(r'STEP TIME COMPLETED (' + NUMBER + r') , TOTAL TIME COMPLETED (' + NUMBER + r')')
        increment_line, increments = one(r'TIME INCREMENT COMPLETED (' + NUMBER + r') , FRACTION OF STEP COMPLETED (' + NUMBER + r')')
        require(all(number(v) == 1 for v in (*times.groups(), *increments.groups())), 'FINAL_TIME_MISMATCH')
        complete, _ = one('THE ANALYSIS HAS BEEN COMPLETED')
        finish, _ = one('ANALYSIS COMPLETE')
        require(heading < static < summary < increment_line < time_line < complete < finish, 'INCOMPLETE_ORDER')
        # Limit this reader to the real observed complete footer, not arbitrary
        # trailing text or a completion substring in an incomplete file.
        tail = [s for s in lines[finish+1:] if s]
        require(len(tail) == 5 and tail[0] == 'JOB TIME SUMMARY'
                and all(re.fullmatch(label + r' = ' + NUMBER, s) for label, s in zip(
                    [r'USER TIME \(SEC\)', r'SYSTEM TIME \(SEC\)', r'TOTAL CPU TIME \(SEC\)', r'WALLCLOCK TIME \(SEC\)'], tail[1:])),
                'UNSUPPORTED_OR_INCOMPLETE_FOOTER')

        values, refs, tables = {}, {}, []
        for header, labels, allowed, offset in [
            ('ELEMENT PT FOOT- S11', ('S11',), {'1'}, 2),
            ('NODE FOOT- U1 U2 U3 RF1 RF2 RF3', ('U1', 'U2', 'U3', 'RF1', 'RF2', 'RF3'), {'1', '2'}, 1)]:
            index, _ = one(re.escape(header))
            require(time_line < index < complete and lines[index+1] == 'NOTE', 'TABLE_CONTEXT')
            prior = [s for s in lines[time_line+1:index] if s]
            if offset == 2:
                require(prior[-2:] == ['THE FOLLOWING TABLE IS PRINTED AT THE INTEGRATION POINTS FOR ELEMENT TYPE T3D2 AND ELEMENT SET', 'BAR'], 'ELEMENT_LOCATION')
            else:
                require(prior[-2:] == ['THE FOLLOWING TABLE IS PRINTED FOR NODES BELONGING TO NODE SET', 'VERIFY'], 'NODE_LOCATION')
            cursor = index+2
            while cursor < complete and not lines[cursor]:
                cursor += 1
            seen = set()
            while cursor < complete and lines[cursor]:
                fields = lines[cursor].split()
                require(len(fields) == offset+len(labels) and fields[0] in allowed and fields[0] not in seen, 'ROW_AMBIGUOUS')
                if offset == 2:
                    require(fields[1] == '1', 'INTEGRATION_POINT_MISMATCH')
                seen.add(fields[0])
                for label, raw in zip(labels, fields[offset:]):
                    key = fields[0] + '_' + label
                    values[key] = number(raw)
                    refs[key] = {'line': cursor+1, 'header_line': index+1, 'raw': raw,
                                 'entity': fields[0], 'component': label,
                                 'position': 'integration_point_1' if offset == 2 else 'global_node'}
                cursor += 1
            require(seen == allowed, 'MISSING_ENTITY')
            tables.append((index, cursor))
        # Reject unrecognized/duplicate output tables in this fixed result section.
        require(sum(s.startswith(('NODE FOOT-', 'ELEMENT PT')) for s in lines) == 2, 'EXTRA_TABLE')
        require(tables == sorted(tables), 'TABLE_ORDER')
        comparisons = []
        force = number(load_n)
        require(Decimal('0.5') <= force <= Decimal('2.5'), 'LOAD_RANGE')
        targets = [('2_U1', str(force / 100), '0.000001', 'mm', 'primary'),
                   ('1_S11', str(force), '0.0001', 'MPa', 'primary'),
                   ('1_RF1', str(-force), '0.0001', 'N', 'primary')]
        targets += [(k, '0', '0.00000001', 'mm', 'additional') for k in ('1_U1', '1_U2', '1_U3', '2_U2', '2_U3')]
        targets += [(k, '0', '0.0001', 'N', 'additional') for k in ('1_RF2', '1_RF3', '2_RF1', '2_RF2', '2_RF3')]
        for key, expected, tolerance, unit, group in targets:
            item = {'quantity': key, 'expected': expected, 'effective_tolerance': tolerance, 'unit': unit, 'group': group}
            if key not in values:
                item.update(status='NOT_RECORDED', actual=None, absolute_error=None, reason='NO_PRINTED_ROW; not inferred as zero')
            else:
                error = abs(values[key] - Decimal(expected))
                item.update(actual=str(values[key]), absolute_error=str(error),
                            status='PASS' if error <= Decimal(tolerance) else 'FAIL', source=refs[key])
            comparisons.append(item)
        if {'1_RF1', '2_RF1'} <= values.keys():
            balance = abs(force + values['1_RF1'] + values['2_RF1'])
            comparisons.append({'quantity': 'X_force_balance', 'group': 'additional', 'absolute_error': str(balance),
                                'effective_tolerance': '0.0002', 'unit': 'N', 'status': 'PASS' if balance <= Decimal('0.0002') else 'FAIL'})
        else:
            comparisons.append({'quantity': 'X_force_balance', 'group': 'additional', 'status': 'NOT_RECORDED'})
        primary = [c['status'] for c in comparisons]
        numerical = 'PRIMARY_THREE_PASS' if all(s == 'PASS' for s in primary) else ('NUMERICAL_FAIL' if 'FAIL' in primary else 'EVIDENCE_INSUFFICIENT')
        result.update(solver='DAT_COMPLETION_TEXT_OBSERVED', numerical=numerical, comparisons=comparisons,
                      full_frozen_checks='PASS' if all(c['status'] == 'PASS' for c in comparisons) else 'NOT_ALL_ESTABLISHED',
                      step=1, increment=1, final_time='1',
                      context={'heading_line': heading+1, 'summary_line': summary+1, 'final_time_line': time_line+1,
                               'completion_line': complete+1, 'footer_line': finish+1},
                      decoding='bounded text; localized page headers allowed')
    except (Refusal, UnicodeError, InvalidOperation, IndexError) as exc:
        result['reason'] = str(exc) if isinstance(exc, Refusal) else type(exc).__name__
    return result
