"""Public offline client + real existing IPC rejection, without any Abaqus launch."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from abqjobpilot.abaqus_preview import prepare
from abqjobpilot.execution.models import ExecutionError, digest
from execution_helpers import inventory
from supervisor_helpers import processes
from abaqus_preview_helpers import case


def test_nonrepo_standalone_client_success_rejection_and_same_export(tmp_path):
    source = Path(__file__).parents[1].resolve()
    args = case(tmp_path)
    for name, value in (("project", args["project"]), ("profile", args["runtime_profile"])):
        (tmp_path / (name + ".json")).write_text(json.dumps(value), encoding="utf-8")
    export = tmp_path / "exports"; export.mkdir()
    cwd = tmp_path / "non_repository_cwd"; cwd.mkdir()
    command = [sys.executable, "-B", str(source / "examples/agent_first/abaqus_offline_preview.py"),
               "--source", str(source), "--project", str(tmp_path / "project.json"),
               "--profile", str(tmp_path / "profile.json"), "--engineering-root", args["engineering_root"],
               "--submission-cwd", args["submission_cwd"], "--main-input", "source.inp", "--job", "candidate",
               "--export-root", str(export)]
    before = inventory(tmp_path)
    records = []
    def invoke(argv):
        process = subprocess.Popen(argv, shell=False, close_fds=True, cwd=cwd,
                      env={"SystemRoot": os.environ["SystemRoot"], "TEMP": str(tmp_path), "TMP": str(tmp_path),
                           "PYTHONDONTWRITEBYTECODE": "1"}, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                      creationflags=subprocess.CREATE_NO_WINDOW)
        stdout, stderr = process.communicate(timeout=20)
        assert stderr == b""
        data = json.loads(stdout)
        records.append({"argv": argv, "cwd": str(cwd), "popen_pid": process.pid,
                        "client_pid": data["client_pid"], "exit_code": process.returncode,
                        "retained_popen_wait_completed": process.poll() is not None})
        process.stdout.close(); process.stderr.close(); process._handle.Close()
        return process.returncode, data
    code, success = invoke(command)
    assert code == 0 and success["status"] == "PREVIEW_PREPARED"
    exported = json.loads((export / "preview.json").read_bytes())
    assert exported == success["preview"] and exported["content_digest"] == digest(exported["body"])
    after = inventory(tmp_path)
    assert {k: v for k, v in after.items() if k != "exports/preview.json" and k != "exports\\preview.json"} == before
    # Independent second ordinary client, explicit unsupported input, no output.
    (Path(args["engineering_root"]) / "rejected.inp").write_text("*NODE, INPUT=external.inp\n")
    rejected = list(command); rejected[rejected.index("source.inp")] = "rejected.inp"
    before_reject = inventory(tmp_path)
    code, refusal = invoke(rejected)
    assert code == 2 and refusal["code"] == "UNSUPPORTED_PARAMETER" and refusal["run_created"] is False
    assert inventory(tmp_path) == before_reject
    assert not cwd.is_relative_to(source)
    (tmp_path / "success.json").write_text(json.dumps(success, indent=2), encoding="utf-8")
    (tmp_path / "rejection.json").write_text(json.dumps(refusal, indent=2), encoding="utf-8")
    (tmp_path / "invocations.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    (tmp_path / "file-integrity.json").write_text(json.dumps({"before": before, "after": after,
        "refusal_no_change": True, "private_credentials_created": 0}, indent=2), encoding="utf-8")


def test_existing_public_ipc_rejects_preview_and_never_downgrades(processes, tmp_path_factory):
    h = processes
    # Keep engineering fixtures outside the old Fake harness's no-INP boundary.
    preview = prepare(**case(tmp_path_factory.mktemp("offline_for_ipc"))).to_dict()
    h.owner()
    client = h.client(); health = client.health()
    assert health["backends"] == [{"backend_id": "fake-v1", "version": 1}]
    assert not any("abaqus" in op.lower() for op in health["operations"])
    before = inventory(Path(h.context.root)); gate = client.dispatch_gate()
    for request in (preview, {**preview, "executable": True, "approved": True, "dry_run": False},
                    {**h.requests[0], "plan_id": preview["content_digest"], "plan_digest": preview["content_digest"]},
                    {**h.requests[0], "plan_digest": preview["content_digest"]}):
        with pytest.raises(ExecutionError) as failure: client.submit(request)
        assert failure.value.code in {"INVALID_REQUEST", "NOT_FOUND", "GRANT_SCOPE_MISMATCH"}
    # No prepare/convert/approve or dynamic backend RPC exists.
    for op in ("prepare_abaqus", "convert_preview", "approve", "register_backend"):
        with pytest.raises(ExecutionError) as failure: client.call(op, {"preview": preview})
        assert failure.value.code == "UNKNOWN_OPERATION"
    assert inventory(Path(h.context.root)) == before and client.dispatch_gate() == gate
    assert client.events() == []
