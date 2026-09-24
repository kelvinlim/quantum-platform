"""CLI: ``qp`` and ``python -m quantum_platform``.

No arguments (or ``serve``) starts the JSON-RPC 2.0 NDJSON stdio server.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from quantum_platform import __version__
from quantum_platform.clock import FakeClock, SystemClock
from quantum_platform.config import ConfigError, load_experiment
from quantum_platform.doctor import run_doctor
from quantum_platform.rpc import JsonRpcServer
from quantum_platform.sidecar import SidecarApp, auto_press_until_done


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="qp",
        description="Quantum Platform capture sidecar (JSON-RPC 2.0 NDJSON over stdio).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--experiments-dir",
        default=None,
        help="Catalog directory (default: ./experiments)",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Working root for sessions/ and experiments/ (default: cwd)",
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("serve", help="JSON-RPC 2.0 NDJSON server on stdin/stdout (default)")
    sub.add_parser("doctor", help="Probe vendor SDK imports and platform support")
    sub.add_parser("status", help="Print a status snapshot (no running session)")

    cal = sub.add_parser("calibrate", help="Calibration helpers")
    cal_sub = cal.add_subparsers(dest="cal_cmd")
    cal_sub.add_parser("gaze", help="Stub gaze look-at calibration")

    sess = sub.add_parser("session", help="Session start/stop (stdio RPC still preferred)")
    sess_sub = sess.add_subparsers(dest="session_cmd")
    start = sess_sub.add_parser("start", help="Start a session then print the result (in-process)")
    start.add_argument("--participant", required=True)
    start.add_argument("--session", required=True)
    start.add_argument("--experiment-id")
    start.add_argument("--experiment-path")
    start.add_argument("--sessions-root")
    start.add_argument("--mock", action="store_true", default=True)
    start.add_argument("--no-mock", action="store_false", dest="mock")
    sess_sub.add_parser("stop", help="Not used in-process; use session.start in the same process or RPC")

    run = sub.add_parser("run", help="Headless dry-run of an experiment (mock workers)")
    run.add_argument("--config", required=True, help="Path to experiment YAML/JSON")
    run.add_argument("--participant", default="P001")
    run.add_argument("--session", default="S001")
    run.add_argument("--sessions-root", default=None)
    run.add_argument("--mock", action="store_true", default=True)
    run.add_argument("--auto-press", action="store_true", help="Check lists and press Continue / End phase")
    run.add_argument(
        "--realtime",
        action="store_true",
        help="Use wall-clock durations instead of a FakeClock (slow)",
    )
    run.add_argument("--json", action="store_true", help="Print a JSON summary")

    val = sub.add_parser("validate", help="Validate an experiment file and print the resolved plan")
    val.add_argument("--config", required=True)
    val.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path.cwd()
    experiments_dir = (
        Path(args.experiments_dir).resolve() if args.experiments_dir else repo_root / "experiments"
    )

    cmd = args.cmd
    if cmd is None or cmd == "serve":
        return cmd_serve(repo_root, experiments_dir)
    if cmd == "doctor":
        print(json.dumps(run_doctor(), indent=2))
        return 0
    if cmd == "status":
        app = SidecarApp(experiments_dir=experiments_dir, repo_root=repo_root)
        print(json.dumps(app.status_get({}), indent=2))
        return 0
    if cmd == "calibrate":
        if args.cal_cmd != "gaze":
            parser.error("use: qp calibrate gaze")
        app = SidecarApp(experiments_dir=experiments_dir, repo_root=repo_root)
        print(json.dumps(app.calibrate_gaze({}), indent=2))
        return 0
    if cmd == "session":
        if args.session_cmd == "start":
            app = SidecarApp(experiments_dir=experiments_dir, repo_root=repo_root)
            params: dict[str, Any] = {
                "participant_id": args.participant,
                "session_id": args.session,
                "mock": args.mock,
            }
            if args.experiment_id:
                params["experiment_id"] = args.experiment_id
            if args.experiment_path:
                params["experiment_path"] = args.experiment_path
            if args.sessions_root:
                params["sessions_root"] = args.sessions_root
            print(json.dumps(app.session_start(params), indent=2))
            print(
                "session left running in this process; this CLI helper is for bring-up. "
                "Prefer `qp serve` or `qp run --auto-press`.",
                file=sys.stderr,
            )
            app.close()
            return 0
        parser.error("use: qp session start ...")
    if cmd == "validate":
        return cmd_validate(args.config, args.json)
    if cmd == "run":
        return cmd_run(args, repo_root, experiments_dir)
    parser.error(f"unknown command {cmd}")
    return 2


def cmd_serve(repo_root: Path, experiments_dir: Path) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(line_buffering=True)
        except Exception:  # noqa: BLE001
            pass
    app = SidecarApp(
        experiments_dir=experiments_dir,
        repo_root=repo_root,
        clock=SystemClock(),
    )
    server = JsonRpcServer(app.handlers())
    app._notify_cb = server.notify
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        app.close()
    return 0


def cmd_validate(path: str, as_json: bool) -> int:
    try:
        plan = load_experiment(path)
    except ConfigError as exc:
        print("validation failed:", file=sys.stderr)
        for err in exc.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    if as_json:
        print(json.dumps(plan.to_dict(), indent=2))
    else:
        print(f"ok  id={plan.id}  stages={len(plan.stages)}  protocol={plan.protocol_version}")
        for i, stage in enumerate(plan.stages):
            dur = "∞" if stage.duration_s is None else f"{stage.duration_s:g}s"
            print(
                f"  {i:02d}  {stage.id:24}  {stage.kind:14}  "
                f"advance={stage.advance:8}  end={stage.end_signal:8}  {dur}  {stage.label}"
            )
    return 0


def cmd_run(args: argparse.Namespace, repo_root: Path, experiments_dir: Path) -> int:
    try:
        load_experiment(args.config)
    except ConfigError as exc:
        print("validation failed:", file=sys.stderr)
        for err in exc.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    clock = SystemClock() if args.realtime else FakeClock()
    lines: list[str] = []
    last_stage: str | None = None

    def notify(method: str, params: dict[str, Any]) -> None:
        nonlocal last_stage
        if method == "event.emit":
            name = params.get("name")
            stage = params.get("stage_id") or ""
            ts = params.get("ts")
            line = f"event  ts={ts:.3f}  {name}  {stage}".rstrip()
            lines.append(line)
            print(line)
        elif method == "device.status":
            line = f"device {params.get('device')} -> {params.get('state')} ({params.get('backend')})"
            lines.append(line)
            print(line)
        elif method == "error":
            line = f"error  {params}"
            lines.append(line)
            print(line, file=sys.stderr)
        elif method == "stage.status":
            label = params.get("label") or params.get("stage_id")
            stage_id = params.get("stage_id")
            if params.get("complete"):
                print("stage  complete")
            elif label and stage_id != last_stage:
                last_stage = stage_id
                print(f"stage  enter {label}")

    app = SidecarApp(
        notify=notify,
        clock=clock,
        experiments_dir=experiments_dir,
        repo_root=repo_root,
    )
    sessions_root = args.sessions_root or str(repo_root / "sessions")
    result = app.session_start(
        {
            "participant_id": args.participant,
            "session_id": args.session,
            "experiment_path": args.config,
            "sessions_root": sessions_root,
            "mock": args.mock,
        }
    )
    print(f"session_dir {result['session_dir']}")
    if args.auto_press or not args.realtime:
        auto_press_until_done(app)
    stop = app.session_stop({})
    summary = {
        "session_dir": stop["session_dir"],
        "session_status": stop["session_status"],
        "events": [ln for ln in lines if ln.startswith("event")],
    }
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"done  status={stop['session_status']}  dir={stop['session_dir']}")
    app.close()
    return 0
