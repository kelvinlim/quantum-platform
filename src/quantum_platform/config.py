"""Experiment YAML loader and validator (EXPERIMENT_CONFIG.md schema_version 1)."""

from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = 1

KINDS = frozenset(
    {"checklist", "timed", "stimulus", "calibration", "operator_wait", "rest"}
)
ADVANCES = frozenset({"auto", "operator", "either"})
END_SIGNALS = frozenset({"auto", "operator"})
EITHER_POLICIES = frozenset({"early", "late", "both"})
REMINDER_WHEN = frozenset({"enter", "exit", "mid", "countdown_at_s"})
REMINDER_TONES = frozenset({"info", "warn", "critical"})
COLLECT_KEYS = frozenset({"thermal", "rgb", "verity", "gaze", "events"})
CONSTRAINT_KEYS = frozenset({"allow_nuc", "allow_talk", "allow_operator_in_fov"})
STIMULUS_CONDITIONS = frozenset({"quantum", "standard", "practice"})
STIMULUS_PRESENTATIONS = frozenset({"physical", "screen"})
STIMULUS_COVERS = frozenset({"on", "off"})

KIND_DEFAULT_ADVANCE = {
    "checklist": "operator",
    "timed": "auto",
    "stimulus": "auto",
    "calibration": "operator",
    "operator_wait": "operator",
    "rest": "auto",
}

# DESIGN.md §6 plus documented optional extensions in EXPERIMENT_CONFIG.md §4.11 / §8.
DESIGN_EVENT_NAMES = frozenset(
    {
        "session_start",
        "session_end",
        "calibration_start",
        "calibration_end",
        "fixation_onset",
        "fixation_offset",
        "stimulus_onset",
        "stimulus_offset",
        "isi_onset",
        "isi_offset",
        "nuc_trigger",
        "operator_advance",
        "operator_end_phase",
        "rest_onset",
        "rest_offset",
        "session_note",
    }
)


class ConfigError(ValueError):
    """One or more experiment-config validation failures."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors) if errors else "invalid experiment config")


@dataclass
class CollectSpec:
    enabled: bool
    hz: float | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"enabled": self.enabled}
        if self.hz is not None:
            out["hz"] = self.hz
        return out


@dataclass
class Constraints:
    allow_nuc: bool = True
    allow_talk: bool = True
    allow_operator_in_fov: bool = True

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)


@dataclass
class Reminder:
    text: str
    when: str
    at_s: float | None = None
    tone: str = "info"

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"text": self.text, "when": self.when, "tone": self.tone}
        if self.at_s is not None:
            out["at_s"] = self.at_s
        return out


@dataclass
class ChecklistItem:
    id: str
    text: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "text": self.text}


@dataclass
class EventSpec:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"name": self.name}
        if self.payload:
            out["payload"] = dict(self.payload)
        return out


@dataclass
class StimulusHint:
    painting_id: str | None = None
    condition: str | None = None
    presentation: str | None = None
    cover: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ResolvedStage:
    id: str
    label: str
    kind: str
    duration_s: float | None
    advance: str
    end_signal: str
    either_policy: str
    collect: dict[str, CollectSpec]
    constraints: Constraints
    reminders: list[Reminder]
    checklist: list[ChecklistItem]
    stimulus: StimulusHint | None = None
    events_enter: EventSpec | None = None
    events_exit: EventSpec | None = None
    block_id: str | None = None
    block_label: str | None = None
    trial_index: int | None = None
    trial_count: int | None = None
    source_id: str = ""
    catalog_item: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "duration_s": self.duration_s,
            "advance": self.advance,
            "end_signal": self.end_signal,
            "either_policy": self.either_policy,
            "collect": {k: v.to_dict() for k, v in self.collect.items()},
            "constraints": self.constraints.to_dict(),
            "reminders": [r.to_dict() for r in self.reminders],
            "checklist": [c.to_dict() for c in self.checklist],
            "stimulus": self.stimulus.to_dict() if self.stimulus else None,
            "events": {
                "enter": self.events_enter.to_dict() if self.events_enter else None,
                "exit": self.events_exit.to_dict() if self.events_exit else None,
            },
            "block_id": self.block_id,
            "block_label": self.block_label,
            "trial_index": self.trial_index,
            "trial_count": self.trial_count,
            "source_id": self.source_id,
            "catalog_item": dict(self.catalog_item) if self.catalog_item else {},
        }


@dataclass
class ResolvedPlan:
    schema_version: int
    id: str
    name: str
    protocol_version: str | None
    description: str | None
    defaults: dict[str, Any]
    catalog: dict[str, Any]
    randomization: dict[str, Any]
    resolved_order: list[Any]
    stages: list[ResolvedStage]
    source_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "name": self.name,
            "protocol_version": self.protocol_version,
            "description": self.description,
            "defaults": self.defaults,
            "catalog": self.catalog,
            "randomization": self.randomization,
            "resolved_order": self.resolved_order,
            "stages": [s.to_dict() for s in self.stages],
            "source_path": self.source_path,
        }


def load_raw(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".json"}:
        data = json.loads(text)
    else:
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ConfigError(["experiment file must be a mapping"])
    return data


def load_experiment(path: str | Path) -> ResolvedPlan:
    path = Path(path)
    raw = load_raw(path)
    plan = validate_and_resolve(raw)
    plan.source_path = str(path.resolve())
    return plan


def find_experiment(experiment_id: str, experiments_dir: str | Path) -> Path:
    root = Path(experiments_dir)
    direct = root / f"{experiment_id}.yaml"
    if direct.is_file():
        return direct
    json_path = root / f"{experiment_id}.json"
    if json_path.is_file():
        return json_path
    for candidate in sorted(root.glob("*.yaml")) + sorted(root.glob("*.yml")) + sorted(
        root.glob("*.json")
    ):
        try:
            raw = load_raw(candidate)
        except (OSError, ConfigError, yaml.YAMLError, json.JSONDecodeError):
            continue
        if raw.get("id") == experiment_id:
            return candidate
    raise ConfigError([f"experiment id not found: {experiment_id} (dir={root})"])


def validate_and_resolve(raw: dict[str, Any]) -> ResolvedPlan:
    errors: list[str] = []
    version = raw.get("schema_version")
    if version != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}, got {version!r}")
    exp_id = raw.get("id")
    if not isinstance(exp_id, str) or not exp_id.strip():
        errors.append("id is required")
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("name is required")
    stages_raw = raw.get("stages")
    if not isinstance(stages_raw, list) or not stages_raw:
        errors.append("stages must be a non-empty list")
        raise ConfigError(errors)

    extra = raw.get("events_extra")
    events_block = raw.get("events")
    if extra is None and isinstance(events_block, dict):
        extra = events_block.get("extra")
    extra_names = _as_str_list(extra)
    allowed_events = set(DESIGN_EVENT_NAMES)
    allowed_events.update(extra_names)

    defaults = raw.get("defaults") or {}
    if defaults is None:
        defaults = {}
    if not isinstance(defaults, dict):
        errors.append("defaults must be a mapping")
        defaults = {}

    default_collect = _parse_collect(defaults.get("collect") or {}, "defaults.collect", errors)
    default_constraints = _parse_constraints(
        defaults.get("constraints") or {}, "defaults.constraints", errors
    )
    default_advance = defaults.get("advance")
    if default_advance is not None and default_advance not in ADVANCES:
        errors.append(f"defaults.advance must be one of {sorted(ADVANCES)}")
    default_end = _normalize_end_signal(defaults, "defaults", errors)

    catalog = raw.get("catalog") or {}
    if catalog is None:
        catalog = {}
    if not isinstance(catalog, dict):
        errors.append("catalog must be a mapping")
        catalog = {}

    randomization = raw.get("randomization") or {}
    if randomization is None:
        randomization = {}
    if not isinstance(randomization, dict):
        errors.append("randomization must be a mapping")
        randomization = {}

    # PROTOCOL §7 / §13 — do not invent a shuffle. Preserve catalog order.
    resolved_order, items = _resolve_catalog_items(catalog, randomization, errors)

    resolved_stages: list[ResolvedStage] = []
    _expand_stage_list(
        stages_raw,
        parent_prefix="",
        block_id=None,
        block_label=None,
        trial_index=None,
        trial_count=None,
        catalog_item={},
        items=items,
        default_collect=default_collect,
        default_constraints=default_constraints,
        default_advance=default_advance if isinstance(default_advance, str) else None,
        default_end=default_end,
        allowed_events=allowed_events,
        errors=errors,
        out=resolved_stages,
    )

    seen: dict[str, int] = {}
    for stage in resolved_stages:
        seen[stage.id] = seen.get(stage.id, 0) + 1
    dupes = [sid for sid, n in seen.items() if n > 1]
    if dupes:
        errors.append(f"duplicate stage id(s) after expansion: {sorted(dupes)}")

    if errors:
        raise ConfigError(errors)

    assert isinstance(exp_id, str) and isinstance(name, str)
    return ResolvedPlan(
        schema_version=SCHEMA_VERSION,
        id=exp_id,
        name=name,
        protocol_version=_opt_str(raw.get("protocol_version")),
        description=_opt_str(raw.get("description")),
        defaults=copy.deepcopy(defaults),
        catalog=copy.deepcopy(catalog),
        randomization=copy.deepcopy(randomization),
        resolved_order=resolved_order,
        stages=resolved_stages,
    )


def _as_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def _opt_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip() or None


def _normalize_end_signal(data: dict[str, Any], where: str, errors: list[str]) -> str | None:
    if "end_signal" in data and data["end_signal"] is not None:
        end = data["end_signal"]
        if end not in END_SIGNALS:
            errors.append(f"{where}.end_signal must be one of {sorted(END_SIGNALS)}")
            return None
        return str(end)
    if "confirm_end" in data and data["confirm_end"] is not None:
        flag = data["confirm_end"]
        if not isinstance(flag, bool):
            errors.append(f"{where}.confirm_end must be a boolean")
            return None
        return "operator" if flag else "auto"
    return None


def _parse_collect(raw: Any, where: str, errors: list[str]) -> dict[str, CollectSpec]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        errors.append(f"{where} must be a mapping")
        return {}
    out: dict[str, CollectSpec] = {}
    for key, value in raw.items():
        if key not in COLLECT_KEYS:
            errors.append(f"{where}: unknown collect key {key!r}")
            continue
        if isinstance(value, bool):
            out[key] = CollectSpec(enabled=value)
        elif isinstance(value, dict):
            enabled = value.get("enabled", True)
            if not isinstance(enabled, bool):
                errors.append(f"{where}.{key}.enabled must be a boolean")
                continue
            hz = value.get("hz")
            if hz is not None and not isinstance(hz, (int, float)):
                errors.append(f"{where}.{key}.hz must be a number")
                continue
            out[key] = CollectSpec(enabled=enabled, hz=float(hz) if hz is not None else None)
        else:
            errors.append(f"{where}.{key} must be a boolean or mapping")
    return out


def _parse_constraints(raw: Any, where: str, errors: list[str]) -> Constraints:
    if raw is None:
        return Constraints()
    if not isinstance(raw, dict):
        errors.append(f"{where} must be a mapping")
        return Constraints()
    kwargs: dict[str, bool] = {}
    for key, value in raw.items():
        if key not in CONSTRAINT_KEYS:
            errors.append(f"{where}: unknown constraint {key!r}")
            continue
        if not isinstance(value, bool):
            errors.append(f"{where}.{key} must be a boolean")
            continue
        kwargs[key] = value
    return Constraints(**kwargs)


def _resolve_catalog_items(
    catalog: dict[str, Any],
    randomization: dict[str, Any],
    errors: list[str],
) -> tuple[list[Any], list[dict[str, Any]]]:
    paintings = catalog.get("paintings") if catalog else None
    items: list[dict[str, Any]] = []
    if isinstance(paintings, list):
        for i, row in enumerate(paintings):
            if not isinstance(row, dict):
                errors.append(f"catalog.paintings[{i}] must be a mapping")
                continue
            items.append(dict(row))
    # Placeholder only — do not invent a randomization scheme.
    scheme = randomization.get("scheme") if randomization else None
    if scheme and scheme not in {"protocol_tbd", None}:
        # Recorded, not executed.
        pass
    resolved_order = [row.get("painting_id", i) for i, row in enumerate(items)]
    return resolved_order, items


def _substitute(value: Any, ctx: dict[str, str]) -> Any:
    if isinstance(value, str):
        out = value
        for key, repl in ctx.items():
            out = out.replace("${" + key + "}", repl)
        return out
    if isinstance(value, dict):
        return {k: _substitute(v, ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute(v, ctx) for v in value]
    return value


def _item_ctx(item: dict[str, Any], index: int) -> dict[str, str]:
    ctx = {"repeat.index": str(index)}
    for key, val in item.items():
        ctx[f"item.{key}"] = "" if val is None else str(val)
    return ctx


def _merge_collect(
    default: dict[str, CollectSpec], override: dict[str, CollectSpec]
) -> dict[str, CollectSpec]:
    merged = dict(default)
    merged.update(override)
    for key in COLLECT_KEYS:
        merged.setdefault(key, CollectSpec(enabled=True if key == "events" else False))
    return merged


def _merge_constraints(default: Constraints, override_raw: dict[str, Any] | None) -> Constraints:
    data = default.to_dict()
    if override_raw:
        for key in CONSTRAINT_KEYS:
            if key in override_raw and isinstance(override_raw[key], bool):
                data[key] = override_raw[key]
    return Constraints(**data)


def _parse_reminders(raw: Any, where: str, errors: list[str]) -> list[Reminder]:
    if not raw:
        return []
    if not isinstance(raw, list):
        errors.append(f"{where}.reminders must be a list")
        return []
    out: list[Reminder] = []
    for i, item in enumerate(raw):
        loc = f"{where}.reminders[{i}]"
        if not isinstance(item, dict):
            errors.append(f"{loc} must be a mapping")
            continue
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{loc}.text is required")
            continue
        when = item.get("when", "enter")
        if when not in REMINDER_WHEN:
            errors.append(f"{loc}.when must be one of {sorted(REMINDER_WHEN)}")
            continue
        at_s = item.get("at_s")
        if when == "countdown_at_s":
            if not isinstance(at_s, (int, float)):
                errors.append(f"{loc}.at_s is required when when=countdown_at_s")
                continue
        elif at_s is not None and not isinstance(at_s, (int, float)):
            errors.append(f"{loc}.at_s must be a number")
            continue
        tone = item.get("tone", "info")
        if tone not in REMINDER_TONES:
            errors.append(f"{loc}.tone must be one of {sorted(REMINDER_TONES)}")
            continue
        out.append(
            Reminder(
                text=text,
                when=when,
                at_s=float(at_s) if isinstance(at_s, (int, float)) else None,
                tone=str(tone),
            )
        )
    return out


def _parse_checklist(raw: Any, where: str, errors: list[str]) -> list[ChecklistItem]:
    if not raw:
        return []
    if not isinstance(raw, list):
        errors.append(f"{where}.checklist must be a list")
        return []
    out: list[ChecklistItem] = []
    seen: set[str] = set()
    for i, item in enumerate(raw):
        loc = f"{where}.checklist[{i}]"
        if not isinstance(item, dict):
            errors.append(f"{loc} must be a mapping")
            continue
        cid = item.get("id")
        text = item.get("text")
        if not isinstance(cid, str) or not cid.strip():
            errors.append(f"{loc}.id is required")
            continue
        if cid in seen:
            errors.append(f"{loc}: duplicate checklist id {cid!r}")
            continue
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{loc}.text is required")
            continue
        seen.add(cid)
        out.append(ChecklistItem(id=cid, text=text))
    return out


def _parse_event(raw: Any, where: str, allowed: set[str], errors: list[str]) -> EventSpec | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = {"name": raw}
    if not isinstance(raw, dict):
        errors.append(f"{where} must be a mapping or name string")
        return None
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        errors.append(f"{where}.name is required")
        return None
    if name not in allowed:
        errors.append(f"{where}.name {name!r} is not in the DESIGN.md / extra allow-list")
        return None
    payload = raw.get("payload") or {}
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        errors.append(f"{where}.payload must be a mapping")
        payload = {}
    return EventSpec(name=name, payload=dict(payload))


def _parse_stimulus(raw: Any, where: str, errors: list[str]) -> StimulusHint | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        errors.append(f"{where}.stimulus must be a mapping")
        return None
    cond = raw.get("condition")
    if cond is not None and cond not in STIMULUS_CONDITIONS:
        errors.append(f"{where}.stimulus.condition must be one of {sorted(STIMULUS_CONDITIONS)}")
    pres = raw.get("presentation")
    if pres is not None and pres not in STIMULUS_PRESENTATIONS:
        errors.append(f"{where}.stimulus.presentation must be one of {sorted(STIMULUS_PRESENTATIONS)}")
    cover = raw.get("cover")
    # YAML 1.1 treats on/off as booleans; the documented example uses unquoted cover: on|off.
    if isinstance(cover, bool):
        cover = "on" if cover else "off"
    if cover is not None and cover not in STIMULUS_COVERS:
        errors.append(f"{where}.stimulus.cover must be one of {sorted(STIMULUS_COVERS)}")
    return StimulusHint(
        painting_id=_opt_str(raw.get("painting_id")),
        condition=_opt_str(cond),
        presentation=_opt_str(pres),
        cover=_opt_str(cover),
    )


def _duration(raw: Any, where: str, errors: list[str]) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    errors.append(f"{where}.duration_s must be a number or null")
    return None


def _expand_stage_list(
    stages_raw: list[Any],
    *,
    parent_prefix: str,
    block_id: str | None,
    block_label: str | None,
    trial_index: int | None,
    trial_count: int | None,
    catalog_item: dict[str, Any],
    items: list[dict[str, Any]],
    default_collect: dict[str, CollectSpec],
    default_constraints: Constraints,
    default_advance: str | None,
    default_end: str | None,
    allowed_events: set[str],
    errors: list[str],
    out: list[ResolvedStage],
) -> None:
    for i, raw in enumerate(stages_raw):
        loc = f"{parent_prefix}stages[{i}]"
        if not isinstance(raw, dict):
            errors.append(f"{loc} must be a mapping")
            continue
        if "repeat" in raw:
            _expand_block(
                raw,
                loc=loc,
                items=items,
                default_collect=default_collect,
                default_constraints=default_constraints,
                default_advance=default_advance,
                default_end=default_end,
                allowed_events=allowed_events,
                errors=errors,
                out=out,
            )
            continue
        stage = _resolve_leaf_stage(
            raw,
            loc=loc,
            block_id=block_id,
            block_label=block_label,
            trial_index=trial_index,
            trial_count=trial_count,
            catalog_item=catalog_item,
            default_collect=default_collect,
            default_constraints=default_constraints,
            default_advance=default_advance,
            default_end=default_end,
            allowed_events=allowed_events,
            errors=errors,
        )
        if stage is not None:
            out.append(stage)


def _expand_block(
    raw: dict[str, Any],
    *,
    loc: str,
    items: list[dict[str, Any]],
    default_collect: dict[str, CollectSpec],
    default_constraints: Constraints,
    default_advance: str | None,
    default_end: str | None,
    allowed_events: set[str],
    errors: list[str],
    out: list[ResolvedStage],
) -> None:
    repeat = raw.get("repeat") or {}
    if not isinstance(repeat, dict):
        errors.append(f"{loc}.repeat must be a mapping")
        return
    nested = raw.get("stages")
    if not isinstance(nested, list) or not nested:
        errors.append(f"{loc}.stages must be a non-empty list when repeat is set")
        return
    block_id = raw.get("id")
    if not isinstance(block_id, str) or not block_id:
        errors.append(f"{loc}.id is required for a repeat block")
        block_id = f"block_{loc}"
    block_label = raw.get("label") or block_id

    over = repeat.get("over")
    n = repeat.get("n")
    loop_items: list[dict[str, Any]]
    if over in {"catalog.paintings", "catalog"}:
        if not items:
            errors.append(f"{loc}.repeat.over={over!r} but catalog.paintings is empty")
        loop_items = list(items)
    elif isinstance(n, int) and n > 0:
        loop_items = [{"index": i} for i in range(n)]
    else:
        errors.append(f"{loc}.repeat needs over: catalog.paintings or n: <int>")
        loop_items = []

    # shuffle / counterbalance are placeholders — keep listed order.
    for idx, item in enumerate(loop_items):
        _expand_stage_list(
            nested,
            parent_prefix=f"{loc}.",
            block_id=str(block_id),
            block_label=str(block_label),
            trial_index=idx + 1,
            trial_count=len(loop_items),
            catalog_item=item,
            items=items,
            default_collect=default_collect,
            default_constraints=default_constraints,
            default_advance=default_advance,
            default_end=default_end,
            allowed_events=allowed_events,
            errors=errors,
            out=out,
        )


def _unique_stage_id(source_id: str, item: dict[str, Any], trial_index: int | None) -> str:
    if trial_index is None:
        return source_id
    if "${" in source_id:
        return source_id
    painting = item.get("painting_id")
    if painting:
        return f"{source_id}__{painting}"
    return f"{source_id}__{trial_index - 1}"


def _resolve_leaf_stage(
    raw: dict[str, Any],
    *,
    loc: str,
    block_id: str | None,
    block_label: str | None,
    trial_index: int | None,
    trial_count: int | None,
    catalog_item: dict[str, Any],
    default_collect: dict[str, CollectSpec],
    default_constraints: Constraints,
    default_advance: str | None,
    default_end: str | None,
    allowed_events: set[str],
    errors: list[str],
) -> ResolvedStage | None:
    ctx = _item_ctx(catalog_item, (trial_index - 1) if trial_index else 0)
    data = _substitute(copy.deepcopy(raw), ctx)
    source_id = data.get("id")
    if not isinstance(source_id, str) or not source_id.strip():
        errors.append(f"{loc}.id is required")
        return None
    stage_id = _unique_stage_id(source_id, catalog_item, trial_index)
    label = data.get("label") or source_id
    if not isinstance(label, str):
        errors.append(f"{loc}.label must be a string")
        label = source_id
    kind = data.get("kind")
    if kind not in KINDS:
        errors.append(f"{loc}.kind must be one of {sorted(KINDS)}")
        kind = "timed"

    advance = data.get("advance")
    if advance is None:
        advance = default_advance or KIND_DEFAULT_ADVANCE.get(kind, "auto")
    if advance not in ADVANCES:
        errors.append(f"{loc}.advance must be one of {sorted(ADVANCES)}")
        advance = "auto"

    end_signal = _normalize_end_signal(data, loc, errors)
    if end_signal is None:
        end_signal = default_end or "auto"

    either_policy = data.get("either_policy") or "both"
    if either_policy not in EITHER_POLICIES:
        errors.append(f"{loc}.either_policy must be one of {sorted(EITHER_POLICIES)}")
        either_policy = "both"

    duration_s = _duration(data.get("duration_s"), loc, errors)
    if advance == "auto" and (duration_s is None or duration_s <= 0) and end_signal != "operator":
        errors.append(
            f"{loc}: advance=auto requires duration_s > 0 unless end_signal is operator"
        )
    if advance == "either" and (duration_s is None or duration_s <= 0):
        errors.append(f"{loc}: advance=either requires duration_s > 0")
    if kind == "checklist" and advance not in {"operator", "either"}:
        errors.append(f"{loc}: kind=checklist should use advance operator or either")

    collect = _merge_collect(default_collect, _parse_collect(data.get("collect") or {}, f"{loc}.collect", errors))
    constraints = _merge_constraints(default_constraints, data.get("constraints") if isinstance(data.get("constraints"), dict) else None)
    if data.get("constraints") is not None and not isinstance(data.get("constraints"), dict):
        errors.append(f"{loc}.constraints must be a mapping")
    if kind == "stimulus" and constraints.allow_nuc:
        errors.append(f"{loc}: constraints.allow_nuc must be false on kind=stimulus")

    reminders = _parse_reminders(data.get("reminders"), loc, errors)
    checklist = _parse_checklist(data.get("checklist"), loc, errors)
    stimulus = _parse_stimulus(data.get("stimulus"), loc, errors)
    events = data.get("events") or {}
    if events is None:
        events = {}
    if events and not isinstance(events, dict):
        errors.append(f"{loc}.events must be a mapping")
        events = {}
    enter = _parse_event(events.get("enter"), f"{loc}.events.enter", allowed_events, errors)
    exit_ = _parse_event(events.get("exit"), f"{loc}.events.exit", allowed_events, errors)

    return ResolvedStage(
        id=stage_id,
        label=label,
        kind=str(kind),
        duration_s=duration_s,
        advance=str(advance),
        end_signal=str(end_signal),
        either_policy=str(either_policy),
        collect=collect,
        constraints=constraints,
        reminders=reminders,
        checklist=checklist,
        stimulus=stimulus,
        events_enter=enter,
        events_exit=exit_,
        block_id=block_id,
        block_label=str(block_label) if block_label else None,
        trial_index=trial_index,
        trial_count=trial_count,
        source_id=source_id,
        catalog_item=dict(catalog_item),
    )
