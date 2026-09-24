"""Config-driven stage runner (EXPERIMENT_CONFIG.md §4–5).

The sidecar owns timed ``advance: auto`` transitions. The operator UI owns
checklist gates and the Continue / End phase button; those arrive as RPCs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from quantum_platform.clock import Clock, SystemClock
from quantum_platform.config import Reminder, ResolvedPlan, ResolvedStage
from quantum_platform.session import EventLog, NotifyFn

ButtonKind = Literal["continue", "end_phase", "hidden"]


@dataclass
class ChecklistState:
    id: str
    text: str
    checked: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "text": self.text, "checked": self.checked}


@dataclass
class StageView:
    """Operator-facing snapshot of the current stage (and overall progress)."""

    stage_id: str | None
    label: str | None
    kind: str | None
    index: int
    total: int
    duration_s: float | None
    remaining_s: float | None
    elapsed_s: float
    advance: str | None
    end_signal: str | None
    either_policy: str | None
    button: ButtonKind
    button_enabled: bool
    button_label: str | None
    waiting_on_operator: bool
    timer_elapsed: bool
    paused: bool
    complete: bool
    checklist: list[ChecklistState] = field(default_factory=list)
    reminders: list[dict[str, Any]] = field(default_factory=list)
    constraints: dict[str, bool] = field(default_factory=dict)
    collect: dict[str, Any] = field(default_factory=dict)
    stimulus: dict[str, Any] | None = None
    trial_index: int | None = None
    trial_count: int | None = None
    block_label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "label": self.label,
            "kind": self.kind,
            "index": self.index,
            "total": self.total,
            "duration_s": self.duration_s,
            "remaining_s": self.remaining_s,
            "elapsed_s": self.elapsed_s,
            "advance": self.advance,
            "end_signal": self.end_signal,
            "either_policy": self.either_policy,
            "button": self.button,
            "button_enabled": self.button_enabled,
            "button_label": self.button_label,
            "waiting_on_operator": self.waiting_on_operator,
            "timer_elapsed": self.timer_elapsed,
            "paused": self.paused,
            "complete": self.complete,
            "checklist": [c.to_dict() for c in self.checklist],
            "reminders": list(self.reminders),
            "constraints": dict(self.constraints),
            "collect": dict(self.collect),
            "stimulus": self.stimulus,
            "trial_index": self.trial_index,
            "trial_count": self.trial_count,
            "block_label": self.block_label,
        }


class StageRunner:
    def __init__(
        self,
        plan: ResolvedPlan,
        events: EventLog,
        clock: Clock | None = None,
        notify: NotifyFn | None = None,
        on_collect_change: Any | None = None,
    ) -> None:
        self.plan = plan
        self.events = events
        self.clock = clock or SystemClock()
        self.notify = notify
        self.on_collect_change = on_collect_change
        self.index = -1
        self.complete = False
        self.paused = False
        self._entered_ns = 0
        self._pause_acc_ns = 0
        self._pause_started_ns: int | None = None
        self._checklist: dict[str, bool] = {}
        self._fired_reminders: set[str] = set()
        self._leave_reason: str | None = None
        self._skipped_exit = False

    @property
    def current(self) -> ResolvedStage | None:
        if 0 <= self.index < len(self.plan.stages):
            return self.plan.stages[self.index]
        return None

    def start(self) -> StageView:
        if not self.plan.stages:
            self.complete = True
            return self.view()
        self._enter(0)
        return self.view()

    def tick(self) -> StageView:
        if self.complete or self.current is None or self.paused:
            return self.view()
        self._refresh_reminders()
        if self._should_auto_leave():
            self._leave(reason="timer")
        return self.view()

    def set_checklist(self, item_id: str, checked: bool) -> StageView:
        stage = self.current
        if stage is None:
            raise RuntimeError("no active stage")
        known = {item.id for item in stage.checklist}
        if item_id not in known:
            raise KeyError(f"unknown checklist item {item_id!r} for stage {stage.id}")
        self._checklist[item_id] = bool(checked)
        self.events.emit(
            "session_note",
            stage_id=stage.id,
            label=stage.label,
            payload={"note": "checklist_item", "item_id": item_id, "checked": bool(checked)},
        )
        view = self.view()
        self._emit_stage_status(view)
        return view

    def operator_advance(self) -> StageView:
        stage = self._require_stage()
        if not self._checklist_complete():
            raise RuntimeError("checklist is incomplete")
        if stage.end_signal == "operator":
            raise RuntimeError("this stage uses End phase, not Continue / Next phase")
        if stage.advance == "auto":
            raise RuntimeError("advance=auto does not accept operator_advance")
        if stage.advance == "either" and stage.either_policy == "late" and not self._timer_elapsed():
            raise RuntimeError("either_policy=late: wait for the timer before advancing")
        self.events.emit(
            "operator_advance",
            stage_id=stage.id,
            label=stage.label,
            payload={"stage_id": stage.id},
        )
        self._leave(reason="operator_advance")
        return self.view()

    def operator_end_phase(self) -> StageView:
        stage = self._require_stage()
        if not self._checklist_complete():
            raise RuntimeError("checklist is incomplete")
        if stage.end_signal != "operator":
            raise RuntimeError("this stage does not use end_signal=operator")
        if not self._end_button_ready(stage):
            raise RuntimeError("End phase is not enabled yet (timer still running)")
        self.events.emit(
            "operator_end_phase",
            stage_id=stage.id,
            label=stage.label,
            payload={"stage_id": stage.id},
        )
        self._leave(reason="operator_end_phase")
        return self.view()

    def pause(self) -> StageView:
        if self.paused or self.complete or self.current is None:
            return self.view()
        self.paused = True
        self._pause_started_ns = self.clock.monotonic_ns()
        stage = self.current
        self.events.emit("session_note", stage_id=stage.id, payload={"note": "pause"})
        return self.view()

    def resume(self) -> StageView:
        if not self.paused:
            return self.view()
        now = self.clock.monotonic_ns()
        if self._pause_started_ns is not None:
            self._pause_acc_ns += now - self._pause_started_ns
        self._pause_started_ns = None
        self.paused = False
        stage = self.current
        if stage is not None:
            self.events.emit("session_note", stage_id=stage.id, payload={"note": "resume"})
        return self.view()

    def skip(self, reason: str) -> StageView:
        stage = self._require_stage()
        if not reason.strip():
            raise RuntimeError("skip requires a reason")
        self._skipped_exit = stage.kind == "stimulus"
        self.events.emit(
            "session_note",
            stage_id=stage.id,
            label=stage.label,
            payload={"note": "skip", "reason": reason},
        )
        self._leave(reason="skip")
        return self.view()

    def view(self) -> StageView:
        stage = self.current
        total = len(self.plan.stages)
        if stage is None:
            return StageView(
                stage_id=None,
                label=None,
                kind=None,
                index=total if self.complete else 0,
                total=total,
                duration_s=None,
                remaining_s=None,
                elapsed_s=0.0,
                advance=None,
                end_signal=None,
                either_policy=None,
                button="hidden",
                button_enabled=False,
                button_label=None,
                waiting_on_operator=False,
                timer_elapsed=False,
                paused=self.paused,
                complete=self.complete,
            )
        elapsed = self._elapsed_s()
        remaining = None
        if stage.duration_s is not None:
            remaining = max(0.0, stage.duration_s - elapsed)
        button, label = self._button(stage)
        enabled = self._button_enabled(stage, button)
        collect = {k: v.to_dict() for k, v in stage.collect.items()}
        return StageView(
            stage_id=stage.id,
            label=stage.label,
            kind=stage.kind,
            index=self.index,
            total=total,
            duration_s=stage.duration_s,
            remaining_s=remaining,
            elapsed_s=elapsed,
            advance=stage.advance,
            end_signal=stage.end_signal,
            either_policy=stage.either_policy,
            button=button,
            button_enabled=enabled,
            button_label=label,
            waiting_on_operator=stage.advance == "operator" and stage.duration_s is None,
            timer_elapsed=self._timer_elapsed(),
            paused=self.paused,
            complete=False,
            checklist=[
                ChecklistState(id=c.id, text=c.text, checked=self._checklist.get(c.id, False))
                for c in stage.checklist
            ],
            reminders=self._active_reminders(stage, remaining),
            constraints=stage.constraints.to_dict(),
            collect=collect,
            stimulus=stage.stimulus.to_dict() if stage.stimulus else None,
            trial_index=stage.trial_index,
            trial_count=stage.trial_count,
            block_label=stage.block_label,
        )

    def _require_stage(self) -> ResolvedStage:
        stage = self.current
        if stage is None:
            raise RuntimeError("no active stage")
        return stage

    def _enter(self, index: int) -> None:
        self.index = index
        self._entered_ns = self.clock.monotonic_ns()
        self._pause_acc_ns = 0
        self._pause_started_ns = None
        self.paused = False
        self._checklist = {}
        self._fired_reminders = set()
        self._leave_reason = None
        self._skipped_exit = False
        stage = self.plan.stages[index]
        if self.on_collect_change:
            self.on_collect_change(stage.collect)
        if stage.events_enter:
            self.events.emit(
                stage.events_enter.name,
                stage_id=stage.id,
                label=stage.label,
                payload=dict(stage.events_enter.payload),
            )
        self._mark_reminder("enter")
        self._refresh_reminders()
        self._emit_stage_status(self.view())

    def _leave(self, reason: str) -> None:
        stage = self.current
        if stage is None:
            return
        self._leave_reason = reason
        remaining = None
        if stage.duration_s is not None:
            remaining = max(0.0, stage.duration_s - self._elapsed_s())
        for rem in stage.reminders:
            if rem.when == "exit":
                self._fire_reminder(rem)
        if stage.events_exit and not self._skipped_exit:
            self.events.emit(
                stage.events_exit.name,
                stage_id=stage.id,
                label=stage.label,
                payload=dict(stage.events_exit.payload),
            )
        nxt = self.index + 1
        if nxt >= len(self.plan.stages):
            self.index = len(self.plan.stages)
            self.complete = True
            if self.on_collect_change:
                self.on_collect_change({})
            view = self.view()
            self._emit_stage_status(view)
            return
        self._enter(nxt)

    def _elapsed_s(self) -> float:
        now = self.clock.monotonic_ns()
        pause = self._pause_acc_ns
        if self.paused and self._pause_started_ns is not None:
            pause += now - self._pause_started_ns
        return max(0.0, (now - self._entered_ns - pause) / 1_000_000_000)

    def _timer_elapsed(self) -> bool:
        stage = self.current
        if stage is None or stage.duration_s is None:
            return False
        return self._elapsed_s() >= stage.duration_s

    def _checklist_complete(self) -> bool:
        stage = self.current
        if stage is None:
            return True
        return all(self._checklist.get(item.id, False) for item in stage.checklist)

    def _button(self, stage: ResolvedStage) -> tuple[ButtonKind, str | None]:
        if stage.end_signal == "operator":
            return "end_phase", "End phase"
        if stage.advance in {"operator", "either"}:
            return "continue", "Continue / Next phase"
        return "hidden", None

    def _end_button_ready(self, stage: ResolvedStage) -> bool:
        if stage.duration_s is None:
            return True
        if stage.either_policy == "early":
            return True
        return self._timer_elapsed()

    def _button_enabled(self, stage: ResolvedStage, button: ButtonKind) -> bool:
        if button == "hidden" or not self._checklist_complete():
            return False
        if button == "end_phase":
            return self._end_button_ready(stage)
        if stage.advance == "either" and stage.either_policy == "late":
            return self._timer_elapsed()
        return True

    def _should_auto_leave(self) -> bool:
        stage = self.current
        if stage is None or not self._checklist_complete():
            return False
        if stage.end_signal == "operator":
            return False
        if stage.advance == "auto":
            return self._timer_elapsed()
        if stage.advance == "either":
            return self._timer_elapsed()
        return False

    def _active_reminders(self, stage: ResolvedStage, remaining: float | None) -> list[dict[str, Any]]:
        active: list[dict[str, Any]] = []
        elapsed = self._elapsed_s()
        for rem in stage.reminders:
            if rem.when == "enter":
                active.append(rem.to_dict())
            elif rem.when == "mid" and stage.duration_s is not None and elapsed >= stage.duration_s / 2:
                active.append(rem.to_dict())
            elif rem.when == "countdown_at_s" and remaining is not None and rem.at_s is not None:
                if remaining <= rem.at_s:
                    active.append(rem.to_dict())
        return active

    def _refresh_reminders(self) -> None:
        stage = self.current
        if stage is None:
            return
        remaining = None
        if stage.duration_s is not None:
            remaining = max(0.0, stage.duration_s - self._elapsed_s())
        elapsed = self._elapsed_s()
        for rem in stage.reminders:
            key = f"{rem.when}:{rem.text}:{rem.at_s}"
            if key in self._fired_reminders:
                continue
            fire = False
            if rem.when == "mid" and stage.duration_s is not None and elapsed >= stage.duration_s / 2:
                fire = True
            if rem.when == "countdown_at_s" and remaining is not None and rem.at_s is not None:
                if remaining <= rem.at_s:
                    fire = True
            if fire:
                self._fire_reminder(rem)

    def _mark_reminder(self, when: str) -> None:
        stage = self.current
        if stage is None:
            return
        for rem in stage.reminders:
            if rem.when == when:
                self._fire_reminder(rem)

    def _fire_reminder(self, rem: Reminder) -> None:
        key = f"{rem.when}:{rem.text}:{rem.at_s}"
        if key in self._fired_reminders:
            return
        self._fired_reminders.add(key)
        if self.notify:
            self.notify("stage.reminder", rem.to_dict() | {"stage_id": self.current.id if self.current else None})

    def _emit_stage_status(self, view: StageView) -> None:
        if self.notify:
            self.notify("stage.status", view.to_dict())
