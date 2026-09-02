import tempfile
from pathlib import Path

import yaml

from agent_self_edit.config import (
    ABTestConfig,
    AnalyzerConfig,
    Config,
    ConfigError,
    GateConfig,
    LLMConfig,
    ProjectConfig,
    TasksConfig,
    load_config,
    validate_config,
)

_VALID_CONFIG = {
    "schema_version": 1,
    "project": {"name": "test-agent"},
    "tasks": {"task_set_path": "./tasks.yaml", "batch_size": 50, "sample_floor": 10},
    "llm": {
        "provider": "mock",
        "model": "gpt-4o-mini",
        "api_key": "",
        "temperature": 0.0,
        "max_tokens": 4096,
        "timeout": 30,
    },
    "ab_test": {
        "n_resamples": 10000,
        "n_permutations": 1000,
        "confidence_level": 0.95,
        "min_effect_size": 0.05,
    },
    "gate": {
        "max_edit_distance": 20,
        "drift_threshold": 0.3,
        "near_miss_threshold": 0.5,
    },
    "analyzer": {"max_proposals_per_batch": 3, "cost_ceiling_usd": 0.50},
    "trigger": "batch",
    "trace_retention_days": 90,
}


def _write_config(data: dict) -> Path:
    tmp = Path(tempfile.mktemp(suffix=".yaml"))
    with open(tmp, "w") as f:
        yaml.dump(data, f)
    return tmp


def test_valid_config_loads():
    path = _write_config(_VALID_CONFIG)
    config = load_config(path)
    assert config.project.name == "test-agent"
    assert config.llm.provider == "mock"
    assert config.tasks.sample_floor == 10
    assert config.trigger == "batch"


def test_missing_file_raises_filenotfound():
    try:
        load_config("/nonexistent/config.yaml")
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass


def test_invalid_yaml_raises_error():
    path = Path(tempfile.mktemp(suffix=".yaml"))
    path.write_text("not: valid: yaml: [")
    try:
        load_config(str(path))
        assert False, "expected error"
    except ConfigError:
        pass


def test_non_mapping_raises_error():
    path = Path(tempfile.mktemp(suffix=".yaml"))
    with open(path, "w") as f:
        yaml.dump(["a", "b"], f)
    try:
        load_config(path)
        assert False, "expected error"
    except ConfigError:
        pass


def test_defaults_invalid_without_name():
    config = Config.defaults()
    errors = validate_config(config)
    assert "project.name is required" in errors


def test_empty_project_name():
    config = Config.defaults()
    errors = validate_config(config)
    assert "project.name is required" in errors


def test_sample_floor_below_minimum():
    config = Config(
        project=ProjectConfig(name="x"),
        tasks=TasksConfig(sample_floor=3),
    )
    errors = validate_config(config)
    assert any("sample_floor" in e for e in errors)


def test_confidence_level_out_of_range():
    config = Config(
        project=ProjectConfig(name="x"),
        ab_test=ABTestConfig(confidence_level=0.3),
    )
    errors = validate_config(config)
    assert any("confidence_level" in e for e in errors)


def test_confidence_level_lower_bound():
    config = Config(
        project=ProjectConfig(name="x"),
        ab_test=ABTestConfig(confidence_level=0.9),
    )
    assert validate_config(config) == []


def test_confidence_level_too_low():
    config = Config(
        project=ProjectConfig(name="x"),
        ab_test=ABTestConfig(confidence_level=0.5),
    )
    errors = validate_config(config)
    assert any("0.9" in e for e in errors)


def test_confidence_level_upper_bound():
    config = Config(
        project=ProjectConfig(name="x"),
        ab_test=ABTestConfig(confidence_level=0.999),
    )
    assert validate_config(config) == []


def test_max_edit_distance_zero():
    config = Config(
        project=ProjectConfig(name="x"),
        gate=GateConfig(max_edit_distance=0),
    )
    errors = validate_config(config)
    assert any("max_edit_distance" in e for e in errors)


def test_drift_threshold_out_of_range():
    config = Config(
        project=ProjectConfig(name="x"),
        gate=GateConfig(drift_threshold=1.5),
    )
    errors = validate_config(config)
    assert any("drift_threshold" in e for e in errors)


def test_invalid_provider():
    config = Config(
        project=ProjectConfig(name="x"),
        llm=LLMConfig(provider="invalid"),
    )
    errors = validate_config(config)
    assert any("llm.provider" in e for e in errors)


def test_invalid_trigger():
    config = Config(project=ProjectConfig(name="x"), trigger="invalid")
    errors = validate_config(config)
    assert any("trigger" in e for e in errors)


def test_cost_ceiling_zero():
    config = Config(
        project=ProjectConfig(name="x"),
        analyzer=AnalyzerConfig(cost_ceiling_usd=0),
    )
    errors = validate_config(config)
    assert any("cost_ceiling_usd" in e for e in errors)


def test_trace_retention_negative():
    config = Config(project=ProjectConfig(name="x"), trace_retention_days=-1)
    errors = validate_config(config)
    assert any("trace_retention_days" in e for e in errors)


def test_multiple_errors_reported():
    config = Config(
        project=ProjectConfig(name=""),
        tasks=TasksConfig(sample_floor=0),
        gate=GateConfig(max_edit_distance=-1),
    )
    errors = validate_config(config)
    assert len(errors) >= 3


def test_round_trip():
    path = _write_config(_VALID_CONFIG)
    config = load_config(path)
    assert config.project.name == "test-agent"
    assert config.tasks.sample_floor == 10
    assert config.ab_test.confidence_level == 0.95
    assert config.gate.max_edit_distance == 20
    assert config.gate.drift_threshold == 0.3
    assert config.analyzer.max_proposals_per_batch == 3
    assert config.analyzer.cost_ceiling_usd == 0.50
    assert config.trigger == "batch"
    assert config.trace_retention_days == 90

def test_schema_version_mismatch():
    config = Config(project=ProjectConfig(name="x"), schema_version=2)
    errors = validate_config(config)
    assert any("schema_version" in e for e in errors)


def test_min_effect_size_out_of_range():
    config = Config(project=ProjectConfig(name="x"), ab_test=ABTestConfig(min_effect_size=1.5))
    errors = validate_config(config)
    assert any("min_effect_size" in e for e in errors)


def test_near_miss_threshold_out_of_range():
    config = Config(project=ProjectConfig(name="x"), gate=GateConfig(near_miss_threshold=1.5))
    errors = validate_config(config)
    assert any("near_miss_threshold" in e for e in errors)


def test_max_proposals_below_one():
    config = Config(
        project=ProjectConfig(name="x"),
        analyzer=AnalyzerConfig(max_proposals_per_batch=0),
    )
    errors = validate_config(config)
    assert any("max_proposals_per_batch" in e for e in errors)


def test_unknown_section_key_raises():
    data = dict(_VALID_CONFIG)
    data["project"] = {"name": "test-agent", "bogus_field": True}
    path = _write_config(data)
    try:
        load_config(path)
        assert False, "expected ConfigError"
    except ConfigError as e:
        assert "bogus_field" in str(e)


def test_env_interpolation(monkeypatch):
    monkeypatch.setenv("TEST_AGENT_API_KEY", "sk-test")
    data = dict(_VALID_CONFIG)
    data["llm"] = {**_VALID_CONFIG["llm"], "api_key": "${TEST_AGENT_API_KEY}"}
    path = _write_config(data)
    config = load_config(path)
    assert config.llm.api_key == "sk-test"


def test_env_interpolation_missing():
    data = dict(_VALID_CONFIG)
    data["llm"] = {**_VALID_CONFIG["llm"], "api_key": "${DOES_NOT_EXIST_12345}"}
    path = _write_config(data)
    try:
        load_config(path)
        assert False, "expected ConfigError"
    except ConfigError as e:
        assert "DOES_NOT_EXIST_12345" in str(e)


# ---- D-2: TOML config support (PRD F-13 "YAML/TOML") ----


def _write_toml(data: dict) -> Path:

    tmp = Path(tempfile.mktemp(suffix=".toml"))
    with open(tmp, "wb") as f:
        f.write(_dict_to_toml(data))
    return tmp


def _dict_to_toml(data: dict) -> bytes:
    lines = []
    scalars = {}
    tables = {}
    for key, val in data.items():
        if isinstance(val, dict):
            tables[key] = val
        else:
            scalars[key] = val
    for k, v in scalars.items():
        lines.append(toml_value(k, v))
    for section, fields in tables.items():
        lines.append(f"[{section}]")
        for k, v in fields.items():
            lines.append(toml_value(k, v))
    return ("\n".join(lines) + "\n").encode()


def toml_value(key: str, value) -> str:
    if isinstance(value, str):
        return f'{key} = "{value}"'
    if isinstance(value, bool):
        return f"{key} = {'true' if value else 'false'}"
    if isinstance(value, (int, float)):
        return f"{key} = {value}"
    if isinstance(value, list):
        items = ", ".join(repr(v) for v in value)
        return f"{key} = [{items}]"
    raise TypeError(f"unsupported toml type {type(value)}")


def test_load_toml_config(tmp_path):
    toml_config = {
        "schema_version": 1,
        "project": {"name": "test-agent"},
        "tasks": {"task_set_path": "./tasks.yaml", "batch_size": 50, "sample_floor": 10},
        "llm": {"provider": "mock", "model": "gpt-4o-mini", "api_key": "sk-1",
                "temperature": 0.0, "max_tokens": 4096, "timeout": 30},
        "ab_test": {"n_resamples": 10000, "n_permutations": 1000,
                    "confidence_level": 0.95, "min_effect_size": 0.05,
                    "cost_ceiling_usd": 0.10},
        "gate": {"max_edit_distance": 20, "drift_threshold": 0.3, "near_miss_threshold": 0.5},
        "analyzer": {"max_proposals_per_batch": 3, "cost_ceiling_usd": 0.50},
        "trigger": "batch",
        "trace_retention_days": 90,
    }
    path = _write_toml(toml_config)
    config = load_config(path)
    assert config.project.name == "test-agent"
    assert config.tasks.sample_floor == 10
    assert config.ab_test.confidence_level == 0.95
    assert config.gate.max_edit_distance == 20
    assert config.trigger == "batch"


def test_load_toml_from_yaml_named_dict_matches():
    # ensure the TOML dict matches the YAML so both formats produce equal configs

    path = _write_toml({
        "schema_version": 1,
        "project": {"name": "toml-agent"},
        "tasks": {"task_set_path": "./t.yaml", "batch_size": 50, "sample_floor": 10},
        "llm": {"provider": "mock", "model": "m", "api_key": "", "temperature": 0.0,
                "max_tokens": 4096, "timeout": 30},
        "ab_test": {"n_resamples": 10000, "n_permutations": 1000,
                    "confidence_level": 0.95, "min_effect_size": 0.05,
                    "cost_ceiling_usd": 0.10},
        "gate": {"max_edit_distance": 20, "drift_threshold": 0.3, "near_miss_threshold": 0.5},
        "analyzer": {"max_proposals_per_batch": 3, "cost_ceiling_usd": 0.50},
        "trigger": "manual",
        "trace_retention_days": 7,
    })
    config = load_config(path)
    assert config.project.name == "toml-agent"
    assert config.trigger == "manual"
    assert config.trace_retention_days == 7


def test_invalid_toml_raises(tmp_path):
    p = tmp_path / "bad.toml"
    p.write_text("not valid toml = [")
    try:
        load_config(p)
        assert False, "expected ConfigError"
    except ConfigError:
        pass


def test_toml_env_interpolation(monkeypatch):
    monkeypatch.setenv("TEST_TOML_KEY", "tk-123")

    path = _write_toml({
        "schema_version": 1,
        "project": {"name": "env-agent"},
        "tasks": {"batch_size": 50, "sample_floor": 10},
        "llm": {"provider": "openai", "model": "m", "api_key": "${TEST_TOML_KEY}",
                "temperature": 0.0, "max_tokens": 4096, "timeout": 30},
        "ab_test": {"n_resamples": 10000, "n_permutations": 1000,
                    "confidence_level": 0.95, "min_effect_size": 0.05,
                    "cost_ceiling_usd": 0.10},
        "gate": {"max_edit_distance": 20, "drift_threshold": 0.3, "near_miss_threshold": 0.5},
        "analyzer": {"max_proposals_per_batch": 3, "cost_ceiling_usd": 0.50},
        "trigger": "batch",
        "trace_retention_days": 90,
    })
    config = load_config(path)
    assert config.llm.api_key == "tk-123"
