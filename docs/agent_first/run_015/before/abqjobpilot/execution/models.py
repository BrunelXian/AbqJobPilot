"""Values for the experimental, Fake-only internal API. No legacy imports."""

from dataclasses import asdict, dataclass
import hashlib
import json
import time
import uuid

FORMAT = "abqjobpilot-agent-first-experiment"
CONTRACT = "af-experiment-v1"
CANONICAL = "af-experiment-json-v1"
RESOURCES = {"slots": 1, "simulated_cpus": 1, "simulated_gpus": 0,
             "max_output_bytes": 65536}


class ExecutionError(Exception):
    def __init__(self, code, message, *, stage="VALIDATE", run_id=None,
                 project_instance_id=None, evidence_refs=(), reconcile=False):
        super().__init__(message)
        self.code, self.stage, self.run_id = code, stage, run_id
        self.project_instance_id = project_instance_id
        self.evidence_refs, self.reconcile = list(evidence_refs), reconcile

    def to_dict(self):
        return {"request_status": "ACCEPTANCE_UNKNOWN" if self.code == "ACCEPTANCE_UNKNOWN"
                else ("ACCEPTED" if self.run_id else "REJECTED"),
                "error": {"code": self.code, "stage": self.stage, "message": str(self),
                          "run_id": self.run_id, "project_instance_id": self.project_instance_id,
                          "evidence_refs": self.evidence_refs,
                          "requires_reconciliation": self.reconcile,
                          "retry": {"mode": "QUERY_FIRST" if self.run_id or self.code == "ACCEPTANCE_UNKNOWN"
                                    else "CORRECT_REQUEST",
                                    "preconditions": ["No automatic execution retry"]}}}


def require(condition, code, message):
    if not condition:
        raise ExecutionError(code, message)


def canonical_json(value):
    def check(item):
        if item is None or type(item) in (str, bool, int):
            return
        if type(item) is list:
            for child in item:
                check(child)
            return
        if type(item) is dict and all(type(key) is str for key in item):
            for child in item.values():
                check(child)
            return
        raise ExecutionError("INVALID_REQUEST", "Only strict JSON without floats is supported")
    check(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def bytes_digest(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


def identifier(prefix):
    return prefix + "_" + uuid.uuid4().hex


def now():
    return time.time_ns() // 1_000_000_000


def fixed_fake_content(plan, run):
    """fake-v1's complete deterministic output contract, not an execution hook."""
    return canonical_json({"format": "fake-result-v1", "simulation": True, "run_id": run["run_id"],
                           "phase_attempt_id": run["phase_attempt_id"], "plan_digest": plan["plan_digest"],
                           "config_digest": plan["config_snapshot"]["digest"],
                           "input_digests": [item["digest"] for item in plan["input_manifest"]]}).encode("utf-8")


def fields(value, required, optional=()):
    require(type(value) is dict and set(required) <= value.keys()
            and value.keys() <= set(required) | set(optional), "INVALID_REQUEST", "Unexpected or missing fields")
    canonical_json(value)


def text(value):
    require(type(value) is str and 0 < len(value) <= 256, "INVALID_REQUEST", "Expected bounded nonempty string")


def integer(value, minimum=0):
    require(type(value) is int and minimum <= value <= 2**63 - 1, "INVALID_REQUEST", "Expected bounded integer")


@dataclass(frozen=True)
class ProjectContext:
    project_id: str
    project_instance_id: str
    test_root: str
    root: str
    runtime_root: str
    execution_store: str
    format_id: str
    schema_version: int
    storage_generation: str
    manifest_digest: str
    root_device: int
    root_inode: int

    def to_dict(self):
        return asdict(self)

    @property
    def context_digest(self):
        return digest(self.to_dict())


@dataclass(frozen=True)
class Document:
    """Store canonical bytes, never a caller-owned mutable dict."""
    _json: str

    @classmethod
    def from_dict(cls, value):
        return cls(canonical_json(value))

    def to_dict(self):
        return json.loads(self._json)


class JobSpec(Document):
    pass


class ConfigSnapshot(Document):
    pass


class ExecutionPlan(Document):
    pass


class ExecutionGrant(Document):
    pass


class SubmissionReceipt(Document):
    pass
