"""Parser for the Agent Command Console internal commands."""

from __future__ import annotations

import argparse
import re
import shlex

from . import config


COMMAND_EXAMPLES = {
    "enqueue": 'enqueue --inp "D:\\path\\Job_xxx.inp" --cpus 14 --gpus 1 --batch batch_name --strategy strategy_name',
    "enqueue-folder": 'enqueue-folder --folder "D:\\path\\strategy_folder" --pattern "*.inp" --cpus 14 --gpus 1 --batch batch_name --strategy strategy_name',
    "list": "list",
    "help": "help",
    "clear": "clear",
}
SUPPORTED_COMMANDS = tuple(COMMAND_EXAMPLES)


def command_help_text(language: str = "en") -> str:
    heading = "支持的命令：" if language == "zh" else "Supported commands:"
    notes = ("说明：\n- 此控制台仅接受 AbqJobPilot 内部命令。\n- 不执行系统 Shell 命令。"
             if language == "zh" else
             "Notes:\n- This console only accepts AbqJobPilot internal commands.\n"
             "- It never executes system shell commands.")
    return f"{heading}\n" + "\n".join(COMMAND_EXAMPLES.values()) + f"\n\n{notes}\n"


HELP_TEXT = command_help_text()


class CommandParseError(ValueError):
    """Raised when an Agent Command cannot be parsed."""


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise CommandParseError(message)


def _str_to_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "y", "on"}:
        return True
    if lowered in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"expected boolean value, got {value!r}")


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="agent", add_help=False)
    subparsers = parser.add_subparsers(dest="command")

    enqueue = subparsers.add_parser("enqueue", add_help=False)
    enqueue.add_argument("--inp", required=True)
    enqueue.add_argument("--cpus", type=int)
    enqueue.add_argument("--gpus", type=int)
    enqueue.add_argument("--batch", dest="batch_name")
    enqueue.add_argument("--strategy", dest="strategy_name")
    enqueue.add_argument("--job-name", dest="job_name")
    enqueue.add_argument("--datacheck", type=_str_to_bool, default=config.DEFAULT_RUN_DATACHECK)
    enqueue.add_argument("--full-run", type=_str_to_bool, default=config.DEFAULT_RUN_FULL)
    enqueue.add_argument("--notes", default="")

    folder = subparsers.add_parser("enqueue-folder", add_help=False)
    folder.add_argument("--folder", required=True)
    folder.add_argument("--pattern", default="*.inp")
    folder.add_argument("--cpus", type=int)
    folder.add_argument("--gpus", type=int)
    folder.add_argument("--batch", dest="batch_name")
    folder.add_argument("--strategy", dest="strategy_name")

    subparsers.add_parser("list", add_help=False)
    subparsers.add_parser("help", add_help=False)
    subparsers.add_parser("clear", add_help=False)
    return parser


def parse_agent_command(command_text: str) -> dict:
    text = command_text.strip()
    if not text:
        raise CommandParseError("empty command")
    try:
        tokens = shlex.split(text)
    except ValueError as exc:
        raise CommandParseError(str(exc)) from exc
    if not tokens:
        raise CommandParseError("empty command")

    parser = _build_parser()
    try:
        namespace, unknown = parser.parse_known_args(tokens)
    except SystemExit as exc:
        raise CommandParseError(str(exc)) from exc
    if unknown:
        raise CommandParseError(f"unknown arguments: {' '.join(unknown)}")
    if not namespace.command:
        raise CommandParseError(f"unknown command: {tokens[0]}")
    return vars(namespace)


def extract_agent_commands(command_text: str) -> list[str]:
    """Extract one or more internal commands from pasted AI/chat output."""

    commands: list[str] = []
    in_code_fence = False
    for raw_line in command_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("```"):
            in_code_fence = not in_code_fence
            continue

        line = re.sub(r"^(?:[-*]|\d+[.)])\s+", "", line)
        if line.startswith(">"):
            line = line[1:].strip()
        if line.startswith("#") or line.startswith("//"):
            continue

        first = line.split(maxsplit=1)[0]
        if first in SUPPORTED_COMMANDS:
            commands.append(line)
            continue
        if in_code_fence:
            for command in SUPPORTED_COMMANDS:
                marker = command + " "
                index = line.find(marker)
                if index >= 0:
                    commands.append(line[index:].strip())
                    break
    return commands
