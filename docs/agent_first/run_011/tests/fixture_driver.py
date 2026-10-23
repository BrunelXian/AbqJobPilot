"""Test-only DI driver; CLI separate from real candidate, fixed Python child only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'controller'))
sys.path.insert(0, r'D:\Projects\abqjobpilot_dev')
from engine import run_once
from records import Refusal
from windows_host import current_host


def spec(root):
    return {'root':str(root), 'job':'test_job', 'experiment_id':'fixture_only',
            'original_digest':'test-only', 'output_identity':'fixture-output', 'budget_seconds':.6}


def main():
    mode, value, tag = sys.argv[1:]
    assert mode in {'worker','launcher','race','crash_intent','crash_created'}
    root = Path(value)
    assert root.is_absolute() and root.name.startswith('case_') and 'Run011' in str(root)
    assert tag in {'a','b','c','d'}
    actual_host = current_host()
    injected_host = {**actual_host, 'job_query_succeeded':True, 'in_any_job':False,
                     'test_only_admission_injected':True, 'actual_job_observation':actual_host}
    if mode == 'race':
        (root / ('driver_ready_' + tag)).touch()
        deadline = time.monotonic() + 8
        while not (root / 'race_go').exists() and time.monotonic() < deadline:
            time.sleep(.01)
        assert (root / 'race_go').exists()
    def create(out, err):
        return subprocess.Popen([sys.executable, '-B', str(HERE / 'fixture_process.py'),
                'launcher' if mode == 'launcher' else 'worker', str(root)],
            cwd=root, stdout=out, stderr=err, stdin=subprocess.DEVNULL,
            shell=False, close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW,
            env={'SystemRoot':r'C:\Windows', 'TEMP':str(root), 'TMP':str(root)})
    def checkpoint(phase):
        if mode == 'crash_intent' and phase == 'intent_persisted': os._exit(91)
        if mode == 'crash_created' and phase == 'process_created': os._exit(92)
    try:
        report = run_once(spec(root), 'candidate_' + tag, lambda: None,
                          lambda:injected_host, create, checkpoint=checkpoint)
        (root / ('reply_' + tag + '.json')).write_text(json.dumps(report))
        return 0
    except Refusal as exc:
        (root / ('reply_' + tag + '.json')).write_text(json.dumps({'code':exc.code}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
