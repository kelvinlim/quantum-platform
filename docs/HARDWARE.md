# Hardware

Two marked camera stations — do not cover both phases from one spot. See [PROTOCOL.md](PROTOCOL.md) §4.

- **Station A (seated viewing, `seated_view`):** [lab-layout.png](figures/lab-layout.png) — dual IR+RGB bar on a tripod/pedestal **between** subject and canvas, ≈0.8–1.0 m from the face, tilted up. Viewing station only.
- **Station B (close interaction, `close_interact`):** [lab-layout-close-interact.png](figures/lab-layout-close-interact.png) — same bar **behind / above** the painting, peeking over the top, looking down at the face (≈30–45°, ≈0.4–0.8 m).

Verify floor marks (both subject positions and both receivers) and eye-height alignment in the actual room. Photograph each locked station once per site.

## Owned

| Item | Notes |
|------|-------|
| Optris PI 450i | 382×288 LWIR, ~80 Hz, USB 2.0; facial IR only (no RGB). Prefer manual NUC between stimuli. SDK: **OTC** (Windows / Linux only; **no official macOS**). See [SDK.md](SDK.md). IR lens: choose for **face sharpness** at the Station B working distance (≈0.4–0.8 m); the same lens stays on the body at Station A. |

## Recommended to purchase

| Item | Role | Notes |
|------|------|-------|
| Teledyne FLIR Blackfly S **BFS-U3-23S3C-C** | Facial RGB | Sony IMX392, global shutter, up to ~163 fps, USB3, Spinnaker/PySpin (Windows / macOS / Linux). ~**$421** body (Teledyne / Edmund). Lead time often ≤ 4 weeks. SDK notes: [SDK.md](SDK.md). |
| C-mount lens ~6–8 mm | RGB FOV | Match sensor class; face 30–50% of frame at Station A (0.8–1.0 m). At Station B the face fills more of the frame; do not swap the lens mid-session. Edmund Optics / Computar. |
| Polar **Verity Sense** | Upper-arm PPG / HR | Preferred over H10 chest strap for seated viewing comfort; place on the upper arm, clear of chair arms. |
| Rigid dual bar | RGB + PI 450i | Aluminum rail / Arca-Swiss / PETG dual bay. Cameras stay tight on this bar for the whole session (preserves RGB↔thermal calibration). |
| Dual-station QR kit | Move the bar without tools | One QR plate **on the bar**; matched clamps **on Station A and Station B** (Arca-Swiss / Manfrotto RC2-style or equivalent). See below. |
| Station A receiver | Seated frontal mount | Tripod / pedestal ≈95–105 cm, floor-marked; QR clamp; tilt up ~12–15°. |
| Station B receiver | Close look-down mount | Wall plate or easel-back / stand behind the painting; short **rigid** riser to peek over the canvas top; QR clamp. No floppy boom. SKU **TBD**. Pilot may use a second tripod until the angle is locked. |
| Dual-spectrum cal target | RGB–thermal | Heated aluminum/mask ~35–40 °C preferred; halogen-lit glossy checkerboard as quick alt. |

## Dual-bar mounts (easy and stable when moving)

Recommended default — one movable bar, two fixed receivers:

1. Assemble PI 450i + Blackfly on **one rigid dual bar**. Do not loosen camera-to-bar bolts when changing stations.
2. Leave a **QR plate on the bar**. Leave a matched clamp on each station.
3. Mid-session move is dock-only: release at A, carry the bar as one unit, lock at B (PROTOCOL §4.1.3). No tools.
4. Station B riser is short and rigid so the bar peeks over the canvas top. Confirm clearance vs painting and the subject’s head.
5. USB (and any power) gets a **service loop** at each receiver so docking does not yank cables.
6. Floor-mark both receivers and both subject positions. Recheck QR lock after every dock.

**Post-move QC.** If the bar stayed rigid, a quick visual RGB–thermal overlap is enough. If the cameras moved relative to each other or the bar was bumped hard, full RGB–thermal recalibration is required. Log which path was taken.

A second spare dual bar (pre-calibrated) is an alternative, not the default (**TBD**).

## Alternatives considered

| Item | When to choose |
|------|----------------|
| Imaging Source DFK 33UX273 | Cheaper RGB, still high fps |
| Basler ace acA1920-155uc | Prefer Basler ecosystem (~$650–750) |
| Basler dart daA1600-60uc | Budget; only 60 fps |
| Polar H10 | Better ECG-like signal; chest strap less ideal for viewing comfort |
| FLIR A50/A70 | Integrated visual+thermal; ~30 Hz, much more expensive — only if replacing PI 450i |
| Dedicated eye tracker (Tobii, Pupil Labs, etc.) | If coarse software gaze proves insufficient |
| Second tripod as Station B | Pilot only; prefer wall / easel hard mount once look-down is locked |
| Second spare dual bar | If QR moves prove too slow or risky for calibration; extra RGB–thermal cal burden |

## Not required for MVP

- Dedicated eye tracker (budget gaze from face RGB)
- Cooled MWIR research cameras
- A second camera pair (default is one bar moved between stations)
