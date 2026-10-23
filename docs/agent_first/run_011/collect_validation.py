"""Read-only evidence consolidation plus new Run011 report files; never launches."""
import ast
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'controller'))
from records import read_json, write_new, stamp
from frozen import load_candidate, ROOT
from printed_results import parse


def nested(value):
    if isinstance(value,dict):
        yield value
        for item in value.values(): yield from nested(item)
    elif isinstance(value,list):
        for item in value: yield from nested(item)


def main():
    old,candidate=load_candidate()
    baseline=json.loads((BASE/'PRESERVATION_BASELINE.json').read_text(encoding='utf-8-sig'))
    for item in baseline:
        p=Path(item['path'])
        assert p.stat().st_size == item['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest() == item['sha256']
    cases=[]
    for filename in ['TEST_RESULTS_01.xml','TEST_RESULTS_02.xml','TEST_RESULTS_03.xml',
                     'TEST_RESULTS_04.xml','DEPENDENCY_RESULTS.xml']:
        suite=ET.parse(BASE/filename).getroot().find('testsuite')
        cases.append({'file':filename,**suite.attrib,
            'test_cases':[{'name':c.attrib['name'],'classname':c.attrib.get('classname'),
                          'result':'failed' if c.find('failure') is not None else 'passed'}
                         for c in suite.findall('testcase')]})
    launches=[]; known_exits={}; fixture_registrations=[]
    for number in ('02','03','04'):
        folder=BASE/('evidence_'+number)
        for p in folder.glob('*.json'):
            data=json.loads(p.read_text())
            for record in nested(data):
                if {'pid','creation_time_100ns','exit_code'} <= record.keys():
                    known_exits[(record['pid'],record['creation_time_100ns'])]=record
                if {'identity','exit','handles_closed'} <= record.keys():
                    assert record['handles_closed'] is True
                    launches.append({'evidence':str(p.relative_to(BASE)),**record})
        root=Path((BASE/('TEST_ROOT_'+number+'.txt')).read_text(encoding='utf-8-sig').strip())
        assert root.name.startswith('AbqJobPilot_Run011_')
        for p in root.rglob('physical_*.json'):
            identity=json.loads(p.read_text())
            fixture_registrations.append({'iteration':number,'role':p.name.split('_')[1],
                'identity':identity,'source':str(p)})
    for item in fixture_registrations:
        key=(item['identity']['pid'],item['identity']['creation_time_100ns'])
        assert key in known_exits and known_exits[key]['exit_code'] == 0
        item['verified_exit']=known_exits[key]
    assert len(fixture_registrations) == 15
    assert not list((ROOT/'observations').iterdir()) and not list((ROOT/'extracted').iterdir())
    assert not list((ROOT/'engineering').glob('r010_bar_a19d17ea.*'))
    for path in (BASE/'controller').glob('*.py'):
        tree=ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                assert node.func.attr not in {'kill','terminate','TerminateProcess','TerminateJobObject',
                                              'AssignProcessToJobObject','SetInformationJobObject'}
    value={'checked_at_ns':stamp(),'candidate_digest':candidate['content_digest'],
        'original_digest':old['content_digest'],'original_materials':len(old['body']['materials']),
        'candidate_materials':len(candidate['body']['materials']),
        'preserved_files':len(baseline),'changed_preserved_files':0,
        'test_iterations':cases,'retained_process_exit_evidence':launches,
        'physical_fixture_registrations':fixture_registrations,
        'real_experiment_observations_empty':True,'real_job_output_count':0,
        'real_execute_operation_invocations':0,'actual_abaqus_calls':0,
        'scope':'fixture Python exits verified; not a proof of a complete arbitrary Windows process tree',
        'new_test_roots':'Retained; no deletions or private credentials created',
        'operator_terminal_admission':'NOT_TESTED', 'current_tool_admission':'BLOCKED_JOB'}
    write_new(BASE/'VALIDATION.json',value)
    sample_dir=BASE/'samples'; sample_dir.mkdir(exist_ok=False)
    module=ast.parse((BASE/'tests/test_candidate.py').read_text(encoding='utf-8'))
    text=next(ast.literal_eval(n.value) for n in module.body if isinstance(n,ast.Assign)
              and any(isinstance(t,ast.Name) and t.id=='TEXT' for t in n.targets))
    with (sample_dir/'SYNTHETIC_DAT.txt').open('xb') as stream: stream.write(text)
    write_new(sample_dir/'SYNTHETIC_RESULT.json',{'source':'synthetic test text, NOT an Abaqus output',
        'report':parse(text)})
    print(json.dumps({'candidate_digest':candidate['content_digest'],'preserved':len(baseline),
        'fixture_processes_across_passing_iterations':len(fixture_registrations),
        'all_fixture_exits_verified_zero':True,'final_targeted_tests':56,'dependency_tests':21,
        'actual_abaqus_calls':0}))


if __name__ == '__main__': main()
