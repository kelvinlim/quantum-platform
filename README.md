# quantum-platform

Integrated multimodal data-collection platform for a study comparing **quantum** and **standard** painting exposures.

Participants view paintings under controlled geometry while the system records:

- Heart rate / PPG (Polar Verity Sense, arm-worn)
- Facial expression and landmarks (RGB machine-vision camera)
- Facial infrared / perfusion (Optris PI 450i)
- Budget gaze on the painting plane (derived from the face RGB camera + software)

This repository holds design docs and the build plan first; capture software follows in later milestones.

## Docs

- [Design](docs/DESIGN.md) — architecture, modalities, sync, data model
- [Plan](docs/PLAN.md) — phased implementation roadmap
- [Hardware](docs/HARDWARE.md) — recommended and owned devices

## Status

Early design. Painting “quantum vs standard” stimulus protocol is still to be defined by the investigators.
