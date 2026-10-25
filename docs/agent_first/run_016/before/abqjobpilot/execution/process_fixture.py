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


def wait(path, deadline, progress=None):
    while not path.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError("Fixed fixture lifetime exceeded")
        if progress:
            progress('WAITING')
        time.sleep(0.01)


class Progress:
    """Fixed, bounded worker messages; no caller-supplied text or paths."""
    def __init__(self, root, binding):
        self.stream = (root / 'progress.jsonl').open('xb', buffering=0)
        self.binding, self.sequence, self.next_at, self.size = binding, 0, 0, 0

    def __call__(self, event):
        if event == 'WAITING' and time.monotonic() < self.next_at:
            return
        self.next_at = time.monotonic() + 0.5
        self.sequence += 1
        payload = (json.dumps({**self.binding, 'sequence': self.sequence, 'event': event,
                              'observed_at': int(time.time())}, separators=(',', ':'))+'\n').encode('utf-8')
        if self.sequence > 128 or self.size + len(payload) > 65536:
            raise ValueError('Fixed progress bound exceeded')
        self.stream.write(payload)
        self.size += len(payload)

    def close(self):
        self.stream.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=("launcher", "worker", "branch", "leaf", "burst"), required=True)
    parser.add_argument("--directory", required=True)
    parser.add_argument('--index',type=int,choices=range(6),default=0)
    args = parser.parse_args()
    root = Path(args.directory)
    # Only the backend creates this fixed bounded manifest in its exclusive Run directory.
    raw = (root / "fixture.json").read_bytes()
    if len(raw) > 16384:
        raise ValueError("Oversize fixture")
    data = json.loads(raw)
    deadline = time.monotonic() + data["max_seconds"]
    binding = {k: data[k] for k in ("run_id", "project_instance_id", "phase_attempt_id", "plan_digest")}
    label=args.role+str(args.index) if args.role=='burst' else args.role
    write(root / (label + ".json"), {**binding, **identity(), "role": args.role,
                                       "environment_keys": sorted(os.environ)})
    def child(role,index=0):
        return subprocess.Popen([sys.executable,'-I','-S','-B',str(Path(__file__).resolve()),
            '--role',role,'--directory',str(root),'--index',str(index)],shell=False,close_fds=True,
            cwd=str(root),env=dict(os.environ),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    if args.role=='burst':
        if data['scenario']!='managed_burst':raise ValueError('Unexpected fixed child scenario')
        return 0
    if args.role=='leaf':
        if data['scenario']!='managed_tree':raise ValueError('Unexpected fixed child scenario')
        wait(root/'leaf-release.json',deadline)
        return 0
    if args.role=='branch':
        if data['scenario']!='managed_tree':raise ValueError('Unexpected fixed child scenario')
        wait(root/'branch-release.json',deadline)
        child('leaf')
        wait(root/'leaf.json',deadline)
        return 0
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
    progress = Progress(root, binding)
    try:
        progress('WORKER_READY')
        if data['scenario']=='managed_tree':
            child('branch');wait(root/'branch.json',deadline)
        if data['scenario']=='managed_burst':
            # Deliberately do not enumerate/wait each transient child for completion.
            # The retained Job's OS accounting, not these files, closes the range.
            for index in range(6):child('burst',index)
        if data["scenario"] == "launcher_early":
            wait(root / "release.json", deadline, progress)
        value = data["expected_result"]
        if data["scenario"] == "invalid_result":
            value = {**value, "plan_digest": "incorrect"}
        write(root / "result.json", value)
        progress('RESULT_WRITTEN')
        if data["scenario"] == "result_wait":
            wait(root / "release.json", deadline, progress)
        progress('WORKER_RETURNING')  # Self-report, never OS exit evidence.
        return 23 if data["scenario"] == "nonzero" else 0
    finally:
        progress.close()


if __name__ == "__main__":
    raise SystemExit(main())
