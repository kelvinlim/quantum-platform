"""JSON-RPC 2.0 newline-delimited JSON (NDJSON) framing.

Locked in INTEGRATIONS.md §2. One object per line on stdin/stdout.
A dedicated stderr/event stream is allowed later; Phase 1 uses one
stdout stream and discriminates request / response / notification
per JSON-RPC 2.0.

On Windows, the C runtime opens inherited stdio in text mode. Writing UTF-8
NDJSON (``ensure_ascii=False``) through ``TextIOWrapper`` to an anonymous
pipe — the Rust host's ``Stdio::piped()`` — raises
``OSError: [Errno 22] Invalid argument``. The writer therefore emits UTF-8
bytes on the binary buffer; ``configure_stdio`` also switches the fds to
``O_BINARY`` on Windows.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any, BinaryIO, TextIO

JSONRPC_VERSION = "2.0"

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
APPLICATION_ERROR = -32000


def encode_message(obj: Mapping[str, Any]) -> str:
    """Serialize one JSON-RPC object as a single NDJSON line (no pretty-print)."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"


def parse_message(line: str) -> dict[str, Any]:
    text = line.strip()
    if not text:
        raise ValueError("empty NDJSON line")
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("JSON-RPC message must be an object")
    return obj


def _binary_buffer(stream: Any) -> BinaryIO | None:
    buf = getattr(stream, "buffer", None)
    if buf is None:
        return None
    write = getattr(buf, "write", None)
    if write is None:
        return None
    return buf


def write_ndjson_line(stream: Any, line: str) -> None:
    """Write one NDJSON line as UTF-8 bytes when a binary buffer is available.

    ``StringIO`` (unit tests) has no ``.buffer`` and keeps the text path.
    Real stdio — including Windows pipes — goes through the binary buffer so
    the CRT never sees a text-mode write of UTF-8.
    """
    payload = line.encode("utf-8")
    buf = _binary_buffer(stream)
    if buf is not None:
        buf.write(payload)
        buf.flush()
        return
    stream.write(line)
    stream.flush()


def read_ndjson_line(stream: Any) -> str | None:
    """Read one raw NDJSON line (including the trailing newline), or ``None`` at EOF."""
    buf = _binary_buffer(stream)
    if buf is not None:
        raw = buf.readline()
        if not raw:
            return None
        if isinstance(raw, bytes):
            return raw.decode("utf-8")
        return raw
    raw = stream.readline()
    if not raw:
        return None
    return raw


def configure_stdio(stdin: Any | None = None, stdout: Any | None = None) -> tuple[Any, Any]:
    """Put inherited stdio in binary mode so UTF-8 NDJSON can cross a Windows pipe.

    Safe to call on macOS/Linux (no-op besides returning the streams). Safe to
    call on objects without ``fileno`` (tests).
    """
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    if sys.platform == "win32":
        _set_binary_mode(stdin)
        _set_binary_mode(stdout)
    return stdin, stdout


def _set_binary_mode(stream: Any) -> None:
    try:
        fd = stream.fileno()
    except (AttributeError, OSError, ValueError):
        return
    try:
        import msvcrt

        msvcrt.setmode(fd, os.O_BINARY)
    except (ImportError, OSError, ValueError):
        return


def iter_ndjson(stream: TextIO) -> Iterator[dict[str, Any]]:
    while True:
        raw = read_ndjson_line(stream)
        if raw is None:
            break
        line = raw.strip()
        if not line:
            continue
        yield parse_message(line)


def request(id: int | str, method: str, params: Any | None = None) -> dict[str, Any]:
    msg: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "id": id, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


def success(id: int | str | None, result: Any) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": id, "result": result}


def error_response(
    id: int | str | None,
    code: int,
    message: str,
    data: Any | None = None,
) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": JSONRPC_VERSION, "id": id, "error": err}


def notification(method: str, params: Any | None = None) -> dict[str, Any]:
    msg: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


def is_request(msg: Mapping[str, Any]) -> bool:
    return "method" in msg and "id" in msg


def is_notification(msg: Mapping[str, Any]) -> bool:
    return "method" in msg and "id" not in msg


def is_response(msg: Mapping[str, Any]) -> bool:
    return "id" in msg and ("result" in msg or "error" in msg) and "method" not in msg


Handler = Callable[[Any], Any]


class RpcError(Exception):
    def __init__(self, code: int, message: str, data: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


@dataclass
class StdioWriter:
    """Thread-safe NDJSON writer for sidecar stdout."""

    stream: Any
    lock: threading.Lock

    def write(self, obj: Mapping[str, Any]) -> None:
        line = encode_message(obj)
        with self.lock:
            write_ndjson_line(self.stream, line)


class JsonRpcServer:
    """Serve JSON-RPC 2.0 requests from ``stdin``, write to ``stdout``.

    Incoming requests are dispatched to ``handlers`` (method name → callable).
    Notifications from the host (no ``id``) are dispatched the same way if a
    handler exists; unknown notifications are ignored.
    """

    def __init__(
        self,
        handlers: Mapping[str, Handler],
        stdin: TextIO | None = None,
        stdout: TextIO | None = None,
    ) -> None:
        self.handlers = dict(handlers)
        using_real_stdio = stdin is None and stdout is None
        self.stdin = stdin if stdin is not None else sys.stdin
        self.stdout = stdout if stdout is not None else sys.stdout
        if using_real_stdio:
            configure_stdio(self.stdin, self.stdout)
        self.writer = StdioWriter(self.stdout, threading.Lock())

    def notify(self, method: str, params: Any | None = None) -> None:
        self.writer.write(notification(method, params))

    def serve_forever(self) -> None:
        while True:
            raw = read_ndjson_line(self.stdin)
            if raw is None:
                break
            line = raw.strip()
            if not line:
                continue
            self.handle_line(line)

    def handle_line(self, line: str) -> dict[str, Any] | None:
        try:
            msg = parse_message(line)
        except (ValueError, json.JSONDecodeError) as exc:
            resp = error_response(None, PARSE_ERROR, f"Parse error: {exc}")
            self.writer.write(resp)
            return resp

        if msg.get("jsonrpc") != JSONRPC_VERSION:
            ident = msg.get("id")
            resp = error_response(ident, INVALID_REQUEST, "jsonrpc must be '2.0'")
            if "id" in msg:
                self.writer.write(resp)
            return resp

        if is_response(msg):
            return None

        method = msg.get("method")
        if not isinstance(method, str):
            ident = msg.get("id")
            resp = error_response(ident, INVALID_REQUEST, "method must be a string")
            if "id" in msg:
                self.writer.write(resp)
            return resp

        params = msg.get("params", {})
        ident = msg.get("id") if "id" in msg else None
        handler = self.handlers.get(method)
        if handler is None:
            if ident is None:
                return None
            resp = error_response(ident, METHOD_NOT_FOUND, f"Method not found: {method}")
            self.writer.write(resp)
            return resp

        try:
            result = handler(params)
        except RpcError as exc:
            if ident is None:
                return None
            resp = error_response(ident, exc.code, str(exc), exc.data)
            self.writer.write(resp)
            return resp
        except Exception as exc:  # noqa: BLE001 — surface to the host
            if ident is None:
                return None
            resp = error_response(ident, INTERNAL_ERROR, f"{type(exc).__name__}: {exc}")
            self.writer.write(resp)
            return resp

        if ident is None:
            return None
        resp = success(ident, result)
        self.writer.write(resp)
        return resp
