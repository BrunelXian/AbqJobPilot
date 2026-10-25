"""Fixed plans for one non-executable TXT fixture operation."""

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


def input_manifest(context, refs):
    require(type(refs) is list and 0 < len(refs) <= 8, "INVALID_REQUEST", "One to eight TXT fixture inputs required")
    result = []
    for ref in refs:
        require(type(ref) is str, "INVALID_REQUEST", "Input path must be a string")
        path = confined(context.test_root, ref, exists=True)
        require(path.is_file() and path.suffix.lower() == ".txt", "INVALID_REQUEST", "Only TXT fixtures are supported")
        require(path.stat().st_size <= 65536, "RESOURCE_LIMIT", "Fixture exceeds 64 KiB")
        with path.open("rb") as stream:
            content = stream.read(65537)
        require(len(content) <= 65536, "RESOURCE_LIMIT", "Fixture exceeds 64 KiB")
        result.append({"path": str(path), "size": len(content), "digest": bytes_digest(content)})
    return result


def prepare_plan(context, spec, config, expires_at):
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
    plan = {"plan_id": identifier("plan"), "job_id": value["job_id"], "job_revision": value["revision"],
            "job_spec": value, "project_instance_id": context.project_instance_id,
            "context_digest": context.context_digest, "input_manifest": input_manifest(context, value["input_refs"]),
            "config_snapshot": config, "backend_id": "fake-v1", "backend_version": 1,
            "phases": ["FAKE"], "action": "emit_fixture_result", "resources": dict(RESOURCES),
            "output_policy": {"root": context.runtime_root, "template": "fake_runs/{run_id}/result.json",
                              "overwrite": False},
            "validation_policy": "fake-result-v1", "expires_at": expires_at,
            "canonicalization": CANONICAL}
    return ExecutionPlan.from_dict({**plan, "plan_digest": digest(plan)})


def check_plan(context, plan, current_config, *, process_binding=None):
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
    require(input_manifest(context, plan["job_spec"]["input_refs"]) == plan["input_manifest"],
            "PLAN_STALE", "Fixture input content changed")
