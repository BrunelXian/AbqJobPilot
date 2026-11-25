"""Owner observation of the fixed JSON in the independent extraction directory."""

from contextlib import ExitStack
import json
import os
from pathlib import Path

from . import hil_odb, sanity_hil
from .models import ExecutionError, bytes_digest, digest, now, require
from .paths import confined

SCHEMA = "sanity-odb-output-provenance/1.0"
OWNER_OUTPUT = "OWNER_VERIFIED_OUTPUT"
OWNER_DIAGNOSTIC = "OWNER_VERIFIED_DIAGNOSTIC"
BINDING = ("project_id", "project_instance_id", "context_digest", "plan_id", "plan_digest", "run_id",
           "phase_attempt_id", "receipt_id", "operation_id", "grant_id", "approval_digest", "owner_id",
           "script", "script_version", "selector")


def check_selector(plan, receipt):
    fixed = plan["sanity"]["hil"]["odb"]
    require(receipt["selector"] == fixed["selector"] == sanity_hil.ODB_SELECTOR,
            "ODB_FIELD_NOT_ALLOWED", "Output must use the fixed TIP U2 selector")
    require(receipt["script"] == fixed["script"] and receipt["script_version"] == fixed["script_version"],
            "PLAN_STALE", "Output must use the approved fixed script")


def _binding(receipt):
    return {**{key: receipt[key] for key in BINDING}, "source_sha256": receipt["source"]["artifact"]["sha256"],
            "source_digest": digest(receipt["source"]), "process_digest": digest(receipt["process"])}


def output_path(context, receipt):
    path = Path(context.runtime_root) / "standard_runs" / receipt["run_id"] / receipt["operation_id"] / "u2.json"
    return confined(context.test_root, path)


def _identity(info):
    return {"device": info.st_dev, "inode": info.st_ino, "size": info.st_size,
            "created_ns": info.st_birthtime_ns, "mtime_ns": info.st_mtime_ns}


def _unique(pairs):
    result = dict(pairs)
    require(len(result) == len(pairs), "ODB_OUTPUT_INVALID", "Duplicate JSON member")
    return result


def _pinned_output(pins, path, recorded_at):
    stream, info = hil_odb._pin(pins, path, hil_odb.MAX_RESULT)
    identity = _identity(info)
    require(min(identity["created_ns"], identity["mtime_ns"]) >= recorded_at * 1_000_000_000,
            "OUTPUT_IDENTITY_MISMATCH", "JSON predates this extraction")
    raw = stream.read(hil_odb.MAX_RESULT + 1)
    try:
        json.loads(raw, object_pairs_hook=_unique)
    except (ValueError, RecursionError) as exc:
        raise ExecutionError("ODB_OUTPUT_INVALID", "Malformed output JSON") from exc
    # Reuse the fixed script result schema while holding the original deny-write/delete handle.
    artifact = hil_odb._read_result(path)
    require(len(raw) == identity["size"] == artifact["size"] and bytes_digest(raw) == artifact["sha256"]
            and identity == _identity(os.fstat(stream.fileno())) == _identity(path.stat()),
            "OUTPUT_IDENTITY_MISMATCH", "Output path or bytes changed during observation")
    return artifact, {**identity, "path": str(path), "sha256": artifact["sha256"]}


def observe(pins, context, plan, receipt, *, diagnostic):
    """Observe newly produced output only inside the original Owner worker."""
    check_selector(plan, receipt)
    artifact, identity = _pinned_output(pins, output_path(context, receipt), receipt["recorded_at"])
    proof = {"schema": SCHEMA, "grade": OWNER_DIAGNOSTIC if diagnostic else OWNER_OUTPUT,
             "binding": _binding(receipt), "observed_at": now(), "file": identity}
    return artifact, {**proof, "proof_digest": digest(proof)}


def check_path_identity(context, receipt, proof):
    path = output_path(context, receipt)
    file = proof["file"]
    require(file["path"] == str(path) and all(file[key] == value for key, value in _identity(path.stat()).items()),
            "OUTPUT_IDENTITY_MISMATCH", "Observed JSON path or file identity changed before commit")


def verify(context, plan, receipt):
    """Validate a persisted observation. This never creates or refreshes one."""
    check_selector(plan, receipt)
    proof = receipt["output_provenance"]
    body = {key: value for key, value in proof.items() if key != "proof_digest"}
    state = receipt["state"]
    nonzero = any(exit["exit_code"] != 0 for exit in receipt["process"]["exits"])
    diagnostic = state == "FAILED" and receipt.get("error_code") == "ODB_EXTRACTION_FAILED" and nonzero
    require(proof["schema"] == SCHEMA and proof["binding"] == _binding(receipt)
            and proof["proof_digest"] == digest(body)
            and receipt["recorded_at"] <= proof["observed_at"]
            and ((diagnostic and proof["grade"] == OWNER_DIAGNOSTIC and "artifact" not in receipt)
                 or (state == "NATIVE_OUTPUT_RECORDED" and not nonzero and proof["grade"] == OWNER_OUTPUT)),
            "OUTPUT_PROVENANCE_MISMATCH", "Output observation does not bind the original extraction")
    with ExitStack() as pins:
        artifact, identity = _pinned_output(pins, output_path(context, receipt), receipt["recorded_at"])
    require(proof["file"]["sha256"] == artifact["sha256"], "OUTPUT_DIGEST_MISMATCH", "Observed JSON digest differs")
    require(proof["file"] == identity, "OUTPUT_IDENTITY_MISMATCH", "Observed JSON file identity differs")
    return artifact
