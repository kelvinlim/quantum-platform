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
| Heart rate / PPG | Polar Verity Sense (arm-worn) | BLE PPG | Heart rate and pulse timing (not ECG R-peaks) |
| Gaze on painting | Derived from RGB + geometry | same as RGB | Coarse AOIs on canvas (center / L/R / U/D) |
| Events / stimulus | Software controller | event markers | Painting onset/offset, fixation, ISI, NUC triggers, responses |
| Optional audio | Mic | as needed | Later; latency must be characterized separately |

### Non-goals for MVP

- Tobii-grade gaze maps
- ECG-quality R-peak analysis (Verity is PPG)
- Replacing PI 450i with an integrated FLIR A50/A70 (optional future path only)

## 3. Viewing geometry (baseline)

For a **70 cm × 90 cm** painting (from prior hardware notes):

- Subject-to-painting ≈ **1.5 m** (~26° × 33° visual angle)
- RGB camera-to-face ≈ **0.8–1.0 m** (face fills ~30–50% of FOV)
- Painting center height ≈ **145–150 cm**
- RGB pedestal ≈ **95–105 cm**, tilted up ~12–15°
- Dual-mount RGB + PI 450i on a rigid rail/PETG frame so RGB↔thermal calibration stays stable

## 4. Architecture

Central **host application** with **one capture worker per modality**, plus a **stimulus / event controller**.

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

- Rigid co-mount; dual-spectrum calibration target (heated/high-emissivity preferred).
- OpenCV: `calibrateCamera`, `stereoCalibrate` / planar `findHomography` at fixed subject distance.
- Map RGB landmarks into thermal coordinates; compute ROI mean/std/max temperature.

## 5. Software stack (preferred)

| Layer | Choice |
|-------|--------|
| Language | Python 3.11+ for MVP workers; C++/Qt later if needed for Optris path |
| Thermal SDK | Optris OTC (gRPC) and/or classic `libirimager` / PIX Connect IPC |
| RGB SDK | Spinnaker / PySpin |
| Vision | OpenCV, MediaPipe (or OpenFace) |
| HR | Polar BLE (GATT); keep hardware timestamps + receive timestamps |
| Sync | pylsl / LSL |
| Config | YAML/JSON session + hardware profiles |
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

## 6. Event model (minimum)

Markers must include at least:

- `session_start` / `session_end`
- `calibration_start` / `calibration_end` (gaze, RGB–thermal)
- `fixation_onset` / `fixation_offset`
- `stimulus_onset` / `stimulus_offset` (painting id, condition: quantum|standard)
- `isi_onset` / `isi_offset`
- `nuc_trigger`
- optional behavioral responses / ratings

## 7. Open investigator decisions

Documented here so they are not lost:

1. Operational definition of **quantum** vs **standard** paintings
2. Physical canvas vs screen reproduction
3. Trial count, duration, randomization / counterbalancing
4. Fixation and ISI lengths; repeat exposures
5. Whether ratings / behavioral responses are collected
6. AOI definitions per painting
7. Privacy / consent / identifiable video retention policy

## 8. Safety and ethics (engineering notes)

- Store participant IDs as study codes, not names, in filenames when possible.
- Face video and thermal are identifiable biometric data — encrypt at rest if required by IRB.
- Do not stream identifiable video off-lab without explicit protocol approval.
