# quantum-platform

Integrated multimodal data-collection platform for a study comparing **quantum** and **standard** painting exposures.

Participants view paintings under controlled geometry while the system records:

- Heart rate / PPG (Polar Verity Sense, arm-worn)
- Facial expression and landmarks (RGB machine-vision camera)
- Facial infrared / perfusion (Optris PI 450i)
- Budget gaze on the painting plane (derived from the face RGB camera + software)

This repository holds design docs and the build plan first; capture software follows in later milestones.

## Docs

- [Architecture](docs/ARCHITECTURE.md) — desktop shell decision (**Option A**: Tauri 2 + React + Rust + Python sidecar), alternatives B–E, and **supported platforms**
- [Integrations](docs/INTEGRATIONS.md) — sidecar IPC (JSON-RPC 2.0 stdio), Python packaging, REDCap field contract, Box folder taxonomy
- [Camera SDKs](docs/SDK.md) — Optris OTC (PI 450i) and Spinnaker / PySpin (Blackfly S); OS support and host-install notes
- [Experiment configurator](docs/EXPERIMENT_CONFIG.md) — declarative stages, collect flags, operator reminders (schema v1 sketch)
- [Design](docs/DESIGN.md) — modalities, sync, data model
- [Plan](docs/PLAN.md) — phased implementation roadmap
- [Hardware](docs/HARDWARE.md) — recommended and owned devices
- [Protocol](docs/PROTOCOL.md) — investigator-facing study protocol (Draft / WIP); [lab-layout figure](docs/figures/lab-layout.png) (provisional geometry)

## Status

Early design. Desktop shell is locked: **Option A** (Tauri 2 + React + Rust + Python sidecar) — see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Tauri runs on Mac and Windows; full thermal capture needs Windows or Linux ([`docs/SDK.md`](docs/SDK.md)). Sidecar IPC, packaging, REDCap fields, and Box paths are locked in [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md). Experiment stages, collect flags, and operator reminders are sketched in [`docs/EXPERIMENT_CONFIG.md`](docs/EXPERIMENT_CONFIG.md). A working protocol outline lives in [`docs/PROTOCOL.md`](docs/PROTOCOL.md). The operational definition of “quantum” vs “standard” paintings, and the other investigator decisions listed there, are still open.
