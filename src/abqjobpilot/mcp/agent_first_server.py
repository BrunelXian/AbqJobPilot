"""Versioned Agent-first MCP tools over stdio."""

import argparse
import asyncio
import json
import sys
from importlib.metadata import version

from .. import __version__
from ..execution.models import ExecutionError, fields, text
from ..execution.odb_contract import FIXTURE, FRAME_LIMIT, REQUEST, SELECTOR, VERSION
from .agent_first_tools import AgentFirstTools, CONTRACT_VERSION, SUBMIT_FIELDS

STRING = {"type": "string", "minLength": 1, "maxLength": 256}


def build_server(project_path, connection_file=None, *, historical_read_only=False):
    if version("mcp").split(".", 1)[0] != "2":
        raise RuntimeError("Agent-first MCP requires Python MCP SDK v2")
    from mcp import types
    from mcp.server.lowlevel import Server

    adapter = AgentFirstTools(project_path, connection_file)
    submit = {**dict.fromkeys(SUBMIT_FIELDS, STRING),
              "job_revision": {"type": "integer", "minimum": 1, "maximum": 2**63 - 1}}
    extraction = {"type": "object", "additionalProperties": False, "required": list(REQUEST),
                  "properties": {"contract_version": {"const": VERSION}, "mode": {"enum": ["TEST_ONLY", "REAL"]},
                                 "receipt_id": STRING, "idempotency_key": STRING, "script_id": {"const": FIXTURE},
                                 **{key: {"const": value} for key, value in SELECTOR.items()},
                                 "first_frame": {"type": "integer", "minimum": 0, "maximum": FRAME_LIMIT - 1},
                                 "frame_count": {"type": "integer", "minimum": 1, "maximum": FRAME_LIMIT}}}
    specs = {
        "abq_check_environment": (adapter.check_environment, "Read bound Project and authenticated Owner capabilities.", {}, "READ"),
        "abq_get_grant_status": (adapter.grant_status, "Read delegated Grant validity and committed Run budget.",
                                 {"grant_id": STRING}, "READ"),
        "abq_submit_job": (adapter.submit_job, "Accept a preapproved TEST_ONLY Plan and consume one Grant unit. "
                           "The Owner dispatches only explicitly execution-enabled Fake Plans and Grants.",
                           submit, "CONTROLLED_WRITE"),
        "abq_get_run_status": (adapter.run_status, "Read a Run, available progress and recorded delegated Fake result evidence.",
                               {"run_id": STRING}, "READ"),
        "abq_get_receipt": (adapter.receipt, "Look up the committed submission Receipt by its original business key.",
                            {"idempotency_key": STRING}, "READ"),
        "abq_extract_odb": (adapter.extract_odb, "Native ODB unavailable. An explicitly provisioned TEST_ONLY fixture is supported.",
                            {"run_id": STRING, "extraction": extraction}, "CONTROLLED_OPERATION"),
    }
    availability = "OWNER_SCOPED"
    instructions = "Project-bound Agent-first MCP v1. Only existing TEST_ONLY delegated Plans may be accepted."
    if historical_read_only:
        from .historical_reads import HistoricalReads
        if connection_file is not None:
            raise ExecutionError("INVALID_REQUEST", "Historical reads do not accept an Owner connection")
        history = HistoricalReads(adapter.context)
        specs = {
            "abq_check_environment": (history.environment, "Read local source and historical Plan identity.", {}, "READ"),
            "abq_get_run_status": (history.run_status, "Read historical Run, Solver verdict and ODB provenance.",
                                   {"run_id": STRING}, "READ"),
            "abq_get_receipt": (history.receipt, "Read accepting Receipt, or extraction disposition and verdict "
                                "with the original extraction key and operation_id.",
                                {"idempotency_key": STRING, "operation_id": STRING}, "READ"),
        }
        availability = "HISTORICAL_READ_ONLY"
        instructions = "Local historical Sanity evidence only. No Owner connection or execution operations."
    optional = {"abq_get_receipt": "operation_id"} if historical_read_only else {"abq_extract_odb": "extraction"}
    required = {name: [key for key in parameters if key != optional.get(name)]
                for name, (_, _, parameters, _) in specs.items()}
    tools = [
        types.Tool(name=name, description=description,
                   inputSchema={"type": "object", "properties": parameters, "required": required[name],
                                "additionalProperties": False},
                   annotations=types.ToolAnnotations(readOnlyHint=permission == "READ", destructiveHint=False,
                                                     idempotentHint=permission != "CONTROLLED_OPERATION",
                                                     openWorldHint=False),
                   _meta={"abqjobpilot/contract_version": CONTRACT_VERSION, "abqjobpilot/permission": permission,
                          "abqjobpilot/availability": "UNAVAILABLE" if permission == "CONTROLLED_OPERATION" else availability})
        for name, (_, description, parameters, permission) in specs.items()
    ]

    async def list_tools(context, params):
        return types.ListToolsResult(tools=tools)

    async def call_tool(context, params):
        name, arguments = params.name, params.arguments if params.arguments is not None else {}
        envelope = {"contract_version": CONTRACT_VERSION, "project": adapter.project}
        try:
            if name not in specs:
                raise ExecutionError("UNKNOWN_TOOL", "Tool is outside the Agent-first interface")
            handler, _, parameters, _ = specs[name]
            if name == "abq_submit_job" and "grant_id" not in arguments:
                raise ExecutionError("GRANT_REQUIRED", "A registered delegated Grant ID is required")
            fields(arguments, required[name], set(parameters) - set(required[name]))
            if historical_read_only and "operation_id" in arguments:
                text(arguments["operation_id"])
            data = await asyncio.to_thread(handler, **arguments)
            payload = {**envelope, "ok": True, "data": data}
        except ExecutionError as exc:
            # Forward the stable error code, without leaking native paths, diagnostics or connection material.
            payload = {**envelope, "ok": False, "error": {"code": exc.code, "stage": exc.stage}}
            if name == "abq_submit_job":
                unknown = exc.code == "ACCEPTANCE_UNKNOWN"
                payload["request_status"] = "ACCEPTANCE_UNKNOWN" if unknown else "REJECTED"
                if unknown:
                    payload["idempotency_key"] = arguments["idempotency_key"]
                    payload["error"]["recovery"] = "QUERY_ORIGINAL_RECEIPT"
            if name == "abq_check_environment":
                payload["supervisor"] = {"status": "UNAVAILABLE"}
            if name == "abq_extract_odb" and exc.code == "ACCEPTANCE_UNKNOWN":
                payload["idempotency_key"] = arguments["extraction"]["idempotency_key"]
                payload["error"]["recovery"] = "QUERY_ORIGINAL_EXTRACTION_KEY"
        return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(payload, ensure_ascii=True))],
                                    structuredContent=payload, isError=not payload["ok"])

    return Server("AbqJobPilot Agent-first", version=__version__, on_list_tools=list_tools, on_call_tool=call_tool,
                  instructions=instructions)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m abqjobpilot.mcp.agent_first_server")
    parser.add_argument("--project", required=True, help="Absolute path to one existing Agent-first Project")
    parser.add_argument("--connection-file", help="Explicit original Project connection document")
    parser.add_argument("--historical-read-only", action="store_true", help="Serve only registered local Sanity evidence")
    args = parser.parse_args(argv)
    try:
        server = build_server(args.project, args.connection_file, historical_read_only=args.historical_read_only)
        from mcp.server.stdio import stdio_server
    except (ExecutionError, OSError, ValueError, RuntimeError, ImportError) as exc:
        print("Agent-first MCP startup refused:", getattr(exc, "code", "CAPABILITY_UNAVAILABLE"), file=sys.stderr)
        return 2

    async def serve():
        async with stdio_server() as (receive, send):
            await server.run(receive, send, server.create_initialization_options())

    asyncio.run(serve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
