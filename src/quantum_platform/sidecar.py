"""Sidecar application: JSON-RPC methods + session/stage/worker supervision."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from quantum_platform import __version__
from quantum_platform.clock import Clock, FakeClock, SystemClock
from quantum_platform.config import ConfigError, find_experiment, load_experiment
from quantum_platform.doctor import run_doctor
from quantum_platform.hardware import current_platform, probe_all
from quantum_platform.integrations import BoxUploader, RedcapClient
from quantum_platform.rpc import APPLICATION_ERROR, INVALID_PARAMS, RpcError
from quantum_platform.runner import StageRunner, StageView
from quantum_platform.session import SessionStore
from quantum_platform.workers import WorkerHub

DEFAULT_EXPERIMENTS_DIR = "experiments"


class SidecarApp:
    def __init__(
        self,
        notify: Any | None = None,
        clock: Clock | None = None,
        experiments_dir: str | Path | None = None,
        repo_root: str | Path | None = None,
    ) -> None:
        self._notify_cb = notify
        self.clock: Clock = clock or SystemClock()
        self.repo_root = Path(repo_root) if repo_root else Path.cwd()
        self.experiments_dir = Path(experiments_dir) if experiments_dir else self.repo_root / DEFAULT_EXPERIMENTS_DIR
        self.lock = threading.RLock()
        self.store: SessionStore | None = None
        self.runner: StageRunner | None = None
        self.workers: WorkerHub | None = None
        self.plan = None
        self.mock = True
        self.redcap = RedcapClient()
        self.box = BoxUploader()
        self._stop_ticker = threading.Event()
        self._ticker: threading.Thread | None = None

    def notify(self, method: str, params: dict[str, Any]) -> None:
        if self._notify_cb:
            self._notify_cb(method, params)

    def handlers(self) -> dict[str, Any]:
        return {
            "status.get": self.status_get,
            "doctor.run": self.doctor_run,
            "session.start": self.session_start,
            "session.stop": self.session_stop,
            "session.advance": self.session_advance,
            "session.end_phase": self.session_end_phase,
            "session.checklist_set": self.session_checklist_set,
            "session.pause": self.session_pause,
            "session.resume": self.session_resume,
            "session.skip": self.session_skip,
            "session.abort": self.session_abort,
            "calibrate.gaze": self.calibrate_gaze,
        }

    def status_get(self, params: Any = None) -> dict[str, Any]:
        with self.lock:
            devices = {}
            if self.workers:
                devices = self.workers.status()
            else:
                for probe in probe_all():
                    if probe.name in {"thermal", "rgb", "verity", "gaze"}:
                        devices[probe.name] = {
                            "state": "disconnected",
                            "backend": "stub",
                            "platform_supported": probe.platform_supported,
                            "importable": probe.importable,
                        }
            stage = self.runner.view().to_dict() if self.runner else None
            session = None
            if self.store:
                session = {
                    "active": True,
                    "participant_id": self.store.participant_id,
                    "session_id": self.store.session_id,
                    "session_dir": str(self.store.paths.root),
                    "mock": self.mock,
                }
            return {
                "sidecar": {"ok": True, "version": __version__, "platform": current_platform()},
                "session": session,
                "stage": stage,
                "devices": devices,
            }

    def doctor_run(self, params: Any = None) -> dict[str, Any]:
        return run_doctor()

    def session_start(self, params: Any = None) -> dict[str, Any]:
        params = params or {}
        participant_id = _req_str(params, "participant_id")
        session_id = _req_str(params, "session_id")
        experiment_id = params.get("experiment_id")
        experiment_path = params.get("experiment_path")
        if experiment_id and experiment_path:
            raise RpcError(INVALID_PARAMS, "provide experiment_id or experiment_path, not both")
        sessions_root = params.get("sessions_root") or str(self.repo_root / "sessions")
        mock = bool(params.get("mock", True))

        with self.lock:
            if self.store is not None:
                raise RpcError(APPLICATION_ERROR, "a session is already running; call session.stop first")

            plan = None
            if experiment_id or experiment_path:
                try:
                    if experiment_path:
                        plan = load_experiment(experiment_path)
                    else:
                        path = find_experiment(str(experiment_id), self.experiments_dir)
                        plan = load_experiment(path)
                except ConfigError as exc:
                    raise RpcError(INVALID_PARAMS, "experiment validation failed", exc.errors) from exc
                except FileNotFoundError as exc:
                    raise RpcError(INVALID_PARAMS, str(exc)) from exc

            store = SessionStore(
                participant_id=participant_id,
                session_id=session_id,
                sessions_root=sessions_root,
                clock=self.clock,
                notify=self.notify,
            )
            store.create_tree(
                plan,
                extra_meta={
                    "mock": mock,
                    "sidecar_version": __version__,
                },
            )
            workers = WorkerHub(store, mock=mock, notify=self.notify)
            try:
                workers.start()
            except NotImplementedError as exc:
                raise RpcError(APPLICATION_ERROR, str(exc)) from exc

            runner = None
            if plan is not None:
                runner = StageRunner(
                    plan,
                    store.events,
                    clock=self.clock,
                    notify=self.notify,
                    on_collect_change=workers.apply_collect,
                )

            self.store = store
            self.workers = workers
            self.runner = runner
            self.plan = plan
            self.mock = mock
            store.events.emit(
                "session_start",
                payload={"participant_id": participant_id, "session_id": session_id},
            )
            view = None
            if runner is not None:
                view = runner.start()
                workers.sample_enabled()
            else:
                # Hardware bring-up session: enable all mock streams.
                from quantum_platform.config import CollectSpec

                workers.apply_collect({name: CollectSpec(enabled=True) for name in ("thermal", "rgb", "verity", "gaze")})
                workers.sample_enabled()

        self._start_ticker()
        result: dict[str, Any] = {
            "ok": True,
            "session_dir": str(store.paths.root),
            "mock": mock,
        }
        if plan is not None:
            result["experiment_id"] = plan.id
            result["plan"] = {
                "id": plan.id,
                "name": plan.name,
                "protocol_version": plan.protocol_version,
                "stages": [s.to_dict() for s in plan.stages],
                "resolved_order": plan.resolved_order,
            }
        if view is not None:
            result["stage"] = view.to_dict()
        return result

    def session_stop(self, params: Any = None) -> dict[str, Any]:
        params = params or {}
        aborted = bool(params.get("aborted", False))
        with self.lock:
            if self.store is None:
                raise RpcError(APPLICATION_ERROR, "no active session")
            self._stop_ticker_unlocked()
            if self.workers:
                self.workers.sample_enabled()
                self.workers.stop()
            status = "aborted" if aborted or self.store.aborted else "complete"
            self.store.events.emit(
                "session_end",
                payload={"status": status},
            )
            self.store.mark_complete(status)
            session_dir = str(self.store.paths.root)
            self.store = None
            self.runner = None
            self.workers = None
            self.plan = None
        return {"ok": True, "session_dir": session_dir, "session_status": status}

    def session_advance(self, params: Any = None) -> dict[str, Any]:
        return self._mutate_runner(lambda r: r.operator_advance())

    def session_end_phase(self, params: Any = None) -> dict[str, Any]:
        return self._mutate_runner(lambda r: r.operator_end_phase())

    def session_checklist_set(self, params: Any = None) -> dict[str, Any]:
        params = params or {}
        item_id = _req_str(params, "item_id")
        checked = params.get("checked", True)
        if not isinstance(checked, bool):
            raise RpcError(INVALID_PARAMS, "checked must be a boolean")
        return self._mutate_runner(lambda r: r.set_checklist(item_id, checked))

    def session_pause(self, params: Any = None) -> dict[str, Any]:
        return self._mutate_runner(lambda r: r.pause())

    def session_resume(self, params: Any = None) -> dict[str, Any]:
        return self._mutate_runner(lambda r: r.resume())

    def session_skip(self, params: Any = None) -> dict[str, Any]:
        params = params or {}
        reason = _req_str(params, "reason")
        return self._mutate_runner(lambda r: r.skip(reason))

    def session_abort(self, params: Any = None) -> dict[str, Any]:
        params = params or {}
        reason = params.get("reason") or "aborted by operator"
        with self.lock:
            if self.store is None:
                raise RpcError(APPLICATION_ERROR, "no active session")
            self.store.aborted = True
            self.store.events.emit(
                "session_note",
                payload={"note": "abort", "reason": str(reason)},
            )
        return self.session_stop({"aborted": True})

    def calibrate_gaze(self, params: Any = None) -> dict[str, Any]:
        params = params or {}
        with self.lock:
            if self.store is not None:
                self.store.events.emit(
                    "calibration_start",
                    payload={"kind": "gaze", "mode": "stub"},
                )
                self.store.events.emit(
                    "calibration_end",
                    payload={"kind": "gaze", "mode": "stub"},
                )
        return {
            "ok": True,
            "mode": "stub",
            "message": "gaze look-at calibration UI is not implemented in Phase 1",
        }

    def tick(self) -> StageView | None:
        with self.lock:
            if self.runner is None:
                return None
            view = self.runner.tick()
            if self.workers:
                self.workers.sample_enabled()
            return view

    def _mutate_runner(self, fn: Any) -> dict[str, Any]:
        with self.lock:
            if self.runner is None:
                raise RpcError(APPLICATION_ERROR, "no active experiment session")
            try:
                view = fn(self.runner)
            except (RuntimeError, KeyError) as exc:
                raise RpcError(APPLICATION_ERROR, str(exc)) from exc
            if self.workers:
                self.workers.sample_enabled()
            return {"ok": True, "stage": view.to_dict(), "complete": view.complete}

    def _start_ticker(self) -> None:
        if isinstance(self.clock, FakeClock):
            return
        self._stop_ticker.clear()
        if self._ticker and self._ticker.is_alive():
            return

        def loop() -> None:
            while not self._stop_ticker.wait(0.05):
                try:
                    self.tick()
                except Exception as exc:  # noqa: BLE001
                    self.notify("error", {"code": "ticker_fault", "message": str(exc)})

        self._ticker = threading.Thread(target=loop, name="qp-ticker", daemon=True)
        self._ticker.start()

    def _stop_ticker_unlocked(self) -> None:
        self._stop_ticker.set()
        ticker = self._ticker
        self._ticker = None
        if ticker and ticker.is_alive() and threading.current_thread() is not ticker:
            ticker.join(timeout=1.0)

    def close(self) -> None:
        with self.lock:
            self._stop_ticker_unlocked()


def _req_str(params: dict[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RpcError(INVALID_PARAMS, f"{key} is required")
    return value.strip()


def auto_press_until_done(app: SidecarApp, max_steps: int = 10_000) -> list[dict[str, Any]]:
    """Drive operator buttons and a FakeClock so a dry-run finishes without a UI."""
    log: list[dict[str, Any]] = []
    for _ in range(max_steps):
        view = app.tick()
        if view is None:
            break
        log.append(view.to_dict())
        if view.complete:
            break
        advanced = False
        for item in view.checklist:
            if not item.checked:
                app.session_checklist_set({"item_id": item.id, "checked": True})
                advanced = True
        view = app.runner.view() if app.runner else view
        if view.button_enabled:
            if view.button == "end_phase":
                app.session_end_phase({})
            elif view.button == "continue":
                app.session_advance({})
            advanced = True
            continue
        if view.remaining_s is not None and view.remaining_s > 0 and isinstance(app.clock, FakeClock):
            app.clock.advance(view.remaining_s + 0.001)
            advanced = True
            continue
        if not advanced:
            # Open-ended stage whose button is still disabled after auto-check.
            if app.runner and app.runner.complete:
                break
            if isinstance(app.clock, FakeClock):
                app.clock.advance(0.01)
            else:
                break
    return log
