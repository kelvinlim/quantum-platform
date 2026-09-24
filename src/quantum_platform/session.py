"""Session directory layout (DESIGN.md §5) and events.jsonl writer."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

from quantum_platform.clock import Clock, SystemClock
from quantum_platform.config import ResolvedPlan

STREAM_NAMES = ("thermal", "rgb", "verity", "gaze")

# LSL name conventions (PLAN.md Phase 1). pylsl outlets are stubbed.
LSL_STREAM_NAMES = {
    "thermal": "QuantumThermal",
    "rgb": "QuantumRgb",
    "verity": "QuantumVerity",
    "gaze": "GazePainting",
    "events": "QuantumEvents",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class EventRecord:
    name: str
    ts: float
    ts_ns: int
    stage_id: str | None = None
    label: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "name": self.name,
            "ts": self.ts,
            "ts_ns": self.ts_ns,
        }
        if self.stage_id is not None:
            rec["stage_id"] = self.stage_id
        if self.label is not None:
            rec["label"] = self.label
        if self.payload:
            rec["payload"] = dict(self.payload)
        return rec


NotifyFn = Callable[[str, dict[str, Any]], None]


class EventLog:
    """Append-only events.jsonl + optional ``event.emit`` notification."""

    def __init__(
        self,
        path: Path,
        clock: Clock,
        origin_ns: int,
        notify: NotifyFn | None = None,
    ) -> None:
        self.path = path
        self.clock = clock
        self.origin_ns = origin_ns
        self.notify = notify
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)
        self._records: list[EventRecord] = []

    def now_ns(self) -> int:
        return self.clock.monotonic_ns()

    def ts_pair(self, ns: int | None = None) -> tuple[float, int]:
        ts_ns = self.clock.monotonic_ns() if ns is None else ns
        rel = (ts_ns - self.origin_ns) / 1_000_000_000
        return rel, ts_ns

    def emit(
        self,
        name: str,
        *,
        stage_id: str | None = None,
        label: str | None = None,
        payload: dict[str, Any] | None = None,
        ts_ns: int | None = None,
    ) -> EventRecord:
        rel, abs_ns = self.ts_pair(ts_ns)
        rec = EventRecord(
            name=name,
            ts=rel,
            ts_ns=abs_ns,
            stage_id=stage_id,
            label=label,
            payload=dict(payload or {}),
        )
        line = json.dumps(rec.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n"
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line)
        self._records.append(rec)
        if self.notify:
            self.notify("event.emit", rec.to_dict())
        return rec

    @property
    def records(self) -> list[EventRecord]:
        return list(self._records)


@dataclass
class SessionPaths:
    root: Path
    meta: Path
    events: Path
    calibration: Path
    streams: Path
    derived: Path
    experiment_source: Path
    experiment_resolved: Path

    def stream_dir(self, name: str) -> Path:
        return self.streams / name


def build_session_paths(sessions_root: str | Path, participant_id: str, session_id: str) -> SessionPaths:
    root = Path(sessions_root) / participant_id / session_id
    return SessionPaths(
        root=root,
        meta=root / "meta.yaml",
        events=root / "events.jsonl",
        calibration=root / "calibration",
        streams=root / "streams",
        derived=root / "derived",
        experiment_source=root / "experiment.yaml",
        experiment_resolved=root / "experiment.resolved.yaml",
    )


class SessionStore:
    def __init__(
        self,
        participant_id: str,
        session_id: str,
        sessions_root: str | Path,
        clock: Clock | None = None,
        notify: NotifyFn | None = None,
    ) -> None:
        self.participant_id = participant_id
        self.session_id = session_id
        self.paths = build_session_paths(sessions_root, participant_id, session_id)
        self.clock = clock or SystemClock()
        self.origin_ns = self.clock.monotonic_ns()
        self.notify = notify
        self.events = EventLog(self.paths.events, self.clock, self.origin_ns, notify)
        self.aborted = False
        self.started_utc = utc_now_iso()

    def create_tree(self, plan: ResolvedPlan | None = None, extra_meta: dict[str, Any] | None = None) -> None:
        root = self.paths.root
        root.mkdir(parents=True, exist_ok=True)
        self.paths.calibration.mkdir(exist_ok=True)
        self.paths.derived.mkdir(exist_ok=True)
        for name in STREAM_NAMES:
            self.paths.stream_dir(name).mkdir(parents=True, exist_ok=True)

        if plan is not None:
            if plan.source_path and Path(plan.source_path).is_file():
                self.paths.experiment_source.write_text(
                    Path(plan.source_path).read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
            else:
                yaml.safe_dump(plan.to_dict(), self.paths.experiment_source.open("w", encoding="utf-8"), sort_keys=False)
            with self.paths.experiment_resolved.open("w", encoding="utf-8") as fh:
                yaml.safe_dump(plan.to_dict(), fh, sort_keys=False)

        meta = {
            "participant_id": self.participant_id,
            "session_id": self.session_id,
            "started_at_utc": self.started_utc,
            "clock": "monotonic",
            "origin_monotonic_ns": self.origin_ns,
            "session_status": "in_progress",
            "lsl_stream_names": dict(LSL_STREAM_NAMES),
        }
        if plan is not None:
            meta.update(
                {
                    "experiment_id": plan.id,
                    "experiment_name": plan.name,
                    "protocol_version": plan.protocol_version,
                    "schema_version": plan.schema_version,
                    "resolved_stage_ids": [s.id for s in plan.stages],
                    "randomization": plan.randomization,
                    "resolved_order": plan.resolved_order,
                }
            )
        if extra_meta:
            meta.update(extra_meta)
        self.write_meta(meta)

    def write_meta(self, meta: dict[str, Any]) -> None:
        with self.paths.meta.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(meta, fh, sort_keys=False)

    def read_meta(self) -> dict[str, Any]:
        with self.paths.meta.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            return {}
        return data

    def update_meta(self, **fields: Any) -> dict[str, Any]:
        meta = self.read_meta()
        meta.update(fields)
        self.write_meta(meta)
        return meta

    def mark_complete(self, status: str = "complete") -> None:
        self.update_meta(
            session_status=status,
            ended_at_utc=utc_now_iso(),
            local_complete=True,
        )
