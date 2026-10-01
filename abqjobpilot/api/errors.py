"""Stable error codes for the small public automation surface."""

from __future__ import annotations


def error_detail(message: str) -> dict[str, str]:
    lowered = message.lower()
    rules = (
        ("inp file does not exist", "INP_NOT_FOUND"),
        ("cpus must", "INVALID_CPU_COUNT"),
        ("gpus must", "INVALID_GPU_COUNT"),
        ("job already exists", "DUPLICATE_ACTIVE_JOB"),
        ("runtime directory does not exist", "RUNTIME_NOT_FOUND"),
        ("invalid status data", "INVALID_STATUS_DATA"),
        ("queue write failed", "QUEUE_WRITE_FAILED"),
        ("invalid queue data", "INVALID_STATUS_DATA"),
        ("expected output file not found", "OUTPUT_NOT_FOUND"),
        ("was not found in queue", "QUEUE_RECORD_NOT_FOUND"),
        ("selected job was not found", "QUEUE_RECORD_NOT_FOUND"),
        ("unsafe_direct_submit", "UNSAFE_OPERATION"),
        ("submit mode requires", "UNSAFE_OPERATION"),
    )
    code = next((code for phrase, code in rules if phrase in lowered), "INVALID_REQUEST")
    return {"code": code, "message": message}
