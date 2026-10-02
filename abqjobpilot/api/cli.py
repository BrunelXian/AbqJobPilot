"""JSON CLI for the safe public abqjobpilot API."""

from __future__ import annotations

import argparse
import json
import sys

from abqjobpilot import config

from .client import AbqJobPilotClient
from .models import JobRequest
from .project_surface import AutomationResult, SurfaceFailure


class CliArgumentError(Exception):
    pass


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliArgumentError(message)


def _selector_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", help="Explicit formal Project directory")
    parser.add_argument("--project-id", help="Registered Project UUID")
    parser.add_argument("--project-name", help="Unique exact registered Project name")


def _selector(args: argparse.Namespace) -> dict[str, str | None]:
    return {"project": getattr(args, "project", None),
            "project_id": getattr(args, "project_id", None),
            "project_name": getattr(args, "project_name", None)}


def _project_commands(subparsers: argparse._SubParsersAction) -> None:
    project = subparsers.add_parser("project", help="Manage formal Projects; never deletes Project files.")
    actions = project.add_subparsers(dest="project_action", required=True)
    for name in ("list", "create", "show", "update", "register", "unregister", "export", "import"):
        item = actions.add_parser(name)
        item.add_argument("--json", action="store_true", dest="as_json")
        if name in {"show", "update", "unregister", "export"}:
            _selector_args(item)
        if name == "create":
            item.add_argument("--name", required=True)
            item.add_argument("--description")
            item.add_argument("--path")
        elif name == "update":
            item.add_argument("--name")
            item.add_argument("--description")
            item.add_argument("--clear-description", action="store_true")
        elif name == "register":
            item.add_argument("--project", required=True)
        elif name == "export":
            item.add_argument("--mode", choices=("metadata", "project-owned"), default="metadata")
            item.add_argument("--output", required=True)
        elif name == "import":
            item.add_argument("--archive", required=True)
            item.add_argument("--destination")

    job = subparsers.add_parser("job", help="Read Project Job/Run history.")
    job_actions = job.add_subparsers(dest="job_action", required=True)
    for name in ("list", "show"):
        item = job_actions.add_parser(name)
        _selector_args(item)
        item.add_argument("--json", action="store_true", dest="as_json")
        if name == "list":
            item.add_argument("--status")
            item.add_argument("--batch")
            item.add_argument("--strategy")
            item.add_argument("--limit", type=int)
        else:
            item.add_argument("--job-id", required=True)


def main(argv: list[str] | None = None) -> int:
    parser = JsonArgumentParser(prog="python -m abqjobpilot.api.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _project_commands(subparsers)

    capabilities_parser = subparsers.add_parser("capabilities", help="Describe the read-only automation contract.")
    capabilities_parser.add_argument("--json", action="store_true", dest="as_json")
    capabilities_parser.add_argument("--runtime-dir")

    list_parser = subparsers.add_parser("list", help="List records in queue.json, including retained results.")
    list_parser.add_argument("--json", action="store_true", dest="as_json")
    list_parser.add_argument("--runtime-dir")
    _selector_args(list_parser)

    _add_request_args(subparsers.add_parser("preflight", help="Validate and preview a job request."))
    enqueue_parser = subparsers.add_parser("enqueue", help="Dry-run or enqueue a job request.")
    _add_request_args(enqueue_parser)
    enqueue_parser.add_argument("--dry-run", action="store_true", default=True, help="Preview only; do not modify queue.json.")
    enqueue_parser.add_argument("--enqueue-only", action="store_true", help="Write queue metadata only; never starts Abaqus.")

    folder_parser = subparsers.add_parser("enqueue-folder", help="Preview or queue INP files in one folder.")
    folder_parser.add_argument("--folder", required=True)
    folder_parser.add_argument("--pattern", default="*.inp")
    folder_parser.add_argument("--cpus", type=int, default=config.DEFAULT_CPUS)
    folder_parser.add_argument("--gpus", type=int, default=config.DEFAULT_GPUS)
    folder_parser.add_argument("--batch")
    folder_parser.add_argument("--strategy")
    folder_parser.add_argument("--enqueue-only", action="store_true")
    folder_parser.add_argument("--runtime-dir")
    _selector_args(folder_parser)
    folder_parser.add_argument("--json", action="store_true", dest="as_json")

    status_parser = subparsers.add_parser("status", help="Read job status.")
    status_parser.add_argument("--job-id")
    status_parser.add_argument("--inp")
    status_parser.add_argument("--json", action="store_true", dest="as_json")
    status_parser.add_argument("--runtime-dir")
    _selector_args(status_parser)

    outputs_parser = subparsers.add_parser("locate-outputs", help="Locate expected job output files.")
    outputs_parser.add_argument("--job-id")
    outputs_parser.add_argument("--inp")
    outputs_parser.add_argument("--json", action="store_true", dest="as_json")
    outputs_parser.add_argument("--runtime-dir")
    _selector_args(outputs_parser)

    try:
        args = parser.parse_args(argv)
    except CliArgumentError as exc:
        return _emit(AutomationResult("INVALID_REQUEST", errors=[str(exc)],
                                      error_details=[{"code": "INVALID_REQUEST", "message": str(exc)}]),
                     "--json" in (argv if argv is not None else sys.argv[1:]))
    client = AbqJobPilotClient(runtime_dir=getattr(args, "runtime_dir", None))
    selector = _selector(args)
    if args.command not in {"project", "job", "capabilities"} and any(selector.values()):
        if getattr(args, "runtime_dir", None):
            result = AutomationResult("INVALID_PROJECT_SELECTOR", errors=["Do not combine Project selection with --runtime-dir"],
                                      error_details=[{"code": "INVALID_PROJECT_SELECTOR", "message": "Do not combine Project selection with --runtime-dir"}])
            return _emit(result, args.as_json)
        try:
            client = client.for_project(**selector)
        except SurfaceFailure as exc:
            return _emit(AutomationResult(exc.code, exc.details, [exc.message],
                                          error_details=[{"code": exc.code, "message": exc.message}]), args.as_json)
        except (OSError, ValueError) as exc:
            return _emit(AutomationResult("PROJECT_INVALID", errors=[str(exc)],
                                          error_details=[{"code": "PROJECT_INVALID", "message": str(exc)}]), args.as_json)

    if args.command == "capabilities":
        result = client.capabilities()
    elif args.command == "project":
        action = args.project_action
        if action == "list":
            result = client.list_projects()
        elif action == "create":
            result = client.create_project(args.name, path=args.path, description=args.description)
        elif action == "show":
            result = client.show_project(**selector)
        elif action == "update":
            result = client.update_project(**selector, name=args.name,
                                           description=None if args.clear_description else args.description,
                                           update_description=args.clear_description or args.description is not None)
        elif action == "register":
            result = client.register_project(args.project)
        elif action == "unregister":
            result = client.unregister_project(**selector)
        elif action == "export":
            result = client.export_project(args.output, mode=args.mode, **selector)
        else:
            result = client.import_project_archive(args.archive, destination=args.destination)
    elif args.command == "job":
        if args.job_action == "list":
            result = client.list_project_jobs(**selector, status=args.status, batch=args.batch,
                                              strategy=args.strategy, limit=args.limit)
        else:
            result = client.show_job(args.job_id, **selector)
    elif args.command == "list":
        result = client.list_jobs()
    elif args.command == "preflight":
        result = client.preflight(_request_from_args(args))
    elif args.command == "enqueue":
        request = _request_from_args(args)
        if args.enqueue_only and request.submission_mode == "preview_only":
            request.submission_mode = "enqueue_only"
        result = client.enqueue(request, dry_run=not bool(args.enqueue_only))
    elif args.command == "status":
        result = client.status(job_id=args.job_id, inp_path=args.inp)
    elif args.command == "enqueue-folder":
        result = client.enqueue_folder(args.folder, args.pattern, cpus=args.cpus, gpus=args.gpus,
                                       batch=args.batch, strategy=args.strategy, dry_run=not args.enqueue_only)
    elif args.command == "locate-outputs":
        result = client.locate_outputs(job_id=args.job_id, inp_path=args.inp)
    else:
        parser.error("unknown command")

    return _emit(result, getattr(args, "as_json", False))


def _emit(result, as_json: bool) -> int:
    data = result if isinstance(result, dict) else result.to_dict()
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(data.get("status", "OK"))
        for key in ("project", "projects", "jobs", "archive", "job"):
            if key in data:
                print(json.dumps({key: data[key]}, ensure_ascii=False, indent=2))
        for error in data.get("errors", []):
            print(error, file=sys.stderr)
    return 0 if not data.get("errors") else 1


def _add_request_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--inp", required=True)
    parser.add_argument("--job-name")
    parser.add_argument("--cpus", type=int, default=config.DEFAULT_CPUS)
    parser.add_argument("--gpus", type=int, default=config.DEFAULT_GPUS)
    parser.add_argument("--batch")
    parser.add_argument("--strategy")
    parser.add_argument("--working-dir")
    parser.add_argument("--submission-mode", default="preview_only", choices=("preview_only", "enqueue_only", "submit"))
    parser.add_argument("--allow-solver-submit", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--runtime-dir")
    _selector_args(parser)


def _request_from_args(args: argparse.Namespace) -> JobRequest:
    return JobRequest(
        inp_path=args.inp,
        job_name=args.job_name,
        cpus=args.cpus,
        gpus=args.gpus,
        batch=args.batch,
        strategy=args.strategy,
        working_dir=args.working_dir,
        submission_mode=args.submission_mode,
        allow_solver_submit=args.allow_solver_submit,
    )


if __name__ == "__main__":
    sys.exit(main())
