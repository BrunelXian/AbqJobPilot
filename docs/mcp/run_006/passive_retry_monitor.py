"""Read-only process observation for a manually started Run 006 GUI job.

Run this from the ordinary Windows user session. It never launches or stops a job.
Its JSONL output is observational evidence, not a solver-success verdict.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from abqjobpilot.process_identity import (  # noqa: E402
    _process_snapshot, capture_identity, observe_descendants, verify_identity,
)
from abqjobpilot.runtime_coordination import runner_ownership_state  # noqa: E402
from abqjobpilot.status_codes import normalize_status  # noqa: E402
from abqjobpilot.utils import now_iso  # noqa: E402


EXPECTED_PROJECT_ID = "404b80d1-9624-473a-b344-a1415649cf6b"
TERMINAL_STATUSES = frozenset({"COMPLETED", "FAILED", "CANCELLED", "SKIPPED"})
NAMED_CANDIDATES = {"cmd.exe", "smalauncher.exe", "smapython.exe", "pre.exe",
                    "package.exe", "standard.exe", "explicit.exe"}
CONFLICT_CANDIDATES = NAMED_CANDIDATES - {"cmd.exe"}
OBSERVED_STATUSES = frozenset({"QUEUED", "RUNNING", "COMPLETED", "FAILED"})
OUTPUT_SUFFIXES = (".sta", ".msg", ".dat", ".log", ".lck", ".odb",
                   ".sim", ".res", ".prt", ".mdl")
MAX_OUTPUT_BYTES = 8_000_000
DISK_WARNING_BYTES = 450_000_000


def _read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def _path_key(value: str | Path | None) -> str | None:
    if not isinstance(value, (str, Path)) or not str(value):
        return None
    try:
        return os.path.normcase(str(Path(value).resolve()))
    except (OSError, ValueError):
        return None


def queue_identity_state(runtime: Path, queue_id: str, inp: Path, *, initial: bool) -> dict:
    jobs = None
    try:
        jobs = _read_json(runtime / "queue.json").get("jobs")
    except (OSError, ValueError) as exc:
        reason = f"queue read failed: {type(exc).__name__}"
    else:
        reason = None
    if not isinstance(jobs, list) or not all(isinstance(job, dict) for job in jobs):
        reason = reason or "queue jobs are not a list of records"
        jobs = []
    matching_inp = [job for job in jobs if _path_key(job.get("inp_path")) == _path_key(inp)]
    matching_id = [job for job in jobs if job.get("queue_id") == queue_id]
    target = matching_id[0] if len(matching_id) == 1 else None
    if reason is None:
        if len(matching_id) != 1:
            reason = "expected queue_id is missing or duplicated"
        elif len(matching_inp) != 1 or matching_inp[0] is not target:
            reason = "queue_id and --inp do not identify the same unique record"
        elif target.get("job_name") != inp.stem:
            reason = "job_name changed or does not match the INP"
        elif _path_key(target.get("work_dir")) != _path_key(inp.parent):
            reason = "working directory changed or does not match the INP"
        elif target.get("cpus") != 1 or target.get("gpus") != 0:
            reason = "CPU/GPU settings changed or differ from 1/0"
        elif initial and target.get("status") != "QUEUED":
            reason = "target must initially be QUEUED"
        elif not initial and normalize_status(target.get("status")) not in OBSERVED_STATUSES:
            reason = "target status is not an expected execution transition"
        elif any(job is not target and normalize_status(job.get("status")) not in TERMINAL_STATUSES
                 for job in jobs):
            reason = "another pending, active or unconfirmed queue record exists"
    return {"state": "OK" if reason is None else "IDENTITY_MISMATCH",
            "reason": reason, "expected_queue_id": queue_id, "expected_inp": str(inp.resolve()),
            "actual_matching_count": len(matching_inp),
            "actual_queue_ids": [job.get("queue_id") for job in jobs],
            "actual_inp_paths": [job.get("inp_path") for job in jobs],
            "actual_statuses": [job.get("status") for job in jobs],
            "target_status": target.get("status") if target is not None else None}


def validate_fixture(project: Path, inp: Path, queue_id: str, *, check_only: bool = False) -> Path:
    manifest = _read_json(project / "project.json")
    if manifest.get("project_id") != EXPECTED_PROJECT_ID:
        raise ValueError("Project identity does not match this Run 006 fixture")
    runtime = project / "runtime"
    state = queue_identity_state(runtime, queue_id, inp, initial=True)
    if state["state"] != "OK":
        raise ValueError(json.dumps(state, ensure_ascii=False))
    if not inp.is_file() or inp.parent.resolve().is_relative_to(project.resolve()):
        raise ValueError("INP must exist outside the Project metadata directory")
    if _read_json(runtime / "live_status.json").get("phase") != "IDLE":
        raise ValueError("runtime is not confirmed idle")
    owner = runner_ownership_state(runtime)["state"]
    if owner not in {"ABSENT", "STALE"}:
        raise ValueError(f"QueueRunner ownership is {owner}; monitor requires no active runner")
    return runtime


def _file_state(inp: Path) -> dict:
    result = {}
    for path in (inp, *(inp.with_suffix(suffix) for suffix in OUTPUT_SUFFIXES)):
        try:
            stat = path.stat()
        except FileNotFoundError:
            result[path.suffix.lower()] = {"exists": False}
        except OSError as exc:
            result[path.suffix.lower()] = {"state": "UNCONFIRMED", "error": type(exc).__name__}
        else:
            result[path.suffix.lower()] = {"exists": True, "size_bytes": stat.st_size,
                                            "mtime_ns": stat.st_mtime_ns}
    return result


def _engineering_size(directory: Path) -> int | None:
    try:
        return sum(path.stat().st_size for path in directory.iterdir() if path.is_file())
    except OSError:
        return None


def collect_observation(runtime: Path, queue_id: str, inp: Path,
                        known: dict[tuple[int, int], dict]) -> dict:
    result = {"observed_at": now_iso(), "queue_id": queue_id,
              "live_phase": "UNCONFIRMED", "launcher": None,
              "descendant_scan": None, "named_candidates": [],
              "tracked_processes": [], "files": _file_state(inp),
              "engineering_bytes": _engineering_size(inp.parent)}
    result["disk_budget_warning"] = (result["engineering_bytes"] is not None
                                     and result["engineering_bytes"] >= DISK_WARNING_BYTES)
    try:
        live = _read_json(runtime / "live_status.json")
        result["live_phase"] = live.get("phase", "UNCONFIRMED")
        evidence = live.get("process_identity")
        if isinstance(evidence, dict) and evidence.get("queue_id") == queue_id:
            launcher = evidence.get("launcher")
            if isinstance(launcher, dict):
                result["launcher"] = launcher
                _remember(known, launcher)
                result["launcher_state"] = verify_identity(launcher)["state"]
                if result["launcher_state"] == "CONFIRMED_ACTIVE":
                    scan = observe_descendants(launcher)
                    result["descendant_scan"] = scan["state"]
                    result["descendants"] = scan["children"][:64]
                    for child in scan["children"][:64]:
                        _remember(known, child)
            for child in evidence.get("observed_children", [])[:64]:
                if isinstance(child, dict):
                    _remember(known, child)
        elif evidence is not None:
            result["live_identity_note"] = "identity belongs to another queue or is invalid"
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        result["live_error"] = type(exc).__name__

    rows = _process_snapshot()
    if rows is None:
        result["named_scan"] = "UNCONFIRMED"
    else:
        result["named_scan"] = "OK"
        for row in sorted(rows, key=lambda item: item["exe"].casefold() == "cmd.exe"):
            if row["exe"].casefold() not in NAMED_CANDIDATES:
                continue
            identity = capture_identity(row["pid"])
            candidate = {"image_name": row["exe"], "parent_pid": row["parent_pid"],
                         "association": "name_only_unconfirmed", **identity}
            result["named_candidates"].append(candidate)
            _remember(known, candidate)
            if len(result["named_candidates"]) >= 64:
                break
    for identity in list(known.values())[:128]:
        result["tracked_processes"].append({"pid": identity["pid"],
                                            "creation_time_100ns": identity["creation_time_100ns"],
                                            "executable_path": identity["executable_path"],
                                            "state": verify_identity(identity)["state"]})
    return result


def _remember(known: dict[tuple[int, int], dict], identity: dict) -> None:
    if (isinstance(identity.get("pid"), int)
            and isinstance(identity.get("creation_time_100ns"), int)
            and isinstance(identity.get("executable_path"), str)
            and identity["executable_path"]):
        known[(identity["pid"], identity["creation_time_100ns"])] = identity


def _write_sample(output, sample: dict, written_bytes: int) -> int:
    line = json.dumps(sample, ensure_ascii=False, separators=(",", ":")) + "\n"
    line_bytes = len(line.encode("utf-8"))
    if written_bytes + line_bytes > MAX_OUTPUT_BYTES:
        raise ValueError("observation reached the 8 MB evidence cap")
    output.write(line)
    output.flush()
    return written_bytes + line_bytes


def run_monitor(runtime: Path, queue_id: str, inp: Path, output_path: Path,
                *, duration: int, interval: float, clock=time.monotonic,
                sleep=time.sleep) -> tuple[int, int, str | None]:
    known: dict[tuple[int, int], dict] = {}
    count = 0
    written_bytes = 0
    ready = False
    stop_reason = None
    with output_path.open("x", encoding="utf-8") as output:
        start = clock()
        while clock() - start < duration:
            if count == 1 and not ready:
                print("MONITOR_READY " + json.dumps({
                    "queue_id": queue_id, "project_id": EXPECTED_PROJECT_ID,
                    "timestamp": now_iso(), "evidence_file": str(output_path.resolve()),
                    "sample_interval": interval}), flush=True)
                ready = True
            sample = collect_observation(runtime, queue_id, inp, known)
            sample["queue_identity"] = queue_identity_state(runtime, queue_id, inp, initial=False)
            if sample.get("named_scan") != "OK":
                sample["monitor_error"] = "Windows process snapshot unavailable"
            written_bytes = _write_sample(output, sample, written_bytes)
            count += 1
            if sample["queue_identity"]["state"] != "OK":
                stop_reason = "queue identity changed; see queue_identity in JSONL"
                break
            if sample.get("monitor_error"):
                stop_reason = sample["monitor_error"]
                break
            if sample["disk_budget_warning"]:
                stop_reason = "engineering directory reached 450 MB; no process was terminated"
                break
            sleep(interval)
    if not ready and stop_reason is None:
        stop_reason = "monitor ended before entering a second sampling iteration"
    return count, len(known), stop_reason


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--inp", type=Path, required=True)
    parser.add_argument("--queue-id", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--duration", type=int, default=600)
    parser.add_argument("--interval", type=float, default=0.2)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.duration <= 600 or not 0.1 <= args.interval <= 1.0:
        parser.error("duration must be 1-600 seconds; interval 0.1-1.0 seconds")
    try:
        runtime = validate_fixture(args.project, args.inp, args.queue_id,
                                   check_only=args.check_only)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if "codexsandbox" in getpass.getuser().casefold():
        parser.error("run the monitor from the ordinary Windows user session, not CodexSandbox")
    initial_rows = _process_snapshot()
    named_before = ([row for row in initial_rows if row["exe"].casefold() in CONFLICT_CANDIDATES]
                    if initial_rows is not None else None)
    prior_outputs = [suffix for suffix in OUTPUT_SUFFIXES if args.inp.with_suffix(suffix).exists()]
    if args.check_only:
        print(json.dumps({"project_id": EXPECTED_PROJECT_ID, "queue_id": args.queue_id,
                          "user": getpass.getuser(), "process_snapshot_available": initial_rows is not None,
                          "preexisting_named_candidates": named_before,
                          "preexisting_job_outputs": prior_outputs}))
        return 0
    if named_before is None or named_before:
        parser.error("process snapshot unavailable or potentially conflicting Abaqus processes already exist")
    if prior_outputs:
        parser.error(f"same-name job outputs already exist: {prior_outputs}")
    if args.output is None or args.output.resolve().is_relative_to(args.project.resolve()):
        parser.error("provide --output outside the Project metadata directory")
    try:
        count, known_count, stop_reason = run_monitor(
            runtime, args.queue_id, args.inp, args.output,
            duration=args.duration, interval=args.interval)
    except KeyboardInterrupt:
        print("Observation stopped by user; no process was terminated.")
        return 1
    except (OSError, ValueError) as exc:
        parser.error(f"monitor failed: {exc}")
    print(f"Samples: {count}; observed identities: {known_count}; output: {args.output}")
    if stop_reason:
        print(f"Monitor stopped: {stop_reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
