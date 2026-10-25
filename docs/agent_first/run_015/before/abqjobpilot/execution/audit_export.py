"""Client-side publication of an already obtained audit view. No store/network IO."""

import os
import json
from pathlib import Path

from .diagnostics import report_bytes
from .models import ExecutionError, identifier, require
from .paths import confined, local_path, no_reparse


def export_report(report, *, export_root, target):
    temporary = identity = None
    try:
        content = report_bytes(report)  # Freeze these exact bytes; never query again.
        content_digest = json.loads(content)["content_digest"]
        require(os.name == "nt", "UNSUPPORTED_PLATFORM", "Audit publication is validated on Windows only")
        root = local_path(export_root)
        destination = local_path(target)
        require(destination.parent == root and destination.suffix.lower() == ".json",
                "OUTPUT_SCOPE_VIOLATION", "Target must be a direct JSON child of the explicit export directory")
        no_reparse(root)
        require(root.is_dir(), "NOT_FOUND", "Explicit export directory must already exist")
        destination = confined(root, destination)
        require(not destination.exists(), "EXPORT_EXISTS", "Audit destination already exists")
        temporary = confined(root, root / (identifier("audit") + ".partial"))
        with temporary.open("xb") as stream:
            info = os.fstat(stream.fileno())
            identity = (info.st_dev, info.st_ino)
            require(stream.write(content) == len(content), "EXPORT_FAILED", "Incomplete audit write")
            stream.flush()
            os.fsync(stream.fileno())
        # On Windows rename fails if the destination appeared, unlike replace.
        confined(root, destination)
        temporary.rename(destination)
        temporary = None
        return {"status": "EXPORTED", "bytes": len(content), "content_digest": content_digest}
    except (ExecutionError, OSError, ValueError, TypeError, RecursionError) as exc:
        code = exc.code if isinstance(exc, ExecutionError) else "EXPORT_FAILED"
        if code not in {"INVALID_REPORT", "LIMIT_EXCEEDED", "OUTPUT_SCOPE_VIOLATION", "NOT_FOUND", "EXPORT_EXISTS", "UNSUPPORTED_PLATFORM"}:
            code = "EXPORT_FAILED"
        raise ExecutionError(code, "Audit export refused or failed; no business state changed; an owned partial file may remain", stage="EXPORT") from None
    finally:
        if temporary is not None and identity is not None:
            try:
                no_reparse(temporary)
                info = temporary.stat()
                if (info.st_dev, info.st_ino) == identity:
                    temporary.unlink()  # Only the file this invocation actually created.
            except (OSError, ExecutionError):
                pass  # Crash/cleanup failure is not silently reported as success.
