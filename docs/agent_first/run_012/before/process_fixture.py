"""Fixed trusted test executable. No database, credentials, imports or commands from requests."""

import argparse
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def identity(pid=None):
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    api.OpenProcess.restype = ctypes.c_void_p
    api.GetProcessTimes.argtypes = [ctypes.c_void_p] * 5
    api.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p]
    api.CloseHandle.argtypes = [ctypes.c_void_p]
    pid = os.getpid() if pid is None else pid
    handle = api.OpenProcess(0x1000, False, pid)
    if not handle:
        raise OSError("Fixture identity unavailable")
    try:
        times = [ctypes.c_uint64() for _ in range(4)]
        if not api.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
            raise OSError("Fixture creation time unavailable")
        buffer, size = ctypes.create_unicode_buffer(32768), ctypes.c_uint32(32768)
        if not api.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            raise OSError("Fixture image unavailable")
        return {"pid": pid, "parent_pid": os.getppid(), "creation_time_100ns": times[0].value, "image_path": buffer.value}
    finally:
        api.CloseHandle(handle)


def write(path, value):
    temporary = path.with_suffix(".partial")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, separators=(",", ":"))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.rename(path)


def wait(path, deadline):
    while not path.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError("Fixed fixture lifetime exceeded")
        time.sleep(0.01)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=("launcher", "worker"), required=True)
    parser.add_argument("--directory", required=True)
    args = parser.parse_args()
    root = Path(args.directory)
    # Only the backend creates this fixed bounded manifest in its exclusive Run directory.
    raw = (root / "fixture.json").read_bytes()
    if len(raw) > 16384:
        raise ValueError("Oversize fixture")
    data = json.loads(raw)
    deadline = time.monotonic() + data["max_seconds"]
    binding = {k: data[k] for k in ("run_id", "project_instance_id", "phase_attempt_id", "plan_digest")}
    write(root / (args.role + ".json"), {**binding, **identity(), "role": args.role,
                                       "environment_keys": sorted(os.environ)})
    if args.role == "launcher":
        worker = subprocess.Popen([sys.executable, "-I", "-S", "-B", str(Path(__file__).resolve()),
                                   "--role", "worker", "--directory", str(root)],
                                  shell=False, close_fds=True, cwd=str(root), env=dict(os.environ),
                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
        write(root / "worker_transport.json", {**binding, **identity(worker.pid), "role": "worker_transport"})
        wait(root / "owner-bound.json", deadline)  # Owner holds every required reference before launcher exits.
        return 0
    wait(root / "owner-bound.json", deadline)
    if data["scenario"] == "launcher_early":
        wait(root / "release.json", deadline)
    value = data["expected_result"]
    if data["scenario"] == "invalid_result":
        value = {**value, "plan_digest": "incorrect"}
    write(root / "result.json", value)
    if data["scenario"] == "result_wait":
        wait(root / "release.json", deadline)
    return 23 if data["scenario"] == "nonzero" else 0


if __name__ == "__main__":
    raise SystemExit(main())
