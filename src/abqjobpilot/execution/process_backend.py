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
from .process_diagnostics import DIAGNOSTIC_NAME, try_write_failure_record


def write_failure_diagnostic(context, run, state, exc):
    """Best-effort diagnostic write, independent of Run completion evidence."""
    try:
        root = directory(context, run)
        diagnostic_path = confined(context.test_root, root / DIAGNOSTIC_NAME)
        if 'diagnostic' in state:
            from .process_diagnostics import write_failure_record
            write_failure_record(diagnostic_path, state['diagnostic'])
            return True
        return try_write_failure_record(diagnostic_path, run, state["stage"], exc)
    except Exception:
        return False


@dataclass(frozen=True)
class ProcessFixtureConfig:
    interpreter: str
    image: str
    interpreter_digest: str
    image_digest: str
    fixture_digest: str
    max_seconds: int = 40
    managed_scope: bool = False

    @classmethod
    def current(cls, *, managed_scope=False):
        from ..application_runtime import is_frozen_runtime, frozen_fixture_identity
        if is_frozen_runtime():
            pin = frozen_fixture_identity()
            return cls(pin['interpreter'], pin['image'], pin['interpreter_digest'], pin['image_digest'],
                       pin['fixture_digest'], managed_scope=managed_scope)
        actual = current_process_identity()
        return cls(str(Path(sys.executable).resolve()), actual["image_path"],
                   bytes_digest(Path(sys.executable).read_bytes()), bytes_digest(Path(actual["image_path"]).read_bytes()),
                   bytes_digest(Path(__file__).with_name("process_fixture.py").read_bytes()), managed_scope=managed_scope)

    def binding(self, scenario):
        require(scenario in SCENARIOS and type(scenario) is str, "INVALID_REQUEST", "Unsupported fixed test scenario")
        require(type(self.managed_scope) is bool and (not scenario.startswith('managed_') or self.managed_scope),
                'INVALID_REQUEST', 'Descendant scenarios require the explicit managed profile')
        require(type(self.max_seconds) is int and 5 <= self.max_seconds <= 60,
                "RESOURCE_LIMIT", "Fixture lifetime must be 5..60 seconds")
        binding = {"interpreter": self.interpreter, "image": self.image,
                "interpreter_digest": self.interpreter_digest, "image_digest": self.image_digest,
                "fixture_digest": self.fixture_digest, "scenario": scenario, "max_seconds": self.max_seconds,
                "max_process_members": 4, "argument_policy": "frozen_owner_fixture_v1" if self._frozen() else "isolated_python_fixture_v1",
                "membership_contract": MEMBERSHIP_CONTRACT, "required_roles": list(REQUIRED_ROLES)}
        if self.managed_scope:
            from .managed_process import POLICY
            from ..application_runtime import frozen_fixture_identity
            implementation_digest = (frozen_fixture_identity()['managed_process_digest'] if self._frozen() else
                bytes_digest(Path(__file__).with_name('managed_process.py').read_bytes()))
            # Up to eight fixed invocations, including this Windows venv's
            # transport chain (24 cumulative processes observed in burst tests).
            # This is a fixture declaration, not an OS-enforced resource limit.
            binding['max_process_members'] = 32
            binding['managed_scope'] = {'policy':POLICY,'implementation_digest':implementation_digest}
        return binding

    @staticmethod
    def _frozen():
        from ..application_runtime import is_frozen_runtime
        return is_frozen_runtime()

    def verify(self, binding):
        fields(binding, self.binding("normal"))
        require(binding == self.binding(binding["scenario"]), "PLAN_STALE", "Trusted fixture configuration changed")
        if self._frozen():
            from ..application_runtime import executable_role, frozen_fixture_identity
            pin = frozen_fixture_identity()
            require(Path(self.interpreter) == Path(pin['interpreter']) and Path(self.image) == Path(pin['image'])
                    and self.interpreter_digest == pin['interpreter_digest'] and self.image_digest == pin['image_digest']
                    and self.fixture_digest == pin['fixture_digest'],
                    'PLAN_STALE', 'Frozen fixture build identity differs')
            if executable_role() == 'owner':
                require(str(Path(sys.executable).resolve()) == self.interpreter
                        and current_process_identity()['image_path'] == self.image,
                        'PLAN_STALE', 'Frozen fixture Owner image differs')
            for path, expected in ((Path(self.interpreter), self.interpreter_digest), (Path(self.image), self.image_digest)):
                no_reparse(path)
                require(bytes_digest(path.read_bytes()) == expected, 'PLAN_STALE', 'Frozen fixture executable changed')
        else:
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
        from .resource_observer import AttemptResources
        self.resources = AttemptResources()
        self.last_diagnostic = None

    def execute(self, context, plan, run, record, checkpoint, authorize_start):
        state = {"stage": "fixture_config_verify", "resources": self.resources.begin(run)}
        primary = None
        result = None
        try:
            result = self._execute(context, plan, run, record, checkpoint, authorize_start, state)
        except BaseException as exc:
            primary = (exc, exc.__traceback__, state['stage'])
        try:
            cleanup = self.resources.finish(failed=primary is not None)
        except Exception as exc:
            cleanup = [exc]
        if primary is not None or cleanup:
            from .process_diagnostics import failure_record
            error, traceback, stage = primary or (cleanup[0], cleanup[0].__traceback__, 'process_handle_close')
            try:
                diagnostic = failure_record(run, stage, error)
                diagnostic['failure_kind'] = 'PRIMARY_EXECUTION_FAILURE' if primary else 'CLEANUP_FAILURE'
                diagnostic['cleanup_errors'] = [failure_record(run, 'process_handle_close', e) for e in cleanup[:2]]
                diagnostic['cleanup_status'] = 'CLEANUP_FAILURE' if cleanup else 'CLEANUP_COMPLETED_OR_RESOURCES_RETAINED'
                state['diagnostic'] = diagnostic
                written = write_failure_diagnostic(context, run, state, error)
                self.last_diagnostic = {**diagnostic, 'diagnostic_status':
                                        'RECORDED' if written else 'DIAGNOSTIC_WRITE_FAILURE'}
            except Exception:
                self.last_diagnostic = {'diagnostic_status': 'DIAGNOSTIC_WRITE_FAILURE'}
            raise error.with_traceback(traceback)
        return result

    def _execute(self, context, plan, run, record, checkpoint, authorize_start, state):
        state["stage"] = "fixture_config_verify"
        self.config.verify(plan["process_fixture"])
        state["stage"] = "run_directory_resolve"
        root = directory(context, run)
        state["stage"] = "run_directory_create"
        root.mkdir(parents=True, exist_ok=False)
        manifest = {**{k: run[k] for k in ("run_id", "project_instance_id", "phase_attempt_id")},
                    "plan_digest": plan["plan_digest"], "scenario": plan["process_fixture"]["scenario"],
                    "max_seconds": self.config.max_seconds, "expected_result": expected_result(context, plan, run)}
        state["stage"] = "fixture_manifest_write"
        with (root / "fixture.json").open("x", encoding="utf-8") as stream:
            stream.write(canonical_json(manifest))
            stream.flush()
            os.fsync(stream.fileno())
        refs, observations, exits = {}, [], []
        state['resources']['refs'] = refs
        process = scope = None
        deadline = time.monotonic() + self.config.max_seconds + 5
        try:
            state["stage"] = "pre_create_checkpoint"
            checkpoint("process:before_create")
            state["stage"] = "start_authorization"
            authorize_start()  # Recheck after any startup delay, before the irreversible OS effect.
            # No inherited IPC/auth/DB handles; only Windows system location is required.
            state["stage"] = "fixture_environment_prepare"
            environment = {"SystemRoot": os.environ["SystemRoot"], "PYTHONDONTWRITEBYTECODE": "1"}
            if self.config._frozen():
                from ..application_runtime import executable_role
                state["stage"] = "fixture_role_entry"
                require(executable_role() == 'owner', 'HOST_UNCONFIRMED', 'Frozen Fixture must launch from the Owner role')
                command = [self.config.interpreter, '--fixture-role', '--role', 'launcher', '--directory', str(root)]
            else:
                command = [self.config.interpreter, "-I", "-S", "-B",
                           str(Path(__file__).with_name("process_fixture.py").resolve()),
                           "--role", "launcher", "--directory", str(root)]
            if self.config.managed_scope:
                from .managed_process import ManagedScope
                state["stage"] = "pre_create_checkpoint"
                checkpoint('managed:before_scope')
                state["stage"] = "managed_scope_create"
                scope = ManagedScope(run)
                state['resources']['scope'] = scope
                state["stage"] = "managed_scope_record_prepared"
                record('MANAGED_SCOPE_PREPARED', managed_scope=scope.description(), managed_completion='NOT_CONFIRMED')
                state["stage"] = "pre_create_checkpoint"
                checkpoint('managed:before_create')
                state["stage"] = "start_authorization"
                authorize_start()
                state["stage"] = "managed_root_create"
                process = scope.create(command,cwd=str(root),env=environment)
                state['resources']['process'] = process
                state["stage"] = "execution_checkpoint"
                checkpoint('managed:after_create')
                state["stage"] = "managed_root_query"
                managed_snapshot = scope.query()
                state["stage"] = "managed_root_record"
                record('MANAGED_ROOT_CREATED', managed_scope=managed_snapshot)
            else:
                state["stage"] = "fixture_role_launch"
                process = subprocess.Popen(command,
                                       shell=False, close_fds=True, cwd=str(root), env=environment,
                                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
                state['resources']['process'] = process
            state["stage"] = "direct_process_identity_open"
            refs["launcher_transport"] = ProcessReference(process.pid)
            state["stage"] = "direct_process_identity_validate"
            require(Path(refs["launcher_transport"].identity["image_path"]) == Path(self.config.interpreter),
                    "PROCESS_IDENTITY_MISMATCH", "Unexpected direct launch image")
            state["stage"] = "execution_checkpoint"
            checkpoint("process:after_create")
            for role in ("launcher", "worker_transport", "worker"):
                state["stage"] = "role_handshake_wait"
                candidate_path = confined(context.test_root, root / (role + ".json"))
                while not candidate_path.exists():
                    require(time.monotonic() < deadline, "PROCESS_IDENTITY_UNKNOWN", "Identity handshake deadline exceeded")
                    time.sleep(0.01)
                state["stage"] = "role_handshake_read"
                require(candidate_path.stat().st_size <= 4096, "PROCESS_IDENTITY_UNKNOWN", "Oversized identity handshake")
                state["stage"] = "role_handshake_parse"
                candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
                state["stage"] = "role_handshake_binding"
                require(all(candidate.get(k) == manifest[k] for k in ("run_id", "project_instance_id", "phase_attempt_id", "plan_digest"))
                        and candidate.get("role") == role, "PROCESS_IDENTITY_MISMATCH", "Handshake binding differs")
                state["stage"] = "role_process_identity_open"
                refs[role] = ProcessReference(candidate["pid"], candidate)
                expected_image = self.config.image if role in {"launcher", "worker"} else self.config.interpreter
                state["stage"] = "role_image_validate"
                require(Path(refs[role].identity["image_path"]) == Path(expected_image),
                        "PROCESS_IDENTITY_MISMATCH", "Unexpected fixture process image")
                if role in {"launcher", "worker"}:
                    state["stage"] = "role_parent_validate"
                    transport = refs[role + "_transport"].identity["pid"]
                    require(candidate["pid"] == transport or candidate.get("parent_pid") == transport,
                            "PROCESS_IDENTITY_MISMATCH", "Fixture role does not match its launch transport")
                state["stage"] = "role_exit_probe"
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
            if scope:
                membership['basis'] = 'KEY_ROLES_ONLY_NOT_MANAGED_DESCENDANT_COMPLETENESS'
            state["stage"] = "process_identities_record"
            record("PROCESS_IDENTITIES", process_observation="IDENTITIES_VERIFIED", process_records=observations,
                   process_membership=membership)
            state["stage"] = "execution_checkpoint"
            checkpoint("process:after_identity")
            state["stage"] = "owner_binding_write"
            (root / "owner-bound.json").write_text("{}", encoding="utf-8")
            state["stage"] = "execution_checkpoint"
            checkpoint("process:after_handoff")
            last_scope_counts = None
            while len(exits) < len(refs):
                require(time.monotonic() < deadline, "PROCESS_EXIT_UNKNOWN", "No complete exit evidence before deadline")
                for role, ref in refs.items():
                    if any(e["role"] == role for e in exits):
                        continue
                    state["stage"] = "process_exit_observe"
                    evidence = ref.exit_evidence()
                    if evidence is not None:
                        state["stage"] = "execution_checkpoint"
                        checkpoint("process:before_exit_record")
                        state["stage"] = "process_exit_record"
                        exits.append({**next(o for o in observations if o["role"] == role), **evidence,
                                      **binding, "exit_contract": EXIT_CONTRACT})
                        record("PROCESS_EXIT_OBSERVED", process_exits=list(exits),
                               process_observation="EXIT_PARTIAL", exit_verification="PARTIAL")
                if scope:
                    state["stage"] = "execution_checkpoint"
                    checkpoint('managed:before_query')
                    state["stage"] = "managed_scope_query"
                    view=scope.query()
                    counts=(view['active_processes'],view['total_processes'])
                    if counts!=last_scope_counts:
                        state["stage"] = "managed_scope_observation_record"
                        record('MANAGED_SCOPE_OBSERVED',managed_scope=view)
                        last_scope_counts=counts
                time.sleep(0.01)
            state["stage"] = "process_exit_observe"
            process.wait(timeout=2)
            state["stage"] = "execution_checkpoint"
            checkpoint("process:after_exit")
            proof=None
            if scope:
                while True:
                    require(time.monotonic()<deadline,'MANAGED_SCOPE_UNKNOWN','Managed range did not end within observation budget')
                    state["stage"] = "execution_checkpoint"
                    checkpoint('managed:before_query')
                    state["stage"] = "managed_scope_query"
                    proof=scope.query()
                    counts=(proof['active_processes'],proof['total_processes'])
                    if counts!=last_scope_counts:
                        state["stage"] = "managed_scope_observation_record"
                        record('MANAGED_SCOPE_OBSERVED',managed_scope=proof)
                        last_scope_counts=counts
                    if proof['state']=='EMPTY_CONFIRMED':break
                    time.sleep(.02)
                state["stage"] = "execution_checkpoint"
                checkpoint('managed:after_empty')
            success = all(e["exit_code"] == 0 for e in exits)
            state["stage"] = "process_completion_record"
            record("PROCESS_COMPLETED", execution="VALIDATING", process_observation="EXIT_OBSERVED",
                   exit_verification="VERIFIED", backend_outcome="COMPLETED" if success else "FAILED")
            return {'success':success,'managed_scope':proof} if scope else success
        finally:
            # execute() cleans up after freezing the primary exception/stage.
            # Every acquired resource is already held by the Owner registry.
            pass
