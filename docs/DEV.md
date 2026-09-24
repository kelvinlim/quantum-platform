# Developer setup: quantum-platform

Phase 1 dry-run path. No cameras, BLE, REDCap, or Box are required.

## Prerequisites

- **Python 3.12** recommended (PySpin wheels on Windows / macOS / Ubuntu 24.04 list 3.10 and 3.12, not 3.11 — [SDK.md](SDK.md)). 3.11+ is enough for this sidecar.
- **Node.js 20+** and npm (operator UI).
- **Rust** recent stable (current Tauri 2 crates need a newer compiler than 1.83). On Linux you also need the usual Tauri system libs (`libwebkit2gtk-4.1-dev`, etc.).

## Python sidecar

From the repo root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Entry points (equivalent):

```bash
python -m quantum_platform         # JSON-RPC 2.0 NDJSON on stdin/stdout
qp serve                           # same
qp doctor                          # SDK import / OS support report
qp validate --config experiments/painting_session_simplified.yaml
qp run --config experiments/painting_session_simplified.yaml --mock --auto-press
```

`qp run --auto-press` uses a **FakeClock** so the documented 60 s baseline and trial timings do not block. Add `--realtime` only if you want wall-clock durations.

`qp doctor` reports whether `optris.otcsdk`, `PySpin`, `bleak`, `mediapipe`, and `pylsl` import. Thermal is marked **unsupported on macOS** ([SDK.md](SDK.md)). Missing vendor SDKs are expected on a dry-run machine.

## Tauri operator UI

The desktop shell lives in `app/` (React + Vite + `src-tauri`). It mirrors [kelvinlim/audio-compare](https://github.com/kelvinlim/audio-compare): Tauri 2, React, a small Rust host, and a spawned sidecar. The Python package occupies `src/quantum_platform/`, so the UI is not at the repo root.

```bash
cd app
npm install
npm run tauri dev
```

The Rust host spawns `python3 -m quantum_platform serve` with `PYTHONPATH=<repo>/src` and `PYTHONUNBUFFERED=1`. Override the interpreter with `QUANTUM_PLATFORM_PYTHON`.

Frontend-only (no sidecar, no IPC):

```bash
cd app && npm run dev
```

That Vite page explains that the operator UI needs the Tauri host.

### Release packaging (not in Phase 1)

[INTEGRATIONS.md](INTEGRATIONS.md) §3: ship a **PyInstaller onedir** as a Tauri `externalBin` (same `bundle.externalBin` pattern as audio-compare’s ffmpeg sidecar). Prefer onedir over onefile. Vendor SDKs (Spinnaker, OTC) still need a host install. Phase 1 does not run PyInstaller.

## Tests

```bash
pytest
cd app && npm run build
cd app/src-tauri && cargo check
```

## Session output

A dry-run writes the tree from [DESIGN.md](DESIGN.md) §5:

```
sessions/<participant_id>/<session_id>/
  meta.yaml
  events.jsonl
  experiment.yaml
  experiment.resolved.yaml
  calibration/
  streams/{thermal,rgb,verity,gaze}/*.jsonl
  derived/
```

Timestamps are **monotonic** (`ts` seconds from session start, `ts_ns` raw `monotonic_ns`).

## IPC

Locked transport: JSON-RPC 2.0, one NDJSON object per line on sidecar stdin/stdout ([INTEGRATIONS.md](INTEGRATIONS.md) §2).

Phase 1 also implements additive operator methods used by the runbook UI (`session.advance`, `session.end_phase`, `session.checklist_set`, pause/resume/skip/abort) and optional `stage.status` notifications. Those names were left open by EXPERIMENT_CONFIG.md §6; they do not change the locked method list.
