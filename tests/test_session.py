from __future__ import annotations

import json
from pathlib import Path

from quantum_platform.clock import FakeClock
from quantum_platform.sidecar import SidecarApp, auto_press_until_done
from quantum_platform.session import STREAM_NAMES, build_session_paths


def _load_events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_session_directory_tree(example_yaml, tmp_path):
    clock = FakeClock()
    emitted: list[tuple[str, dict]] = []

    def notify(method: str, params: dict) -> None:
        emitted.append((method, params))

    app = SidecarApp(
        notify=notify,
        clock=clock,
        experiments_dir=example_yaml.parent,
        repo_root=tmp_path,
    )
    result = app.session_start(
        {
            "participant_id": "P001",
            "session_id": "S001",
            "experiment_path": str(example_yaml),
            "sessions_root": str(tmp_path / "sessions"),
            "mock": True,
        }
    )
    auto_press_until_done(app)
    stop = app.session_stop({})
    root = Path(result["session_dir"])
    assert stop["session_dir"] == str(root)

    paths = build_session_paths(tmp_path / "sessions", "P001", "S001")
    assert paths.root == root
    assert (root / "meta.yaml").is_file()
    assert (root / "events.jsonl").is_file()
    assert (root / "experiment.yaml").is_file()
    assert (root / "experiment.resolved.yaml").is_file()
    assert (root / "calibration").is_dir()
    assert (root / "derived").is_dir()
    for name in STREAM_NAMES:
        stream = root / "streams" / name
        assert stream.is_dir()
        assert (stream / f"{name}.jsonl").is_file()

    events = _load_events(root / "events.jsonl")
    names = [e["name"] for e in events]
    assert names[0] == "session_start"
    assert names[-1] == "session_end"
    assert "operator_advance" in names
    assert "operator_end_phase" in names
    assert names.count("stimulus_onset") == 2
    assert names.count("stimulus_offset") == 2
    assert names.count("fixation_onset") == 2
    assert names.count("isi_offset") == 2

    timestamps = [e["ts"] for e in events]
    assert timestamps == sorted(timestamps)
    assert all(e["ts_ns"] >= events[0]["ts_ns"] for e in events)
    assert all("ts" in e and "ts_ns" in e for e in events)

    q = next(e for e in events if e["name"] == "stimulus_onset" and e.get("payload", {}).get("painting_id") == "Q001")
    assert q["payload"]["condition"] == "quantum"
    assert q["stage_id"] == "exposure__Q001"

    device_notes = [p for m, p in emitted if m == "device.status"]
    assert any(p.get("device") == "thermal" for p in device_notes)

    meta_text = (root / "meta.yaml").read_text(encoding="utf-8")
    assert "participant_id: P001" in meta_text
    assert "session_status: complete" in meta_text
    assert "painting_session_simplified" in meta_text


def test_event_log_format_unit(tmp_path):
    from quantum_platform.session import EventLog

    clock = FakeClock(start_ns=1_000_000_000)
    log = EventLog(tmp_path / "events.jsonl", clock, clock.monotonic_ns())
    log.emit("session_start", payload={"participant_id": "P001"})
    clock.advance(0.25)
    log.emit("fixation_onset", stage_id="fix", label="Fixation")
    recs = _load_events(tmp_path / "events.jsonl")
    assert recs[0]["name"] == "session_start"
    assert recs[0]["ts"] == 0.0
    assert recs[1]["ts"] == 0.25
    assert recs[1]["stage_id"] == "fix"
    assert recs[1]["ts_ns"] > recs[0]["ts_ns"]


def test_rpc_session_methods_roundtrip(example_yaml, tmp_path):
    from quantum_platform.rpc import JsonRpcServer, encode_message, request

    clock = FakeClock()
    app = SidecarApp(clock=clock, experiments_dir=example_yaml.parent, repo_root=tmp_path)
    stdout = __import__("io").StringIO()
    server = JsonRpcServer(app.handlers(), stdout=stdout)
    app._notify_cb = server.notify

    start_line = encode_message(
        request(
            1,
            "session.start",
            {
                "participant_id": "P002",
                "session_id": "S002",
                "experiment_id": "painting_session_simplified",
                "sessions_root": str(tmp_path / "sessions"),
                "mock": True,
            },
        )
    )
    resp = server.handle_line(start_line)
    assert resp["result"]["ok"] is True
    assert "session_dir" in resp["result"]

    status = server.handle_line(encode_message(request(2, "status.get")))
    assert status["result"]["session"]["participant_id"] == "P002"

    doctor = server.handle_line(encode_message(request(3, "doctor.run")))
    assert doctor["result"]["ok"] is True
    assert "sdks" in doctor["result"]

    stop = server.handle_line(encode_message(request(4, "session.stop")))
    assert stop["result"]["ok"] is True
    app.close()
