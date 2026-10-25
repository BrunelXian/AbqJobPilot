"""One bounded UTF-8 JSON frame per loopback connection. No executable objects."""

import json
import socket
import struct
import time

from .models import ExecutionError, canonical_json, require

PROTOCOL = "af-local-json-v1"
MAX_REQUEST = 65536
MAX_RESPONSE = 262144
MAX_CONNECTIONS = 8
MAX_EVENTS = 64
IO_TIMEOUT = 2.0


def _remaining(stream, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Frame deadline expired")
    stream.settimeout(remaining)


def _read_exact(stream, size, deadline):
    parts = bytearray()
    while len(parts) < size:
        _remaining(stream, deadline)
        block = stream.recv(size - len(parts))
        if not block:
            raise EOFError("Truncated frame")
        parts.extend(block)
    return bytes(parts)


def receive(stream, limit, *, timeout=IO_TIMEOUT):
    deadline = time.monotonic() + timeout
    size = struct.unpack("!I", _read_exact(stream, 4, deadline))[0]
    require(0 < size <= limit, "MESSAGE_TOO_LARGE", "Frame exceeds protocol bound")
    raw = _read_exact(stream, size, deadline)
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, "INVALID_REQUEST", "Duplicate JSON key")
            value[key] = item
        return value
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
        canonical_json(value)  # Also rejects floats/NaN/Infinity.
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ExecutionError("INVALID_REQUEST", "Invalid bounded UTF-8 JSON") from exc


def send(stream, value, limit, *, timeout=IO_TIMEOUT):
    content = canonical_json(value).encode("utf-8")
    require(0 < len(content) <= limit, "MESSAGE_TOO_LARGE", "Response or request exceeds protocol bound")
    stream.settimeout(timeout)
    stream.sendall(struct.pack("!I", len(content)) + content)


def connect(port, *, timeout=IO_TIMEOUT):
    # Caller cannot select a remote host, command or transport.
    return socket.create_connection(("127.0.0.1", port), timeout=timeout)
