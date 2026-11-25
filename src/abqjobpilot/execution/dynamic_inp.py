"""Versioned preparation evidence for an admission-only candidate."""

from pathlib import Path
import re

from .delegated_grant import input_root
from .models import digest, fields, require
from .paths import confined

CONTRACT = "abq-controlled-inp-v1"
PROFILE = "t3d2-static-ascii-v1"
REQUIRED = {"NODE", "ELEMENT", "MATERIAL", "ELASTIC", "SOLID SECTION", "BOUNDARY", "CLOAD", "STEP", "STATIC", "END STEP"}
REQUEST_FIELDS = ("candidate_id", "main", "includes")
RECORD_FIELDS = (*REQUEST_FIELDS, "contract_version", "profile", "project_id", "project_instance_id",
                 "context_digest", "working_directory", "directory_identity", "files", "include_edges",
                 "keywords", "main_sha256", "input_manifest_digest", "v1", "v2")


def preflight(context, request, *, pin_scope=None):
    """Read a prepared candidate within one Project. This issues no approval."""
    from ..abaqus_preview.inputs import LABEL, MAX_FILES, directory, read_inputs, relative

    fields(request, REQUEST_FIELDS)
    candidate = request["candidate_id"]
    require(type(candidate) is str and re.fullmatch(LABEL, candidate) and relative(candidate) == candidate,
            "INVALID_CANDIDATE", "Use a bounded candidate directory identifier")
    main = relative(request["main"])
    includes = request["includes"]
    require(type(includes) is list and len(includes) < MAX_FILES, "INVALID_CANDIDATE", "Bound the dependency declaration")
    refs = [main, *(relative(item) for item in includes)]
    require(all("/" not in ref and ref.lower().endswith(".inp") for ref in refs)
            and len({ref.casefold() for ref in refs}) == len(refs),
            "UNSUPPORTED_PATH", "Use distinct .inp filenames from the candidate directory")
    base = input_root(context)
    root = directory(str(confined(base, base / candidate, exists=True)))
    files, edges, keywords, identity = read_inputs(root, main, approved_refs=set(refs), pin_scope=pin_scope)
    require(REQUIRED <= set(keywords), "UNSUPPORTED_MODEL", "An explicit static truss deck is required")
    return {"contract_version": CONTRACT, "profile": PROFILE,
            "candidate_id": candidate, "main": main, "includes": sorted(refs[1:]),
            "project_id": context.project_id, "project_instance_id": context.project_instance_id,
            "context_digest": context.context_digest, "working_directory": str(root), "directory_identity": identity,
            "files": files, "include_edges": edges, "keywords": keywords, "main_sha256": files[0]["content_digest"],
            "input_manifest_digest": digest({"directory": identity, "files": files, "edges": edges}),
            "v1": "STATIC_SUBSET_PASS", "v2": "NOT_RUN"}


def recheck(context, reviewed, *, pin_scope=None):
    fields(reviewed, RECORD_FIELDS)
    require((reviewed["project_id"], reviewed["project_instance_id"], reviewed["context_digest"])
            == (context.project_id, context.project_instance_id, context.context_digest),
            "PROJECT_IDENTITY_MISMATCH", "Candidate evidence belongs to another Project")
    current = preflight(context, {key: reviewed[key] for key in REQUEST_FIELDS}, pin_scope=pin_scope)
    require(digest(current) == digest(reviewed), "INPUT_CHANGED", "Candidate or a declared dependency changed after preflight")
    root = Path(current["working_directory"])
    return [{"path": str(root / item["reference"]), "size": item["bytes"], "digest": item["content_digest"]}
            for item in current["files"]]


def receipt_binding(plan, grant_id):
    candidate = plan["dynamic_inp"]
    keys = ("contract_version", "candidate_id", "project_id", "project_instance_id", "main_sha256",
            "input_manifest_digest", "v1", "v2")
    return {**{key: candidate[key] for key in keys}, "plan_id": plan["plan_id"],
            "plan_digest": plan["plan_digest"], "grant_id": grant_id, "v0": "INPUT_BOUND"}
