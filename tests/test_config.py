from __future__ import annotations

import copy

import pytest
import yaml

from quantum_platform.config import ConfigError, load_experiment, validate_and_resolve


def test_example_loads(example_yaml):
    plan = load_experiment(example_yaml)
    assert plan.id == "painting_session_simplified"
    assert plan.schema_version == 1
    ids = [s.id for s in plan.stages]
    assert "setup" in ids
    assert "baseline" in ids
    assert "hang_painting" in ids
    assert "fixation__Q001" in ids
    assert "exposure__S001" in ids
    assert "closeout" in ids
    assert len(plan.stages) == 4 + 2 * 3 + 1  # setup, cal, baseline, hang, 2 trials, closeout
    exposure_q = next(s for s in plan.stages if s.id == "exposure__Q001")
    assert exposure_q.stimulus is not None
    assert exposure_q.stimulus.painting_id == "Q001"
    assert exposure_q.stimulus.condition == "quantum"
    assert exposure_q.constraints.allow_nuc is False
    baseline = next(s for s in plan.stages if s.id == "baseline")
    assert baseline.end_signal == "operator"
    assert baseline.advance == "auto"


def test_unknown_schema_version():
    with pytest.raises(ConfigError) as exc:
        validate_and_resolve({"schema_version": 2, "id": "x", "name": "x", "stages": [{"id": "a", "kind": "timed", "duration_s": 1, "advance": "auto"}]})
    assert any("schema_version" in e for e in exc.value.errors)


def test_unknown_kind_fails():
    with pytest.raises(ConfigError) as exc:
        validate_and_resolve(
            {
                "schema_version": 1,
                "id": "x",
                "name": "x",
                "stages": [{"id": "a", "kind": "dance", "duration_s": 1, "advance": "auto"}],
            }
        )
    assert any("kind" in e for e in exc.value.errors)


def test_unknown_collect_key_fails():
    with pytest.raises(ConfigError) as exc:
        validate_and_resolve(
            {
                "schema_version": 1,
                "id": "x",
                "name": "x",
                "stages": [
                    {
                        "id": "a",
                        "kind": "timed",
                        "duration_s": 1,
                        "advance": "auto",
                        "collect": {"audio": True},
                    }
                ],
            }
        )
    assert any("collect" in e for e in exc.value.errors)


def test_unknown_reminder_when_fails():
    with pytest.raises(ConfigError) as exc:
        validate_and_resolve(
            {
                "schema_version": 1,
                "id": "x",
                "name": "x",
                "stages": [
                    {
                        "id": "a",
                        "kind": "timed",
                        "duration_s": 1,
                        "advance": "auto",
                        "reminders": [{"text": "hi", "when": "whenever"}],
                    }
                ],
            }
        )
    assert any("when" in e for e in exc.value.errors)


def test_auto_requires_duration_unless_end_signal_operator():
    with pytest.raises(ConfigError) as exc:
        validate_and_resolve(
            {
                "schema_version": 1,
                "id": "x",
                "name": "x",
                "stages": [{"id": "a", "kind": "timed", "duration_s": None, "advance": "auto"}],
            }
        )
    assert any("duration_s" in e for e in exc.value.errors)

    plan = validate_and_resolve(
        {
            "schema_version": 1,
            "id": "x",
            "name": "x",
            "stages": [
                {
                    "id": "a",
                    "kind": "rest",
                    "duration_s": None,
                    "advance": "auto",
                    "end_signal": "operator",
                }
            ],
        }
    )
    assert plan.stages[0].end_signal == "operator"


def test_confirm_end_alias():
    plan = validate_and_resolve(
        {
            "schema_version": 1,
            "id": "x",
            "name": "x",
            "stages": [
                {
                    "id": "a",
                    "kind": "rest",
                    "duration_s": 3,
                    "advance": "auto",
                    "confirm_end": True,
                }
            ],
        }
    )
    assert plan.stages[0].end_signal == "operator"


def test_stimulus_allow_nuc_rejected():
    with pytest.raises(ConfigError) as exc:
        validate_and_resolve(
            {
                "schema_version": 1,
                "id": "x",
                "name": "x",
                "stages": [
                    {
                        "id": "a",
                        "kind": "stimulus",
                        "duration_s": 1,
                        "advance": "auto",
                        "constraints": {"allow_nuc": True},
                    }
                ],
            }
        )
    assert any("allow_nuc" in e for e in exc.value.errors)


def test_unknown_event_name_fails():
    with pytest.raises(ConfigError) as exc:
        validate_and_resolve(
            {
                "schema_version": 1,
                "id": "x",
                "name": "x",
                "stages": [
                    {
                        "id": "a",
                        "kind": "timed",
                        "duration_s": 1,
                        "advance": "auto",
                        "events": {"enter": {"name": "not_a_real_event"}},
                    }
                ],
            }
        )
    assert any("not_a_real_event" in e for e in exc.value.errors)


def test_events_extra_allow_list():
    plan = validate_and_resolve(
        {
            "schema_version": 1,
            "id": "x",
            "name": "x",
            "events_extra": ["custom_mark"],
            "stages": [
                {
                    "id": "a",
                    "kind": "timed",
                    "duration_s": 1,
                    "advance": "auto",
                    "events": {"enter": {"name": "custom_mark"}},
                }
            ],
        }
    )
    assert plan.stages[0].events_enter is not None
    assert plan.stages[0].events_enter.name == "custom_mark"


def test_block_expansion_unique_ids(tmp_path):
    raw = {
        "schema_version": 1,
        "id": "blk",
        "name": "blk",
        "catalog": {"paintings": [{"painting_id": "A", "condition": "quantum"}, {"painting_id": "B", "condition": "standard"}]},
        "stages": [
            {
                "id": "block",
                "repeat": {"over": "catalog.paintings"},
                "stages": [
                    {
                        "id": "fix",
                        "kind": "timed",
                        "duration_s": 1,
                        "advance": "auto",
                    }
                ],
            }
        ],
    }
    plan = validate_and_resolve(raw)
    assert [s.id for s in plan.stages] == ["fix__A", "fix__B"]


def test_missing_required_fields():
    with pytest.raises(ConfigError):
        validate_and_resolve({"schema_version": 1, "id": "x", "name": "x", "stages": []})


def test_example_roundtrip_yaml_text(example_yaml):
    # The repo example should stay a valid YAML document matching the docs sketch.
    data = yaml.safe_load(example_yaml.read_text(encoding="utf-8"))
    assert data["id"] == "painting_session_simplified"
    assert data["catalog"]["paintings"][0]["painting_id"] == "Q001"
    cloned = copy.deepcopy(data)
    plan = validate_and_resolve(cloned)
    assert plan.resolved_order == ["Q001", "S001"]
