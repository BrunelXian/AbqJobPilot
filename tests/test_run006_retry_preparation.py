"""No-solver checks for the disposable Run 006 retry preparation tools."""

from __future__ import annotations

import json
import runpy
from itertools import count
from pathlib import Path

import pytest


TOOLS = Path(__file__).resolve().parents[1] / "docs" / "mcp" / "run_006"
INP_TOOL = runpy.run_path(str(TOOLS / "retry_sanity_inp.py"))
MONITOR_TOOL = runpy.run_path(str(TOOLS / "passive_retry_monitor.py"))


def monitor_fixture(tmp_path, *, name="run006_c3d8_sanity_03"):
    project = tmp_path / "project"
    runtime = project / "runtime"
    runtime.mkdir(parents=True)
    inp = tmp_path / "engineering" / f"{name}.inp"
    INP_TOOL["write_if_absent"](inp)
    (project / "project.json").write_text(json.dumps({
        "project_id": MONITOR_TOOL["EXPECTED_PROJECT_ID"]}), encoding="utf-8")
    (runtime / "live_status.json").write_text('{"phase":"IDLE"}', encoding="utf-8")
    job = {"queue_id": "q_fixture", "job_name": inp.stem, "inp_path": str(inp),
           "work_dir": str(inp.parent), "status": "QUEUED", "cpus": 1, "gpus": 0}
    queue_file = runtime / "queue.json"
    queue_file.write_text(json.dumps({"jobs": [job]}), encoding="utf-8")
    return project, runtime, inp, queue_file, job


def test_sanity_inp_has_positive_jacobian_and_required_output(tmp_path):
    path = tmp_path / "engineering" / "run006_c3d8_sanity_01.inp"
    assert INP_TOOL["write_if_absent"](path) == "CREATED"
    checked = INP_TOOL["validate_inp"](path.read_text(encoding="ascii"))
    assert checked["nodes"] == 8
    assert checked["elements"] == 1
    assert checked["jacobian_at_center"] == 0.125
    assert checked["requested_outputs"] == ["U", "RF", "S", "E"]
    assert INP_TOOL["write_if_absent"](path) == "REUSED_IDENTICAL"


def test_sanity_inp_does_not_overwrite_existing_content(tmp_path):
    path = tmp_path / "engineering" / "run006_c3d8_sanity_01.inp"
    path.parent.mkdir()
    path.write_text("existing research data", encoding="utf-8")
    with pytest.raises(FileExistsError):
        INP_TOOL["write_if_absent"](path)
    assert path.read_text(encoding="utf-8") == "existing research data"


def test_monitor_requires_one_matching_project_job_and_is_read_only(tmp_path):
    project, runtime, inp, queue_file, job = monitor_fixture(tmp_path)
    queue_file.write_text('{"jobs": []}', encoding="utf-8")
    validate = MONITOR_TOOL["validate_fixture"]
    with pytest.raises(ValueError, match="missing or duplicated"):
        validate(project, inp, "q_fixture", check_only=True)

    queue_file.write_text(json.dumps({"jobs": [job]}), encoding="utf-8")
    before = queue_file.read_bytes()
    assert validate(project, inp, "q_fixture") == runtime
    assert queue_file.read_bytes() == before
    (runtime / "live_status.json").write_text('{"phase":"RUNNER_ACTIVE"}', encoding="utf-8")
    with pytest.raises(ValueError, match="not confirmed idle"):
        validate(project, inp, "q_fixture")
    queue_file.write_text(json.dumps({"jobs": [job, job]}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing or duplicated"):
        validate(project, inp, "q_fixture")


def test_monitor_accepts_terminal_history_before_one_queued_target(tmp_path):
    project, runtime, inp, queue_file, target = monitor_fixture(tmp_path)
    historical = {"queue_id": "q_old", "job_name": "run006_c3d8_sanity_01",
                  "inp_path": str(inp.parent / "run006_c3d8_sanity_01.inp"),
                  "status": "COMPLETED_WITH_WARNINGS"}
    queue_file.write_text(json.dumps({"jobs": [historical, target]}), encoding="utf-8")
    before = queue_file.read_bytes()
    assert MONITOR_TOOL["validate_fixture"](project, inp, "q_fixture", check_only=True) == runtime
    assert MONITOR_TOOL["validate_fixture"](project, inp, "q_fixture") == runtime
    assert queue_file.read_bytes() == before

    other = {**historical, "queue_id": "q_other", "status": "QUEUED"}
    queue_file.write_text(json.dumps({"jobs": [historical, target, other]}), encoding="utf-8")
    with pytest.raises(ValueError, match="another pending"):
        MONITOR_TOOL["validate_fixture"](project, inp, "q_fixture", check_only=True)


@pytest.mark.parametrize("other_status", ["DATACHECK_OK", "RUNNING", "UNKNOWN_INTERRUPTED", None])
def test_monitor_rejects_other_nonterminal_jobs(tmp_path, other_status):
    project, runtime, inp, queue_file, target = monitor_fixture(tmp_path)
    other = {"queue_id": "q_other", "inp_path": str(inp.parent / "other.inp"),
             "status": other_status}
    queue_file.write_text(json.dumps({"jobs": [other, target]}), encoding="utf-8")
    with pytest.raises(ValueError, match="another pending, active or unconfirmed"):
        MONITOR_TOOL["validate_fixture"](project, inp, "q_fixture", check_only=True)


def test_monitor_observation_does_not_change_runtime(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    live = runtime / "live_status.json"
    live.write_text('{"phase":"IDLE"}', encoding="utf-8")
    inp = tmp_path / "engineering" / "run006_c3d8_sanity_01.inp"
    INP_TOOL["write_if_absent"](inp)
    before = live.read_bytes()
    monkeypatch.setitem(MONITOR_TOOL["collect_observation"].__globals__, "_process_snapshot", lambda: [])
    result = MONITOR_TOOL["collect_observation"](runtime, "q_fixture", inp, {})
    assert result["live_phase"] == "IDLE"
    assert result["named_candidates"] == []
    assert result["files"][".inp"]["exists"] is True
    assert result["files"][".odb"]["exists"] is False
    assert result["disk_budget_warning"] is False
    assert live.read_bytes() == before


def test_monitor_queue_id_and_inp_mismatch_reports_actual_records(tmp_path):
    project, runtime, inp, queue_file, job = monitor_fixture(tmp_path)
    state = MONITOR_TOOL["queue_identity_state"](runtime, "q_wrong", inp, initial=True)
    assert state["state"] == "IDENTITY_MISMATCH"
    assert state["expected_queue_id"] == "q_wrong"
    assert state["actual_matching_count"] == 1
    assert state["actual_queue_ids"] == ["q_fixture"]
    assert state["actual_inp_paths"] == [str(inp)]
    assert state["actual_statuses"] == ["QUEUED"]
    with pytest.raises(ValueError, match="q_wrong"):
        MONITOR_TOOL["validate_fixture"](project, inp, "q_wrong")

    wrong_inp = inp.parent / "other.inp"
    state = MONITOR_TOOL["queue_identity_state"](runtime, "q_fixture", wrong_inp, initial=True)
    assert state["actual_matching_count"] == 0
    assert "same unique record" in state["reason"]
    queue_file.write_text(json.dumps({"jobs": [job, {**job, "queue_id": "q_duplicate"}]}),
                          encoding="utf-8")
    state = MONITOR_TOOL["queue_identity_state"](runtime, "q_fixture", inp, initial=True)
    assert state["actual_matching_count"] == 2
    assert state["actual_queue_ids"] == ["q_fixture", "q_duplicate"]


def _mock_sample(_runtime, _queue_id, _inp, _known):
    return {"named_scan": "OK", "disk_budget_warning": False}


def _fast_clock():
    ticks = count(step=0.5)
    return lambda: next(ticks)


def test_monitor_running_transition_and_ready_after_first_flush(tmp_path, monkeypatch, capsys):
    _project, runtime, inp, queue_file, job = monitor_fixture(tmp_path)
    calls = 0

    def sample(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            queue_file.write_text(json.dumps({"jobs": [{**job, "status": "FULL_RUNNING"}]}),
                                  encoding="utf-8")
        return _mock_sample(*args)

    monkeypatch.setitem(MONITOR_TOOL["run_monitor"].__globals__, "collect_observation", sample)
    output = tmp_path / "evidence.jsonl"
    count_written, identities, reason = MONITOR_TOOL["run_monitor"](
        runtime, "q_fixture", inp, output, duration=1.5, interval=0.5,
        clock=_fast_clock(), sleep=lambda _: None)
    assert (count_written, identities, reason) == (2, 0, None)
    lines = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert [line["queue_identity"]["target_status"] for line in lines] == ["QUEUED", "FULL_RUNNING"]
    ready = capsys.readouterr().out
    assert ready.startswith("MONITOR_READY ")
    payload = json.loads(ready.removeprefix("MONITOR_READY ").strip())
    assert payload["queue_id"] == "q_fixture"
    assert payload["project_id"] == MONITOR_TOOL["EXPECTED_PROJECT_ID"]
    assert payload["evidence_file"] == str(output.resolve())
    assert payload["sample_interval"] == 0.5
    assert payload["timestamp"]


def test_monitor_records_replaced_queue_id_and_stops(tmp_path, monkeypatch, capsys):
    _project, runtime, inp, queue_file, job = monitor_fixture(tmp_path)
    calls = 0

    def sample(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            queue_file.write_text(json.dumps({"jobs": [{**job, "queue_id": "q_replaced"}]}),
                                  encoding="utf-8")
        return _mock_sample(*args)

    monkeypatch.setitem(MONITOR_TOOL["run_monitor"].__globals__, "collect_observation", sample)
    output = tmp_path / "evidence.jsonl"
    count_written, _identities, reason = MONITOR_TOOL["run_monitor"](
        runtime, "q_fixture", inp, output, duration=1.5, interval=0.5,
        clock=_fast_clock(), sleep=lambda _: None)
    assert count_written == 2
    assert "queue identity changed" in reason
    lines = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert lines[-1]["queue_identity"]["state"] == "IDENTITY_MISMATCH"
    assert lines[-1]["queue_identity"]["actual_queue_ids"] == ["q_replaced"]
    assert "MONITOR_READY" in capsys.readouterr().out


def test_monitor_snapshot_failure_never_claims_ready(tmp_path, monkeypatch, capsys):
    _project, runtime, inp, _queue_file, _job = monitor_fixture(tmp_path)
    monkeypatch.setitem(MONITOR_TOOL["run_monitor"].__globals__, "collect_observation",
                        lambda *_: {"named_scan": "UNCONFIRMED", "disk_budget_warning": False})
    output = tmp_path / "evidence.jsonl"
    count_written, _identities, reason = MONITOR_TOOL["run_monitor"](
        runtime, "q_fixture", inp, output, duration=1.5, interval=0.5,
        clock=_fast_clock(), sleep=lambda _: None)
    assert count_written == 1
    assert reason == "Windows process snapshot unavailable"
    assert "MONITOR_READY" not in capsys.readouterr().out
    assert json.loads(output.read_text(encoding="utf-8").splitlines()[0])["monitor_error"] == reason


def test_monitor_first_sample_write_failure_never_claims_ready(tmp_path, monkeypatch, capsys):
    _project, runtime, inp, _queue_file, _job = monitor_fixture(tmp_path)
    monkeypatch.setitem(MONITOR_TOOL["run_monitor"].__globals__, "collect_observation", _mock_sample)
    monkeypatch.setitem(MONITOR_TOOL["run_monitor"].__globals__, "_write_sample",
                        lambda *_: (_ for _ in ()).throw(OSError("fixture write failure")))
    output = tmp_path / "evidence.jsonl"
    with pytest.raises(OSError, match="fixture write failure"):
        MONITOR_TOOL["run_monitor"](runtime, "q_fixture", inp, output,
                                    duration=1.5, interval=0.5,
                                    clock=_fast_clock(), sleep=lambda _: None)
    assert output.exists()
    assert "MONITOR_READY" not in capsys.readouterr().out
