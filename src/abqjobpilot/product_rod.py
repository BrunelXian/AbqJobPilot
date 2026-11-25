"""Public persistent inert rod product facade. Never starts an Owner or issues Grants.

The product uses existing AF format-3 tables and initial-preparation ownership.
Every call closes its own lease. A disconnected client can reopen by the explicit
Project path and exact Plan reference, without a client-side Store dependency.
"""

import json
from pathlib import Path
from types import SimpleNamespace

from .execution.models import (
    bytes_digest,
    canonical_json,
    digest,
    fields,
    integer,
    require,
)
from .execution.paths import confined
from .execution.rod_plan_adapter import BACKEND, inspect_registered, register_plan
from .execution.rod_profile import (
    RodCandidate,
    TOLERANCES,
    check_candidate,
    compile_candidate,
    materialize_candidate,
    prepare_preview,
    _label,
)
from .execution.store import (
    acquire_initial_preparation_store,
    document,
    open_existing_read_only,
)
from .product_project import create_project, open_project
from .service_discovery import project_identity
from .service_lifecycle import ServiceLifecycleManager

REF_SCHEMA = "af-rod-plan-ref-v1"
REQUEST_SCHEMA = "af-rod-product-request-v1"


def _file_bytes(root, path, limit=65536):
    """Read a bounded regular file with stable handle and path identity checks."""
    import os

    path = confined(root, path, exists=True)
    require(path.is_file(), "PLAN_STALE", "Regular file required")
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
        current = path.stat()

    def identity(info):
        return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns

    require(
        len(raw) <= limit
        and len(raw) == before.st_size
        and identity(before) == identity(after) == identity(current),
        "PLAN_STALE",
        "File changed during bounded reading",
    )
    return raw


class RodProduct:
    """Explicit new inert execution Project; old fixed product remains unchanged."""

    @classmethod
    def create(cls, directory, display_name):
        create_project(directory, display_name)
        return cls(directory)

    def __init__(self, directory):
        self.directory = Path(directory)
        open_project(self.directory)
        self.context = project_identity(self.directory)

    def disconnect(self):
        return {
            "state": "DISCONNECTED",
            "project_instance_id": self.context.project_instance_id,
        }

    @staticmethod
    def owner_runtime_preview(config):
        """Non-executable qualification of the existing Route C Owner entry."""
        from .execution.rod_local_hil import owner_runtime_preview
        return owner_runtime_preview(config)

    def _reader(self):
        open_project(self.directory)
        return SimpleNamespace(
            context=self.context, store=open_existing_read_only(self.context)
        )

    def _stored(self):
        reader = self._reader()
        with reader.store.read() as conn:
            rows = conn.execute(
                "SELECT CASE WHEN length(body)<=65536 THEN body END FROM plans LIMIT 2"
            ).fetchall()
            require(
                len(rows) <= 1 and all(row[0] for row in rows),
                "LIMIT_EXCEEDED",
                "One bounded rod Plan required",
            )
            require(
                all(
                    conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] == 0
                    for table in ("runs", "grants", "receipts", "consumption")
                ),
                "ROD_EXECUTION_UNQUALIFIED",
                "Inert product must have no execution records",
            )
            require(
                conn.execute("SELECT state FROM dispatch_gate WHERE id=1").fetchone()[0]
                == "PAUSED",
                "DISPATCH_POLICY_MISMATCH",
                "Inert product must remain PAUSED",
            )
        return None if not rows else json.loads(rows[0][0])

    def _checked(self, plan_id, expected_digest, at_time):
        integer(at_time, 1)
        reader = self._reader()
        inspect_registered(reader, plan_id, expected_digest)
        with reader.store.read() as conn:
            plan = document(conn, "plans", "plan_id", plan_id)
        require(
            self._stored() == plan, "PLAN_STALE", "Exact inert product Plan required"
        )
        require(
            plan.get("backend_id") == BACKEND
            and type(plan.get("product_request")) is dict,
            "CAPABILITY_UNAVAILABLE",
            "Public rod product preparation required",
        )
        request = plan["product_request"]
        fields(
            request,
            (
                "schema",
                "research_project_id",
                "contract_digest",
                "research_revision",
                "candidate_id",
                "request_key",
                "input_digest",
                "load_n",
                "expires_at",
                "tolerances",
                "phase",
                "request_digest",
            ),
        )
        for key in ("research_project_id", "candidate_id", "request_key"):
            _label(request[key])
        integer(request["research_revision"], 1)
        require(
            request.get("schema") == REQUEST_SCHEMA
            and request.get("request_digest")
            == digest({k: v for k, v in request.items() if k != "request_digest"}),
            "PLAN_STALE",
            "Product request fingerprint differs",
        )
        require(plan["expires_at"] > at_time, "PLAN_EXPIRED", "Inert Plan expired")
        raw = plan["rod_preview"]
        require(
            request["phase"] == "A"
            and request["research_project_id"] == raw["research_project_id"]
            and request["contract_digest"] == raw["contract_digest"]
            and request["expires_at"] == raw["expires_at"] == plan["expires_at"]
            and request["tolerances"] == raw["tolerances"]
            and request["load_n"] == raw["candidate"]["load_n"],
            "PLAN_STALE",
            "Product request contradicts frozen rod preview",
        )
        input_bytes = _file_bytes(self.context.test_root, raw["input_path"])
        metadata = json.loads(
            _file_bytes(
                self.context.test_root,
                Path(raw["input_path"]).with_name("candidate.json"),
            )
        )
        candidate = RodCandidate(input_bytes, canonical_json(metadata))
        check_candidate(candidate)
        require(
            metadata == raw["candidate"]
            and bytes_digest(input_bytes) == request["input_digest"]
            and plan["input_manifest"]
            == [
                {
                    "path": raw["input_path"],
                    "size": len(input_bytes),
                    "digest": metadata["input_digest"],
                }
            ]
            and plan["resources"] == raw["resources"]
            and plan["output_policy"]
            == {"overwrite": False, "root": raw["output_path"]}
            and plan["output_key"] == digest({"output": raw["output_path"].casefold()}),
            "PLAN_STALE",
            "Persisted inputs, resources or output differ",
        )
        for field in ("scratch", "output_path"):
            require(
                confined(self.context.test_root, raw[field], exists=True).is_dir(),
                "OUTPUT_SCOPE_VIOLATION",
                "Exact output directories required",
            )
        return plan, candidate

    def read_real_artifact(self, plan_id, expected_plan_digest, request_key):
        """Bound public read-only original-record/DAT acquisition; no Store exposed."""
        from .execution.rod_trusted import acquire
        manager = ServiceLifecycleManager(self.directory)
        profile = manager._profile()
        reader = SimpleNamespace(context=self.context, store=open_existing_read_only(self.context),
                                 client_namespace=profile["client_namespace"])
        return acquire(reader, self.context, plan_id=plan_id,
                       expected_plan_digest=expected_plan_digest, request_key=request_key)

    def read_real_artifacts(self, plan_id, expected_plan_digest, request_key):
        """Read the bound DAT/STA/MSG collector records; does not authenticate origin."""
        from .execution.rod_trusted import acquire

        manager = ServiceLifecycleManager(self.directory)
        profile = manager._profile()
        reader = SimpleNamespace(context=self.context, store=open_existing_read_only(self.context),
                                 client_namespace=profile["client_namespace"])
        return acquire(reader, self.context, plan_id=plan_id,
                       expected_plan_digest=expected_plan_digest, request_key=request_key,
                       include_completion_artifacts=True)

    def read_acceptance(self, plan_id, expected_plan_digest, request_key):
        from .execution.rod_local_read import acceptance
        reader = self._reader()
        reader.client_namespace = ServiceLifecycleManager(self.directory)._profile()['client_namespace']
        return acceptance(reader, plan_id=plan_id, expected_plan_digest=expected_plan_digest, request_key=request_key)

    def read_started(self, plan_id, expected_plan_digest, request_key):
        from .execution.rod_local_read import started
        reader = self._reader()
        reader.client_namespace = ServiceLifecycleManager(self.directory)._profile()['client_namespace']
        return started(reader, plan_id=plan_id, expected_plan_digest=expected_plan_digest, request_key=request_key)

    def read_denial(self, plan_id, expected_plan_digest, request_key):
        from .execution.rod_local_read import denial
        reader = self._reader()
        return denial(reader, plan_id=plan_id, expected_plan_digest=expected_plan_digest, request_key=request_key)

    def read_orderly_stop(self, plan_id, expected_plan_digest, request_key):
        from .execution.rod_local_read import orderly_stop
        manager = ServiceLifecycleManager(self.directory)
        reader = self._reader()
        reader.client_namespace = manager._profile()['client_namespace']
        return orderly_stop(reader, manager, plan_id=plan_id, expected_plan_digest=expected_plan_digest, request_key=request_key)

    def preflight_real(self, plan_id, expected_plan_digest, *, config, expected_contract):
        """Recheck a prepared A using an exact frozen reference; no activation writes."""
        from .execution.rod_trusted import preflight
        from .execution.standard_contract import StandardConfig

        require(type(config) is StandardConfig, "INVALID_REQUEST", "Trusted config type required")
        config.verify()
        reader = self._reader()
        reader._standard_backend = SimpleNamespace(config=config)
        return preflight(reader, self.context, plan_id=plan_id,
                         expected_plan_digest=expected_plan_digest,
                         expected_contract=expected_contract)

    def review_real_plan(self, plan_id, expected_plan_digest, *, config,
                         expected_contract, at_time):
        """Exact non-executable review view of the original real-profile Plan."""
        integer(at_time, 1)
        value = self.preflight_real(plan_id, expected_plan_digest, config=config,
                                    expected_contract=expected_contract)
        require(at_time < value["expires_at"], "PLAN_EXPIRED", "Review Plan expired")
        return {
            "schema": "af-real-rod-plan-review-v1", "source": "REAL_ROD_PREFLIGHT_ONLY",
            "project_id": value["project_id"],
            "project_instance_id": value["project_instance_id"],
            "plan_id": plan_id, "plan_digest": expected_plan_digest,
            **value["research_contract"], "load_n": value["load_n"],
            "resources": value["resources"], "input_path": value["input_path"],
            "output_path": value["engineering"], "output_identity": value["output_key"],
            "scratch": value["scratch"], "expires_at": value["expires_at"],
            "declared_outputs": value["declared_outputs"],
            "runtime_binding_digest": value["runtime_binding_digest"],
            "authorization_state": "NOT_AUTHORIZED", "execution_authorized": False,
        }

    def a_only_application(self, plan_id, expected_plan_digest, *, config,
                           expected_contract, nonce, not_before, expires_at):
        """Exact pending human review packet; no provisioning, decision or Grant."""
        from .execution.models import now
        from .execution.product_standard import scope
        _label(nonce)
        integer(not_before, 1)
        integer(expires_at, 1)
        value = self.preflight_real(plan_id, expected_plan_digest, config=config,
                                    expected_contract=expected_contract)
        require(not_before <= now() < expires_at <= min(value["expires_at"], not_before + 600),
                "APPROVAL_EXPIRED", "Short exact A review window required")
        with self._reader().store.read() as conn:
            plan = document(conn, "plans", "plan_id", plan_id)
        require(plan["plan_digest"] == expected_plan_digest, "PLAN_STALE", "Plan changed during review")
        exact_scope = scope(plan)
        return {"schema": "rod-a-only-application-v1", "plan_id": plan_id,
                "plan_digest": expected_plan_digest, "scope": exact_scope,
                "scope_digest": digest(exact_scope), "nonce": nonce,
                "not_before": not_before, "expires_at": expires_at, "execution_authorized": False}

    def prepare_real(self, *, frozen_template, candidate_bytes, load_n, config,
                     research_project_id, contract_digest, research_revision,
                     candidate_id, request_nonce, expires_at, phase="A", local_contract=None):
        """Public exact real-Plan preparation, without Operator or Grant creation.

        The caller supplies a trusted configuration object, not a launch flag.
        Existing TEST_ONLY lifecycle cannot start this Project until a separately
        approved protected deployment provisions its exact Standard binding.
        """
        from .execution import rod_trusted
        from .execution.standard_contract import StandardConfig
        from .execution.service import ExecutionService
        require(type(config) is StandardConfig, "INVALID_REQUEST", "Exact trusted configuration type required")
        config.verify()
        require(phase == "A" or local_contract is not None, "REAL_A_EVIDENCE_REQUIRED", "B requires new local contract")
        compiler = compile_candidate
        if local_contract is not None:
            from .execution.rod_output_v2 import compile_candidate as compiler
        candidate = compiler(frozen_template, load_n)
        require(type(candidate_bytes) is bytes and candidate_bytes == candidate.input_bytes,
                "ROD_MUTATION_DENIED", "Exact reviewed candidate bytes required")
        arguments = dict(research_project_id=research_project_id, contract_digest=contract_digest,
                         research_revision=research_revision, candidate_id=candidate_id,
                         request_nonce=request_nonce, expires_at=expires_at, phase=phase, local_contract=local_contract)
        manager = ServiceLifecycleManager(self.directory)
        profile = manager._profile()
        require(profile["process_config"] is None and "standard_extension" not in profile,
                "LIFECYCLE_PROVISIONING_CLOSED", "New exact prerequisite Project required")
        store = acquire_initial_preparation_store(self.context, profile["authority_instance"])
        try:
            service = ExecutionService(self.context, store, client_namespace=profile["client_namespace"],
                                       standard_config=config)
            with store.read() as conn:
                rows = conn.execute("SELECT body FROM plans LIMIT 2").fetchall()
            require(len(rows) <= 1, "IDEMPOTENCY_CONFLICT", "One exact real Plan required")
            if rows:
                prior = json.loads(rows[0][0])
                require(prior.get("backend_id") == rod_trusted.BACKEND,
                        "IDEMPOTENCY_CONFLICT", "Existing offline or fixed Plan cannot migrate")
                workspace = Path(prior["engineering"])
            else:
                workspace = materialize_candidate(Path(self.context.test_root), candidate)
            plan = rod_trusted.prepare(service, workspace, candidate, **arguments).to_dict()
            return {"project_id": self.context.project_id, "execution_authorized": False,
                    "activation": "HUMAN_LOCAL_PROVISION_REQUIRED" if local_contract else "PROTECTED_DEPLOYMENT_REQUIRED", **{k: plan[k] for k in
                    ("plan_id", "plan_digest", "project_instance_id", "backend_id", "backend_version",
                     "resources", "output_key", "rod_contract", "validation_policy")}}
        finally:
            store.close()

    def inspect(self, plan_id, expected_digest, *, at_time):
        plan, candidate = self._checked(plan_id, expected_digest, at_time)
        raw, request = plan["rod_preview"], plan["product_request"]
        return {
            "schema": REF_SCHEMA,
            "source": "INERT_ROD_PLAN",
            "profile": raw["profile"],
            "project_id": self.context.project_id,
            "project_instance_id": self.context.project_instance_id,
            "plan_id": plan_id,
            "plan_digest": expected_digest,
            "candidate_id": request["candidate_id"],
            "candidate_digest": candidate.to_dict()["candidate_digest"],
            "input_digest": request["input_digest"],
            "input_size": len(candidate.input_bytes),
            "resources": plan["resources"],
            "resources_digest": digest(plan["resources"]),
            "output_identity": plan["output_key"],
            "input_path": raw["input_path"],
            "output_path": raw["output_path"],
            "contract_digest": request["contract_digest"],
            "research_project_id": request["research_project_id"],
            "research_revision": request["research_revision"],
            "phase": request["phase"],
            "expires_at": plan["expires_at"],
            "load_n": candidate.to_dict()["load_n"],
            "tolerances": raw["tolerances"],
            "verification_policy_digest": digest(raw["tolerances"]),
            "authorization_state": "NOT_AUTHORIZED",
            "execution_authorized": False,
        }

    def prepare(
        self,
        *,
        frozen_template,
        candidate_bytes,
        load_n,
        research_project_id,
        contract_digest,
        research_revision,
        candidate_id,
        request_key,
        expires_at,
        at_time,
        tolerances=None,
        phase="A",
    ):
        require(
            phase == "A",
            "REAL_A_EVIDENCE_REQUIRED",
            "Real B cannot be prepared before qualified actual A",
        )
        for item in (research_project_id, candidate_id, request_key):
            _label(item)
        integer(research_revision, 1)
        candidate = compile_candidate(frozen_template, load_n)
        require(
            type(candidate_bytes) is bytes and candidate.input_bytes == candidate_bytes,
            "ROD_MUTATION_DENIED",
            "Actual GD-CAE candidate bytes must exactly match",
        )
        request = {
            "schema": REQUEST_SCHEMA,
            "research_project_id": research_project_id,
            "contract_digest": contract_digest,
            "research_revision": research_revision,
            "candidate_id": candidate_id,
            "request_key": request_key,
            "input_digest": bytes_digest(candidate_bytes),
            "load_n": candidate.to_dict()["load_n"],
            "expires_at": expires_at,
            "tolerances": dict(TOLERANCES if tolerances is None else tolerances),
            "phase": phase,
        }
        request["request_digest"] = digest(request)
        previous = self._stored()
        if previous is not None:
            require(
                previous.get("product_request") == request,
                "IDEMPOTENCY_CONFLICT",
                "One immutable product request required",
            )
            return self.inspect(
                previous["plan_id"], previous["plan_digest"], at_time=at_time
            )
        manager = ServiceLifecycleManager(self.directory)
        profile = manager._profile()
        require(
            profile["process_config"] is None and "standard_extension" not in profile,
            "LIFECYCLE_SCOPE_UNSUPPORTED",
            "No fixed or test execution profile may be mixed",
        )
        store = acquire_initial_preparation_store(
            self.context, profile["authority_instance"]
        )
        try:
            # Check again after exclusive initial-preparation ownership is acquired.
            require(
                self._stored() is None,
                "OWNER_BUSY",
                "Another preparer committed; query exact reference",
            )
            workspace = materialize_candidate(Path(self.context.test_root), candidate)
            preview = prepare_preview(
                candidate,
                test_root=self.context.test_root,
                workspace=workspace,
                project_id=self.context.project_id,
                project_instance_id=self.context.project_instance_id,
                research_project_id=research_project_id,
                contract_digest=contract_digest,
                expires_at=expires_at,
                at_time=at_time,
                tolerances=request["tolerances"],
            )
            from .execution.service import ExecutionService

            service = ExecutionService(
                self.context, store, client_namespace=profile["client_namespace"]
            )
            result = register_plan(
                service,
                preview,
                candidate,
                expected_digest=preview.to_dict()["plan_digest"],
                at_time=at_time,
                product_request=request,
            ).to_dict()
        finally:
            store.close()
        return self.inspect(result["plan_id"], result["plan_digest"], at_time=at_time)


def validate_local_reader(product, config, runtime):
    """Public read-only qualification; never expose the execution Store or Operator."""
    from .execution.standard_contract import StandardConfig
    from .execution.rod_local_hil import check_runtime
    require(type(product) is RodProduct and type(config) is StandardConfig,
            "READ_PORT_UNQUALIFIED", "Exact bounded public reader required")
    check_runtime(config, runtime)
