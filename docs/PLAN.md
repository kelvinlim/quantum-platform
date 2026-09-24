# Plan: quantum-platform

Phased roadmap. Docs-first repo; software follows.

## Phase 0 — Docs and decisions

- [x] Capture hardware notes from prior Gemini design discussion
- [x] Lock preferred HR: **Polar Verity Sense** (arm)
- [x] Recommend RGB: **Blackfly S BFS-U3-23S3C-C** (~$421 body)
- [x] Budget gaze approach: face RGB + MediaPipe/OpenFace + painting-plane intersection
- [x] Protocol outline drafted (`docs/PROTOCOL.md`) — **WIP**; trial flow, provisional timing, measures, event markers, operator checklist
- [x] Dual camera stations documented (PROTOCOL v0.2): Station A `seated_view` ([lab-layout.png](docs/figures/lab-layout.png)); Station B `close_interact` ([lab-layout-close-interact.png](docs/figures/lab-layout-close-interact.png)); QR move of one rigid dual bar
- [x] Lock desktop shell: **Option A** — Tauri 2 + React + Rust shell + Python capture sidecar ([ARCHITECTURE.md](ARCHITECTURE.md), Sep 2026). Alternatives B–E documented, not chosen.
- [x] Lock architecture follow-ups: JSON-RPC 2.0 stdio, PyInstaller onedir (release), REDCap/Box contracts ([INTEGRATIONS.md](INTEGRATIONS.md), Sep 2026)
- [x] Experiment configurator design: declarative stages, collect flags, operator reminders ([EXPERIMENT_CONFIG.md](EXPERIMENT_CONFIG.md), Sep 2026)
- [ ] Investigator: operational definition of **quantum** vs **standard** paintings (not invented in the protocol draft)
- [ ] Investigator remaining decisions (see `docs/PROTOCOL.md` §13), including:
  - Stimulus set size and catalog
  - Physical canvas vs screen
  - Exact fixation / exposure / ISI durations (draft defaults: 2.5 / 25 / 8 s)
  - Ratings / behavioral responses (whether, which, when)
  - Per-painting AOIs; HR/thermal baseline windows
  - Sample size, eligibility, confirmatory vs exploratory hypotheses
  - Station B SKU / look-down angle; close-interaction and VR timing
- [ ] Order RGB camera + C-mount lens; confirm Verity Sense kit
- [ ] Confirm IRB / data-retention constraints for face/thermal video

**Exit:** Design + plan merged; shopping list agreed; protocol outline drafted (WIP). Investigator decisions in `docs/PROTOCOL.md` §13 still block a confirmatory run.

## Phase 1 — Repo scaffolding (MVP skeleton) (software landed)

**Assume Option A** ([ARCHITECTURE.md](ARCHITECTURE.md)): Tauri 2 + React operator UI, Rust session orchestrator, Python capture sidecar. Do not scaffold a Python-only GUI or Electron host.

**Assume locked integrations** ([INTEGRATIONS.md](INTEGRATIONS.md)): JSON-RPC 2.0 NDJSON over sidecar stdio; REDCap field dictionary and Box path taxonomy as specified there. Release packaging (**PyInstaller onedir** as Tauri `externalBin`) can wait until a hardware worker lands; Phase 1 runs the sidecar from a venv (`python -m quantum_platform` / `qp`).

- [x] Tauri 2 + React operator shell (session start/stop, participant code, device status) — `app/`
- [x] Rust orchestrator stubs: sidecar spawn/lifecycle, **JSON-RPC 2.0 NDJSON over stdio**, session directory, command/event relay
- [x] Python sidecar package (`src/quantum_platform/`); run as `python -m quantum_platform` or `qp`
- [x] Config schemas for hardware profiles, session metadata, and `redcap.*` / `box.*` / `sidecar.*` keys — `config/default.yaml`
- [x] **Experiment configurator** ([EXPERIMENT_CONFIG.md](EXPERIMENT_CONFIG.md)): `schema_version: 1` YAML schema + loader/validator; operator **stage UI**; sidecar runner consumes the **same YAML**. Button presses log `operator_advance` / `operator_end_phase`. Example: `experiments/painting_session_simplified.yaml`
- [x] LSL stream name conventions (recorded in `meta.yaml`) + `events.jsonl` writer
- [x] Stub / mock workers: `thermal`, `rgb`, `verity`, `gaze`, plus a config-driven stage runner (stimulus). Vendor SDK backends raise `NotImplementedError` until Phase 2
- [x] Sidecar CLI: `qp run --auto-press`, `qp session start`, `qp calibrate gaze`, `qp doctor`
- [x] Unit tests for config validation, stage transitions, JSON-RPC framing, timestamp pairing, and session directory output
- [x] REDCap/Box **stubs** only (INTEGRATIONS.md contracts; no network)

**Exit:** Dry-run session from the Tauri UI (or `qp run --mock --auto-press`) follows the experiment config stages and produces aligned fake streams + markers on disk. See [DEV.md](DEV.md). Real capture, REDCap/Box I/O, and PyInstaller `externalBin` remain later phases.

## Phase 2 — Hardware bring-up

1. **RGB** — Spinnaker capture at 60–120 Hz with monotonic timestamps; lens FOV check at 0.9 m
2. **Thermal** — Optris SDK path; raw uint16 + verified °C conversion; manual NUC API
3. **Verity** — BLE connect, PPG/HR samples, dual timestamps, band-side metadata
4. **Co-mount** — Print/assemble dual bay; RGB–thermal calibration routine
5. **Gaze** — MediaPipe iris → painting-plane; 5–9 point look-at calibration UI

**Exit:** Live multi-stream session (even without paintings) with NUC only in ISI.

## Phase 3 — Stimulus controller

- **Config-driven** stages from the experiment YAML ([EXPERIMENT_CONFIG.md](EXPERIMENT_CONFIG.md)); do not hard-code fixation → stimulus → ISI
- Condition tags: `quantum` | `standard` (and painting IDs) as opaque labels from the catalog / config
- Optional on-screen instructions / rating scales if protocol requires (REDCap ratings stay in REDCap; reminders may point there)
- Enforce “no NUC during stimulus” from stage `constraints`

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
