# Camera SDKs: quantum-platform

| Field | Value |
|-------|--------|
| Document | `docs/SDK.md` |
| Status | **Research notes** (not an implementation lock) |
| Researched | 2026-09-23 (vendor pages) |
| Related | [ARCHITECTURE.md](ARCHITECTURE.md) §2.1, [HARDWARE.md](HARDWARE.md), [INTEGRATIONS.md](INTEGRATIONS.md) §3 |

Vendor camera SDKs for the owned **Optris PI 450i** and the recommended **Teledyne FLIR Blackfly S BFS-U3-23S3C-C**. Use this for host bring-up and Tauri sidecar packaging. It does **not** reopen Option A ([ARCHITECTURE.md](ARCHITECTURE.md)).

**Source of truth:** vendor product pages, download listings, and SDK docs. Versions seen on 2026-09-23 (OTC SDK ~11.x, Spinnaker / PySpin ~4.4.x) **will drift**. Recheck the links below before installing.

---

## Lab recommendation

| Host role | OS | Why |
|-----------|----|-----|
| **Primary capture workstation** | **Windows 11** (or Ubuntu 22.04 / 24.04) | Full modality set: OTC SDK (thermal) + Spinnaker (RGB) + BLE + gaze |
| UI / dry-run / RGB bring-up | macOS | Tauri shell, Blackfly S, Polar Verity Sense, and software gaze work; **no official Optris Mac SDK** |

macOS operator builds: UI + non-thermal streams are fine. The thermal worker should be mock / disabled / deferred until Optris ships a Mac SDK **or** capture runs on a Windows/Linux host.

---

## 1. Optris PI 450i — OTC SDK (preferred)

Facial IR / perfusion only (no RGB on this body). Typical USB format: **382×288 @ 80 Hz** (also 27 Hz). PI 450i is listed among supported PI/Xi cameras (OTC feature table, May 2026). High-precision mode for PI450 / PI450i is implemented but **not yet fully tested** in that table (⬜).

### Preferred stack: OTC SDK (Optris Thermal Camera SDK)

**Languages:** C++ (native), C#, Python 3. Full API via bindings.

**Python import** ([start developing](https://optris.github.io/otcsdk_downloads/start-developing.html)):

```python
import optris.otcsdk as otc
```

| Platform | Python / notes |
|----------|----------------|
| Linux | Distro `python3` + `python3-numpy` (apt) |
| Windows | Python **≥ 3.9**, NumPy **≥ 2.0.0** |

Optional vendor gRPC middleware is for distributed acquisition. **Not required** for the local sidecar MVP.

### Official OS support (OTC SDK)

| OS | Architectures | Notes |
|----|---------------|-------|
| Windows 10 / 11 | x64 (amd64) | MSVC v143 / Windows SDK 10.0 per GitHub binaries README |
| Linux Ubuntu 22.04 LTS | amd64, arm64 | gcc 11.x; match GLIBC / GLIBCXX |
| Linux Ubuntu 24.04 LTS | amd64, arm64 | gcc 13.x |
| **macOS** | — | **Not listed.** No macOS package in `otcsdk_downloads` or on the OTC product page. **Do not claim Mac thermal capture.** |

### Links

| What | URL |
|------|-----|
| Product page | https://optris.com/software/otc-sdk/ |
| Download / binaries listing | https://github.com/optris/otcsdk_downloads |
| Online docs (example version seen: 11.4.10) | https://optris.github.io/otcsdk_downloads/ |
| Features matrix | https://optris.github.io/otcsdk_downloads/features.html |
| Start developing (Python import) | https://optris.github.io/otcsdk_downloads/start-developing.html |
| Form downloads | https://optris.com/support-service/downloads/ |
| Extra binaries on request | direct-sdk@optris.com |

### Legacy: IRImagerDirect / libirimager

Windows + Linux only. C/C++ (older binding ecosystem). Prefer **OTC SDK** for new work. Mention legacy only as historical / fallback.

| What | URL |
|------|-----|
| Docs | https://sdk.optris.com/libirimager2/html/index.html |
| Downloads | https://sdk.optris.com/downloads/ |

### Implication for this repo

- Full PI 450i capture path: **Windows (lab host) or Linux** with OTC SDK **installed on the host**.
- A bundled Tauri sidecar does **not** replace the host OTC install ([INTEGRATIONS.md](INTEGRATIONS.md) §3).

---

## 2. Blackfly S BFS-U3-23S3C-C — Spinnaker / PySpin

USB3 Vision RGB camera locked in [HARDWARE.md](HARDWARE.md). Requires **Spinnaker SDK** (not FlyCapture2 — Blackfly S is Spinnaker-only per the vendor benefits table).

**Languages:** C++, C, C#, VB.NET, Python (**PySpin**).

Install the **Spinnaker runtime first**, then the **matching** `spinnaker_python-…whl` from **that same SDK build**. Version mismatch → `ImportError` / crashes. Disk: ~700 MB+ for the SDK. SpinView GUI ships with the SDK for bring-up.

### Official OS support (vendor product page, 2026-09-23)

| OS | Notes |
|----|--------|
| Windows 11 (64-bit) | Primary Windows target. Older notes deprecate Win10 / 32-bit in recent releases — prefer Win11 for new installs |
| Linux Ubuntu 20.04 / 22.04 / 24.04 (64-bit) | x64 + ARM64 (Linux) |
| macOS | Product page listed Sequoia, Tahoe; PySpin docs: macOS 14 (Sonoma)+ on x64 and ARM64 |
| Apple Silicon | Spinnaker **4.1.0.172+** targeted Apple Silicon (tested on Sonoma). Intel Macs historically used older branches (e.g. 3.2). Pin a current **4.x** Mac build for Apple Silicon |

### PySpin (docs 4.4.x)

| Platform | Python | Arch |
|----------|--------|------|
| Windows 10 / 11 | 3.10, 3.12 | x64 |
| Ubuntu 20.04 | 3.8 | x64, ARM64, ARMHF |
| Ubuntu 22.04 | 3.10 | x64, ARM64, ARMHF |
| Ubuntu 24.04 | 3.12 | x64, ARM64, ARMHF |
| macOS 14+ | 3.10, 3.12 | x64, ARM64 |

The sidecar contract is Python **3.11+** ([INTEGRATIONS.md](INTEGRATIONS.md) §3). PySpin wheels on Windows / macOS are listed for **3.10 and 3.12**, not 3.11. Prefer an interpreter that has a matching wheel (typically **3.12** on Windows 11 / Ubuntu 24.04 / macOS 14+) rather than assuming 3.11 has a PySpin wheel.

### Links

| What | URL |
|------|-----|
| Spinnaker product page | https://www.teledynevisionsolutions.com/products/spinnaker-sdk/ (regional mirrors e.g. `/en-au/…`) |
| Docs (example 4.4.x) | https://softwareservices.flir.com/spinnaker/latest/ |
| Python getting started | https://softwareservices.flir.com/spinnaker/latest/getting-started/python.html |
| Benefits / OS comparison | https://softwareservices.flir.com/spinnaker/latest/guides/benefits.html |
| Release notes | https://www.teledynevisionsolutions.com/support/support-center/technical-guidance/iis/spinnaker-sdk-release-notes/ |

### Implication for this repo

- RGB path: **Windows, macOS, and Linux** via Spinnaker + PySpin.
- Host must install Spinnaker. A PyInstaller onedir sidecar still typically needs the Spinnaker runtime on `PATH` / the library path (same vendor-SDK host-install pattern as [INTEGRATIONS.md](INTEGRATIONS.md) §3).

---

## 3. Tauri sidecar packaging

Tauri 2 ships native apps for Windows, macOS, and Linux from one React + Rust codebase. The Python sidecar is built/bundled **per OS** (dev: venv; release: PyInstaller onedir as `externalBin` — [INTEGRATIONS.md](INTEGRATIONS.md) §3).

Vendor camera SDKs (**OTC**, **Spinnaker**) still require a **separate host install** even when the sidecar is bundled. `qp doctor` should check for those runtimes.
