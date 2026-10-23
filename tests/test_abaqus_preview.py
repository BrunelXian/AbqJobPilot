"""Run009 lexical boundary, read consistency, no-execution and export contracts."""

import ast
import json
import os
from pathlib import Path

import pytest

from abqjobpilot.abaqus_preview import AbaqusPlanPreview, prepare, inspect, export_preview
from abqjobpilot.abaqus_preview import inputs, preview as module
from abqjobpilot.execution.models import ExecutionError, digest, now
from execution_helpers import guard_environment, harness, inventory
from abaqus_preview_helpers import case, MODEL, STEP


def error(code, call):
    with pytest.raises(ExecutionError) as caught:
        call()
    assert caught.value.code == code
    return caught.value


def test_stable_body_and_distinct_observation_no_filesystem_writes(tmp_path, monkeypatch):
    args = case(tmp_path)
    before = inventory(tmp_path)
    monkeypatch.setattr(module, "now", lambda: 100)
    a = prepare(**args)
    monkeypatch.setattr(module, "now", lambda: 200)
    b = prepare(**args)
    assert inspect(a)["body"] == inspect(b)["body"]
    assert inspect(a)["content_digest"] == inspect(b)["content_digest"]
    assert inspect(a)["observation"] != inspect(b)["observation"]
    assert inventory(tmp_path) == before
    assert not (Path(args["engineering_root"]) / "scratch").exists()
    assert inspect(a)["body"]["checks"] == module.STATUS


@pytest.mark.parametrize("change", ["main_bytes", "dependency_bytes", "memory", "wall", "profile_version", "profile_id",
                                   "scratch", "job", "project", "instance", "input_name", "root"])
def test_semantic_changes_change_digest(tmp_path, change):
    args = case(tmp_path, contents="*INCLUDE, INPUT=part.inp\n" + STEP)
    root = Path(args["engineering_root"])
    (root / "part.inp").write_text(MODEL, encoding="ascii")
    a = prepare(**args).to_dict()["content_digest"]
    if change == "main_bytes": (root / "source.inp").write_text("**changed\n*INCLUDE, INPUT=part.inp\n" + STEP)
    elif change == "dependency_bytes": (root / "part.inp").write_text(MODEL.replace("210000", "200000"))
    elif change == "memory": args["runtime_profile"]["memory_mb"] = 1024
    elif change == "wall": args["runtime_profile"]["wall_seconds"] = 120
    elif change == "profile_version": args["runtime_profile"]["profile_version"] = 2
    elif change == "profile_id": args["runtime_profile"]["profile_id"] = "other"
    elif change == "scratch": args["runtime_profile"]["scratch_relative"] = "other_scratch"
    elif change == "job": args["job_name"] = "other_job"
    elif change == "project": args["project"]["project_id"] = "other"
    elif change == "instance": args["project"]["project_instance_id"] = "other"
    elif change == "input_name":
        (root / "source.inp").rename(root / "other.inp"); args["main_input"] = "other.inp"
    elif change == "root":
        other = tmp_path / "other"; other.mkdir()
        for p in root.iterdir(): (other / p.name).write_bytes(p.read_bytes())
        args["engineering_root"] = args["submission_cwd"] = str(other)
    assert prepare(**args).to_dict()["content_digest"] != a


def test_include_is_submission_root_not_including_parent_and_case_rules(tmp_path):
    args = case(tmp_path, contents="*include, input=sub/part.inp\n" + STEP.lower())
    root = Path(args["engineering_root"]); (root / "sub").mkdir()
    (root / "sub/part.inp").write_text("*INCLUDE, INPUT=model.inp\n")
    (root / "sub/model.inp").write_text(MODEL)
    error("INPUT_NOT_FOUND", lambda: prepare(**args))  # no parent fallback
    (root / "model.inp").write_text(MODEL)
    report = inspect(prepare(**args))["body"]
    assert [x["reference"] for x in report["input_manifest"]] == ["source.inp", "sub/part.inp", "model.inp"]
    assert all(e["base"] == "submission_cwd" for e in report["include_edges"])


@pytest.mark.parametrize("bad,code", [
    ("*NOD\n1,0,0,0\n", "UNSUPPORTED_KEYWORD"),
    ("*NODE, INPUT=outside.inp\n1,0,0,0\n", "UNSUPPORTED_PARAMETER"),
    ("*ELEMENT, TYPE=T3D2, ELSET=A, FILE=other\n1,1,2\n", "UNSUPPORTED_PARAMETER"),
    ("*INCLUDE, INPUT=a.inp, PASSWORD=secret\n", "UNSUPPORTED_PARAMETER"),
    ('*INCLUDE, INPUT="a.inp"\n', "UNSUPPORTED_SYNTAX"),
    ("*NODE,\n INPUT=a.inp\n", "UNSUPPORTED_SYNTAX"),
    ("*PARAMETER\nfoo=1\n", "UNSUPPORTED_KEYWORD"),
    ("*RESTART, READ=YES\n", "UNSUPPORTED_KEYWORD"),
    ("*INITIAL CONDITIONS, TYPE=STRESS, FILE=old\n", "UNSUPPORTED_KEYWORD"),
    ("*USER MATERIAL\n", "UNSUPPORTED_KEYWORD"),
    ("*INCLUDE, INPUT=a.inp, INPUT=b.inp\n", "UNSUPPORTED_PARAMETER"),
    ("*NODE\n1,<x>,0,0\n", "UNSUPPORTED_DATA"),
    ("*NODE\n1,0,0,\n", "UNSUPPORTED_DATA"),
    ("*NODE\n1,0,0,0,4\n", "UNSUPPORTED_DATA"),
    ("*NODE\n1,0,0,0\n\n", "UNSUPPORTED_SYNTAX"),
    (" ** comment\n", "UNSUPPORTED_KEYWORD"),
    ("*STEP, NLGEOM=YES\n", "UNSUPPORTED_PARAMETER"),
    ("*STATIC, RIKS=YES\n0.1,1,1e-5,0.1\n", "UNSUPPORTED_PARAMETER"),
    ("*NODE\n1,NaN,0,0\n", "UNSUPPORTED_DATA"),
    ("*HEADING\n<script>\n", "UNSUPPORTED_DATA"),
])
def test_unsupported_grammar_never_claims_coverage(tmp_path, bad, code):
    args = case(tmp_path, contents=bad + STEP)
    error(code, lambda: prepare(**args))


@pytest.mark.parametrize("payload", [b"\xff\n", b"*HEADING\nno newline", b"*HEADING\ntext\rmore\n", b"**" + b"x" * 256 + b"\n", b"**\tcomment\n"])
def test_encoding_line_and_control_limits(tmp_path, payload):
    args = case(tmp_path); (Path(args["engineering_root"]) / "source.inp").write_bytes(payload)
    error("UNSUPPORTED_SYNTAX", lambda: prepare(**args))


@pytest.mark.parametrize("path", ["../outside.inp", "/root.inp", "C:/root.inp", "C:root.inp", "\\\\host\\file.inp",
                                  "a.inp:stream", "./a.inp", "dir//a.inp", "NUL.inp", "dir./a.inp", "a file.inp", "$INPUT.inp", "a.txt"])
def test_unsafe_references_refused_before_read(tmp_path, monkeypatch, path):
    args = case(tmp_path, contents="*INCLUDE, INPUT=" + path + "\n" + STEP)
    original = inputs._open_pinned
    accessed = []
    def record(p, **kw):
        accessed.append(str(p))
        assert kw.get("is_directory") or p.name == "source.inp"
        return original(p, **kw)
    monkeypatch.setattr(inputs, "_open_pinned", record)
    error("UNSUPPORTED_PATH", lambda: prepare(**args))
    assert len(accessed) == 2


@pytest.mark.parametrize("mode", ["missing", "cycle", "duplicate", "depth", "count", "file_bytes", "total_bytes", "blocks"])
def test_missing_cycles_and_limits(tmp_path, mode):
    args = case(tmp_path); root = Path(args["engineering_root"])
    expected = "LIMIT_EXCEEDED"
    if mode == "missing": content = "*INCLUDE, INPUT=absent.inp\n"; expected = "INPUT_NOT_FOUND"
    elif mode == "cycle": content = "*INCLUDE, INPUT=source.inp\n"; expected = "INPUT_CYCLE"
    elif mode == "duplicate":
        (root / "a.inp").write_text(MODEL)
        content = "*INCLUDE, INPUT=a.inp\n*INCLUDE, INPUT=a.inp\n"; expected = "INPUT_DUPLICATE"
    elif mode == "depth":
        for i in range(6): (root / f"a{i}.inp").write_text(f"*INCLUDE, INPUT=a{i+1}.inp\n")
        content = "*INCLUDE, INPUT=a0.inp\n"
    elif mode in ("count", "total_bytes"):
        n = 8 if mode == "count" else 5
        for i in range(n): (root / f"a{i}.inp").write_text("**" + "x" * 200 + "\n" if mode == "count" else ("**" + "x" * 200 + "\n") * 300)
        content = "".join(f"*INCLUDE, INPUT=a{i}.inp\n" for i in range(n))
    elif mode == "file_bytes": content = "**x\n" * 20000
    else: content = "*NODE\n1,0,0,0\n" * 513
    (root / "source.inp").write_text(content + STEP)
    error(expected, lambda: prepare(**args))


@pytest.mark.parametrize("field,value,code", [("cpus", 2, "RESOURCE_LIMIT"), ("cpus", True, "INVALID_REQUEST"),
        ("gpus", 1, "RESOURCE_LIMIT"), ("memory_mb", 4097, "RESOURCE_LIMIT"), ("wall_seconds", 0, "RESOURCE_LIMIT"),
        ("declared_version", "2025", "UNSUPPORTED_PROFILE"), ("product", "Abaqus/Explicit", "UNSUPPORTED_PROFILE"),
        ("phase", "datacheck", "UNSUPPORTED_PROFILE"), ("scratch_relative", "../scratch", "UNSUPPORTED_PATH"),
        ("arbitrary_args", [], "INVALID_REQUEST"), ("command", "secret", "INVALID_REQUEST"),
        ("env", {}, "INVALID_REQUEST"), ("user", "a.for", "INVALID_REQUEST"), ("queue", "remote", "INVALID_REQUEST")])
def test_profile_whitelist(tmp_path, field, value, code):
    args = case(tmp_path); args["runtime_profile"][field] = value
    error(code, lambda: prepare(**args))


def test_output_scope_is_physical_directory_and_job_not_project(tmp_path):
    args = case(tmp_path); a = inspect(prepare(**args))
    args["project"] = {"project_id": "another", "project_instance_id": "another_instance"}
    b = inspect(prepare(**args))
    assert a["body"]["output"]["candidate_key"] == b["body"]["output"]["candidate_key"]
    assert a["content_digest"] != b["content_digest"]
    (Path(args["engineering_root"]) / "candidate.log").write_text("old unrelated output")
    assert inspect(prepare(**args))["body"]["output"]["reservation"] == "NONE"
    assert inspect(prepare(**args))["body"]["output"]["existing_outputs_checked"] is False
    args["job_name"] = "SOURCE"
    error("OUTPUT_INPUT_COLLISION", lambda: prepare(**args))


def test_actual_hardlink_rejected_and_writer_cannot_change_pinned_file(tmp_path, monkeypatch):
    args = case(tmp_path); root = Path(args["engineering_root"])
    os.link(root / "source.inp", root / "alias.inp")
    error("UNSUPPORTED_PATH", lambda: prepare(**args))
    (root / "alias.inp").unlink()
    original = inputs._block
    attempted = []
    def block(*args):
        with pytest.raises(PermissionError): (root / "source.inp").write_bytes(b"changed")
        attempted.append(True)
        return original(*args)
    monkeypatch.setattr(inputs, "_block", block)
    prepare(**args)
    assert attempted and (root / "source.inp").read_text().startswith("*HEADING")


def test_second_pass_detects_unstable_identity(tmp_path, monkeypatch):
    args = case(tmp_path)
    original = inputs._identity; calls = []
    def identity(info):
        calls.append(1)
        return ("changed",) if len(calls) == 3 else original(info)
    monkeypatch.setattr(inputs, "_identity", identity)
    error("INPUT_UNSTABLE", lambda: prepare(**args))


def test_export_uses_original_snapshot_nooverwrite_and_failure_cleanup(tmp_path, monkeypatch):
    args = case(tmp_path); value = prepare(**args); original = inspect(value)
    root = tmp_path / "exports"; root.mkdir()
    (Path(args["engineering_root"]) / "source.inp").write_bytes(b"invalid current contents")
    monkeypatch.setattr(module, "read_inputs", lambda *a: pytest.fail("export must not read inputs"))
    exported = export_preview(value, export_root=str(root), target="one.json")
    assert json.loads((root / "one.json").read_bytes()) == original
    assert exported["content_digest"] == original["content_digest"]
    error("EXPORT_EXISTS", lambda: export_preview(value, export_root=str(root), target="one.json"))
    before = inventory(tmp_path)
    monkeypatch.setattr(os, "fsync", lambda *a: (_ for _ in ()).throw(OSError("SECRET_OS_ERROR")))
    exc = error("PREVIEW_UNAVAILABLE", lambda: export_preview(value, export_root=str(root), target="two.json"))
    assert "SECRET" not in json.dumps(exc.to_dict()) and inventory(tmp_path) == before


@pytest.mark.parametrize("target", ["../a.json", "C:/a.json", "a.json:stream", "NUL.json", "dir/a.json", "a.inp"])
def test_export_path_rejection(tmp_path, target):
    args = case(tmp_path); value = prepare(**args); root = tmp_path / "export"; root.mkdir()
    before = inventory(tmp_path)
    error("UNSUPPORTED_PATH", lambda: export_preview(value, export_root=str(root), target=target))
    assert inventory(tmp_path) == before


def test_inspection_is_offline_bounded_and_not_an_execution_attestation(tmp_path, monkeypatch):
    value = prepare(**case(tmp_path)); data = value.to_dict()
    monkeypatch.setattr(Path, "open", lambda *a, **kw: pytest.fail("inspect must not read files"))
    assert inspect(value) == data
    data["body"]["checks"]["real_execution_capability"] = "AVAILABLE"
    data["content_digest"] = digest(data["body"])
    error("INVALID_PREVIEW", lambda: inspect(AbaqusPlanPreview.from_dict(data)))
    error("LIMIT_EXCEEDED", lambda: inspect(AbaqusPlanPreview(" " * 32769)))


def test_direct_service_and_trusted_issuer_cannot_accept_preview(harness):
    h = harness; args = case(h.root)
    value = prepare(**args); fake = h.plan(); grant = h.grant(fake)
    before = inventory(h.root); counts = h.counts(); gate = h.store.gate()
    error("INVALID_REQUEST", lambda: h.service.prepare(h.context, value, h.config, expires_at=now() + 60))
    error("INVALID_REQUEST", lambda: h.service.submit(h.context, value.to_dict()))
    for grant_id in (grant, "ProcessGrantFixture", None):
        request = h.request(fake, grant_id, plan_id=value.to_dict()["content_digest"], plan_digest=value.to_dict()["content_digest"])
        error("NOT_FOUND", lambda: h.service.submit(h.context, request))
    from abqjobpilot.execution.test_authority import issue_process_execution
    error("NOT_FOUND", lambda: issue_process_execution(h.service, value.to_dict()["content_digest"], expires_at=now()+60))
    assert counts == h.counts() and gate == h.store.gate() and inventory(h.root) == before


def test_offline_dependency_graph_has_no_execution_authority_or_legacy_imports():
    root = Path(__file__).parents[1] / "abqjobpilot/abaqus_preview"
    allowed = {"contextlib", "ctypes", "msvcrt", "os", "pathlib", "re", "stat", "functools", "uuid",
               "abqjobpilot.execution.models", "abqjobpilot.execution.paths", "preview", "inputs"}
    for path in root.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import): assert all(n.name in allowed for n in node.names)
            if isinstance(node, ast.ImportFrom): assert node.module in allowed
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"eval", "exec", "compile", "__import__"}


def test_actual_reparse_input_and_export_refused(tmp_path):
    from test_execution_isolation import _junction
    args = case(tmp_path, contents="*INCLUDE, INPUT=link/part.inp\n" + STEP)
    root = Path(args["engineering_root"]); outside = tmp_path / "outside"; outside.mkdir()
    (outside / "part.inp").write_text(MODEL)
    _junction(root / "link", outside)
    error("OUTPUT_SCOPE_VIOLATION", lambda: prepare(**args))
    (root / "source.inp").write_text(MODEL + STEP)
    preview = prepare(**args)
    _junction(tmp_path / "exports", outside)
    error("OUTPUT_SCOPE_VIOLATION", lambda: export_preview(preview, export_root=str(tmp_path / "exports"), target="a.json"))
    assert not (outside / "a.json").exists()


def test_no_storage_or_validation_access_even_with_existing_store(harness, monkeypatch):
    import sqlite3
    from abqjobpilot.execution.fake_backend import FakeBackend
    from abqjobpilot.execution.process_backend import ProcessBackend
    import abqjobpilot.execution.validation as validation
    h = harness; args = case(h.root); before = inventory(h.root)
    def forbidden(*a, **kw): pytest.fail("offline path crossed execution/storage boundary")
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(FakeBackend, "emit", forbidden)
    monkeypatch.setattr(ProcessBackend, "execute", forbidden)
    monkeypatch.setattr(validation, "validate_artifact", forbidden)
    monkeypatch.setattr(h.store, "transaction", forbidden)
    assert inspect(prepare(**args))["body"]["checks"]["run"] == "NOT_CREATED"
    assert inventory(h.root) == before


def test_recomputed_execution_plan_backend_still_rejected_before_consumption(harness):
    from abqjobpilot.execution.models import ExecutionPlan
    from abqjobpilot.execution.test_authority import issue_process_execution
    from test_process_contract import process_plan
    h = harness
    process = process_plan(h)
    process_grant = h.grant(process, issuer="ProcessGrantFixture", allowed_action="launch_fixed_python_fixture")
    fake = h.plan(); fake_grant = h.grant(fake)
    args = case(h.root); value = prepare(**args).to_dict()
    before = inventory(h.root); counts = h.counts()
    for p, g in ((process, process_grant), (fake, fake_grant)):
        forged = p.to_dict(); forged["backend_id"] = "abaqus-standard"; forged["action"] = "analysis"
        forged.pop("plan_digest"); forged["plan_digest"] = digest(forged)
        error("GRANT_SCOPE_MISMATCH", lambda: h.service.submit(h.context, h.request(ExecutionPlan.from_dict(forged), g)))
        with h.store.read() as c:
            error("TEST_GRANT_ONLY", lambda: h.service._check(c, h.context, forged, g))
    error("NOT_FOUND", lambda: issue_process_execution(h.service, value["content_digest"], expires_at=now()+60))
    assert inventory(h.root) == before and counts == h.counts()


def test_export_race_does_not_overwrite_or_cleanup_someone_elses_file(tmp_path, monkeypatch):
    args = case(tmp_path); value = prepare(**args); root = tmp_path / "exports"; root.mkdir()
    rename = os.rename
    def concurrent(a, b):
        Path(b).write_bytes(b"other writer")
        return rename(a, b)
    monkeypatch.setattr(os, "rename", concurrent)
    error("PREVIEW_UNAVAILABLE", lambda: export_preview(value, export_root=str(root), target="out.json"))
    assert (root / "out.json").read_bytes() == b"other writer" and len(list(root.iterdir())) == 1
