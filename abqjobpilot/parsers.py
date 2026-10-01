"""Lightweight Abaqus status parsers for the MVP."""

from __future__ import annotations

import re


SUCCESS_PATTERN = "THE ANALYSIS HAS COMPLETED SUCCESSFULLY"
FATAL_PATTERNS = (
    "THE ANALYSIS HAS BEEN TERMINATED",
    "Abaqus/Standard aborted",
    "Too many attempts made for this increment",
    "Analysis Input File Processor exited with an error",
    "THE ANALYSIS HAS NOT BEEN COMPLETED",
    "Abaqus Error",
    "Error in job",
)
NON_FATAL_ERROR_PHRASES = (
    "CONTACT FORCE ERROR TOLERANCE",
    "force error tolerance",
    "residual error",
    "relative error",
)
DATACHECK_INVALID_GPU_OPTION = 'Command line option "gpus" may not be used with "datacheck"'


def _contains_success(text: str) -> bool:
    return SUCCESS_PATTERN in text.upper()


def _fatal_matches(text: str) -> list[str]:
    matches: list[str] = []
    lines = text.splitlines() or [text]
    for line in lines:
        if any(phrase.lower() in line.lower() for phrase in NON_FATAL_ERROR_PHRASES):
            continue
        for pattern in FATAL_PATTERNS:
            if pattern.lower() in line.lower():
                matches.append(pattern)
                break
    return matches


def parse_sta_status(sta_text: str) -> dict:
    status = {
        "step": "",
        "increment": "",
        "analysis_time": "",
        "last_numeric_line": "",
        "completed_successfully": _contains_success(sta_text),
        "fatal_detected": False,
        "fatal_reason": "",
    }
    matches = _fatal_matches(sta_text)
    if matches:
        status["fatal_detected"] = True
        status["fatal_reason"] = matches[0]

    numeric_lines: list[list[str]] = []
    for line in sta_text.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
            numeric_lines.append(parts)
            status["last_numeric_line"] = line.strip()
    if numeric_lines:
        latest = numeric_lines[-1]
        status["step"] = latest[0]
        status["increment"] = latest[1]
        for token in reversed(latest):
            if re.search(r"[0-9]", token):
                status["analysis_time"] = token
                break
    return status


def parse_console_status(log_text: str) -> dict:
    matches = _fatal_matches(log_text)
    warning_count = len(re.findall(r"\bWARNING\b", log_text, flags=re.IGNORECASE))
    return {
        "completed_successfully": _contains_success(log_text),
        "fatal_detected": bool(matches),
        "fatal_reason": matches[0] if matches else "",
        "warning_count": warning_count,
    }


def latest_attempt_block(log_text: str, phase: str) -> str:
    lines = log_text.splitlines()
    start_marker = f"START {phase}"
    end_marker = f"END {phase}"
    start_index = None
    for index, line in enumerate(lines):
        if start_marker in line:
            start_index = index
    if start_index is None:
        return log_text

    end_index = len(lines) - 1
    for index in range(start_index + 1, len(lines)):
        if end_marker in lines[index]:
            end_index = index
            break
    return "\n".join(lines[start_index : end_index + 1])


def _contains_abaqus_job_completed(text: str) -> bool:
    lowered = text.lower()
    return "abaqus job" in lowered and "completed" in lowered


def _contains_invalid_datacheck_gpu_option(text: str) -> bool:
    normalized = text.replace("“", '"').replace("”", '"')
    return DATACHECK_INVALID_GPU_OPTION.lower() in normalized.lower()


def classify_datacheck_attempt(log_text: str = "", return_code: int | None = None) -> dict:
    block = latest_attempt_block(log_text or "", "DATACHECK_RUNNING")
    warning_count = len(re.findall(r"\bWARNING\b", block, flags=re.IGNORECASE))

    if _contains_invalid_datacheck_gpu_option(block):
        return {
            "status": "DATACHECK_FAILED_INVALID_GPU_OPTION",
            "final_verdict": "FAILED",
            "fatal_reason": DATACHECK_INVALID_GPU_OPTION,
            "warning_count": warning_count,
            "attempt_block": block,
        }

    if _contains_abaqus_job_completed(block) and "abaqus error:" not in block.lower():
        return {
            "status": "DATACHECK_PASS",
            "final_verdict": "DATACHECK_PASS",
            "fatal_reason": "",
            "warning_count": warning_count,
            "attempt_block": block,
        }

    matches = _fatal_matches(block)
    if matches:
        return {
            "status": "DATACHECK_FAILED",
            "final_verdict": "FAILED",
            "fatal_reason": matches[0],
            "warning_count": warning_count,
            "attempt_block": block,
        }
    if return_code not in (None, 0):
        return {
            "status": "DATACHECK_FAILED",
            "final_verdict": "FAILED",
            "fatal_reason": f"datacheck return code {return_code}",
            "warning_count": warning_count,
            "attempt_block": block,
        }
    return {
        "status": "DATACHECK_PASS",
        "final_verdict": "DATACHECK_PASS",
        "fatal_reason": "",
        "warning_count": warning_count,
        "attempt_block": block,
    }


def classify_final_verdict(
    sta_text: str = "",
    msg_text: str = "",
    dat_text: str = "",
    log_text: str = "",
    return_code: int | None = None,
) -> dict:
    combined = "\n".join([sta_text or "", msg_text or "", dat_text or "", log_text or ""])
    matches = _fatal_matches(combined)
    warning_count = len(re.findall(r"\bWARNING\b", combined, flags=re.IGNORECASE))

    if matches:
        return {
            "status": "FAILED_FATAL",
            "final_verdict": "FAILED",
            "fatal_reason": matches[0],
            "warning_count": warning_count,
        }
    if return_code not in (None, 0):
        return {
            "status": "UNKNOWN_INTERRUPTED",
            "final_verdict": "FAILED",
            "fatal_reason": f"non-zero return code: {return_code}",
            "warning_count": warning_count,
        }
    if _contains_success(combined):
        return {
            "status": "COMPLETED_WITH_WARNINGS" if warning_count else "COMPLETED_OK",
            "final_verdict": "SUCCESS",
            "fatal_reason": "",
            "warning_count": warning_count,
        }
    return {
        "status": "UNKNOWN_INTERRUPTED",
        "final_verdict": "UNKNOWN",
        "fatal_reason": "",
        "warning_count": warning_count,
    }
