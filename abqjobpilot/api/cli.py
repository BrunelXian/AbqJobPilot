"""JSON CLI for the safe public abqjobpilot API."""

from __future__ import annotations

import argparse
import json
import sys

from abqjobpilot import config

from .client import AbqJobPilotClient
from .models import JobRequest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m abqjobpilot.api.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    capabilities_parser = subparsers.add_parser("capabilities", help="Describe the read-only automation contract.")
    capabilities_parser.add_argument("--json", action="store_true", dest="as_json")
    capabilities_parser.add_argument("--runtime-dir")

    list_parser = subparsers.add_parser("list", help="List records in queue.json, including retained results.")
    list_parser.add_argument("--json", action="store_true", dest="as_json")
    list_parser.add_argument("--runtime-dir")

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
    folder_parser.add_argument("--json", action="store_true", dest="as_json")

    status_parser = subparsers.add_parser("status", help="Read job status.")
    status_parser.add_argument("--job-id")
    status_parser.add_argument("--inp")
    status_parser.add_argument("--json", action="store_true", dest="as_json")
    status_parser.add_argument("--runtime-dir")

    outputs_parser = subparsers.add_parser("locate-outputs", help="Locate expected job output files.")
    outputs_parser.add_argument("--job-id")
    outputs_parser.add_argument("--inp")
    outputs_parser.add_argument("--json", action="store_true", dest="as_json")
    outputs_parser.add_argument("--runtime-dir")

    args = parser.parse_args(argv)
    client = AbqJobPilotClient(runtime_dir=getattr(args, "runtime_dir", None))

    if args.command == "capabilities":
        result = client.capabilities()
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

    data = result if isinstance(result, dict) else result.to_dict()
    print(json.dumps(data, ensure_ascii=False, indent=2))
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
