"""Fixed plans for one non-executable TXT fixture operation."""

import os
import stat

from .delegated_grant import EXECUTE, input_root, plan_resources
from .models import (CANONICAL, RESOURCES, ConfigSnapshot, ExecutionPlan, JobSpec,
                     bytes_digest, digest, fields, identifier, integer, now, require, text)
from .paths import confined


def configuration(snapshot):
    require(type(snapshot) is ConfigSnapshot, "INVALID_REQUEST", "Expected ConfigSnapshot")
    value = snapshot.to_dict()
    fields(value, ("config_revision", "values"))
    integer(value["config_revision"], 1)
    fields(value["values"], ("label",))
    text(value["values"]["label"])
    value.update(source="fixture_configuration", defaulted_fields=[], canonicalization=CANONICAL)
    return {**value, "digest": digest(value)}


def input_manifest(context, refs, *, delegated=False):
    require(type(refs) is list and 0 < len(refs) <= 8, "INVALID_REQUEST", "One to eight TXT fixture inputs required")
    result = []
    root = input_root(context) if delegated else context.test_root
    for ref in refs:
        require(type(ref) is str, "INVALID_REQUEST", "Input path must be a string")
        path = confined(root, ref, exists=True)
        require(path.is_file() and path.suffix.lower() == ".txt", "INVALID_REQUEST", "Only TXT fixtures are supported")
        require(path.stat().st_size <= 65536, "RESOURCE_LIMIT", "Fixture exceeds 64 KiB")
        with path.open("rb") as stream:
            if delegated:
                original = os.fstat(stream.fileno())
                require(stat.S_ISREG(original.st_mode) and original.st_nlink == 1,
                        "OUTPUT_SCOPE_VIOLATION", "Delegated fixtures must be unshared regular files")
            content = stream.read(65537)
            if delegated:
                current = confined(root, path, exists=True).stat()
                require(original.st_dev == current.st_dev and original.st_ino == current.st_ino
                        and original.st_mtime_ns == current.st_mtime_ns and original.st_size == current.st_size
                        and current.st_nlink == 1, "PLAN_STALE", "Delegated fixture changed during capture")
        require(len(content) <= 65536, "RESOURCE_LIMIT", "Fixture exceeds 64 KiB")
        result.append({"path": str(path), "size": len(content), "digest": bytes_digest(content)})
    return result


def prepare_plan(context, spec, config, expires_at, *, delegated_resources=None, candidate=None, delegated_execution=None):
    require(type(spec) is JobSpec, "INVALID_REQUEST", "Expected JobSpec")
    value = spec.to_dict()
    fields(value, ("job_id", "revision", "project_id", "project_instance_id", "input_refs", "resources", "metadata"))
    text(value["job_id"])
    integer(value["revision"], 1)
    require(value["project_id"] == context.project_id and value["project_instance_id"] == context.project_instance_id,
            "PROJECT_IDENTITY_MISMATCH", "Job belongs to another Project")
    fields(value["resources"], RESOURCES)
    for amount in value["resources"].values():
        integer(amount)
    require(value["resources"] == RESOURCES, "RESOURCE_LIMIT", "Only the fixed Fake resource policy is supported")
    require(type(value["metadata"]) is dict, "INVALID_REQUEST", "metadata must be an object")
    integer(expires_at)
    require(expires_at > now(), "PLAN_EXPIRED", "Plan must expire in the future")
    delegated = delegated_resources is not None
    if delegated_execution is not None:
        require(delegated and candidate is None and delegated_execution == EXECUTE,
                "DELEGATED_SCOPE_MISMATCH", "Delegated execution requires the fixed TXT Fake Plan")
    if delegated:
        plan_resources(delegated_resources)
    if candidate is not None:
        from .dynamic_inp import recheck

        require(delegated, "TEST_SCOPE_REQUIRED", "INP candidates require delegated TEST_ONLY admission")
        manifest = recheck(context, candidate)
        require(value["input_refs"] == [item["path"] for item in manifest],
                "INPUT_DECLARATION_MISMATCH", "Job inputs must match the exact candidate manifest")
    else:
        manifest = input_manifest(context, value["input_refs"], delegated=delegated)
    plan = {"plan_id": identifier("plan"), "job_id": value["job_id"], "job_revision": value["revision"],
            "job_spec": value, "project_instance_id": context.project_instance_id,
            "context_digest": context.context_digest,
            "input_manifest": manifest,
            "config_snapshot": config, "backend_id": "fake-v1", "backend_version": 1,
            "phases": ["FAKE"], "action": "emit_fixture_result", "resources": dict(RESOURCES),
            "output_policy": {"root": context.runtime_root, "template": "fake_runs/{run_id}/result.json",
                              "overwrite": False},
            "validation_policy": "fake-result-v1", "expires_at": expires_at,
            "canonicalization": CANONICAL}
    if delegated:
        plan["delegated_admission"] = delegated_resources
    if delegated_execution is not None:
        plan["delegated_execution"] = delegated_execution
    if candidate is not None:
        plan["dynamic_inp"] = candidate
    return ExecutionPlan.from_dict({**plan, "plan_digest": digest(plan)})


def check_plan(context, plan, current_config, *, process_binding=None, pin_scope=None):
    original = dict(plan)
    stored_digest = original.pop("plan_digest", None)
    require(stored_digest == digest(original), "PLAN_STALE", "Plan digest does not match stored content")
    require(plan["context_digest"] == context.context_digest
            and plan["project_instance_id"] == context.project_instance_id,
            "PROJECT_IDENTITY_MISMATCH", "Plan context changed")
    if process_binding is None:
        require(plan["backend_id"] == "fake-v1" and plan["action"] == "emit_fixture_result"
                and plan["validation_policy"] == "fake-result-v1", "TEST_GRANT_ONLY", "Only fixed Fake operation is supported")
    else:
        require(plan["backend_id"] == "python-process-fixture-v1" and plan["backend_version"] == 1
                and plan["action"] == "launch_fixed_python_fixture" and plan["phases"] == ["PROCESS_FIXTURE"]
                and plan["validation_policy"] == "process-fixture-result-v1"
                and plan["process_fixture"] == process_binding and plan["resources"] == RESOURCES
                and plan["output_policy"] == {"root": context.runtime_root,
                    "template": "process_runs/{run_id}/result.json", "overwrite": False},
                "PLAN_STALE", "Fixed process policy differs")
    require(plan["expires_at"] > now(), "PLAN_EXPIRED", "Plan expired")
    require(plan["config_snapshot"] == current_config, "PLAN_STALE", "Configuration changed")
    if "dynamic_inp" in plan:
        from .dynamic_inp import recheck

        require(process_binding is None and "delegated_admission" in plan, "TEST_SCOPE_REQUIRED",
                "INP candidates are admission-only")
        manifest = recheck(context, plan["dynamic_inp"], pin_scope=pin_scope)
        require(plan["job_spec"]["input_refs"] == [item["path"] for item in manifest],
                "INPUT_DECLARATION_MISMATCH", "Plan references differ from the candidate")
    else:
        manifest = input_manifest(context, plan["job_spec"]["input_refs"], delegated="delegated_admission" in plan)
    require(manifest == plan["input_manifest"],
            "PLAN_STALE", "Fixture input content changed")
