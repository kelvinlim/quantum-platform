# quantum-platform

Integrated multimodal data-collection platform for a study comparing **quantum** and **standard** painting exposures.

Participants view paintings under controlled geometry while the system records:

- Heart rate / PPG (Polar Verity Sense, arm-worn)
- Facial expression and landmarks (RGB machine-vision camera)
- Facial infrared / perfusion (Optris PI 450i)
- Budget gaze on the painting plane (derived from the face RGB camera + software)

Phase 1 software is a **dry-run skeleton**: Tauri 2 + React operator UI, Rust host, and a Python capture sidecar talking JSON-RPC 2.0 NDJSON over stdio. Mock workers write the session directory tree with no hardware attached.

## Docs

- [Developer setup](docs/DEV.md) — venv, sidecar CLI, Tauri dev, tests
- [Architecture](docs/ARCHITECTURE.md) — desktop shell decision (**Option A**: Tauri 2 + React + Rust + Python sidecar), alternatives B–E, and **supported platforms**
- [Integrations](docs/INTEGRATIONS.md) — sidecar IPC (JSON-RPC 2.0 stdio), Python packaging, REDCap field contract, Box folder taxonomy
- [Camera SDKs](docs/SDK.md) — Optris OTC (PI 450i) and Spinnaker / PySpin (Blackfly S); OS support and host-install notes
- [Experiment configurator](docs/EXPERIMENT_CONFIG.md) — declarative stages, collect flags, operator reminders (schema v1)
- [Design](docs/DESIGN.md) — modalities, sync, data model
- [Plan](docs/PLAN.md) — phased implementation roadmap
- [Hardware](docs/HARDWARE.md) — recommended and owned devices
- [Protocol](docs/PROTOCOL.md) — investigator-facing study protocol (Draft / WIP); [lab-layout figure](docs/figures/lab-layout.png) (provisional geometry)

## Status

Phase 1 scaffolding is in the repo. Desktop shell is **Option A** (Tauri 2 + React + Rust + Python sidecar) — [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Tauri runs on Mac and Windows; full thermal capture needs Windows or Linux ([`docs/SDK.md`](docs/SDK.md)). Sidecar IPC, packaging, REDCap fields, and Box paths are locked in [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md). Experiment stages live in [`experiments/painting_session_simplified.yaml`](experiments/painting_session_simplified.yaml). The operational definition of “quantum” vs “standard” paintings remains an investigator decision ([`docs/PROTOCOL.md`](docs/PROTOCOL.md) §13).

## Quick start (no hardware)

Python 3.12 recommended (PySpin wheels). From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
qp doctor
qp run --config experiments/painting_session_simplified.yaml --mock --auto-press
```

That dry-run walks the example stages (auto-checking lists and pressing Continue / End phase) and writes `sessions/P001/S001/`.

Operator UI (dev machine with Node + Rust):

```bash
cd app
npm install
npm run tauri dev
```

See [docs/DEV.md](docs/DEV.md) for tests, the stdio RPC contract, and the planned PyInstaller `externalBin` release path.

## Layout

| Path | Role |
|------|------|
| `src/quantum_platform/` | Python sidecar (`qp`, `python -m quantum_platform`) |
| `experiments/` | Versioned experiment YAML catalog |
| `config/default.yaml` | `sidecar.*` / `redcap.*` / `box.*` / `experiments.*` sketch |
| `app/` | Tauri 2 + React operator UI and Rust host (`src-tauri`) |
| `tests/` | pytest (config, runner, RPC, session tree) |
