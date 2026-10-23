"""Small INP grammar and bounded Windows reads, not an Abaqus interpreter."""

from contextlib import ExitStack
import ctypes
from ctypes import wintypes
import msvcrt
import os
from pathlib import Path
import re
import stat

from abqjobpilot.execution.models import ExecutionError, bytes_digest, require
from abqjobpilot.execution.paths import local_path, no_reparse

MAX_FILES = 8
MAX_DEPTH = 4
MAX_FILE_BYTES = 65536
MAX_TOTAL_BYTES = 262144
MAX_BLOCKS = 512
LABEL = r"[A-Za-z][A-Za-z0-9_]{0,31}"
NUMBER = r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[EeDd][+-]?[0-9]{1,3})?"
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)), *(f"LPT{i}" for i in range(10))}


def relative(value):
    require(type(value) is str and 0 < len(value) <= 160, "UNSUPPORTED_PATH", "Bounded relative path required")
    require(re.fullmatch(r"[A-Za-z0-9_.\-/\\]+", value) is not None, "UNSUPPORTED_PATH", "Unsupported path syntax")
    parts = value.replace("\\", "/").split("/")
    require(all(p not in ("", ".", "..") and not p.endswith((".", " "))
                and p.split(".")[0].upper() not in RESERVED for p in parts),
            "UNSUPPORTED_PATH", "Unsupported path component")
    return "/".join(parts)


def directory(value):
    require(type(value) is str and len(value) <= 240, "UNSUPPORTED_PATH", "Explicit local directory required")
    path = local_path(value)
    require(os.name == "nt", "UNSUPPORTED_PLATFORM", "Windows local profile required")
    drive_type = ctypes.WinDLL("kernel32", use_last_error=True).GetDriveTypeW
    drive_type.argtypes = [wintypes.LPCWSTR]
    drive_type.restype = wintypes.UINT
    require(drive_type(path.anchor) == 3, "UNSUPPORTED_PATH", "Only fixed local drives supported")
    # Reject Win32 aliases, devices and ADS before filesystem access.
    require(all(not p.endswith((".", " ")) and p.split(".")[0].upper() not in RESERVED
                for p in path.parts[1:]), "UNSUPPORTED_PATH", "Unsupported directory component")
    no_reparse(path)
    require(path.is_dir(), "INPUT_NOT_FOUND", "Explicit directory must exist")
    return path.resolve()


def _identity(info):
    # Windows Python 3.12 path-stat ctime can be creation time while fd-stat
    # reports change time. Neither is content identity; byte hashes remain required.
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def _open_pinned(path, *, is_directory=False):
    """Retain a noninheritable OS reference; deny writes/deletes to input files."""
    require(os.name == "nt", "UNSUPPORTED_PLATFORM", "This preview profile requires Windows")
    no_reparse(path)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    # OPEN_REPARSE_POINT disallows accidentally following a replaced leaf.
    handle = create(str(path), 0x80000000, 3 if is_directory else 1, None, 3,
                    0x00200000 | (0x02000000 if is_directory else 0), None)
    if handle == ctypes.c_void_p(-1).value:
        code = "INPUT_NOT_FOUND" if ctypes.get_last_error() in (2, 3) else "INPUT_READ_FAILED"
        raise ExecutionError(code, "Cannot obtain stable read reference")
    try:
        final = kernel.GetFinalPathNameByHandleW
        final.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
        final.restype = wintypes.DWORD
        buffer = ctypes.create_unicode_buffer(32768)
        count = final(handle, buffer, len(buffer), 0)
        require(0 < count < len(buffer), "INPUT_UNSTABLE", "Physical path unavailable")
        actual = buffer.value.removeprefix("\\\\?\\")
        no_reparse(path)
        require(os.path.normcase(actual) == os.path.normcase(str(path)),
                "INPUT_UNSTABLE", "Physical path differs from declared path")
        if is_directory:
            return handle, close
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY | os.O_NOINHERIT)
        handle = None  # descriptor now owns the reference
        stream = os.fdopen(fd, "rb")
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            stream.close()
            raise ExecutionError("UNSUPPORTED_PATH", "Only ordinary files with one link are supported")
        return stream
    except BaseException:
        if handle is not None:
            close(handle)
        raise


def _parameters(line):
    require(not line.endswith(",") and '"' not in line and "'" not in line,
            "UNSUPPORTED_SYNTAX", "Quotes and continuation are not supported")
    parts = line[1:].split(",")
    keyword = parts.pop(0).strip().upper()
    params = {}
    for item in parts:
        require(item.count("=") == 1, "UNSUPPORTED_PARAMETER", "Only named exact parameters are supported")
        name, value = [p.strip() for p in item.split("=")]
        name = name.upper()
        require(name not in params and bool(value), "UNSUPPORTED_PARAMETER", "Duplicate or empty parameter")
        params[name] = value
    return keyword, params


def _block(keyword, params, rows, *, probe_print=False):
    """Validate only lexical/data shape. No node linkage or engineering semantics."""
    if probe_print and keyword in {"NODE PRINT", "EL PRINT"}:
        fixed = {"FREQUENCY": "1", "SUMMARY": "NO", "TOTALS": "NO"}
        if keyword == "NODE PRINT":
            fixed["GLOBAL"] = "YES"
            expected_rows = ["U", "RF"]
        else:
            fixed["POSITION"] = "INTEGRATION POINTS"
            fixed["ELSET"] = "BAR"
            expected_rows = ["S"]
        require({k: v.upper() for k, v in params.items()} == fixed,
                "UNSUPPORTED_PARAMETER", "Only the fixed probe print request is supported")
        require([row.upper() for row in rows] == expected_rows,
                "UNSUPPORTED_DATA", "Only fixed probe output variables are supported")
        return
    exact = {"HEADING": {}, "NODE": {}, "MATERIAL": {"NAME": "label"},
             "ELASTIC": {}, "SOLID SECTION": {"ELSET": "label", "MATERIAL": "label"},
             "STEP": {}, "STATIC": {}, "BOUNDARY": {}, "CLOAD": {}, "END STEP": {}}
    if keyword == "ELEMENT":
        require(set(params) == {"TYPE", "ELSET"} and params["TYPE"].upper() == "T3D2",
                "UNSUPPORTED_PARAMETER", "Only explicit T3D2 with ELSET supported")
        require(re.fullmatch(LABEL, params["ELSET"]), "UNSUPPORTED_PARAMETER", "Bounded label required")
    else:
        require(keyword in exact, "UNSUPPORTED_KEYWORD", "Keyword outside preview subset")
        require(set(params) == set(exact[keyword]), "UNSUPPORTED_PARAMETER", "Parameter combination outside subset")
        for value in params.values():
            require(re.fullmatch(LABEL, value), "UNSUPPORTED_PARAMETER", "Bounded label required")
    if keyword in ("MATERIAL", "STEP", "END STEP"):
        require(not rows, "UNSUPPORTED_DATA", "This option has no supported data rows")
        return
    require(bool(rows), "UNSUPPORTED_DATA", "Option requires data rows")
    if keyword in ("HEADING", "ELASTIC", "SOLID SECTION", "STATIC"):
        require(len(rows) == 1, "UNSUPPORTED_DATA", "Exactly one data row supported")
    for row in rows:
        if keyword == "HEADING":
            require(re.fullmatch(r"[A-Za-z0-9 _.-]{1,80}", row), "UNSUPPORTED_DATA", "Only plain heading text supported")
            continue
        values = [v.strip() for v in row.split(",")]
        shapes = {"NODE": (4, (0,)), "ELEMENT": (3, (0, 1, 2)), "ELASTIC": (2, ()),
                  "SOLID SECTION": (1, ()), "STATIC": (4, ()),
                  "BOUNDARY": (4, (0, 1, 2)), "CLOAD": (3, (0, 1))}
        count, ints = shapes[keyword]
        require(len(values) == count, "UNSUPPORTED_DATA", "Data shape outside subset")
        for i, value in enumerate(values):
            pattern = r"[1-9][0-9]{0,8}" if i in ints else NUMBER
            require(len(value) <= 32 and re.fullmatch(pattern, value), "UNSUPPORTED_DATA", "Only explicit bounded numbers supported")


def read_inputs(root, main, *, probe_print=False):
    """Pinned files + second content pass; no cross-file atomic snapshot claim."""
    manifest, edges, blocks, active, seen, total = [], [], [], set(), {}, 0
    with ExitStack() as stack:
        root_handle, close = _open_pinned(root, is_directory=True)
        stack.callback(close, root_handle)
        root_info = root.stat()

        def visit(ref, depth):
            nonlocal total
            ref = relative(ref)
            require(ref.lower().endswith(".inp"), "UNSUPPORTED_PATH", "Only INP references supported")
            require(depth <= MAX_DEPTH, "LIMIT_EXCEEDED", "Include depth exceeded")
            key = ref.lower()
            require(key not in active, "INPUT_CYCLE", "Include cycle detected")
            # Repeated includes are rejected too: no hidden duplicated model data.
            require(key not in seen, "INPUT_DUPLICATE", "Repeated input reference is unsupported")
            require(len(manifest) < MAX_FILES, "LIMIT_EXCEEDED", "Input count exceeded")
            path = root / ref
            require(len(str(path)) <= 256, "UNSUPPORTED_PATH", "Input path too long")
            stream = stack.enter_context(_open_pinned(path))
            before = os.fstat(stream.fileno())
            content = stream.read(MAX_FILE_BYTES + 1)
            require(len(content) <= MAX_FILE_BYTES, "LIMIT_EXCEEDED", "Input file limit exceeded")
            total += len(content)
            require(total <= MAX_TOTAL_BYTES, "LIMIT_EXCEEDED", "Total input limit exceeded")
            require(_identity(before) == _identity(os.fstat(stream.fileno())), "INPUT_UNSTABLE", "Input changed during read")
            try:
                source = content.decode("ascii")
            except UnicodeError:
                raise ExecutionError("UNSUPPORTED_SYNTAX", "Only ASCII input supported") from None
            require(source.endswith("\n") and not source.replace("\r\n", "\n").count("\r"),
                    "UNSUPPORTED_SYNTAX", "LF or CRLF terminated lines required")
            require(all(c in "\r\n" or 32 <= ord(c) <= 126 for c in source),
                    "UNSUPPORTED_SYNTAX", "Control characters are unsupported")
            entry = {"reference": ref, "bytes": len(content), "content_digest": bytes_digest(content)}
            manifest.append(entry)
            seen[key] = (path, stream, before, entry)
            active.add(key)
            current, params, rows = None, {}, []

            def finish():
                if current is not None:
                    if probe_print:
                        _block(current, params, rows, probe_print=True)
                    else:
                        _block(current, params, rows)
                    require(len(blocks) < MAX_BLOCKS, "LIMIT_EXCEEDED", "Option count exceeded")
                    blocks.append(current)

            for line in source.splitlines():
                require(0 < len(line) <= 256, "UNSUPPORTED_SYNTAX", "Blank or oversized lines unsupported")
                if line.startswith("**"):
                    continue
                line = line.strip()
                if line.startswith("*"):
                    finish()
                    current, params = _parameters(line)
                    rows = []
                    if current == "INCLUDE":
                        require(set(params) == {"INPUT"}, "UNSUPPORTED_PARAMETER", "Only unencrypted INCLUDE INPUT supported")
                        child = relative(params["INPUT"])
                        edges.append({"from": ref, "to": child, "base": "submission_cwd"})
                        visit(child, depth + 1)
                        current = None
                else:
                    require(current is not None, "UNSUPPORTED_DATA", "Data must belong to a local option block")
                    rows.append(line)
            finish()
            active.remove(key)

        visit(main, 0)
        require(blocks.count("STEP") == blocks.count("STATIC") == blocks.count("END STEP") == 1,
                "UNSUPPORTED_STAGE", "Exactly one static step required")
        start, procedure, end = (blocks.index(k) for k in ("STEP", "STATIC", "END STEP"))
        require(start < procedure < end == len(blocks) - 1, "UNSUPPORTED_STAGE", "Single final static step required")
        history = {"STATIC", "BOUNDARY", "CLOAD"} | ({"NODE PRINT", "EL PRINT"} if probe_print else set())
        require(all(k in {"HEADING", "NODE", "ELEMENT", "MATERIAL", "ELASTIC", "SOLID SECTION", "BOUNDARY"}
                    for k in blocks[:start]) and all(k in history for k in blocks[start+1:end]),
                "UNSUPPORTED_STAGE", "Model/history ordering outside subset")
        if probe_print:
            require(blocks.count("NODE PRINT") == blocks.count("EL PRINT") == 1,
                    "UNSUPPORTED_STAGE", "Probe profile requires exactly one of each fixed print request")
        for path, stream, before, entry in seen.values():
            no_reparse(path)
            stream.seek(0)
            require(bytes_digest(stream.read(MAX_FILE_BYTES + 1)) == entry["content_digest"]
                    and _identity(path.stat()) == _identity(before), "INPUT_UNSTABLE", "Input identity or bytes changed")
        require((root.stat().st_dev, root.stat().st_ino) == (root_info.st_dev, root_info.st_ino),
                "INPUT_UNSTABLE", "Engineering root identity changed")
    return manifest, edges, sorted(set(blocks)), {"device": root_info.st_dev, "file_id": root_info.st_ino}
