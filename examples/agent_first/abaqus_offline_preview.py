"""Ordinary offline client. Inputs/profile are supplied by the operator, never generated here."""

import argparse
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description="Development-only non-executable Abaqus preview")
    for flag in ("source", "project", "profile", "engineering-root", "submission-cwd", "main-input", "job"):
        parser.add_argument("--" + flag, required=True)
    parser.add_argument("--export-root")
    parser.add_argument("--export-name", default="preview.json")
    parser.add_argument("--support-profile", default="windows-standard-static-subset-v1")
    args = parser.parse_args()
    source = Path(args.source)
    if not source.is_absolute():
        parser.error("--source must be an absolute Dev import root")
    sys.path.insert(0, str(source))  # Only this client process; no installation.

    def guard(event, values):
        if event in {"subprocess.Popen", "os.system", "os.startfile", "sqlite3.connect", "socket.connect"}:
            raise RuntimeError("Offline client has no execution or database capability")
        if event == "import" and (values[0].startswith(("tests", "pytest", "abqjobpilot.execution.store",
                "abqjobpilot.execution.service", "abqjobpilot.execution.test_authority", "abqjobpilot.runner_core",
                "abqjobpilot.config", "abqjobpilot.project", "abqjobpilot.gui_app", "abqjobpilot.settings_store"))):
            raise RuntimeError("Forbidden offline client import")
    sys.addaudithook(guard)
    from abqjobpilot.abaqus_preview import prepare, inspect, export_preview
    from abqjobpilot.execution.models import ExecutionError, require
    from abqjobpilot.abaqus_preview.inputs import directory, relative, _open_pinned

    def read_object(name):
        path = Path(name)
        root = directory(str(path.parent))
        relative(path.name)
        with _open_pinned(root / path.name) as stream:
            content = stream.read(4097)
        require(len(content) <= 4096, "LIMIT_EXCEEDED", "Declaration too large")
        def pairs(items):
            result = {}
            for key, value in items:
                require(key not in result, "INVALID_REQUEST", "Duplicate declaration key")
                result[key] = value
            return result
        return json.loads(content.decode("utf-8"), object_pairs_hook=pairs)

    try:
        preview = prepare(project=read_object(args.project), runtime_profile=read_object(args.profile),
                          engineering_root=args.engineering_root, submission_cwd=args.submission_cwd,
                          main_input=args.main_input, job_name=args.job,
                          support_profile_version=args.support_profile)
        result = {"status": "PREVIEW_PREPARED", "preview": inspect(preview), "client_pid": os.getpid()}
        if args.export_root:
            result["export"] = export_preview(preview, export_root=args.export_root, target=args.export_name)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0
    except ExecutionError as exc:
        print(json.dumps({"status": "PREVIEW_REJECTED", "code": exc.code, "client_pid": os.getpid(),
                          "run_created": False, "next_step": "Correct the restricted offline request; no execution was accepted"}))
        return 2
    except (OSError, ValueError, TypeError):
        print(json.dumps({"status": "PREVIEW_REJECTED", "code": "INVALID_DECLARATION", "run_created": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
