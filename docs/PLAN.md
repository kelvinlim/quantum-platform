# Plan: quantum-platform

Phased roadmap. Docs-first repo; software follows.

## Phase 0 — Docs and decisions (current)

- [x] Capture hardware notes from prior Gemini design discussion
- [x] Lock preferred HR: **Polar Verity Sense** (arm)
- [x] Recommend RGB: **Blackfly S BFS-U3-23S3C-C** (~$421 body)
- [x] Budget gaze approach: face RGB + MediaPipe/OpenFace + painting-plane intersection
- [ ] Investigator: define quantum vs standard stimulus protocol
- [ ] Order RGB camera + C-mount lens; confirm Verity Sense kit
- [ ] Confirm IRB / data-retention constraints for face/thermal video

**Exit:** Design + plan merged; shopping list agreed; protocol outline drafted.

## Phase 1 — Repo scaffolding (MVP skeleton)

- Python package layout (`src/quantum_platform/`)
- Config schemas for hardware profiles and session metadata
- LSL stream name conventions + `events.jsonl` writer
- Stub workers: `thermal`, `rgb`, `verity`, `gaze`, `stimulus` (simulate clocks if hardware absent)
- CLI: `qp session start|stop`, `qp calibrate gaze`, `qp doctor` (device presence checks)
- Unit tests for timestamp pairing and event log format

**Exit:** Dry-run session produces aligned fake streams + markers on disk.

## Phase 2 — Hardware bring-up

1. **RGB** — Spinnaker capture at 60–120 Hz with monotonic timestamps; lens FOV check at 0.9 m
2. **Thermal** — Optris SDK path; raw uint16 + verified °C conversion; manual NUC API
3. **Verity** — BLE connect, PPG/HR samples, dual timestamps, band-side metadata
4. **Co-mount** — Print/assemble dual bay; RGB–thermal calibration routine
5. **Gaze** — MediaPipe iris → painting-plane; 5–9 point look-at calibration UI

**Exit:** Live multi-stream session (even without paintings) with NUC only in ISI.

## Phase 3 — Stimulus controller

- Painting trial state machine: fixation → stimulus → ISI → …
- Condition tags: `quantum` | `standard` (and painting IDs)
- Optional on-screen instructions / rating scales if protocol requires
- Enforce “no NUC during stimulus”

**Exit:** Pilot with 1–2 colleagues; timing logs reviewed.

## Phase 4 — Derived features and QC

- Facial AUs / blinks (MediaPipe or OpenFace offline or online)
- Thermal ROI time series mapped from RGB landmarks
- Gaze AOI occupancy per painting
- HR summary windows locked to stimulus markers
- Session QC report (dropouts, sync gaps, NUC collisions)

**Exit:** Analysis-ready exports (CSV/Parquet) keyed by `participant`, `painting_id`, `condition`.

## Phase 5 — Hardening

- Failure modes: USB drop, BLE disconnect, disk full
- Checksums / recording integrity
- Operator checklist and run book in `docs/RUNBOOK.md`
- Performance: ring buffers, optional C++ thermal path if Python lags

## Suggested near-term tasks (next 2 weeks)

1. Merge this design/plan to `main`
2. Finalize shopping: Blackfly S + lens + Verity Sense
3. Draft stimulus protocol appendix (`docs/PROTOCOL.md`) — even a one-page WIP
4. Scaffold Python package + LSL stubs (Phase 1)
5. Bring up Verity BLE worker (no camera required)

## Success criteria (study-ready)

- One operator can run a full session from a checklist
- All modalities share aligned timestamps within measured tolerance
- Every painting exposure has onset/offset markers and condition labels
- NUC never fires during exposures
- Gaze AOIs are reproducible after calibration within agreed error bound
