"""Read-only approval-package recheck. No launch, grant, database or result inference.

The expected digest must come from the independently reviewed approval request.
This is a change detector, not a signature, lock, permission or runtime validation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys


def review(manifest, expected_digest):
    from abqjobpilot.abaqus_preview import prepare, inspect
    from abqjobpilot.abaqus_preview.inputs import directory
    from abqjobpilot.execution.paths import no_reparse
    from abqjobpilot.execution.models import digest, require

    require(type(manifest) is dict and set(manifest) == {"body", "content_digest"},
            "INVALID_REQUEST", "Expected review manifest")
    body = manifest["body"]
    require(manifest["content_digest"] == expected_digest == digest(body),
            "PACKAGE_CHANGED", "Manifest differs from reviewed digest")
    require(body["schema_version"] == "abaqus-first-probe-manifest-v1"
            and body["execution_authorized"] is False, "INVALID_REQUEST", "Preparation only")
    require(1 <= len(body["materials"]) <= 64, "LIMIT_EXCEEDED", "Material count exceeded")
    for item in body["materials"]:
        path = Path(item["path"])
        directory(str(path.parent))
        require(type(item["bytes"]) is int and 0 <= item["bytes"] <= 16 * 1024 * 1024,
                "LIMIT_EXCEEDED", "Material size exceeded")
        no_reparse(path)
        # Installed Windows components may have legitimate NTFS hardlinks.
        # This is a static material change check, not an INP identity policy.
        # prepare() below still uses the original pinned, single-link INP path.
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            require(stat.S_ISREG(before.st_mode), "UNSUPPORTED_PATH", "Regular material required")
            data = stream.read(item["bytes"] + 1)
            stream.seek(0)
            require(stream.read(item["bytes"] + 1) == data, "PACKAGE_CHANGED", "Material unstable")
        no_reparse(path)
        after = path.stat()
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
                "PACKAGE_CHANGED", "Material identity changed")
        require(len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"],
                "PACKAGE_CHANGED", "Reviewed material changed")
    preview = inspect(prepare(**body["prepare_request"]))
    require(preview["content_digest"] == body["preview_digest"], "PACKAGE_CHANGED", "Preview changed")
    root = directory(body["prepare_request"]["submission_cwd"])
    job = body["prepare_request"]["job_name"]
    require(not any(root.glob(job + ".*")), "OUTPUT_EXISTS", "Do not reuse candidate output name")
    return {"status": "OFFLINE_PACKAGE_UNCHANGED", "experiment_id": body["experiment_id"],
            "manifest_digest": expected_digest, "preview_digest": preview["content_digest"],
            "execution_authorized": False, "run_created": False,
            "runtime_verified": False, "output_reserved": False,
            "warning": "Read view only; changed materials or output competition require refusal before any future launch"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--expected-manifest-digest", required=True)
    args = parser.parse_args()
    if not Path(args.source).is_absolute() or not Path(args.manifest).is_absolute():
        parser.error("Explicit absolute source and manifest required")
    sys.path.insert(0, args.source)

    def no_execution(event, values):
        if event in {"subprocess.Popen", "os.system", "os.startfile", "sqlite3.connect", "socket.connect"}:
            raise RuntimeError("Read-only review has no execution capability")
    sys.addaudithook(no_execution)
    from abqjobpilot.execution.models import ExecutionError
    try:
        with Path(args.manifest).open("rb") as stream:
            data = stream.read(65537)
        if len(data) > 65536:
            raise ExecutionError("LIMIT_EXCEEDED", "Manifest limit")
        result = review(json.loads(data), args.expected_manifest_digest)
        print(json.dumps(result, sort_keys=True))
        return 0
    except ExecutionError as exc:
        print(json.dumps({"status": "REVIEW_REFUSED", "code": exc.code, "execution_authorized": False}))
        return 2
    except (OSError, ValueError, TypeError, KeyError):
        print(json.dumps({"status": "REVIEW_REFUSED", "code": "PACKAGE_UNAVAILABLE", "execution_authorized": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
