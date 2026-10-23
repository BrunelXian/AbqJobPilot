"""Public offline prepare/inspect API. A preview is never an ExecutionPlan."""

from contextlib import ExitStack
from functools import wraps
import os
from pathlib import Path
import re
import uuid

from abqjobpilot.execution.models import (Document, ExecutionError, canonical_json, digest,
                                         fields, integer, now, require)
from abqjobpilot.execution.paths import no_reparse
from .inputs import (LABEL, RESERVED, MAX_FILES, MAX_DEPTH, MAX_FILE_BYTES, MAX_TOTAL_BYTES,
                     MAX_BLOCKS, directory, read_inputs, relative, _open_pinned)

SCHEMA = "abaqus-offline-preview-v1"
PROFILE = "windows-standard-static-subset-v1"
PROBE_PROFILE = "windows-standard-axial-print-v1"
MAX_REPORT_BYTES = 32768
STATUS = {"static_check": "COMPLETED_FOR_SUPPORTED_SUBSET",
          "dependency_coverage": "COMPLETE_FOR_SUPPORTED_SUBSET",
          "solver_input_semantics": "NOT_VERIFIED", "runtime": "NOT_VERIFIED",
          "resources": "NOT_RESERVED", "output": "NOT_RESERVED",
          "real_execution_capability": "UNAVAILABLE", "run": "NOT_CREATED",
          "solver_conclusion": "NOT_RUN", "artifact_validation": "NOT_RUN"}
UNRESOLVED = ["TARGET_2024_DOCUMENTATION_NOT_CONFIRMED", "SOLVER_MODEL_SEMANTICS_UNVERIFIED",
              "INSTALLATION_AND_ENVIRONMENT_UNVERIFIED", "LICENSE_AND_RESOURCES_UNVERIFIED",
              "OUTPUT_EXCLUSIVITY_NOT_ACQUIRED", "REAL_BACKEND_AND_APPROVAL_UNIMPLEMENTED",
              "NO_CROSS_FILE_ATOMIC_SNAPSHOT", "EXECUTION_TIME_INPUT_RECHECK_REQUIRED"]
LIMITS = {"files": MAX_FILES, "include_depth": MAX_DEPTH, "file_bytes": MAX_FILE_BYTES,
          "total_bytes": MAX_TOTAL_BYTES, "option_blocks": MAX_BLOCKS, "report_bytes": MAX_REPORT_BYTES}
PROFILE_FIELDS = ("profile_id", "profile_version", "platform", "product", "declared_version",
                  "phase", "cpus", "gpus", "memory_mb", "wall_seconds", "scratch_relative")


def _public(function):
    @wraps(function)
    def call(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except ExecutionError as exc:
            # Never echo input bytes, raw OS exceptions, arbitrary fields or paths.
            raise ExecutionError(exc.code, "Offline preview refused (" + exc.code + "); correct the named precondition",
                                 stage="OFFLINE_PREVIEW") from None
        except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError):
            raise ExecutionError("PREVIEW_UNAVAILABLE", "Offline operation could not be completed",
                                 stage="OFFLINE_PREVIEW") from None
    return call


class AbaqusPlanPreview(Document):
    """Immutable canonical document; not stored, registered, approved or executable."""


def _label(value):
    require(type(value) is str and re.fullmatch(LABEL, value), "INVALID_REQUEST", "Bounded identifier required")


def _profile(value):
    fields(value, PROFILE_FIELDS)
    _label(value["profile_id"])
    integer(value["profile_version"], 1)
    require({k: value[k] for k in ("platform", "product", "declared_version", "phase")} ==
            {"platform": "windows-local", "product": "Abaqus/Standard", "declared_version": "2024", "phase": "analysis"},
            "UNSUPPORTED_PROFILE", "Only the declared Windows Standard 2024 analysis intent is supported")
    for key in ("cpus", "gpus", "memory_mb", "wall_seconds"):
        integer(value[key])
    require(value["cpus"] == 1 and value["gpus"] == 0 and 64 <= value["memory_mb"] <= 4096
            and 1 <= value["wall_seconds"] <= 3600, "RESOURCE_LIMIT", "Resource declaration outside profile")
    return {**value, "scratch_relative": relative(value["scratch_relative"])}


def _context(value):
    fields(value, ("project_id", "project_instance_id"))
    for identifier in value.values():
        require(type(identifier) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", identifier),
                "INVALID_REQUEST", "Explicit public Project identifiers required")
    return dict(value)


@_public
def prepare(*, project, runtime_profile, engineering_root, submission_cwd, main_input, job_name,
            support_profile_version=PROFILE):
    """Read only explicit input files. Context IDs are declarations, not DB authentication."""
    context, profile = _context(project), _profile(runtime_profile)
    require(support_profile_version in (PROFILE, PROBE_PROFILE), "UNSUPPORTED_PROFILE", "Unknown support profile")
    _label(job_name)
    require(job_name.upper() not in RESERVED, "UNSUPPORTED_PATH", "Reserved job name")
    root, cwd = directory(engineering_root), directory(submission_cwd)
    require(root == cwd, "UNSUPPORTED_PROFILE", "Submission directory must be engineering root")
    main = relative(main_input)
    # Scratch is declared only; existence/reparse checks do not create it.
    scratch = root / profile["scratch_relative"]
    no_reparse(scratch)
    require(not scratch.exists() or scratch.is_dir(), "UNSUPPORTED_PATH", "Scratch declaration must name a directory")
    manifest, edges, keywords, physical = read_inputs(root, main, probe_print=support_profile_version == PROBE_PROFILE)
    require(not any(Path(item["reference"]).parent == Path(".")
                    and Path(item["reference"]).stem.lower() == job_name.lower() for item in manifest),
            "OUTPUT_INPUT_COLLISION", "Candidate job basename collides with known input")
    output_key = digest({"directory_identity": physical, "job_name_casefold": job_name.lower()})
    body = {"schema_version": SCHEMA, "support_profile_version": support_profile_version, "project": context,
            "runtime_profile": profile, "runtime_profile_digest": digest(profile),
            "target": {"product": profile["product"], "declared_version": profile["declared_version"], "phase": "analysis"},
            "engineering_root": str(root), "submission_cwd": str(cwd), "directory_identity": physical,
            "main_input": main, "input_manifest": manifest, "include_edges": edges,
            "resources": {k: profile[k] for k in ("cpus", "gpus", "memory_mb", "wall_seconds")},
            "output": {"job_name": job_name, "directory": str(cwd), "candidate_key": output_key,
                       "scratch_declaration": str(scratch), "reservation": "NONE", "existing_outputs_checked": False},
            "invocation_intent": {"kind": "structured_declaration_only", "input": main, "job": job_name, "phase": "analysis"},
            "checks": dict(STATUS), "supported_keywords_encountered": keywords,
            "limits": dict(LIMITS), "unresolved": list(UNRESOLVED),
            "reference_manual_version": "2025", "execution_plan_compatible": False}
    value = {"body": body, "content_digest": digest(body),
             "observation": {"read_at": now(), "file_view": "PINNED_LOCAL_READS_WITH_SECOND_CONTENT_CHECK",
                             "atomic_filesystem_snapshot": False}}
    result = AbaqusPlanPreview.from_dict(value)
    inspect(result)
    return result


@_public
def inspect(preview):
    """Check document shape/digest only; no reread, registration or attestation."""
    require(type(preview) is AbaqusPlanPreview and type(preview._json) is str,
            "INVALID_REQUEST", "Expected offline preview type")
    require(len(preview._json.encode("utf-8")) <= MAX_REPORT_BYTES, "LIMIT_EXCEEDED", "Report too large")
    value = preview.to_dict()
    fields(value, ("body", "content_digest", "observation"))
    b = value["body"]
    fields(b, ("schema_version", "support_profile_version", "project", "runtime_profile", "runtime_profile_digest",
               "target", "engineering_root", "submission_cwd", "directory_identity", "main_input", "input_manifest",
               "include_edges", "resources", "output", "invocation_intent", "checks", "supported_keywords_encountered",
               "limits", "unresolved", "reference_manual_version", "execution_plan_compatible"))
    require(b["schema_version"] == SCHEMA and b["support_profile_version"] in (PROFILE, PROBE_PROFILE),
            "UNSUPPORTED_FORMAT", "Unsupported preview format")
    require(b["checks"] == STATUS and b["execution_plan_compatible"] is False and b["limits"] == LIMITS
            and b["unresolved"] == UNRESOLVED and b["reference_manual_version"] == "2025",
            "INVALID_PREVIEW", "Preview scope cannot be upgraded")
    profile = _profile(b["runtime_profile"])
    _context(b["project"])
    require(b["runtime_profile_digest"] == digest(profile) and b["target"] ==
            {"product": profile["product"], "declared_version": profile["declared_version"], "phase": "analysis"}
            and b["resources"] == {k: profile[k] for k in ("cpus", "gpus", "memory_mb", "wall_seconds")},
            "INVALID_PREVIEW", "Inconsistent declarations")
    fields(b["directory_identity"], ("device", "file_id"))
    for identity in b["directory_identity"].values():
        require(type(identity) is int and identity >= 0, "INVALID_PREVIEW", "Invalid directory identity")
    for key in ("engineering_root", "submission_cwd"):
        require(type(b[key]) is str and len(b[key]) <= 256, "INVALID_PREVIEW", "Invalid declared directory")
    require(b["engineering_root"] == b["submission_cwd"], "INVALID_PREVIEW", "Directory mismatch")
    relative(b["main_input"])
    items = b["input_manifest"]
    require(type(items) is list and 1 <= len(items) <= MAX_FILES, "LIMIT_EXCEEDED", "Input list limit")
    for item in items:
        fields(item, ("reference", "bytes", "content_digest"))
        relative(item["reference"])
        require(type(item["bytes"]) is int and 0 <= item["bytes"] <= MAX_FILE_BYTES
                and type(item["content_digest"]) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", item["content_digest"]),
                "INVALID_PREVIEW", "Invalid input declaration")
    require(sum(x["bytes"] for x in items) <= MAX_TOTAL_BYTES and items[0]["reference"] == b["main_input"],
            "INVALID_PREVIEW", "Inconsistent manifest")
    require(type(b["include_edges"]) is list and len(b["include_edges"]) < MAX_FILES, "LIMIT_EXCEEDED", "Edge limit")
    refs = {item["reference"] for item in items}
    for edge in b["include_edges"]:
        fields(edge, ("from", "to", "base"))
        require(edge["from"] in refs and edge["to"] in refs and edge["base"] == "submission_cwd",
                "INVALID_PREVIEW", "Invalid include declaration")
    output = b["output"]
    fields(output, ("job_name", "directory", "candidate_key", "scratch_declaration", "reservation", "existing_outputs_checked"))
    _label(output["job_name"])
    require(output["directory"] == b["submission_cwd"] and output["reservation"] == "NONE"
            and output["existing_outputs_checked"] is False and output["candidate_key"] == digest(
                {"directory_identity": b["directory_identity"], "job_name_casefold": output["job_name"].lower()})
            and output["scratch_declaration"] == str(Path(b["engineering_root"]) / profile["scratch_relative"]),
            "INVALID_PREVIEW", "Invalid candidate output")
    require(b["invocation_intent"] == {"kind": "structured_declaration_only", "input": b["main_input"],
                                      "job": output["job_name"], "phase": "analysis"},
            "INVALID_PREVIEW", "No executable invocation supported")
    allowed_keywords = {"HEADING", "NODE", "ELEMENT", "MATERIAL", "ELASTIC", "SOLID SECTION", "STEP", "STATIC",
                        "BOUNDARY", "CLOAD", "END STEP"}
    if b["support_profile_version"] == PROBE_PROFILE:
        allowed_keywords |= {"NODE PRINT", "EL PRINT"}
        require({"NODE PRINT", "EL PRINT"} <= set(b["supported_keywords_encountered"]),
                "INVALID_PREVIEW", "Probe output requests missing")
    require(type(b["supported_keywords_encountered"]) is list
            and len(b["supported_keywords_encountered"]) <= len(allowed_keywords)
            and all(k in allowed_keywords for k in b["supported_keywords_encountered"]),
            "INVALID_PREVIEW", "Unknown support declaration")
    fields(value["observation"], ("read_at", "file_view", "atomic_filesystem_snapshot"))
    integer(value["observation"]["read_at"])
    require(value["observation"]["file_view"] == "PINNED_LOCAL_READS_WITH_SECOND_CONTENT_CHECK"
            and value["observation"]["atomic_filesystem_snapshot"] is False and value["content_digest"] == digest(b),
            "INVALID_PREVIEW", "Digest or read view differs")
    return value


@_public
def export_preview(preview, *, export_root, target):
    """Export the same object. No reread; no overwrite; only own partial cleanup."""
    value = inspect(preview)
    root = directory(export_root)
    engineering = Path(value["body"]["engineering_root"])
    require(not root.is_relative_to(engineering) and not engineering.is_relative_to(root),
            "OUTPUT_SCOPE_VIOLATION", "Export directory must be separate from engineering input")
    name = relative(target)
    require("/" not in name and name.lower().endswith(".json"), "UNSUPPORTED_PATH", "Single JSON filename required")
    destination = root / name
    no_reparse(destination)
    require(not destination.exists(), "EXPORT_EXISTS", "Target exists")
    data = canonical_json(value).encode("utf-8")
    require(len(data) <= MAX_REPORT_BYTES, "LIMIT_EXCEEDED", "Export limit exceeded")
    temporary = root / ("preview-" + uuid.uuid4().hex + ".partial")
    identity = None
    with ExitStack() as stack:
        handle, close = _open_pinned(root, is_directory=True)
        stack.callback(close, handle)
        try:
            with temporary.open("xb") as stream:
                info = os.fstat(stream.fileno())
                identity = (info.st_dev, info.st_ino)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            no_reparse(root)
            no_reparse(destination)
            os.rename(temporary, destination)  # Windows rename refuses existing target.
        finally:
            if identity is not None and temporary.exists():
                info = temporary.lstat()
                if (info.st_dev, info.st_ino) == identity:
                    temporary.unlink()
    return {"exported": name, "content_digest": value["content_digest"], "bytes": len(data),
            "scope": "offline_declaration_not_execution_permission"}
