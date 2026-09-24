"""Capture workers. Phase 1 ships mock writers; vendor backends are stubs."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from quantum_platform.clock import Clock
from quantum_platform.config import CollectSpec
from quantum_platform.hardware import (
    MediaPipeGazeBackend,
    OptrisOtcBackend,
    PolarBleBackend,
    PySpinBackend,
)
from quantum_platform.session import LSL_STREAM_NAMES, NotifyFn, SessionStore

WORKER_NAMES = ("thermal", "rgb", "verity", "gaze")


class MockStreamWorker:
    """Writes placeholder JSONL samples while the stage collect flag is on."""

    def __init__(
        self,
        name: str,
        stream_dir: Path,
        clock: Clock,
        origin_ns: int,
        notify: NotifyFn | None = None,
        hz: float = 2.0,
    ) -> None:
        self.name = name
        self.stream_dir = stream_dir
        self.clock = clock
        self.origin_ns = origin_ns
        self.notify = notify
        self.hz = hz
        self.path = stream_dir / f"{name}.jsonl"
        self.enabled = False
        self._lock = threading.Lock()
        self._seq = 0
        self.stream_dir.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def set_enabled(self, enabled: bool, hz: float | None = None) -> None:
        with self._lock:
            was = self.enabled
            self.enabled = bool(enabled)
            if hz is not None:
                self.hz = hz
        if enabled and not was and self.notify:
            self.notify("device.status", {"device": self.name, "state": "recording", "backend": "mock"})
        elif not enabled and was and self.notify:
            self.notify("device.status", {"device": self.name, "state": "idle", "backend": "mock"})

    def write_sample(self, extra: dict[str, Any] | None = None) -> dict[str, Any] | None:
        with self._lock:
            if not self.enabled:
                return None
            self._seq += 1
            seq = self._seq
        now = self.clock.monotonic_ns()
        rec = {
            "seq": seq,
            "ts": (now - self.origin_ns) / 1_000_000_000,
            "ts_ns": now,
            "device": self.name,
            "backend": "mock",
            "lsl_stream": LSL_STREAM_NAMES.get(self.name),
            "placeholder": True,
        }
        if extra:
            rec.update(extra)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")
        return rec

    def connect(self) -> None:
        if self.notify:
            self.notify("device.status", {"device": self.name, "state": "connected", "backend": "mock"})

    def disconnect(self) -> None:
        if self.notify:
            self.notify("device.status", {"device": self.name, "state": "disconnected", "backend": "mock"})


class WorkerHub:
    """Supervises mock (or later real) workers for one session."""

    def __init__(
        self,
        store: SessionStore,
        mock: bool = True,
        notify: NotifyFn | None = None,
    ) -> None:
        self.store = store
        self.mock = mock
        self.notify = notify
        self.workers: dict[str, MockStreamWorker] = {}
        self._real_backends = {
            "thermal": OptrisOtcBackend(),
            "rgb": PySpinBackend(),
            "verity": PolarBleBackend(),
            "gaze": MediaPipeGazeBackend(),
        }
        for name in WORKER_NAMES:
            worker = MockStreamWorker(
                name,
                store.paths.stream_dir(name),
                store.clock,
                store.origin_ns,
                notify=notify,
            )
            self.workers[name] = worker

    def start(self) -> None:
        if not self.mock:
            for name, backend in self._real_backends.items():
                # Phase 1: refuse real capture rather than silently writing mocks.
                try:
                    backend.start()
                except NotImplementedError as exc:
                    if self.notify:
                        self.notify(
                            "error",
                            {
                                "code": "backend_stub",
                                "message": str(exc),
                                "device": name,
                            },
                        )
                    raise
        for worker in self.workers.values():
            worker.connect()

    def apply_collect(self, collect: dict[str, CollectSpec] | dict[str, Any]) -> None:
        for name, worker in self.workers.items():
            spec = collect.get(name) if collect else None
            if spec is None:
                worker.set_enabled(False)
                continue
            if hasattr(spec, "enabled"):
                worker.set_enabled(bool(spec.enabled), getattr(spec, "hz", None))
            elif isinstance(spec, dict):
                worker.set_enabled(bool(spec.get("enabled", False)), spec.get("hz"))
            else:
                worker.set_enabled(bool(spec))

    def sample_enabled(self) -> None:
        for worker in self.workers.values():
            worker.write_sample()

    def stop(self) -> None:
        for worker in self.workers.values():
            worker.set_enabled(False)
            worker.disconnect()

    def status(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name, worker in self.workers.items():
            out[name] = {
                "state": "recording" if worker.enabled else "connected" if self.mock else "unknown",
                "backend": "mock" if self.mock else "stub",
                "path": str(worker.path),
                "samples": worker._seq,
            }
        return out
