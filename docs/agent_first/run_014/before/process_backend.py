"""Opt-in fixed Python process fixture; never selected by a client command."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from .models import ExecutionError, bytes_digest, canonical_json, fields, now, require
from .ownership import current_process_identity
from .paths import confined, no_reparse
from .process_handles import ProcessReference
from .process_contract import (BACKEND, ACTION, SCENARIOS, MEMBERSHIP_CONTRACT, EXIT_CONTRACT,
                               REQUIRED_ROLES, directory, expected_result)


@dataclass(frozen=True)
class ProcessFixtureConfig:
    interpreter: str
    image: str
    interpreter_digest: str
    image_digest: str
    fixture_digest: str
    max_seconds: int = 40

    @classmethod
    def current(cls):
        actual = current_process_identity()
        return cls(str(Path(sys.executable).resolve()), actual["image_path"],
                   bytes_digest(Path(sys.executable).read_bytes()), bytes_digest(Path(actual["image_path"]).read_bytes()),
                   bytes_digest(Path(__file__).with_name("process_fixture.py").read_bytes()))

    def binding(self, scenario):
        require(scenario in SCENARIOS and type(scenario) is str, "INVALID_REQUEST", "Unsupported fixed test scenario")
        require(type(self.max_seconds) is int and 5 <= self.max_seconds <= 60,
                "RESOURCE_LIMIT", "Fixture lifetime must be 5..60 seconds")
        return {"interpreter": self.interpreter, "image": self.image,
                "interpreter_digest": self.interpreter_digest, "image_digest": self.image_digest,
                "fixture_digest": self.fixture_digest, "scenario": scenario, "max_seconds": self.max_seconds,
                "max_process_members": 4, "argument_policy": "isolated_python_fixture_v1",
                "membership_contract": MEMBERSHIP_CONTRACT, "required_roles": list(REQUIRED_ROLES)}

    def verify(self, binding):
        fields(binding, self.binding("normal"))
        require(binding == self.binding(binding["scenario"]), "PLAN_STALE", "Trusted fixture configuration changed")
        require(str(Path(sys.executable).resolve()) == self.interpreter
                and current_process_identity()["image_path"] == self.image,
                "PLAN_STALE", "Owner interpreter differs from trusted fixture configuration")
        for path, expected in ((Path(self.interpreter), self.interpreter_digest), (Path(self.image), self.image_digest),
                               (Path(__file__).with_name("process_fixture.py"), self.fixture_digest)):
            no_reparse(path)
            require(bytes_digest(path.read_bytes()) == expected, "PLAN_STALE", "Fixed execution object changed")


class ProcessBackend:
    def __init__(self, config):
        require(type(config) is ProcessFixtureConfig, "INVALID_REQUEST", "Explicit trusted test configuration required")
        self.config = config

    def execute(self, context, plan, run, record, checkpoint, authorize_start):
        self.config.verify(plan["process_fixture"])
        root = directory(context, run)
        root.mkdir(parents=True, exist_ok=False)
        manifest = {**{k: run[k] for k in ("run_id", "project_instance_id", "phase_attempt_id")},
                    "plan_digest": plan["plan_digest"], "scenario": plan["process_fixture"]["scenario"],
                    "max_seconds": self.config.max_seconds, "expected_result": expected_result(context, plan, run)}
        with (root / "fixture.json").open("x", encoding="utf-8") as stream:
            stream.write(canonical_json(manifest))
            stream.flush()
            os.fsync(stream.fileno())
        refs, observations, exits = {}, [], []
        process = None
        deadline = time.monotonic() + self.config.max_seconds + 5
        try:
            checkpoint("process:before_create")
            authorize_start()  # Recheck after any startup delay, before the irreversible OS effect.
            # No inherited IPC/auth/DB handles; only Windows system location is required.
            environment = {"SystemRoot": os.environ["SystemRoot"], "PYTHONDONTWRITEBYTECODE": "1"}
            process = subprocess.Popen([self.config.interpreter, "-I", "-S", "-B",
                                        str(Path(__file__).with_name("process_fixture.py").resolve()),
                                        "--role", "launcher", "--directory", str(root)],
                                       shell=False, close_fds=True, cwd=str(root), env=environment,
                                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
            refs["launcher_transport"] = ProcessReference(process.pid)
            require(Path(refs["launcher_transport"].identity["image_path"]) == Path(self.config.interpreter),
                    "PROCESS_IDENTITY_MISMATCH", "Unexpected direct launch image")
            checkpoint("process:after_create")
            for role in ("launcher", "worker_transport", "worker"):
                candidate_path = confined(context.test_root, root / (role + ".json"))
                while not candidate_path.exists():
                    require(time.monotonic() < deadline, "PROCESS_IDENTITY_UNKNOWN", "Identity handshake deadline exceeded")
                    time.sleep(0.01)
                require(candidate_path.stat().st_size <= 4096, "PROCESS_IDENTITY_UNKNOWN", "Oversized identity handshake")
                candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
                require(all(candidate.get(k) == manifest[k] for k in ("run_id", "project_instance_id", "phase_attempt_id", "plan_digest"))
                        and candidate.get("role") == role, "PROCESS_IDENTITY_MISMATCH", "Handshake binding differs")
                refs[role] = ProcessReference(candidate["pid"], candidate)
                expected_image = self.config.image if role in {"launcher", "worker"} else self.config.interpreter
                require(Path(refs[role].identity["image_path"]) == Path(expected_image),
                        "PROCESS_IDENTITY_MISMATCH", "Unexpected fixture process image")
                if role in {"launcher", "worker"}:
                    transport = refs[role + "_transport"].identity["pid"]
                    require(candidate["pid"] == transport or candidate.get("parent_pid") == transport,
                            "PROCESS_IDENTITY_MISMATCH", "Fixture role does not match its launch transport")
                require(refs[role].exit_evidence() is None, "PROCESS_IDENTITY_UNKNOWN", "Fixture exited before owner bound it")
            for role, ref in refs.items():
                observations.append({**ref.identity, "role": role, "identity_status": "VERIFIED", "observed_at": now(),
                                     "execution_object_digest": self.config.fixture_digest,
                                     "image_digest": self.config.image_digest if role in {"launcher", "worker"} else self.config.interpreter_digest})
            binding = {k: run[k] for k in ("project_instance_id", "run_id", "plan_id", "plan_digest",
                       "phase_attempt_id", "owner_id", "owner_epoch")}
            membership = {**binding, "contract": MEMBERSHIP_CONTRACT, "backend_id": BACKEND,
                          "backend_version": 1, "required_roles": list(REQUIRED_ROLES),
                          "basis": "FIXED_FIXTURE_ALL_ROLES_OS_VERIFIED_BEFORE_RELEASE",
                          "fixture_digest": self.config.fixture_digest}
            record("PROCESS_IDENTITIES", process_observation="IDENTITIES_VERIFIED", process_records=observations,
                   process_membership=membership)
            checkpoint("process:after_identity")
            (root / "owner-bound.json").write_text("{}", encoding="utf-8")
            checkpoint("process:after_handoff")
            while len(exits) < len(refs):
                require(time.monotonic() < deadline, "PROCESS_EXIT_UNKNOWN", "No complete exit evidence before deadline")
                for role, ref in refs.items():
                    if any(e["role"] == role for e in exits):
                        continue
                    evidence = ref.exit_evidence()
                    if evidence is not None:
                        checkpoint("process:before_exit_record")
                        exits.append({**next(o for o in observations if o["role"] == role), **evidence,
                                      **binding, "exit_contract": EXIT_CONTRACT})
                        record("PROCESS_EXIT_OBSERVED", process_exits=list(exits),
                               process_observation="EXIT_PARTIAL", exit_verification="PARTIAL")
                time.sleep(0.01)
            process.wait(timeout=2)
            checkpoint("process:after_exit")
            success = all(e["exit_code"] == 0 for e in exits)
            record("PROCESS_COMPLETED", execution="VALIDATING", process_observation="EXIT_OBSERVED",
                   exit_verification="VERIFIED", backend_outcome="COMPLETED" if success else "FAILED")
            return success
        finally:
            # Failure never kills/adopts/restarts a possibly running worker. It expires or harness cleans it.
            for ref in refs.values():
                ref.close()
            if process is not None and process.poll() is not None:
                process.wait()
