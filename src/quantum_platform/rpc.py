"""JSON-RPC 2.0 newline-delimited JSON (NDJSON) framing.

Locked in INTEGRATIONS.md §2. One object per line on stdin/stdout.
A dedicated stderr/event stream is allowed later; Phase 1 uses one
stdout stream and discriminates request / response / notification
per JSON-RPC 2.0.
"""

from __future__ import annotations

import json
import sys
import threading
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any, TextIO

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


def iter_ndjson(stream: TextIO) -> Iterator[dict[str, Any]]:
    for raw in stream:
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

    stream: TextIO
    lock: threading.Lock

    def write(self, obj: Mapping[str, Any]) -> None:
        line = encode_message(obj)
        with self.lock:
            self.stream.write(line)
            self.stream.flush()


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
        self.stdin = stdin if stdin is not None else sys.stdin
        self.stdout = stdout if stdout is not None else sys.stdout
        self.writer = StdioWriter(self.stdout, threading.Lock())

    def notify(self, method: str, params: Any | None = None) -> None:
        self.writer.write(notification(method, params))

    def serve_forever(self) -> None:
        for raw in self.stdin:
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
