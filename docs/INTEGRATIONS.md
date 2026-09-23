# Integrations: quantum-platform

| Field | Value |
|-------|--------|
| Document | `docs/INTEGRATIONS.md` |
| Status | **Contracts locked** |
| Date | 2026-09-23 |
| Related | [ARCHITECTURE.md](ARCHITECTURE.md), [DESIGN.md](DESIGN.md), [PLAN.md](PLAN.md), [EXPERIMENT_CONFIG.md](EXPERIMENT_CONFIG.md), [SDK.md](SDK.md) |

This document is the app-facing contract for sidecar IPC, Python packaging, REDCap registry fields, and Box session paths. It locks the four follow-ups in [ARCHITECTURE.md](ARCHITECTURE.md) §8. It does **not** reopen Option A (Tauri 2 + React + Rust + Python sidecar). Experiment stage schema lives in [EXPERIMENT_CONFIG.md](EXPERIMENT_CONFIG.md) and does **not** change the locks below.

No software is implemented here. Phase 1 scaffolding in [PLAN.md](PLAN.md) should assume these contracts.

---

## 1. Status / decision summary

Locked 23 September 2026:

| Topic | Decision |
|-------|----------|
| Sidecar IPC | JSON-RPC 2.0, newline-delimited JSON on the Python sidecar **stdin/stdout** |
| Python packaging | Dev: Python 3.11+ venv (or uv) + editable install. Release: **PyInstaller onedir** as Tauri `externalBin` |
| REDCap | App field dictionary: `participants` (classic) + `sessions` (repeating). No blob file fields |
| Box | Mirror local `sessions/<participant_id>/<session_id>/` under a study root folder |

---

## 2. Sidecar IPC — JSON-RPC 2.0 over stdio

### Chosen

**JSON-RPC 2.0**, **newline-delimited JSON (NDJSON)** on the Python sidecar’s **stdin/stdout**.

The Rust orchestrator:

1. Spawns the sidecar (dev: `python -m quantum_platform` or `qp`; release: bundled onedir binary).
2. Writes JSON-RPC **requests** to sidecar stdin (session start/stop, calibrate, doctor, status).
3. Reads JSON-RPC **responses** and **notifications/events** from the same stdout channel.

Prefer **one NDJSON stream on stdout**, discriminating request / response / notification per JSON-RPC 2.0. A dedicated stderr or event stream is allowed later if the mixed stream becomes noisy; it is not required for Phase 1.

### Not chosen for MVP

**gRPC.** Revisit only if we need typed high-rate control beyond start / stop / status / events.

### Optional later

The same JSON-RPC over `127.0.0.1` TCP, for debugging without Tauri. Not required for Phase 1.

### Methods (minimum)

| Method | Kind | Purpose |
|--------|------|---------|
| `session.start` | request | Arm a session: participant / session IDs, create the local tree, start workers. Params include `experiment_id` **or** `experiment_path` (see below). |
| `session.stop` | request | Stop capture, flush writers, mark local complete |
| `doctor.run` | request | Device presence / SDK / PATH checks |
| `calibrate.gaze` | request | Start or record gaze look-at calibration |
| `status.get` | request | Snapshot of devices, session, and worker health |

### Notifications (minimum)

| Method | Kind | Purpose |
|--------|------|---------|
| `event.emit` | notification | Protocol / stimulus / marker events (mirrors `events.jsonl` lines) |
| `device.status` | notification | Device connect / disconnect, NUC state, BLE, dropouts |
| `error` | notification | Recoverable or fatal sidecar errors |

### Message sketch

Each line is one JSON-RPC 2.0 object.

Request (orchestrator → sidecar):

```json
{"jsonrpc":"2.0","id":1,"method":"session.start","params":{"participant_id":"P001","session_id":"S001","experiment_id":"painting_session_simplified"}}
```

`session.start` params (additive; method list and transport stay locked):

| Param | Required | Notes |
|-------|----------|--------|
| `participant_id` | yes | Study code |
| `session_id` | yes | Visit id |
| `experiment_id` | one of these | Catalog id (`experiments/<id>.yaml` under `experiments.dir`) |
| `experiment_path` | one of these | Explicit path to a YAML/JSON experiment file ([EXPERIMENT_CONFIG.md](EXPERIMENT_CONFIG.md)) |

Provide **`experiment_id` or `experiment_path`**, not both. The sidecar loads that file, validates `schema_version`, and the stimulus worker plus operator UI share the resolved plan. Missing both may be allowed only for `doctor` / hardware bring-up sessions that are not a protocol run.

Response:

```json
{"jsonrpc":"2.0","id":1,"result":{"ok":true,"session_dir":"sessions/P001/S001"}}
```

Notifications (sidecar → orchestrator):

```json
{"jsonrpc":"2.0","method":"event.emit","params":{"name":"session_start","ts":0}}
```

```json
{"jsonrpc":"2.0","method":"device.status","params":{"device":"verity","state":"connected"}}
```

```json
{"jsonrpc":"2.0","method":"error","params":{"code":"worker_fault","message":"thermal worker exited"}}
```

Param schemas can tighten when Phase 1 stubs land. This method list is the scaffolding contract.

---

## 3. Python packaging

### Dev

- Python **3.11+** virtual environment (**venv** or **uv**).
- Editable install of the sidecar package.
- Run as `python -m quantum_platform`, or the `qp` CLI entry point (`qp session start`, `qp doctor`, `qp calibrate gaze`).

### Release

- **PyInstaller onedir** (directory + executable), bundled as a Tauri `externalBin` sidecar.
- Prefer **onedir over onefile**. Spinnaker, MediaPipe, and other native libraries unpack poorly from a single-file archive (slow start, temp-dir races, missing `.so` / `.dll` next to the binary).

### Not chosen for MVP

- **PyOxidizer** — not the primary path.
- **conda-pack** — not the primary path.

Either may be a fallback if PyInstaller cannot ship a required native SDK.

### Vendor SDKs on the lab host

Even with a bundled sidecar, **Spinnaker** and **Optris** (and similar vendor SDKs) may still need **separate installers and/or PATH** on the capture host. The sidecar binary does not replace those vendor runtimes for MVP.

OS support, download links, Python imports, and the Mac thermal gap: [SDK.md](SDK.md) (researched 2026-09-23; vendor pages remain the source of truth).

- **Optris OTC SDK** (PI 450i): Windows and Linux only. **No official macOS SDK.** Full thermal capture needs a Windows 11 or Ubuntu host.
- **Spinnaker / PySpin** (Blackfly S): Windows, macOS, and Linux. Install the runtime first, then the **matching** `spinnaker_python` wheel from that SDK build.

---

## 4. REDCap project fields (app contract)

This is the **integration contract the orchestrator will expect**. Mapping these names onto a live REDCap project can happen later. Field names below are the defaults; they are overridable in config YAML later.

REDCap holds participant codes, eligibility, consent, and session registry — **not** raw video or thermal blobs ([ARCHITECTURE.md](ARCHITECTURE.md) §5).

### Instrument A — `participants` (classic / non-repeating)

| Field | Type / values | Notes |
|-------|---------------|-------|
| `record_id` | text | Study participant code. **This is `participant_id`** in local and Box session paths. |
| `eligible` | yes/no | Screening result |
| `consent_status` | `not_consented` \| `consented` \| `withdrawn` | |
| `consent_date` | date | |
| `notes` | notes | Free-text coordinator / operator notes |

### Instrument B — `sessions` (repeating instrument on the participant record)

| Field | Type / values | Notes |
|-------|---------------|-------|
| `session_id` | text | Unique per visit; used in local and Box paths |
| `session_date` | date | Calendar date of the visit |
| `session_datetime` | datetime | Optional finer timestamp |
| `session_status` | `planned` \| `in_progress` \| `complete` \| `aborted` | |
| `operator` | text | Operator identifier |
| `protocol_version` | text | Protocol / software protocol version |
| `box_folder_path` | text | Link to blob location (path); **not the bytes** |
| `box_folder_id` | text | Link to blob location (Box folder ID); **not the bytes** |
| `local_complete` | yes/no | Local session write finished |
| `upload_status` | `pending` \| `uploaded` \| `failed` | Box upload state |
| `qc_ok` | yes/no or unchecked | Session QC flag |
| `session_notes` | notes | Per-visit notes |

Either `box_folder_path` or `box_folder_id` (or both) may be populated. They point at the session folder, not at individual stream files.

### Rules

- **No file fields** for RGB, thermal, or other session blobs in REDCap.
- Ratings / behavioral CRFs are **optional later instruments**. A stub `ratings` repeating form is out of scope for this lock; add it later without changing `participants` / `sessions`.
- Config stores REDCap **base URL**, **API token**, and **project id** (see §6). The field names above are the defaults the orchestrator uses.

---

## 5. Box folder taxonomy

### Chosen

Mirror the local session tree under a study root folder in Box:

```
QuantumPlatform/                    ← Box folder (ID in app config)
  sessions/
    <participant_id>/
      <session_id>/
        meta.yaml
        events.jsonl
        calibration/
        streams/...
        derived/...
```

- Upload **only after** the local write succeeds.
- Same **relative paths** as local `sessions/<participant_id>/<session_id>/`.
- Local disk remains the source of truth until upload is confirmed.

### Deferred

Multi-site prefixes (`site/<code>/...`) are **not** needed for the single-lab MVP. Revisit if a second site is added.

### Config

`box.root_folder_id` (or path) plus OAuth or JWT as appropriate for the Box connector the app will use later (see §6). Auth flavor is not locked here.

---

## 6. Config keys (sketch)

YAML (or equivalent) later. Names below are the contract sketch, not an implemented schema.

```yaml
sidecar:
  command: python          # or path to the PyInstaller onedir binary
  args: ["-m", "quantum_platform"]
  ipc: jsonrpc-ndjson-stdio
  # optional later (debug without Tauri):
  # tcp_host: 127.0.0.1
  # tcp_port: 8700

redcap:
  base_url: https://redcap.example.edu/api/
  api_token: ${REDCAP_API_TOKEN}
  project_id: 12345
  # field-name overrides (defaults = names in §4)
  fields:
    record_id: record_id
    session_id: session_id

box:
  root_folder_id: "<QuantumPlatform folder ID>"
  # or: root_folder_path: /QuantumPlatform
  # auth: oauth | jwt — as required by the later Box connector

# optional — experiment catalog ([EXPERIMENT_CONFIG.md](EXPERIMENT_CONFIG.md))
experiments:
  dir: experiments/                 # repo- or config-relative YAML catalog
  # default_id: painting_session_simplified
```

Secrets (API tokens, Box credentials) stay in environment variables or the OS secret store, not in committed YAML.

---

## 7. What this does not lock

- Option A vs B–E (already locked in [ARCHITECTURE.md](ARCHITECTURE.md)).
- Investigator protocol items ([PROTOCOL.md](PROTOCOL.md) §13).
- Experiment stage schema, reminder text, and block/randomization hooks ([EXPERIMENT_CONFIG.md](EXPERIMENT_CONFIG.md)). Adding `experiment_id` / `experiment_path` on `session.start` and optional `experiments.*` does **not** reopen IPC transport, packaging, REDCap fields, or Box taxonomy.
- Exact JSON-RPC param schemas (tighten at Phase 1 stubs).
- Live REDCap project creation or field-map onto an existing project.
- Box auth flavor (OAuth vs JWT) and the concrete connector implementation.
