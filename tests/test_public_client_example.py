"""The example runs without pytest imports/fixtures/SQL in its business flow."""

import json
import os
from pathlib import Path
import subprocess
import sys

from abqjobpilot.execution.diagnostics import report_bytes
from abqjobpilot.execution.models import digest
from supervisor_helpers import read_json


def test_previous_v2_report_allowed_validation_source_remains_readable():
    # Preserve the prior envelope's accepted enum even though the normal R7
    # process path did not emit Fake reconciliation validations.
    source = Path(__file__).resolve().parents[1]
    report = read_json(source / "tests/fixtures/synthetic/diagnostic_v2.json")
    assert report["body"]["facts"]["validations"]
    report["body"]["facts"]["validations"][0]["source"] = "explicit_reconciliation"
    report["content_digest"] = digest(report["body"])
    assert json.loads(report_bytes(report)) == report


def test_standalone_operator_and_two_public_clients_from_nonrepo_cwd(tmp_path):
    source = Path(__file__).resolve().parents[1]
    root = tmp_path / "standalone_demo"
    command = [sys.executable, "-B", str(source / "examples/agent_first/operator_demo.py"),
               "--source", str(source), "--root", str(root)]
    # The operator owns all child cleanup. Its independent 90s control deadline
    # bounds a failed invocation; no pytest fixture participates in the workflow.
    process = subprocess.Popen(command, cwd=str(tmp_path), shell=False, close_fds=True,
                  env={"SystemRoot": os.environ["SystemRoot"], "TEMP": str(tmp_path), "TMP": str(tmp_path),
                       "PYTHONDONTWRITEBYTECODE": "1"}, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                  creationflags=subprocess.CREATE_NO_WINDOW)
    stdout, stderr = process.communicate(timeout=120)
    assert process.returncode == 0, stderr.decode()
    assert stdout == stderr == b""
    evidence = read_json(root / "workflow-evidence.json")
    a = read_json(root / "client_session/accepted.json")
    b = read_json(root / "client_session/complete.json")
    assert len({evidence[k] for k in ("owner_pid", "client_A_pid", "client_B_pid")}) == 3
    assert a["run_id"] == b["run_id"] == evidence["run_id"] and b["replayed"] and not a["replayed"]
    assert evidence["launch_attempts"] == 1 and len(evidence["os_verified_members"]) == 4
    assert len(evidence["service_recorded_exits"]) == 4 and all(e["exit_code"] == 0 for e in evidence["service_recorded_exits"])
    assert evidence["original_receipt_preserved"] and evidence["client_import_and_execution_guard"] and evidence["recent_unchanged"]
    assert not Path(evidence["non_repository_cwd"]).is_relative_to(source)
    assert read_json(root / "control/client-exit-owner-continues.json")["worker_exit_not_yet_observed"]
    assert read_json(root / "client_session/rejection.json")["code"] == "GRANT_REQUIRED"
    assert b["run"] == {"execution": "FINISHED", "backend_outcome": "COMPLETED", "process_observation": "EXIT_OBSERVED",
                        "exit_verification": "VERIFIED", "artifact_validation": "VALID", "solver_conclusion": "NOT_RUN", "reconciliation": "NONE"}
    assert len(b["validation_records"]) == 2
    assert sum(v["source"] == "explicit_client_validation" for v in b["validation_records"]) == 1
    report = read_json(root / "exports/diagnostic.json")
    assert digest(report["body"]) == b["export_content_digest"] == report["content_digest"]
    assert len(report_bytes(report)) <= 131072 and report["body"]["view"] == b["diagnostic_view"]
    assert report["body"]["disclosure"]["artifact_bytes_included"] is False
    assert report["body"]["disclosure"]["artifacts_revalidated_now"] is False
    for directory in (root / "client_session", root / "exports"):
        text = "".join(p.read_text(encoding="utf-8") for p in directory.glob("*.json"))
        assert '"management_grant_id"' not in text and '"grant_id"' not in text and '"credential"' not in text
        assert str(root) not in text and "image_path" not in text
    cleanup = read_json(root / "cleanup.json")
    assert cleanup["all_children_waited"] and cleanup["all_handles_closed"] and cleanup["cleanup_errors"] == []
    assert cleanup["remaining_private_files"] == 0 and not list((root / "operator_private").iterdir())
    assert all(r["exit"] is not None and r["handle_closed"] for r in read_json(root / "lifecycle.json"))
    (tmp_path / "example-invocation.json").write_text(json.dumps({"argv": command, "cwd": str(tmp_path), "returncode": process.returncode}), encoding="utf-8")
