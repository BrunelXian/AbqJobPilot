import ast
import builtins
import ctypes
import os
from pathlib import Path
import struct
import sys

import pytest

import abqjobpilot.execution as execution
from abqjobpilot.execution import ExecutionError, create_experiment
from abqjobpilot.execution.paths import confined
from execution_helpers import guard_environment, harness, inventory


def test_dependency_graph_excludes_all_legacy_and_launch_modules():
    root = Path(execution.__file__).parent
    allowed = {"dataclasses", "hashlib", "json", "time", "uuid", "pathlib", "stat", "contextlib",
               "sqlite3", "threading", "os"}
    # Explicit owner/transport modules may use only these additional stdlib APIs.
    # Core Fake/plan/validation retain their original no-launch dependency bound.
    # Exact operator capability comparison only. No process/OS transport APIs
    # are permitted in the new product control module; old bounds stay intact.
    additions = {"recovery": {"types"}, "interruption_probe": {"ctypes"}, "product_standard": {"hmac"}, "lifecycle": {"hmac"},"ownership": {"ctypes", "msvcrt", "sys"}, "protocol": {"socket", "struct"},
                 "supervisor": {"argparse", "hmac", "socket"}, "client": set(),
                 "process_handles": {"ctypes"}, "process_backend": {"subprocess", "sys"},
                 'managed_process': {'ctypes', 'subprocess', 'sys', 'msvcrt'},
                 "process_fixture": {"argparse", "ctypes", "subprocess", "sys"},
                 "standard_contract": {"re"}, "standard_dat": {"decimal", "re"},
                 "standard_process": {"ctypes", "sys"}, "standard_backend": {"subprocess"}}
    local_modules = {p.stem for p in root.glob("*.py")}
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        permitted = allowed | additions.get(path.stem, set())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(item.name in permitted for item in node.names), (path, ast.dump(node))
            if isinstance(node, ast.ImportFrom):
                assert (node.level == 1 and node.module in local_modules) or (node.level == 0 and node.module in permitted) or (path.stem == "lifecycle" and node.level == 2 and node.module == "service_lifecycle") or (path.stem == 'recovery' and node.level == 1 and node.module is None and [n.name for n in node.names] == ['closeout'])
                if path.stem in {"fake_backend", "planning", "validation", "authorization", "paths", "models"} and node.level:
                    assert node.module in {"models", "paths"}
                if path.stem == "client" and node.level:
                    assert node.module in {"models", "protocol", "audit_export"}
                if path.stem == "audit_export" and node.level:
                    assert node.module in {"models", "paths", "diagnostics"}
                if path.stem == "diagnostics" and node.level:
                    assert node.module == "models"
            if isinstance(node, ast.Call):
                assert not (isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec", "__import__", "compile"})
                if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                    permitted_os = {"getpid", "getppid", "fstat", "set_inheritable"} if path.stem == "ownership" else {"fsync"}
                    if path.stem in {"reconciliation", "audit_export", "progress_log"}:
                        permitted_os = {"fsync", "fstat"}
                    if path.stem == "process_fixture":
                        permitted_os = {"fsync", "getpid", "getppid"}
                    if path.stem == 'standard_process': permitted_os = {'getpid'}
                    assert node.func.attr in permitted_os
                if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
                    if path.stem == 'managed_process':
                        assert node.func.attr == 'list2cmdline'  # quoting only, no Popen fallback
                        continue
                    assert path.stem in {"process_backend", "process_fixture", "standard_backend"}
                    assert node.func.attr == "Popen"
                    assert any(k.arg == "shell" and isinstance(k.value, ast.Constant) and k.value.value is False for k in node.keywords)
                    assert any(k.arg == "close_fds" and isinstance(k.value, ast.Constant) and k.value.value is True for k in node.keywords)
        if path.stem == 'managed_process':
            forbidden={'TerminateProcess','TerminateJobObject','OpenJobObjectW','AssignProcessToJobObject',
                       'CREATE_BREAKAWAY_FROM_JOB','PROC_THREAD_ATTRIBUTE_PARENT_PROCESS'}
            assert not forbidden.intersection(n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute))
            assert not forbidden.intersection(n.id for n in ast.walk(tree) if isinstance(n,ast.Name))
            calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='CreateProcessW']
            assert len(calls)==1
            # Native inheritance is permitted only for the explicit three-file
            # HANDLE_LIST; the fixed Python path continues with no handles.
            assert ast.unparse(calls[0].args[4])=='bool(std_handles)'
            assert 'k.UpdateProcThreadAttribute(attrs, 0, HANDLE_LIST, handles, C.sizeof(handles), None, None)' in ast.unparse(tree)
            assert 'len(std_handles) == 3' in ast.unparse(tree)
            def flags(node):
                if isinstance(node,ast.Constant):return node.value
                assert isinstance(node,ast.BinOp) and isinstance(node.op,ast.BitOr)
                return flags(node.left)|flags(node.right)
            assert flags(calls[0].args[5])==0x00080000|0x08000000|0x00000400
            assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='UpdateProcThreadAttribute'
                       and isinstance(n.args[2],ast.Name) and n.args[2].id=='JOB_LIST' for n in ast.walk(tree))
        if path.stem in {'interruption','interruption_probe'}:
            forbidden={'CreateProcessW','TerminateProcess','TerminateJobObject','OpenJobObjectW',
                       'AssignProcessToJobObject','Popen','transaction','acquire_supervisor_store',
                       'execute_pending','submit','apply_closeout','resume_dispatch','write_text','write_bytes'}
            assert not forbidden.intersection(n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute))
            assert not forbidden.intersection(n.id for n in ast.walk(tree) if isinstance(n,ast.Name))
            for n in ast.walk(tree):
                if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='ProcessReference':
                    assert any(k.arg=='cleanup' and isinstance(k.value,ast.Constant) and k.value.value is False for k in n.keywords)
    assert "abqjobpilot.config" not in sys.modules
    assert "abqjobpilot.runner_core" not in sys.modules
    assert "tkinter" not in sys.modules


def test_all_runtime_io_confined_and_default_navigation_untouched(harness, monkeypatch):
    h = harness
    recent_before = inventory(h.root)["recent-fixture.json"]
    original_open = Path.open
    actual = []
    def checked_open(path, *args, **kwargs):
        assert path.is_relative_to(h.root), str(path)
        actual.append(str(path))
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", checked_open)
    _, _, receipt = h.accept()
    h.service.execute_pending(h.context, receipt["run_id"])
    assert actual and all(Path(p).is_relative_to(h.root) for p in actual)
    assert inventory(h.root)["recent-fixture.json"] == recent_before
    assert not any(p.name in {"queue.json", "live_status.json", "project.db", "project.json"} for p in h.root.rglob("*"))
    assert not any(p.suffix.lower() in {".inp", ".odb", ".cae", ".jnl"} for p in h.root.rglob("*"))


@pytest.mark.parametrize("variant", ["outside", "parent", "unc", "relative", "ads"])
def test_path_escape_rejected_before_candidate_filesystem_access(harness, monkeypatch, variant):
    h = harness
    candidates = {"outside": str(h.root.parent / "outside-do-not-read.txt"),
                  "parent": str(h.root / ".." / "outside-do-not-read.txt"),
                  "unc": "//unreachable-host/share/input.txt", "relative": "input.txt",
                  "ads": str(h.root / "source.txt:stream")}
    candidate = candidates[variant]
    original = Path.lstat
    calls = []
    def tracked(path, *args, **kwargs):
        calls.append(str(path))
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "lstat", tracked)
    with pytest.raises(ExecutionError) as failure:
        confined(h.root, candidate, exists=True)
    assert failure.value.code == "OUTPUT_SCOPE_VIOLATION"
    assert calls == []


def _junction(link, target):
    if sys.platform != "win32":
        os.symlink(target, link, target_is_directory=True)
        return
    # Test-only native junction creation in tmp_path; no shell or external process.
    link.mkdir()
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                                ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    api.CreateFileW.restype = ctypes.c_void_p
    api.DeviceIoControl.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32,
                                    ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p]
    api.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = api.CreateFileW(str(link), 0x40000000, 0, None, 3, 0x02200000, None)
    assert handle != ctypes.c_void_p(-1).value, ctypes.get_last_error()
    substitute = ("\\??\\" + str(target)).encode("utf-16le")
    display = str(target).encode("utf-16le")
    names = substitute + b"\0\0" + display + b"\0\0"
    data = struct.pack("<IHHHHHH", 0xA0000003, len(names) + 8, 0, 0, len(substitute), len(substitute) + 2, len(display)) + names
    buffer, returned = ctypes.create_string_buffer(data), ctypes.c_uint32()
    try:
        assert api.DeviceIoControl(handle, 0x900A4, buffer, len(data), None, 0, ctypes.byref(returned), None), ctypes.get_last_error()
    finally:
        api.CloseHandle(handle)


def test_real_junction_or_symlink_is_rejected(harness):
    h = harness
    target = h.root / "target"
    target.mkdir()
    (target / "input.txt").write_text("fixture", encoding="utf-8")
    link = h.root / "junction"
    _junction(link, target)
    with pytest.raises(ExecutionError) as failure:
        confined(h.root, link / "input.txt", exists=True)
    assert failure.value.code == "OUTPUT_SCOPE_VIOLATION"


def test_creation_never_adopts_existing_directory(harness):
    h = harness
    before = inventory(h.root)
    with pytest.raises(ExecutionError) as failure:
        create_experiment(h.root, Path(h.context.root))
    assert failure.value.code == "PROJECT_EXISTS"
    assert inventory(h.root) == before
