# Hardware

Provisional room placement (painting, cameras, subject) is shown in [lab-layout.png](figures/lab-layout.png).

## Owned

| Item | Notes |
|------|-------|
| Optris PI 450i | 382×288 LWIR, ~80 Hz, USB 2.0; facial IR only (no RGB). Prefer manual NUC between stimuli. |

## Recommended to purchase

| Item | Role | Notes |
|------|------|-------|
| Teledyne FLIR Blackfly S **BFS-U3-23S3C-C** | Facial RGB | Sony IMX392, global shutter, up to ~163 fps, USB3, Spinnaker/PySpin. ~**$421** body (Teledyne / Edmund). Lead time often ≤ 4 weeks. |
| C-mount lens ~6–8 mm | RGB FOV | Match sensor class; face 30–50% of frame at 0.8–1.0 m. Edmund Optics / Computar. |
| Polar **Verity Sense** | Arm PPG / HR | Preferred over H10 chest strap for painting viewing comfort. |
| Rigid dual mount | RGB + PI 450i | Aluminum rail / Arca-Swiss / PETG dual bay; maintain calibration. |
| Dual-spectrum cal target | RGB–thermal | Heated aluminum/mask ~35–40 °C preferred; halogen-lit glossy checkerboard as quick alt. |

## Alternatives considered

| Item | When to choose |
|------|----------------|
| Imaging Source DFK 33UX273 | Cheaper RGB, still high fps |
| Basler ace acA1920-155uc | Prefer Basler ecosystem (~$650–750) |
| Basler dart daA1600-60uc | Budget; only 60 fps |
| Polar H10 | Better ECG-like signal; chest strap less ideal for viewing comfort |
| FLIR A50/A70 | Integrated visual+thermal; ~30 Hz, much more expensive — only if replacing PI 450i |
| Dedicated eye tracker (Tobii, Pupil Labs, etc.) | If coarse software gaze proves insufficient |

## Not required for MVP

- Dedicated eye tracker (budget gaze from face RGB)
- Cooled MWIR research cameras
