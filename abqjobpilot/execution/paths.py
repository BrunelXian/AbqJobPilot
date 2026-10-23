"""Explicit local test-root confinement, with no default path discovery."""

from pathlib import Path
import stat

from .models import ExecutionError, require


def local_path(value):
    path = Path(value)
    require(path.is_absolute() and not str(path).startswith(("\\\\", "//"))
            and ".." not in path.parts, "OUTPUT_SCOPE_VIOLATION", "An absolute local path without '..' is required")
    # Reject ADS and drive-relative components, including on Windows.
    require(all(":" not in part for part in path.parts[1:]), "OUTPUT_SCOPE_VIOLATION", "Alternate streams are unsupported")
    return path


def no_reparse(path):
    for part in (*reversed(path.parents), path):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ExecutionError("PATH_UNAVAILABLE", str(exc)) from exc
        require(not stat.S_ISLNK(info.st_mode)
                and not (getattr(info, "st_file_attributes", 0) & 0x400),
                "OUTPUT_SCOPE_VIOLATION", "Symlinks and reparse points are unsupported")


def confined(root, value, *, exists=False):
    root, path = local_path(root), local_path(value)
    # This lexical check precedes filesystem access to a supplied candidate.
    require(path.is_relative_to(root), "OUTPUT_SCOPE_VIOLATION", "Path lies outside explicit test root")
    no_reparse(root)
    no_reparse(path)
    resolved = path.resolve()
    require(resolved.is_relative_to(root.resolve()), "OUTPUT_SCOPE_VIOLATION", "Resolved path escapes test root")
    if exists:
        require(resolved.exists(), "NOT_FOUND", "Explicit path does not exist")
    return resolved


def result_path(context, run_id):
    require(type(run_id) is str and run_id.startswith("r_")
            and len(run_id) == 34 and all(c in "0123456789abcdef" for c in run_id[2:]),
            "INVALID_REQUEST", "Invalid Run ID")
    return confined(context.test_root, Path(context.runtime_root) / "fake_runs" / run_id / "result.json")
