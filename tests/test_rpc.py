from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from quantum_platform.rpc import (
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    JsonRpcServer,
    StdioWriter,
    encode_message,
    is_notification,
    is_request,
    is_response,
    notification,
    parse_message,
    request,
    success,
    write_ndjson_line,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
NON_ASCII_REMINDER = "Eye height ≈ painting center (145–150 cm) — ready"


def test_encode_is_single_line():
    line = encode_message(request(1, "status.get", {"x": 1}))
    assert line.endswith("\n")
    assert line.count("\n") == 1
    obj = json.loads(line)
    assert obj["jsonrpc"] == "2.0"
    assert obj["method"] == "status.get"


def test_parse_and_discriminate():
    req = parse_message(encode_message(request(1, "session.start", {"participant_id": "P001"})))
    note = parse_message(encode_message(notification("event.emit", {"name": "session_start", "ts": 0})))
    resp = parse_message(encode_message(success(1, {"ok": True})))
    assert is_request(req)
    assert is_notification(note)
    assert is_response(resp)
    assert note["method"] == "event.emit"
    assert "id" not in note


def test_server_request_response():
    stdout = io.StringIO()
    stdin = io.StringIO()
    server = JsonRpcServer({"status.get": lambda p: {"ok": True, "echo": p}}, stdin=stdin, stdout=stdout)
    resp = server.handle_line(encode_message(request(7, "status.get", {"a": 1})))
    assert resp is not None
    assert resp["id"] == 7
    assert resp["result"]["echo"] == {"a": 1}
    written = stdout.getvalue().strip().splitlines()
    assert len(written) == 1
    assert json.loads(written[0])["result"]["ok"] is True


def test_server_unknown_method():
    stdout = io.StringIO()
    server = JsonRpcServer({}, stdout=stdout)
    resp = server.handle_line(encode_message(request(3, "nope.method")))
    assert resp["error"]["code"] == METHOD_NOT_FOUND
    assert resp["id"] == 3


def test_server_parse_error():
    stdout = io.StringIO()
    server = JsonRpcServer({}, stdout=stdout)
    resp = server.handle_line("{not json")
    assert resp["error"]["code"] == PARSE_ERROR
    assert resp["id"] is None


def test_server_invalid_version():
    stdout = io.StringIO()
    server = JsonRpcServer({"status.get": lambda p: {}}, stdout=stdout)
    resp = server.handle_line('{"jsonrpc":"1.0","id":1,"method":"status.get"}\n')
    assert resp["error"]["code"] == INVALID_REQUEST


def test_notification_from_server():
    stdout = io.StringIO()
    server = JsonRpcServer({}, stdout=stdout)
    server.notify("device.status", {"device": "verity", "state": "connected"})
    obj = json.loads(stdout.getvalue())
    assert obj["method"] == "device.status"
    assert "id" not in obj


def test_incoming_notification_no_response():
    stdout = io.StringIO()
    called = {}

    def handler(params):
        called["params"] = params
        return {"should": "not be written"}

    server = JsonRpcServer({"ping": handler}, stdout=stdout)
    resp = server.handle_line(encode_message(notification("ping", {"x": 1})))
    assert resp is None
    assert called["params"] == {"x": 1}
    assert stdout.getvalue() == ""


def test_encode_preserves_non_ascii():
    line = encode_message(notification("stage.reminder", {"text": NON_ASCII_REMINDER}))
    assert "≈" in line
    assert "–" in line
    assert "—" in line
    assert "\\u" not in line
    obj = json.loads(line)
    assert obj["params"]["text"] == NON_ASCII_REMINDER


class _WindowsLikeTextPipe:
    """Text stream whose ``write`` rejects non-ASCII the way a Windows pipe can.

    ``OSError: [Errno 22] Invalid argument`` is what ``TextIOWrapper.write``
    raises on a Windows anonymous pipe when the C runtime is in text mode.
    The binary ``.buffer`` path must be used instead.
    """

    def __init__(self, raw: io.BytesIO) -> None:
        self.buffer = raw
        self.text_writes = 0

    def write(self, s: str) -> int:
        self.text_writes += 1
        if any(ord(ch) > 127 for ch in s):
            raise OSError(22, "Invalid argument")
        return self.buffer.write(s.encode("ascii"))

    def flush(self) -> None:
        self.buffer.flush()


def test_stdio_writer_uses_binary_buffer_for_non_ascii():
    raw = io.BytesIO()
    stream = _WindowsLikeTextPipe(raw)
    writer = StdioWriter(stream, threading.Lock())
    writer.write(notification("stage.reminder", {"text": NON_ASCII_REMINDER, "when": "enter"}))
    payload = raw.getvalue()
    assert stream.text_writes == 0
    assert b"\xe2\x89\x88" in payload  # ≈
    assert payload.endswith(b"\n")
    obj = json.loads(payload.decode("utf-8"))
    assert obj["method"] == "stage.reminder"
    assert obj["params"]["text"] == NON_ASCII_REMINDER


def test_write_ndjson_line_through_os_pipe():
    r_fd, w_fd = os.pipe()
    writer_stream = open(w_fd, "w", encoding="utf-8", closefd=True)
    reader = open(r_fd, "rb", closefd=True)
    try:
        write_ndjson_line(
            writer_stream,
            encode_message(notification("stage.reminder", {"text": NON_ASCII_REMINDER})),
        )
        writer_stream.close()
        payload = reader.read()
    finally:
        reader.close()
        if not writer_stream.closed:
            writer_stream.close()
    assert b"\xe2\x89\x88" in payload
    obj = json.loads(payload.decode("utf-8"))
    assert obj["params"]["text"] == NON_ASCII_REMINDER


def test_jsonrpc_server_error_response_with_non_ascii_on_hostile_pipe():
    raw = io.BytesIO()
    stream = _WindowsLikeTextPipe(raw)
    server = JsonRpcServer({}, stdout=stream)

    def boom(_params):
        raise RuntimeError(NON_ASCII_REMINDER)

    server.handlers["session.start"] = boom
    resp = server.handle_line(encode_message(request(9, "session.start", {})))
    assert resp["error"]["code"] == -32603
    assert "≈" in resp["error"]["message"]
    obj = json.loads(raw.getvalue().decode("utf-8"))
    assert obj["id"] == 9
    assert "≈" in obj["error"]["message"]


def _read_rpc_until_id(stdout: object, ident: int, timeout: float = 15.0) -> tuple[list[dict], dict]:
    deadline = time.time() + timeout
    messages: list[dict] = []
    while time.time() < deadline:
        line = stdout.readline()  # type: ignore[attr-defined]
        if not line:
            break
        obj = json.loads(line)
        messages.append(obj)
        if obj.get("id") == ident:
            return messages, obj
    raise AssertionError(f"no response id={ident} in {messages!r}")


def test_serve_session_start_over_pipe_emits_non_ascii(example_yaml, tmp_path):
    """End-to-end: host-style piped stdio must carry session.start + reminders."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "quantum_platform",
            "--repo-root",
            str(tmp_path),
            "--experiments-dir",
            str(example_yaml.parent),
            "serve",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(tmp_path),
        env=env,
    )
    assert proc.stdin is not None and proc.stdout is not None
    try:
        start = encode_message(
            request(
                1,
                "session.start",
                {
                    "participant_id": "Pwin",
                    "session_id": "Spipe",
                    "experiment_id": "painting_session_simplified",
                    "sessions_root": str(tmp_path / "sessions"),
                    "mock": True,
                },
            )
        )
        proc.stdin.write(start.encode("utf-8"))
        proc.stdin.flush()
        messages, resp = _read_rpc_until_id(proc.stdout, 1)
        assert "error" not in resp, resp
        assert resp["result"]["ok"] is True
        texts = json.dumps(messages, ensure_ascii=False)
        assert "≈" in texts
        reminders = [m for m in messages if m.get("method") == "stage.reminder"]
        assert reminders
        stop = encode_message(request(2, "session.stop", {}))
        proc.stdin.write(stop.encode("utf-8"))
        proc.stdin.flush()
        _read_rpc_until_id(proc.stdout, 2)
    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
