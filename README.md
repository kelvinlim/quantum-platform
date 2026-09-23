# quantum-platform

Integrated multimodal data-collection platform for a study comparing **quantum** and **standard** painting exposures.

Participants view paintings under controlled geometry while the system records:

- Heart rate / PPG (Polar Verity Sense, arm-worn)
- Facial expression and landmarks (RGB machine-vision camera)
- Facial infrared / perfusion (Optris PI 450i)
- Budget gaze on the painting plane (derived from the face RGB camera + software)

This repository holds design docs and the build plan first; capture software follows in later milestones.

## Docs

- [Architecture](docs/ARCHITECTURE.md) — desktop shell decision (**Option A**: Tauri 2 + React + Rust + Python sidecar) and alternatives B–E
- [Design](docs/DESIGN.md) — modalities, sync, data model
- [Plan](docs/PLAN.md) — phased implementation roadmap
- [Hardware](docs/HARDWARE.md) — recommended and owned devices
- [Protocol](docs/PROTOCOL.md) — investigator-facing study protocol (Draft / WIP); [lab-layout figure](docs/figures/lab-layout.png) (provisional geometry)

## Status

Early design. Desktop shell is locked: **Option A** (Tauri 2 + React + Rust + Python sidecar) — see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). A working protocol outline lives in [`docs/PROTOCOL.md`](docs/PROTOCOL.md). The operational definition of “quantum” vs “standard” paintings, and the other investigator decisions listed there, are still open.
