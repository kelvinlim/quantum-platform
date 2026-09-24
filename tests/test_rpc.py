from __future__ import annotations

import io
import json

from quantum_platform.rpc import (
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    JsonRpcServer,
    encode_message,
    is_notification,
    is_request,
    is_response,
    notification,
    parse_message,
    request,
    success,
)


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
