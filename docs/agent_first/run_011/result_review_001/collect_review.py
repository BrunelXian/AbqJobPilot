"""Fixed, read-only source review. Writes only new files beside this module.

Run once with the registered ordinary Python. No subprocess, network, database,
OS process re-probe, output repair or ODB access. Existing results never replaced.
"""
import sys
from pathlib import Path
import datetime
import hashlib
import json
import re
import time

HERE = Path(__file__).resolve().parent
ROOT = Path(r'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a')
JOB = 'r010_bar_a19d17ea'
ATTEMPT = 'attempt_d932768199b84915a89c8d7a83ef9c3f'
DAT_HASH = '23ac0cdd7714ef956f481fdf1ec97530cd0cf44a160ae286cd689400efc3f045'
CANDIDATE = 'sha256:d427264f99b2e1128a50d171c09b852cc57662ee002de5c31ba7cdc9d60b840c'


def guard(event, args):
    if event in {'subprocess.Popen', 'os.system', 'os.startfile', 'sqlite3.connect', 'socket.connect'}:
        raise RuntimeError('OFFLINE_REVIEW_NO_EXECUTION')
    if event == 'open':
        import os
        path, mode, flags = args
        writing = (mode and any(c in mode for c in 'wax+')) or (flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if writing:
            if not isinstance(path, (str, bytes)) or Path(path).resolve().parent != HERE:
                raise RuntimeError('WRITES_ONLY_IN_NEW_REVIEW_DIRECTORY')


def utc(ns):
    return datetime.datetime.fromtimestamp(ns / 1e9, datetime.timezone.utc).isoformat()


def main():
    sys.addaudithook(guard)
    sys.path[:0] = [str(HERE), str(HERE.parent/'controller'), str(HERE.parent/'host_policy_candidate_001'), str(HERE.parents[3])]
    from records import stable_read, require
    import package
    import frozen
    import printed_results
    from host_policy import evaluate
    import dat_review

    # load, not verify_before_attempt: old output-conflict guard must remain
    # blocking after execution; review never bypasses it to launch anything.
    candidate, history = package.load(CANDIDATE)
    original, old = frozen.load_candidate(package.OLD_DIGEST)
    sources = {}
    def read(relative):
        path = ROOT / relative
        data, identity = stable_read(path)
        st = path.stat()
        sources[relative] = {**identity, 'birthtime_ns': getattr(st, 'st_birthtime_ns', None),
                             'read_at_ns': time.time_ns()}
        return data
    intent = json.loads(read('observations/attempt.json'))
    report = json.loads(read('observations/controller_report.json'))
    events = [json.loads(line) for line in read('observations/controller_events.jsonl').splitlines()]
    out = read('observations/stdout.bin').decode('cp936', errors='strict').splitlines()
    err = read('observations/stderr.bin').decode('cp936', errors='strict')
    inp = read('engineering/axial_bar.inp')
    dat_path = f'engineering/{JOB}.dat'
    dat = read(dat_path)
    sta = read(f'engineering/{JOB}.sta').decode('cp936', errors='strict').splitlines()
    msg = read(f'engineering/{JOB}.msg').decode('cp936', errors='strict').splitlines()
    # Include any actual same-Job text log, without searching other jobs.
    log_paths = sorted((ROOT/'engineering').glob(JOB+'*.log'))
    require(len(log_paths) <= 8, 'LOG_LIMIT')
    for path in log_paths:
        read(str(path.relative_to(ROOT)))
    require(intent['attempt_id'] == report['attempt_id'] == ATTEMPT, 'ATTEMPT_MISMATCH')
    require(intent['candidate_digest'] == report['candidate_digest'] == CANDIDATE, 'CANDIDATE_MISMATCH')
    require(intent['original_digest'] == original['content_digest'], 'ORIGINAL_MISMATCH')
    require(intent['output_identity'] == original['body']['output']['candidate_key'], 'OUTPUT_IDENTITY_MISMATCH')
    require(intent['experiment_id'] == report['experiment_id'] == frozen.EXPERIMENT, 'EXPERIMENT_MISMATCH')
    require(intent['input_digest'] == original['body']['input_digest'] == 'sha256:'+hashlib.sha256(inp).hexdigest(), 'INPUT_CHANGED')
    require(hashlib.sha256(dat).hexdigest() == DAT_HASH == report['results']['dat_identity']['sha256'], 'DAT_CHANGED')
    for key in ('device', 'inode', 'bytes', 'mtime_ns'):
        require(sources[dat_path][key] == report['results']['dat_identity'][key], 'DAT_IDENTITY_CHANGED')
    require(sources[dat_path]['birthtime_ns'] >= intent['start_intent_at_ns'], 'DAT_PREDATES_ATTEMPT')
    require([e['sequence'] for e in events] == list(range(1, len(events)+1)), 'EVENT_SEQUENCE')
    require([e['observed_at_ns'] for e in events] == sorted(e['observed_at_ns'] for e in events), 'EVENT_TIME_ORDER')
    require(events[0]['attempt_id'] == ATTEMPT and events[0]['kind'] == 'START_INTENT_PERSISTED', 'INTENT_EVENT')
    require(sum(e['kind'] == 'CREATE_CALL_ENTERING' for e in events) == 1, 'CALL_COUNT')
    require(sum(e['kind'] == 'PROCESS_OBJECT_RETURNED' for e in events) == 1, 'CREATE_COUNT')
    processes = report['processes']
    def identity(p):
        return p['pid'], p['creation_time_100ns'], p['image_path']
    identified = [e['identity'] for e in events if e['kind'] in ('PROCESS_IDENTIFIED', 'PROCESS_CANDIDATE_IDENTIFIED')]
    exits = [e for e in events if e['kind'] == 'PROCESS_EXIT_OBSERVED']
    ids = {identity(p) for p in identified}
    require(len(ids) == len(identified) == len(exits) == 11, 'IDENTITY_SET_CONFLICT')
    require(ids == {identity(e['record']) for e in exits} == {identity(e) for e in processes['exits']}, 'EXIT_SET_MISMATCH')
    require([e['record'] for e in exits] == processes['exits'], 'EXIT_RECORD_MISMATCH')
    require(events[-1]['kind'] == 'OBSERVATION_ENDED' and events[-1]['processes'] == processes, 'FINAL_VIEW_MISMATCH')
    require(all(e['record']['exit_code'] == 0 and e['record'].get('exit_source', e['record'].get('source')) in
                ('retained_windows_handle', 'direct_Popen_handle') for e in exits), 'EXIT_EVIDENCE')
    for obs in report['results']['observations']:
        rel = obs['relative_path'].replace('\\', '/')
        if rel in sources:
            require(sources[rel]['bytes'] == obs['bytes'] and sources[rel]['mtime_ns'] == obs['mtime_ns'], 'LOG_METADATA_CHANGED')
    # Keep bytes private except the DAT regression fixture. Report excerpts
    # exclude license server details and unrelated license/banner information.
    def matching(lines, predicate, name):
        return [{'file': name, 'line': i+1, 'text': line.strip()} for i, line in enumerate(lines) if predicate(line.strip())]
    solver_refs = matching(sta, lambda s: s == 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY', 'STA')
    solver_refs += matching(msg, lambda s: s in ('THE ANALYSIS HAS BEEN COMPLETED', '0  ERROR MESSAGES') or
                            bool(re.fullmatch(r'0\s+ERROR MESSAGES', s)), 'MSG')
    solver_refs += matching(out, lambda s: s in ('Abaqus 2024', 'Begin Abaqus/Standard Analysis',
                             'End Abaqus/Standard Analysis', f'Abaqus JOB {JOB} COMPLETED'), 'stdout')
    sta_rows = [s.split() for s in sta if re.match(r'\s*\d', s)]
    require(len(sta_rows) == 1 and sta_rows[0][:3] == ['1','1','1'] and
            all(dat_review.number(v) == 1 for v in sta_rows[0][6:9]), 'STA_FINAL_CONTEXT')
    require(len(solver_refs) == 7, 'SOLVER_CORROBORATION_INCOMPLETE')
    require(not any('***ERROR' in s or 'HAS NOT BEEN COMPLETED' in s for s in sta+msg), 'SOLVER_FAILURE_TEXT')
    parsed = dat_review.parse(dat)
    require(parsed['solver'] == 'DAT_COMPLETION_TEXT_OBSERVED', 'DAT_REVIEW_INCOMPLETE')
    try:
        dat.decode('ascii')
        decode_failure = None
    except UnicodeDecodeError as exc:
        decode_failure = {'encoding': 'ascii', 'byte_offset_zero_based': exc.start,
                          'bytes_hex': dat[exc.start:exc.start+2].hex(),
                          'strict_cp936_character': dat[exc.start:exc.start+2].decode('cp936'),
                          'line': dat[:exc.start].count(b'\n')+1}
    direct_exit = next(e for e in exits if e['record']['pid'] == report['launch_pid'])
    result = {'schema': 'r011-post-experiment-review-v1', 'reviewed_at_ns': time.time_ns(),
        'attempt_id': ATTEMPT, 'experiment_id': frozen.EXPERIMENT, 'candidate_digest': CANDIDATE,
        'original_digest': original['content_digest'], 'frozen_materials': {'new':37,'old':21,'original':34,'status':'MATCH'},
        'input_sha256': hashlib.sha256(inp).hexdigest(), 'dat_sha256': DAT_HASH, 'sources': sources,
        'source_attribution': 'same frozen input, attempt/output identity, post-intent file birth, controller-recorded DAT hash and stable file identity; no cross-filesystem atomic snapshot claim',
        'host_admission_from_record': evaluate(intent['host']),
        'wrapper_calls_recorded':1, 'extra_abaqus_calls_recorded':0, 'new_abaqus_calls_this_review':0,
        'call_count_scope': 'one controller create event/object and one Job transcript; internal license helper belongs to this invocation, not an extra diagnostic command',
        'start_intent_utc':utc(intent['start_intent_at_ns']),
        'direct_exit_observed_utc':utc(direct_exit['observed_at_ns']),
        'direct_exit_after_intent_seconds':(direct_exit['observed_at_ns']-intent['start_intent_at_ns'])/1e9,
        'observation_finished_utc':utc(report['observation_finished_at_ns']),
        'observation_elapsed_seconds':report['observation_elapsed_seconds'], 'deadline_reached': report['deadline_reached'],
        'processes':processes, 'process_evidence_check':'11 unique retained identities and exit records agree with event journal',
        'no_new_process_probe':True, 'no_current_disappearance_used_as_exit':True,
        'solver':'NORMAL_COMPLETION_CORROBORATED_TEXT_AND_RECORDED_STANDARD_EXIT',
        'solver_references':solver_refs, 'numeric_review':parsed,
        'old_parser_reproduced':printed_results.parse(dat), 'old_parser_first_failure':decode_failure,
        'old_result_preserved':{'solver':report['solver'],'numerical':report['numerical'],'overall':report['overall']},
        'known_wrapper_warning':'VS2022 path warning occurred; subsequent Standard start/completion is separately recorded',
        'stderr_scope':'existing invocation license-check transcript; no new license query; server details omitted',
        'overall':'PARTIAL', 'odb_content_validation':'NOT_RUN',
        'remaining':['full required Abaqus member set not proven', 'node 1 U1/U2/U3 absent from DAT; not inferred as zero',
                     'ODB content not inspected', 'no host-wide resource/handle release proof'],
        'window':'No known recorded process requires the operator window to remain for this completed observation. Unknown unobserved members prevent a universal closure-survival guarantee.',
        'implementation_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [HERE/'dat_review.py',Path(__file__)]}}
    # Recheck each actually read source before committing our independent record.
    for rel, before in sources.items():
        _, after = stable_read(ROOT/rel)
        require(all(before[k] == after[k] for k in ('device','inode','bytes','mtime_ns','sha256')), 'SOURCE_CHANGED_DURING_REVIEW')
    with (HERE/'ORIGINAL_DAT.bin').open('xb') as stream:
        stream.write(dat)
    with (HERE/'VALIDATION.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=True, indent=2)
    print(json.dumps({'status':'REVIEW_SAVED','solver':result['solver'],'numerical':parsed['numerical'],
                      'overall':result['overall'],'new_abaqus_calls':0}))


if __name__ == '__main__':
    main()
