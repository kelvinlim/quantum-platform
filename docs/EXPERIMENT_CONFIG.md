# Experiment configurator: quantum-platform

| Field | Value |
|-------|--------|
| Document | `docs/EXPERIMENT_CONFIG.md` |
| Status | **Design sketch** (`schema_version: 1`); Phase 1 implements the loader, validator, and runner |
| Date | 2026-09-23 |
| Related | [DESIGN.md](DESIGN.md), [PLAN.md](PLAN.md), [PROTOCOL.md](PROTOCOL.md), [ARCHITECTURE.md](ARCHITECTURE.md), [INTEGRATIONS.md](INTEGRATIONS.md) |

Declarative experiment files so a session is a **guided runbook**, not a hard-coded trial loop. One YAML (JSON is acceptable) is the single source of truth for **stages**, **what to collect**, **how long**, **operator reminders**, **checklists**, and **event markers**.

This is a design sketch. No loader, validator, or UI is implemented here. Phase 1 scaffolding in [PLAN.md](PLAN.md) should assume this model.

---

## 1. Why

Kelvin wants an experiment configurator that:

- Specifies the **stages** of a session (setup → calibration → baseline → trials → closeout).
- For each stage: **what should be collected**, and **for how long**.
- Puts **on-screen reminders** in front of the experimenter (checklists, “do NUC now”, “do not talk”, “start painting”, Phase labels).
- Lets a stage **require a button press** to continue to the next phase, or to **end the current phase**, so the experimenter — not only the timer — controls complicated transitions.
- Helps prevent mistakes in complicated runs (NUC during exposure, talking during a trial, skipped calibration).
- Fits Phase 1 scaffolding: the operator UI is **driven by config**, not a hard-coded fixation → exposure → ISI loop.

[PROTOCOL.md](PROTOCOL.md) stays the investigator-facing protocol. The experiment YAML is the **machine-readable subset** for a given run: timings, stream enablement, operator prompts, and markers that the software can execute.

---

## 2. Goals

- **Declarative definition.** YAML preferred; JSON OK. Files live at `experiments/<name>.yaml` (or an equivalent catalog path).
- **Single source of truth** for timing, modalities, operator prompts, and event markers.
- **Guided operator UI:** current stage, countdown, next actions, enabled streams, and hard constraints (e.g. no NUC during exposure).
- **Button-driven phase control.** A stage can require a press to go to the next phase, a press to end the current phase, or neither (timer-only). Checklist gates block the button until checked.
- **Same config** consumed by the Python stimulus worker and the Tauri/React operator UI, via the Rust orchestrator and JSON-RPC ([INTEGRATIONS.md](INTEGRATIONS.md) §2).
- **Versioned schema.** Every file declares `schema_version: 1`. Unknown versions fail validation.

---

## 3. Relation to existing docs

| Document | Role vs this file |
|----------|-------------------|
| [PROTOCOL.md](PROTOCOL.md) | Investigator protocol: scientific decisions, eligibility, hypotheses, provisional timing. Not executed by software. |
| **This file** | Machine-readable subset for one run: stages, collect flags, reminders, checklists, markers. |
| [DESIGN.md](DESIGN.md) §6 | Event **names** and payloads. Stage `events.enter` / `events.exit` must map onto that model. |
| [DESIGN.md](DESIGN.md) / [PLAN.md](PLAN.md) Phase 3 | Stimulus controller is **config-driven** by this file, not a hard-coded state machine. |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Operator UI is a guided runbook over the loaded experiment; the sidecar `stimulus` worker executes stages. Shell remains **Option A**. |
| [INTEGRATIONS.md](INTEGRATIONS.md) | Locked IPC / packaging / REDCap / Box are unchanged. `session.start` params include `experiment_id` or `experiment_path`; optional `experiments.*` config key. |

Does **not** invent a quantum vs standard definition. Condition tags remain opaque (`quantum` \| `standard` \| `practice`) as in PROTOCOL.md.

---

## 4. Config model (sketch)

### 4.1 Location and identity

```
experiments/<name>.yaml
```

Top-level identity:

| Field | Type | Notes |
|-------|------|--------|
| `schema_version` | int | **Required.** `1` for this sketch. |
| `id` | string | Stable machine id (`painting_session_simplified`). Used as `experiment_id`. |
| `name` | string | Operator-facing title. |
| `protocol_version` | string | Investigator protocol this run implements (e.g. `"0.1"`). Copied into `meta.yaml` / REDCap `protocol_version`. |
| `description` | string | Optional prose. |

### 4.2 `defaults`

Session-wide fallbacks. A stage may override.

| Field | Notes |
|-------|--------|
| `collect` | Modality on/off (see §4.5). Missing stage `collect` inherits this. |
| `sample_rates` | Hints only (`thermal_hz`, `rgb_hz`). Hardware profiles still win if they cannot meet the hint. |
| `geometry` | Reference to the PROTOCOL / HARDWARE stations. PROTOCOL v0.2 names `seated_view` (Station A) and `close_interact` (Station B). This field is not a second geometry spec; tag events with those names. |
| `advance` | Default advance policy if a stage omits it. |
| `end_signal` | Default end-of-phase policy (`auto` unless a stage sets `operator` / `confirm_end`). |
| `constraints` | Default hard constraints (e.g. `allow_nuc: true` outside exposure). |

### 4.3 `stages[]`

Ordered list. The run walks this list (after expanding blocks — §4.10). Each stage:

| Field | Type | Notes |
|-------|------|--------|
| `id` | string | Stable within the file. Unique after block expansion if using `${repeat.index}` / `${item.painting_id}`. |
| `label` | string | What the operator sees: `"Phase 1 — Baseline"`, `"Fixation"`, `"Exposure"`, `"ISI"`, `"Ratings"`. |
| `kind` | enum | See §4.4. |
| `duration_s` | number \| null | Wall-clock length. **`null`** if the stage is open-ended. Required when `advance` is `auto` (timer must have something to count). When `advance` is `operator`, a duration is **guidance only** (countdown shown; it does not leave by itself). |
| `advance` | `auto` \| `operator` \| `either` | Who may leave the stage — see §4.3.1. |
| `end_signal` | `auto` \| `operator` | Optional. `operator` = explicit **End phase** click required before leave, even if a duration has elapsed. Alias: `confirm_end: true`. See §4.3.1. |
| `collect` | map | Streams active this stage (§4.5). |
| `stimulus` | object \| null | Optional painting / condition / presentation hints (§4.6). |
| `constraints` | object | Hard constraints the UI badges and the sidecar enforces (§4.7). |
| `reminders[]` | list | Operator-facing strings with `when` (§4.8). |
| `checklist[]` | list | Required confirmations. The primary **Continue / Next** or **End phase** button stays disabled until every item is checked (§4.9). |
| `events` | object | Markers to emit on enter / exit (§4.11). Operator button presses also emit `operator_advance` / `operator_end_phase`. |

### 4.3.1 Phase control (`advance` and `end_signal`)

Two independent questions: **who may leave**, and **whether leaving still needs an explicit end click**.

**`advance` — who may leave the stage**

| `advance` | Meaning |
|-----------|---------|
| `auto` | Timer or sidecar condition advances **alone**. No operator press required. Hide or disable the primary phase button (Pause / Skip / Abort stay available). |
| `operator` | Operator **must** press **Continue / Next phase**. A `duration_s` may still be shown as guidance; the timer does **not** leave the stage. Open-ended `operator_wait` / `stimulus` / `calibration` / `checklist` use this. |
| `either` | Timer **may** auto-advance **or** the operator may press. First event wins; log which. Optional `either_policy`: `early` (press before the timer), `late` (press after the timer would have fired — treat as confirm), `both` (default). |

**`end_signal` — explicit end-of-phase click**

| `end_signal` | Meaning |
|--------------|---------|
| `auto` (default) | Leave as soon as the `advance` condition is met. No extra click. |
| `operator` | Stage has (or may have) a duration, but still needs an explicit **End phase** click before leaving. The timer reaching zero does **not** dismiss the stage; it enables (or keeps enabling) the button. |

`confirm_end: true` is an alias for `end_signal: operator`. `confirm_end: false` is `end_signal: auto`. Prefer `end_signal` in new files.

Typical combinations:

| Intent | `advance` | `duration_s` | `end_signal` | Primary button |
|--------|-----------|--------------|--------------|----------------|
| Fixed epoch (fixation, exposure) | `auto` | e.g. 25 | `auto` | none (timer leaves) |
| Must click to go to the **next** phase | `operator` | `null` or guidance | `auto` | **Continue / Next phase** |
| Timed, but must click **end of this phase** | `auto` | e.g. 60 | `operator` | **End phase** (enabled at t=0, or always enabled if `either_policy` allows early) |
| Open-ended wait / hang painting / “Done” | `operator` | `null` | `auto` or `operator` | **Continue / Next** or **End phase** (one button; label from kind — see §5.2) |
| Timer *or* operator | `either` | required | `auto` | **Continue / Next phase** (optional) |

Do not set `advance: auto` with `duration_s: null` unless `end_signal` is `operator` (otherwise nothing can leave). Prefer `advance: operator` for open-ended stages.

Button presses are first-class events (§4.11): `operator_advance` and `operator_end_phase`, with timestamps. They are in addition to the stage’s configured `events.exit`.

### 4.4 `kind` enum (v1 sketch)

| `kind` | Typical use | Default `advance` |
|--------|-------------|-------------------|
| `checklist` | Setup / closeout gates (“chair locked”, “Verity LED green”) | `operator` |
| `timed` | Fixed wait with collection (generic countdown) | `auto` |
| `stimulus` | Painting (or screen) exposure | `auto` |
| `calibration` | Gaze look-at or RGB–thermal; operator-paced points | `operator` |
| `operator_wait` | “Hang the next painting”, mid-session break | `operator` |
| `rest` | Baseline or recovery; collect without a stimulus | `auto` |

`kind` is a **hint** for UI chrome and worker behavior (e.g. `stimulus` applies NUC defaults; `calibration` opens the look-at wizard). It does not replace `constraints`, `collect`, `events`, or the **Continue / End phase** button policy in §4.3.1. An open-ended `stimulus` that ends only when the experimenter presses Done uses `advance: operator` (and `duration_s: null`).

### 4.5 `collect`

Which streams are **active** during the stage. Values are `true` / `false`, or a rate override.

```yaml
collect:
  thermal: true
  rgb: true
  verity: true
  gaze: true
  events: true          # always true for a real run; false only in unit tests
```

Rate override:

```yaml
collect:
  thermal: { enabled: true, hz: 80 }
  rgb: false
```

Known keys (v1): `thermal`, `rgb`, `verity`, `gaze`, `events`. Unknown keys fail validation.

`events` means “write `events.jsonl` / emit `event.emit`.” It is not an LSL camera stream.

### 4.6 `stimulus` (optional)

Hints for a `stimulus` (or practice) stage. Catalog fields stay investigator-owned ([PROTOCOL.md](PROTOCOL.md) §3.4).

| Field | Notes |
|-------|--------|
| `painting_id` | Literal, or a substitution from the current block item (`${item.painting_id}`). |
| `condition` | `quantum` \| `standard` \| `practice` — opaque tags. |
| `presentation` | `physical` \| `screen` (must match the session medium). |
| `cover` | `on` \| `off` — expected easel / display state for the operator reminder. |

Do not put full catalog science (matching rules, AOI art notes) here. Reference the catalog; expand in a block.

### 4.7 `constraints`

Hard rules. The operator UI shows **badges**; the sidecar **refuses** forbidden actions (e.g. NUC RPC during exposure).

| Field | Meaning |
|-------|---------|
| `allow_nuc` | PI 450i manual shutter. **`false` during exposure.** |
| `allow_talk` | Operator/participant talking. `false` → “DO NOT TALK” badge. |
| `allow_operator_in_fov` | Operator body in camera FOV. |

Unset inherits `defaults.constraints`. A `stimulus` stage should set `allow_nuc: false` explicitly even if defaults already say so.

### 4.8 `reminders[]`

Operator-facing strings. They do not emit events unless `events` also says so.

| Field | Notes |
|-------|--------|
| `text` | Required. Short, imperative (“Do NUC now”, “Start painting”, “Do not talk”). |
| `when` | `enter` \| `exit` \| `mid` \| `countdown_at_s` |
| `at_s` | Required when `when: countdown_at_s`. Seconds **remaining** (or elapsed — pick remaining for v1). |
| `tone` | Optional: `info` \| `warn` \| `critical` (badge color). |

Examples: Phase labels on enter; “do NUC now” at ISI enter; “prepare cover” at 5 s remaining on exposure.

### 4.9 `checklist[]`

Required confirmations before the stage can **leave** (and, for a leading `checklist` stage, before the session may proceed).

```yaml
checklist:
  - id: chair_locked
    text: Chair locked on floor marks
  - id: verity_green
    text: Verity LED green / live HR in UI
  - id: painting_hung
    text: Next painting hung (or cover on for fixation)
```

The primary **Continue / Next phase** or **End phase** button stays **disabled until every item is checked**. Checks are logged (operator, timestamp, stage id). Skip / abort are separate controls and still require a reason.

### 4.10 Loops / blocks

Repeat a **group** of stages N times, or once per catalog item.

```yaml
- id: experimental_block
  repeat:
    over: catalog.paintings     # or: n: 16
    shuffle: protocol_tbd       # placeholder — do not invent a scheme
    max_consecutive_same_condition: 2   # PROTOCOL §7 provisional
    first_condition_counterbalance: participant_parity
  stages:
    - id: fixation
      ...
    - id: exposure
      stimulus:
        painting_id: ${item.painting_id}
        condition: ${item.condition}
      ...
    - id: isi
      ...
```

| Hook | v1 status |
|------|-----------|
| `over: catalog.paintings` | Expand one iteration per catalog row. |
| `n` | Fixed repeat count (practice loops, rest cycles). |
| `shuffle` / `counterbalance` | **Placeholders** tied to [PROTOCOL.md](PROTOCOL.md) §7 / §13. The loader records the **resolved order** into session `meta.yaml` before `session_start`. Do not invent a new randomization science here. |

A resolved run is a **flat stage list** (block unrolled). The operator UI and the stimulus worker both see that flat list plus the original block labels for progress (“Trial 4 / 16”).

Optional top-level `catalog:` (painting ids + condition tags only) may live in the experiment file **or** be referenced (`catalog_ref:`). Full catalog science stays in PROTOCOL.

### 4.11 `events` → DESIGN event model

Stage boundaries emit markers that match [DESIGN.md](DESIGN.md) §6 and [PROTOCOL.md](PROTOCOL.md) §11.

```yaml
events:
  enter:
    name: stimulus_onset
    payload:
      painting_id: ${item.painting_id}
      condition: ${item.condition}
  exit:
    name: stimulus_offset
```

| Stage role | Typical enter / exit |
|------------|----------------------|
| Session arm / disarm | `session_start` / `session_end` (often owned by `session.start` / `session.stop`, not a stage) |
| Calibration | `calibration_start` / `calibration_end` (`kind: gaze` \| `rgb_thermal`) |
| Fixation | `fixation_onset` / `fixation_offset` |
| Exposure | `stimulus_onset` / `stimulus_offset` (+ `painting_id`, `condition`) |
| ISI | `isi_onset` / `isi_offset` |
| NUC (reminder + sidecar action) | `nuc_trigger` — only when `constraints.allow_nuc` is true |
| Operator **Continue / Next phase** | `operator_advance` — timestamp, `stage_id`, optional `label` |
| Operator **End phase** | `operator_end_phase` — timestamp, `stage_id`, optional `label` |

`operator_advance` / `operator_end_phase` fire when the primary button is pressed (in addition to the stage’s configured enter/exit names). They are optional extensions of [DESIGN.md](DESIGN.md) §6 (same family as abort / note).

Unknown `name` values fail validation unless listed in an `events.extra` allow-list (keep empty in v1). Optional ratings / abort notes stay as in DESIGN.md.

The sidecar writes the same objects to `events.jsonl` and notifies the UI via `event.emit` ([INTEGRATIONS.md](INTEGRATIONS.md) §2).

---

## 5. Operator UI behavior

The Tauri/React UI is a **guided runbook** over the loaded experiment. It does not own trial timing. The sidecar stimulus worker owns the clock; the UI renders state the orchestrator relays.

### 5.1 Load

- Operator picks an experiment (`experiment_id` from the catalog, or a path).
- `session.start` includes `experiment_id` **or** `experiment_path` ([INTEGRATIONS.md](INTEGRATIONS.md) §2).
- Loader validates `schema_version`, expands blocks, writes the **resolved** plan into the session directory (e.g. `experiment.resolved.yaml`) so the run is reproducible.

### 5.2 Layout (v1)

| Surface | Behavior |
|---------|----------|
| Stage list + progress | Full session outline; current stage highlighted; “Trial *k* / *N*” for blocks. |
| Current-stage banner | Large `label` (Phase / Fixation / Exposure / ISI). |
| Countdown | Remaining `duration_s` when set (guidance or hard timer). “Waiting on operator” when `advance: operator` and `duration_s` is null. |
| Phase-control button | Large primary control — see below. |
| Reminders | Live stack by `when` (`enter` on stage start, `countdown_at_s` when remaining hits `at_s`, `exit` on leave). |
| Constraint badges | Persistent while the stage is active. Example: red **NO NUC**, **DO NOT TALK**. |
| Checklist gates | **Continue / Next** and **End phase** stay disabled until all items confirmed. |
| Device status strip | Unchanged from ARCHITECTURE.md §4.1 (dropouts, BLE, NUC-safe window). Always visible. |
| Enabled streams | Icons / chips from `collect` (thermal / RGB / Verity / gaze). |

**Primary phase button (MVP).** One large control; label depends on the pending action (two visible buttons are OK if clearer, but not required):

| Pending action | Button label | Logged event |
|----------------|--------------|--------------|
| `advance: operator` (and `end_signal` is not `operator`) | **Continue / Next phase** | `operator_advance` |
| `end_signal: operator` (timed confirm, or Done on an open-ended wait) | **End phase** | `operator_end_phase` |
| `advance: either` | **Continue / Next phase** | `operator_advance` if pressed; if the timer wins, no button event |
| `advance: auto` and `end_signal: auto` | Hidden or disabled | none |

Presses include a host timestamp and `stage_id`. The sidecar then emits the configured `events.exit` and walks to the next stage.

Checklist items still **block** this button. Keyboard shortcut (e.g. Space / Enter) is **optional later**; the on-screen button is the v1 affordance. Do not bind a silent hotkey in Phase 1.

### 5.3 Abort / pause / skip

All three are **logged** (reason required for skip and abort).

| Action | Effect |
|--------|--------|
| **Pause** | Freeze the stage timer; workers keep writing (or hold buffers — Phase 1: freeze timer only). Reminders stay up. |
| **Skip** | Leave the stage without meeting `advance`; write a skip note + reason; do **not** emit a successful `stimulus_offset` if exposure never started. |
| **Abort** | `session.stop` path; `session_end` + abort note; session `session_status` → `aborted` when REDCap is wired. |

### 5.4 Dry-run

Dry-run mode (fake clocks, no hardware) **follows the same config**: same stages, durations, reminders, checklists, constraints, **Continue / Next** and **End phase** buttons, and markers. Streams are simulated ([PLAN.md](PLAN.md) Phase 1). Constraint badges still show; NUC is a no-op that still logs `nuc_trigger` only when allowed. Button presses still emit `operator_advance` / `operator_end_phase`.

---

## 6. Shared consumption

```
experiments/<name>.yaml
        │
        ▼
 Rust orchestrator  ── session.start({ experiment_id | experiment_path, ... })
        │
        ├──────────────► Tauri/React UI   (render runbook from resolved plan + live events)
        │
        └──────────────► Python sidecar stimulus worker
                         (advance stages, enable collect, enforce constraints, emit markers)
```

- **One file, two consumers.** Do not keep a second “UI-only” trial list.
- The sidecar is authoritative for **when** a timed `advance: auto` stage ends (and `end_signal` is `auto`).
- The UI is authoritative for **checklist gates**, **Continue / Next phase**, and **End phase** (sends an advance / end-phase RPC; exact method names can wait for Phase 1 stubs — do not add a locked INTEGRATIONS method in this sketch).
- Stage progress can ride on existing `event.emit` notifications. A later `stage.status` notification is optional and is **not** required to lock IPC again.

Copy the source YAML (and the resolved expansion) into the session tree next to `meta.yaml`.

---

## 7. Example — simplified painting session

Provisional timings match [PROTOCOL.md](PROTOCOL.md) §6 (2.5 / 25 / 8 s). Catalog items are placeholders.

```yaml
schema_version: 1
id: painting_session_simplified
name: Simplified painting session
protocol_version: "0.1"
description: >
  Setup checklist (Continue / Next), gaze calibration, baseline rest
  with End-phase confirmation, hang-painting wait (button), then a
  small fixation → exposure → ISI block. Not a confirmatory protocol.

defaults:
  collect:
    thermal: true
    rgb: true
    verity: true
    gaze: true
    events: true
  sample_rates:
    thermal_hz: 80
    rgb_hz: 60
  geometry: protocol_baseline
  constraints:
    allow_nuc: true
    allow_talk: true
    allow_operator_in_fov: true

catalog:
  paintings:
    - { painting_id: Q001, condition: quantum }
    - { painting_id: S001, condition: standard }

# Randomization / counterbalance: PROTOCOL §7 / §13 — placeholder only.
randomization:
  scheme: protocol_tbd
  max_consecutive_same_condition: 2
  first_condition_counterbalance: participant_parity

stages:
  - id: setup
    label: "Phase 1 — Setup"
    kind: checklist
    duration_s: null
    advance: operator
    collect:
      thermal: false
      rgb: false
      verity: false
      gaze: false
      events: true
    reminders:
      - when: enter
        text: "Complete setup, then press Continue / Next phase."
        tone: info
    checklist:
      - id: chair_locked
        text: Chair locked on floor marks (~1.5 m)
      - id: eye_height
        text: Eye height ≈ painting center (145–150 cm)
      - id: verity_green
        text: Verity on designated upper arm; LED / live HR green
      - id: painting_ready
        text: First painting ready; cover on for fixation
    events:
      enter: { name: session_note, payload: { note: setup_begin } }

  - id: gaze_cal
    label: "Gaze calibration"
    kind: calibration
    duration_s: null
    advance: operator
    collect:
      thermal: false
      rgb: true
      verity: true
      gaze: true
      events: true
    reminders:
      - when: enter
        text: "5–9 look-at marks. Cue each point; do not rush."
    checklist:
      - id: gaze_qc
        text: Look-at QC acceptable (or chin rest added and redone)
    events:
      enter: { name: calibration_start, payload: { kind: gaze } }
      exit: { name: calibration_end, payload: { kind: gaze } }

  - id: baseline
    label: "Phase 1 — Baseline"
    kind: rest
    duration_s: 60
    advance: auto
    end_signal: operator          # timer is guidance/elapsed; must click End phase
    # confirm_end: true           # alias for end_signal: operator
    collect:
      thermal: true
      rgb: true
      verity: true
      gaze: true
      events: true
    constraints:
      allow_nuc: true
      allow_talk: false
      allow_operator_in_fov: false
    reminders:
      - when: enter
        text: "Baseline rest. Do not talk. Stay out of FOV."
        tone: warn
      - when: countdown_at_s
        at_s: 10
        text: "10 s left — then press End phase (do not leave on the timer alone)."
    events:
      enter: { name: rest_onset, payload: { kind: baseline } }
      exit: { name: rest_offset, payload: { kind: baseline } }

  - id: hang_painting
    label: "Hang next painting"
    kind: operator_wait
    duration_s: null
    advance: operator            # must press Continue / Next phase
    collect:
      thermal: true
      rgb: true
      verity: true
      gaze: false
      events: true
    constraints:
      allow_nuc: true
      allow_talk: true
      allow_operator_in_fov: true
    reminders:
      - when: enter
        text: "Hang the first experimental painting. Cover on. Then press Continue / Next phase."
    checklist:
      - id: painting_hung
        text: Painting hung; cover on for fixation
    events:
      enter: { name: session_note, payload: { note: hang_painting } }

  - id: experimental_block
    label: "Experimental trials"
    repeat:
      over: catalog.paintings
      shuffle: protocol_tbd
    stages:
      - id: fixation
        label: "Fixation"
        kind: timed
        duration_s: 2.5
        advance: auto
        constraints:
          allow_nuc: false
          allow_talk: false
          allow_operator_in_fov: false
        reminders:
          - when: enter
            text: "Fixation. Cover on. Do not talk."
        events:
          enter: { name: fixation_onset }
          exit: { name: fixation_offset }

      - id: exposure
        label: "Exposure"
        kind: stimulus
        duration_s: 25
        advance: auto
        stimulus:
          painting_id: ${item.painting_id}
          condition: ${item.condition}
          presentation: physical
          cover: off
        constraints:
          allow_nuc: false
          allow_talk: false
          allow_operator_in_fov: false
        reminders:
          - when: enter
            text: "Start painting. NO NUC. Do not talk. Stay out of FOV."
            tone: critical
          - when: countdown_at_s
            at_s: 5
            text: "5 s — prepare cover."
            tone: warn
        events:
          enter:
            name: stimulus_onset
            payload:
              painting_id: ${item.painting_id}
              condition: ${item.condition}
          exit:
            name: stimulus_offset
            payload:
              painting_id: ${item.painting_id}
              condition: ${item.condition}

      - id: isi
        label: "ISI"
        kind: timed
        duration_s: 8
        advance: auto
        stimulus:
          cover: on
        constraints:
          allow_nuc: true
          allow_talk: false
          allow_operator_in_fov: false
        reminders:
          - when: enter
            text: "ISI. Cover on. Do NUC now (if due)."
            tone: warn
          - when: enter
            text: "If ratings are enabled this session: enter rating in REDCap (not in this UI)."
            tone: info
        events:
          enter: { name: isi_onset }
          exit: { name: isi_offset }

  - id: closeout
    label: "Session end"
    kind: checklist
    duration_s: null
    advance: operator
    collect:
      thermal: false
      rgb: false
      verity: false
      gaze: false
      events: true
    reminders:
      - when: enter
        text: "Capture should be stopped. Queue Box upload after local write. Press Continue / Next when the checklist is done."
    checklist:
      - id: events_paired
        text: events.jsonl has paired onset/offset for every exposure
      - id: no_nuc_in_exposure
        text: No nuc_trigger inside any stimulus window
      - id: upload_reminder
        text: Local write complete — start / confirm Box upload when network is available
    events:
      enter: { name: session_note, payload: { note: closeout_begin } }
```

`rest_onset` / `rest_offset` and `session_note` are optional extensions of DESIGN.md §6 (same family as abort / note). Prefer the required names in the table there for calibration, fixation, stimulus, ISI, and NUC.

---

## 8. Validation (v1, implement in Phase 1)

- `schema_version` must be `1`.
- `id`, `name`, and a non-empty `stages` list are required.
- Unknown `kind`, `advance`, `end_signal`, `collect` keys, or `reminders.when` fail.
- `advance: auto` requires numeric `duration_s` > 0 **unless** `end_signal` is `operator` (open-ended confirm). Prefer `advance: operator` for open-ended stages.
- `advance: operator` does **not** require `duration_s`; if present, treat as guidance only.
- `confirm_end: true` normalizes to `end_signal: operator`.
- `checklist` kind should use `advance: operator` (or `either`).
- `constraints.allow_nuc: true` is rejected on `kind: stimulus` (hard fail).
- `events.*.name` must be in the DESIGN.md §6 / PROTOCOL.md §11 set, or a documented optional name (`operator_advance`, `operator_end_phase`, `rest_*`, `session_note`).
- After block expansion, stage `id`s must be unique (allow `${repeat.index}` / `${item.painting_id}` in templates).
- Dry-run uses the same validator (including button-gated stages).

---

## 9. Non-goals for v1

- **Full GUI experiment editor.** Start with YAML + validate. A visual editor is later.
- **Replacing REDCap ratings instruments.** Reminders may say “enter rating in REDCap.” Do not embed CRF widgets in the operator UI in v1.
- **Inventing quantum vs standard definitions.** Tags stay opaque; catalog science stays in PROTOCOL.md.
- **Reopening Option A** or the INTEGRATIONS locks (IPC transport, packaging, REDCap field dictionary, Box taxonomy).
- **Shipping `experiments/*.yaml` as runnable science.** The example is a sketch; investigator timings and catalog remain TBD.
