"""Pure identity and bounded output contract, without process creation capability."""

from pathlib import Path

from .paths import confined

BACKEND = "python-process-fixture-v1"
ACTION = "launch_fixed_python_fixture"
SCENARIOS = ("normal", "launcher_early", "result_wait", "nonzero", "invalid_result", "managed_tree", "managed_burst")
MEMBERSHIP_CONTRACT = "fixed-windows-members-v1"
EXIT_CONTRACT = "recorded-os-exit-v1"
REQUIRED_ROLES = ("launcher_transport", "launcher", "worker_transport", "worker")


def directory(context, run):
    return confined(context.test_root, Path(context.runtime_root) / "process_runs" / run["run_id"])


def expected_result(context, plan, run):
    return {"format": "process-fixture-result-v1", "backend_id": BACKEND, "backend_version": 1,
            "simulation": True, "project_instance_id": context.project_instance_id,
            "run_id": run["run_id"], "phase_attempt_id": run["phase_attempt_id"], "plan_digest": plan["plan_digest"],
            "fixture_digest": plan["process_fixture"]["fixture_digest"], "scenario": plan["process_fixture"]["scenario"],
            "input_digests": [v["digest"] for v in plan["input_manifest"]]}
