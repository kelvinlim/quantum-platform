from __future__ import annotations

from pathlib import Path

import pytest

from quantum_platform.clock import FakeClock
from quantum_platform.config import load_experiment
from quantum_platform.runner import StageRunner
from quantum_platform.session import EventLog

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _runner(name: str, tmp_path: Path) -> tuple[StageRunner, FakeClock, EventLog]:
    clock = FakeClock()
    events = EventLog(tmp_path / "events.jsonl", clock, clock.monotonic_ns())
    plan = load_experiment(FIXTURES / name)
    runner = StageRunner(plan, events, clock=clock)
    return runner, clock, events


def test_auto_advances_after_duration(tmp_path):
    runner, clock, events = _runner("mini_auto.yaml", tmp_path)
    view = runner.start()
    assert view.stage_id == "a"
    assert view.button == "hidden"
    runner.tick()
    assert runner.current is not None and runner.current.id == "a"
    clock.advance(1.0)
    view = runner.tick()
    assert view.stage_id == "b"
    clock.advance(1.0)
    view = runner.tick()
    assert view.complete
    names = [r.name for r in events.records]
    assert names == ["fixation_onset", "fixation_offset", "isi_onset", "isi_offset"]


def test_operator_does_not_auto_advance(tmp_path):
    runner, clock, events = _runner("mini_operator.yaml", tmp_path)
    view = runner.start()
    assert view.stage_id == "wait"
    assert view.button == "continue"
    assert view.button_enabled is False
    clock.advance(30)
    view = runner.tick()
    assert view.stage_id == "wait"
    with pytest.raises(RuntimeError, match="checklist"):
        runner.operator_advance()
    runner.set_checklist("ready", True)
    view = runner.view()
    assert view.button_enabled is True
    view = runner.operator_advance()
    assert view.complete
    names = [r.name for r in events.records]
    assert "operator_advance" in names
    assert names[-1] == "operator_advance" or "operator_advance" in names


def test_either_timer_wins(tmp_path):
    runner, clock, events = _runner("mini_either.yaml", tmp_path)
    runner.start()
    clock.advance(2.0)
    view = runner.tick()
    assert view.complete
    assert "operator_advance" not in [r.name for r in events.records]
    assert [r.name for r in events.records] == ["fixation_onset", "fixation_offset"]


def test_either_operator_wins(tmp_path):
    runner, clock, events = _runner("mini_either.yaml", tmp_path)
    runner.start()
    clock.advance(0.5)
    view = runner.operator_advance()
    assert view.complete
    names = [r.name for r in events.records]
    assert names == ["fixation_onset", "operator_advance", "fixation_offset"]


def test_end_signal_operator_waits_for_click(tmp_path):
    runner, clock, events = _runner("mini_end_signal.yaml", tmp_path)
    view = runner.start()
    assert view.button == "end_phase"
    assert view.button_enabled is False
    clock.advance(5.0)
    view = runner.tick()
    assert view.stage_id == "rest"
    assert view.timer_elapsed is True
    assert view.button_enabled is True
    with pytest.raises(RuntimeError, match="End phase"):
        runner.operator_advance()
    view = runner.operator_end_phase()
    assert view.complete
    names = [r.name for r in events.records]
    assert names == ["rest_onset", "operator_end_phase", "rest_offset"]


def test_end_signal_before_timer_rejected(tmp_path):
    runner, clock, _ = _runner("mini_end_signal.yaml", tmp_path)
    runner.start()
    clock.advance(1.0)
    with pytest.raises(RuntimeError, match="not enabled"):
        runner.operator_end_phase()


def test_confirm_end_alias_in_runner(tmp_path):
    runner, clock, _ = _runner("mini_confirm_end.yaml", tmp_path)
    view = runner.start()
    assert view.end_signal == "operator"
    assert view.button == "end_phase"
    clock.advance(3.0)
    runner.tick()
    runner.operator_end_phase()
    assert runner.complete


def test_checklist_gates_auto_leave(tmp_path):
    clock = FakeClock()
    events = EventLog(tmp_path / "events.jsonl", clock, 0)
    from quantum_platform.config import validate_and_resolve

    plan = validate_and_resolve(
        {
            "schema_version": 1,
            "id": "gate",
            "name": "gate",
            "stages": [
                {
                    "id": "t",
                    "kind": "timed",
                    "duration_s": 1,
                    "advance": "auto",
                    "checklist": [{"id": "ok", "text": "OK"}],
                }
            ],
        }
    )
    runner = StageRunner(plan, events, clock=clock)
    runner.start()
    clock.advance(1.0)
    view = runner.tick()
    assert view.stage_id == "t"
    assert view.complete is False
    runner.set_checklist("ok", True)
    view = runner.tick()
    assert view.complete


def test_countdown_reminder(tmp_path):
    from quantum_platform.config import validate_and_resolve

    clock = FakeClock()
    events = EventLog(tmp_path / "events.jsonl", clock, 0)
    plan = validate_and_resolve(
        {
            "schema_version": 1,
            "id": "rem",
            "name": "rem",
            "stages": [
                {
                    "id": "t",
                    "kind": "timed",
                    "duration_s": 10,
                    "advance": "auto",
                    "reminders": [
                        {"when": "enter", "text": "go"},
                        {"when": "countdown_at_s", "at_s": 3, "text": "almost", "tone": "warn"},
                    ],
                }
            ],
        }
    )
    runner = StageRunner(plan, events, clock=clock)
    view = runner.start()
    texts = [r["text"] for r in view.reminders]
    assert "go" in texts
    assert "almost" not in texts
    clock.advance(7.0)
    view = runner.tick()
    texts = [r["text"] for r in view.reminders]
    assert "almost" in texts


def test_pause_freezes_timer(tmp_path):
    runner, clock, _ = _runner("mini_auto.yaml", tmp_path)
    runner.start()
    runner.pause()
    clock.advance(5.0)
    view = runner.tick()
    assert view.stage_id == "a"
    runner.resume()
    clock.advance(1.0)
    view = runner.tick()
    assert view.stage_id == "b"
