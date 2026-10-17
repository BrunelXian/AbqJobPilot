"""Explicitly Project-bound, read-only MCP server over stdio."""

from __future__ import annotations

import argparse
import logging
import sys
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from abqjobpilot import __version__, config
from abqjobpilot.api.project_surface import SurfaceFailure
from .tools import ReadOnlyTools


def build_server(project_path: str):
    """Build five SDK tools without starting transport or changing Project state."""
    try:
        sdk_version = version("mcp")
        if sdk_version.split(".", 1)[0] != "2":
            raise RuntimeError(f"MCP Python SDK v2 is required; found {sdk_version}")
        from mcp.server import MCPServer
        from mcp.types import ToolAnnotations
    except (PackageNotFoundError, ModuleNotFoundError) as exc:
        raise RuntimeError("Optional MCP Python SDK v2 is unavailable; install mcp>=2,<3 in an isolated environment") from exc

    adapter = ReadOnlyTools(project_path)
    server = MCPServer(
        "AbqJobPilot",
        version=__version__,
        instructions="Read-only AbqJobPilot Project inspection and enqueue preview. No solver start or queue mutation.",
    )
    readonly = ToolAnnotations(readOnlyHint=True, destructiveHint=False)

    @server.tool(annotations=readonly, structured_output=True)
    def abq_preflight(inp_path: str, job_name: str | None = None,
                      cpus: int = config.DEFAULT_CPUS, gpus: int = config.DEFAULT_GPUS,
                      working_dir: str | None = None, batch: str | None = None,
                      strategy: str | None = None) -> dict[str, Any]:
        """Validate an INP request and preview commands without Abaqus datacheck."""
        return adapter.preflight(inp_path, job_name, cpus, gpus, working_dir, batch, strategy)

    @server.tool(annotations=readonly, structured_output=True)
    def abq_list_jobs(scope: str = "queue", status: str | None = None,
                      batch: str | None = None, strategy: str | None = None,
                      limit: int = 50) -> dict[str, Any]:
        """List bounded queue records or logical historical Jobs for the bound Project."""
        return adapter.list_jobs(scope, status, batch, strategy, limit)

    @server.tool(annotations=readonly, structured_output=True)
    def abq_job_status(scope: str, identifier: str) -> dict[str, Any]:
        """Read queue_id or logical job_id status; stored RUNNING is unconfirmed."""
        return adapter.job_status(scope, identifier)

    @server.tool(annotations=readonly, structured_output=True)
    def abq_locate_outputs(queue_id: str | None = None,
                           inp_path: str | None = None) -> dict[str, Any]:
        """Locate expected or recorded ODB/STA/MSG/DAT/LOG/LCK paths without opening ODB."""
        return adapter.locate_outputs(queue_id, inp_path)

    @server.tool(annotations=readonly, structured_output=True)
    def abq_prepare_enqueue(inp_path: str, job_name: str | None = None,
                            cpus: int = config.DEFAULT_CPUS, gpus: int = config.DEFAULT_GPUS,
                            working_dir: str | None = None, batch: str | None = None,
                            strategy: str | None = None) -> dict[str, Any]:
        """Dry-run a queue request; no enqueue, approval, runner, or solver action."""
        return adapter.prepare_enqueue(inp_path, job_name, cpus, gpus, working_dir, batch, strategy)

    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m abqjobpilot.mcp.server")
    parser.add_argument("--project", required=True, help="Path to one formal AbqJobPilot Project")
    args = parser.parse_args(argv)
    try:
        server = build_server(args.project)
    except (OSError, ValueError, RuntimeError, SurfaceFailure) as exc:
        logging.basicConfig(stream=sys.stderr, level=logging.ERROR, format="%(levelname)s: %(message)s")
        logging.error("Cannot start AbqJobPilot MCP server: %s", exc)
        return 2
    server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
