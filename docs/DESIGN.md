# Design: quantum-platform

## 1. Goal

Build a desktop multimodal capture system for a viewing study in which participants look at physical (or displayed) paintings under standardized geometry while synchronized streams record autonomic and attentional signals.

Primary research contrast (investigator-defined; not yet finalized in this repo):

- **Quantum paintings** vs **standard paintings**

## 2. Modalities

| Stream | Device | Rate (target) | Role |
|--------|--------|---------------|------|
| Facial IR / perfusion | Optris PI 450i (owned) | 80 Hz (or 27 Hz) | Skin-temperature ROIs (nasal tip/alar, nostrils, inner canthi, periorbita, forehead) |
| Facial RGB / expression | Teledyne FLIR Blackfly S BFS-U3-23S3C-C (recommended) | 60–120 Hz | Landmarks, FACS/AUs, blinks, micro-motion, iris for budget gaze |
| Heart rate / PPG | Polar Verity Sense (upper arm) | BLE PPG | Heart rate and pulse timing (not ECG R-peaks); keep clear of chair arms |
| Gaze on painting | Derived from RGB + geometry | same as RGB | Coarse AOIs on canvas (center / L/R / U/D) |
| Events / stimulus | Software controller | event markers | Painting onset/offset, fixation, ISI, NUC triggers, responses |
| Optional audio | Mic | as needed | Later; latency must be characterized separately |

### Non-goals for MVP

- Tobii-grade gaze maps
- ECG-quality R-peak analysis (Verity is PPG)
- Replacing PI 450i with an integrated FLIR A50/A70 (optional future path only)

## 3. Viewing geometry (two stations)

Two marked camera geometries — do **not** cover both phases from one spot. Operator procedure, QR mounts, and figures: [PROTOCOL.md](PROTOCOL.md) §4 and [HARDWARE.md](HARDWARE.md).

**Station A — seated viewing** (`seated_view`; [lab-layout.png](figures/lab-layout.png), viewing station only):

- Subject **seated** in a comfortable, **fixed / locked chair**; subject-to-painting ≈ **1.5 m** (~26° × 33° visual angle)
- Seat height adjusted so **eye height ≈ painting center (≈145–150 cm)**
- Dual bar on a tripod/pedestal **between** subject and canvas; camera-to-face ≈ **0.8–1.0 m**; pedestal ≈ **95–105 cm**, tilted up ~12–15°
- Chin rest not required unless gaze calibration fails

**Station B — close interaction** (`close_interact`; [lab-layout-close-interact.png](figures/lab-layout-close-interact.png)):

- Subject **stands or leans** close to the canvas with hands near/over the painting (last pre-VR capture)
- Same PI 450i + Blackfly dual bar **behind / above** the painting, peeking over the top, look-down ≈ **30–45°**, camera-to-face ≈ **0.4–0.8 m**
- Wall plate or easel-back + short rigid riser (no floppy boom). SKU and exact angle **TBD**

Both stations: RGB + PI 450i stay on **one rigid dual bar** with a QR plate; matched clamps stay on the receivers so the bar moves without loosening cameras (preserves RGB↔thermal calibration). Tag events with `seated_view` or `close_interact`.

## 4. Architecture

Desktop shell (locked Sep 2026): **Tauri 2 + React + Rust orchestrator + Python capture sidecar** — **Option A**. Decision, diagram, REDCap/Box roles, and alternatives B–E: [ARCHITECTURE.md](ARCHITECTURE.md). Operator UI and the stimulus worker share one experiment config: [EXPERIMENT_CONFIG.md](EXPERIMENT_CONFIG.md).

Central **host application** with **one capture worker per modality**, plus a **stimulus / event controller** that executes **config-driven stages** ([EXPERIMENT_CONFIG.md](EXPERIMENT_CONFIG.md)) rather than a hard-coded trial loop.

```
┌─────────────────────────────────────────────────────────┐
│                     Host / Session UI                    │
│         (start/stop, participant ID, calibration)        │
└───────────────┬─────────────────────────────────────────┘
                │
     ┌──────────┼──────────┬──────────────┬──────────────┐
     ▼          ▼          ▼              ▼              ▼
 Thermal    RGB face    Verity BLE    Gaze worker    Stimulus
 worker     worker      worker        (from RGB)     / events
     │          │          │              │              │
     └──────────┴──────────┴──────────────┴──────────────┘
                              │
                              ▼
                    Lab Streaming Layer (LSL)
                    + local ring buffers
                              │
                              ▼
                    Session store (raw + markers)
```

### Synchronization

- Shared **monotonic clock** (`time.monotonic_ns()` / `steady_clock`).
- Timestamp every sample **on arrival** in its capture thread.
- **Do not** blocking frame-lock cameras with different rates.
- Pair RGB↔thermal by **nearest timestamp** (e.g. ±6.25 ms at 80 Hz thermal).
- Prefer **Lab Streaming Layer (LSL)** for multimodal transport and clock sync.
- Measure BLE and audio latency empirically; do not assume constants.

### Thermal NUC / shutter

- PI 450i NUC can interrupt frames for ~200–500 ms.
- Prefer **manual shutter** when supported.
- Trigger calibration only during **fixation / ISI**, never during painting exposure.

### Budget gaze (no dedicated eye tracker)

1. Face mesh + iris (MediaPipe Face Mesh/Iris or OpenFace) on RGB frames.
2. Head pose via `solvePnP`.
3. Gaze ray → intersect known **painting plane** (canvas corners in room coords).
4. Per-session **look-at calibration** (5–9 marks on/around canvas).
5. Emit painting-plane `(x, y)` on LSL (e.g. stream name `GazePainting`).

Expect **coarse AOIs** (a few degrees / centimeters on canvas), not fine brushstroke maps.

### RGB ↔ thermal fusion

- Rigid dual bar; dual-spectrum calibration target (heated/high-emissivity preferred). Do not loosen cameras on the bar when docking Station A ↔ B.
- OpenCV: `calibrateCamera`, `stereoCalibrate` / planar `findHomography` at fixed subject distance (Station A, ≈0.8–1.0 m).
- After a clean QR dock, visual RGB–thermal overlap may suffice; full recalibration if the cameras moved relative to each other or the bar was bumped hard ([PROTOCOL.md](PROTOCOL.md) §4.1.3).
- Map RGB landmarks into thermal coordinates; compute ROI mean/std/max temperature. Drop frames where landmarks fail (close-interaction occlusion).

## 5. Software stack (preferred)

| Layer | Choice |
|-------|--------|
| Language | Python 3.11+ sidecar workers; desktop shell is Tauri/React/Rust ([ARCHITECTURE.md](ARCHITECTURE.md)). C++ later only if the Optris path requires it |
| Thermal SDK | Optris **OTC** preferred (Windows / Linux only; no official macOS); legacy `libirimager` as fallback — [SDK.md](SDK.md) |
| RGB SDK | Spinnaker / PySpin (Windows / macOS / Linux) — [SDK.md](SDK.md) |
| Vision | OpenCV, MediaPipe (or OpenFace) |
| HR | Polar BLE (GATT); keep hardware timestamps + receive timestamps |
| Sync | pylsl / LSL |
| Config | YAML/JSON session + hardware profiles; experiment stages in `experiments/<name>.yaml` ([EXPERIMENT_CONFIG.md](EXPERIMENT_CONFIG.md)) |
| Storage | Per-session directory: raw streams or chunked recordings, `events.jsonl`, `meta.yaml`, calibration artifacts |

### Suggested session layout

```
sessions/<participant_id>/<session_id>/
  meta.yaml
  events.jsonl
  calibration/
  streams/
    thermal/ ...
    rgb/ ...
    verity/ ...
    gaze/ ...
  derived/   # optional online or offline features
```

REDCap registry fields and Box upload paths: [INTEGRATIONS.md](INTEGRATIONS.md) (same relative tree as local `sessions/<participant_id>/<session_id>/`).

## 6. Event model (minimum)

Markers must include at least:

- `session_start` / `session_end`
- `calibration_start` / `calibration_end` (gaze, RGB–thermal)
- `fixation_onset` / `fixation_offset`
- `stimulus_onset` / `stimulus_offset` (painting id, condition: quantum|standard, geometry: seated_view|close_interact)
- optional `geometry_change` (from/to station; post-move QC path)
- `isi_onset` / `isi_offset`
- `nuc_trigger`
- optional behavioral responses / ratings
- optional operator phase control: `operator_advance` (Continue / Next phase), `operator_end_phase` (End phase) — [EXPERIMENT_CONFIG.md](EXPERIMENT_CONFIG.md) §4.3.1 / §5.2

Stage enter/exit in the experiment config ([EXPERIMENT_CONFIG.md](EXPERIMENT_CONFIG.md) §4.11) **maps onto these names**. The stimulus worker emits them from the loaded YAML; do not keep a second, hard-coded marker list in the trial loop.

## 7. Open investigator decisions

Documented here so they are not lost:

1. Operational definition of **quantum** vs **standard** paintings
2. Physical canvas vs screen reproduction
3. Trial count, duration, randomization / counterbalancing
4. Fixation and ISI lengths; repeat exposures
5. Whether ratings / behavioral responses are collected
6. AOI definitions per painting
7. Privacy / consent / identifiable video retention policy
8. Station B SKU (wall vs easel), exact look-down angle, one movable bar vs spare bar
9. Close-interaction task / timing and the following VR break (PROTOCOL §13)

## 8. Safety and ethics (engineering notes)

- Store participant IDs as study codes, not names, in filenames when possible.
- Face video and thermal are identifiable biometric data — encrypt at rest if required by IRB.
- Do not stream identifiable video off-lab without explicit protocol approval.
