# Plan: quantum-platform

Phased roadmap. Docs-first repo; software follows.

## Phase 0 — Docs and decisions (current)

- [x] Capture hardware notes from prior Gemini design discussion
- [x] Lock preferred HR: **Polar Verity Sense** (arm)
- [x] Recommend RGB: **Blackfly S BFS-U3-23S3C-C** (~$421 body)
- [x] Budget gaze approach: face RGB + MediaPipe/OpenFace + painting-plane intersection
- [x] Protocol outline drafted (`docs/PROTOCOL.md`) — **WIP**; trial flow, provisional timing, measures, event markers, operator checklist
- [x] Lock desktop shell: **Option A** — Tauri 2 + React + Rust shell + Python capture sidecar ([ARCHITECTURE.md](ARCHITECTURE.md), Sep 2026). Alternatives B–E documented, not chosen.
- [ ] Investigator: operational definition of **quantum** vs **standard** paintings (not invented in the protocol draft)
- [ ] Investigator remaining decisions (see `docs/PROTOCOL.md` §13), including:
  - Stimulus set size and catalog
  - Physical canvas vs screen
  - Exact fixation / exposure / ISI durations (draft defaults: 2.5 / 25 / 8 s)
  - Ratings / behavioral responses (whether, which, when)
  - Per-painting AOIs; HR/thermal baseline windows
  - Sample size, eligibility, confirmatory vs exploratory hypotheses
- [ ] Order RGB camera + C-mount lens; confirm Verity Sense kit
- [ ] Confirm IRB / data-retention constraints for face/thermal video

**Exit:** Design + plan merged; shopping list agreed; protocol outline drafted (WIP). Investigator decisions in `docs/PROTOCOL.md` §13 still block a confirmatory run.

## Phase 1 — Repo scaffolding (MVP skeleton)

**Assume Option A** ([ARCHITECTURE.md](ARCHITECTURE.md)): Tauri 2 + React operator UI, Rust session orchestrator, Python capture sidecar. Do not scaffold a Python-only GUI or Electron host.

- Tauri 2 + React operator shell (session start/stop, participant code, device status)
- Rust orchestrator stubs: sidecar spawn/lifecycle, session directory, command/event relay
- Python sidecar package (`src/quantum_platform/` or equivalent)
- Config schemas for hardware profiles and session metadata
- LSL stream name conventions + `events.jsonl` writer
- Stub workers in the sidecar: `thermal`, `rgb`, `verity`, `gaze`, `stimulus` (simulate clocks if hardware absent)
- Sidecar CLI still useful for lab bring-up: `qp session start|stop`, `qp calibrate gaze`, `qp doctor` (device presence checks)
- Unit tests for timestamp pairing and event log format

**Exit:** Dry-run session from the Tauri UI (or sidecar CLI) produces aligned fake streams + markers on disk.

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
3. Investigator: close `docs/PROTOCOL.md` §13 decisions (definition, catalog, timing, ratings)
4. Scaffold Tauri 2 + React + Rust shell + Python sidecar stubs (Phase 1)
5. Bring up Verity BLE worker (no camera required)

## Success criteria (study-ready)

- One operator can run a full session from a checklist
- All modalities share aligned timestamps within measured tolerance
- Every painting exposure has onset/offset markers and condition labels
- NUC never fires during exposures
- Gaze AOIs are reproducible after calibration within agreed error bound
