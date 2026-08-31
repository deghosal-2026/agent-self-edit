import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib
import yaml


class ConfigError(Exception):
    """Raised on config validation failure."""


@dataclass(frozen=True)
class ProjectConfig:
    name: str = ""
    registry_path: str = "./registry"
    trace_path: str = "./traces.db"


@dataclass(frozen=True)
class TasksConfig:
    task_set_path: str = "./tasks.yaml"
    batch_size: int = 50
    sample_floor: int = 10


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout: int = 30


@dataclass(frozen=True)
class ABTestConfig:
    n_resamples: int = 10000
    n_permutations: int = 1000
    confidence_level: float = 0.95
    min_effect_size: float = 0.05
    cost_ceiling_usd: float = 0.10


@dataclass(frozen=True)
class GateConfig:
    max_edit_distance: int = 20
    drift_threshold: float = 0.3
    near_miss_threshold: float = 0.5


@dataclass(frozen=True)
class AnalyzerConfig:
    max_proposals_per_batch: int = 3
    cost_ceiling_usd: float = 0.50


@dataclass(frozen=True)
class Config:
    schema_version: int = 1
    project: ProjectConfig = field(default_factory=lambda: ProjectConfig())
    tasks: TasksConfig = field(default_factory=lambda: TasksConfig())
    llm: LLMConfig = field(default_factory=lambda: LLMConfig())
    ab_test: ABTestConfig = field(default_factory=lambda: ABTestConfig())
    gate: GateConfig = field(default_factory=lambda: GateConfig())
    analyzer: AnalyzerConfig = field(default_factory=lambda: AnalyzerConfig())
    trigger: str = "batch"
    trace_retention_days: int = 90

    @classmethod
    def defaults(cls) -> "Config":
        return cls()


def _interpolate_env(value: Any) -> Any:
    if isinstance(value, str):
        match = re.fullmatch(r"\$\{(\w+)\}", value)
        if match:
            env_val = os.environ.get(match.group(1))
            if env_val is None:
                raise ConfigError(f"Environment variable '{match.group(1)}' is not set")
            return env_val
    return value


def _deep_interpolate(raw: Any) -> Any:
    if isinstance(raw, dict):
        return {k: _deep_interpolate(v) for k, v in raw.items()}
    if isinstance(raw, list):
        return [_deep_interpolate(v) for v in raw]
    return _interpolate_env(raw)


def _build_config(data: dict[str, Any]) -> Config:
    try:
        return Config(
            schema_version=data.get("schema_version", 1),
            project=ProjectConfig(**data.get("project", {})),
            tasks=TasksConfig(**data.get("tasks", {})),
            llm=LLMConfig(**data.get("llm", {})),
            ab_test=ABTestConfig(**data.get("ab_test", {})),
            gate=GateConfig(**data.get("gate", {})),
            analyzer=AnalyzerConfig(**data.get("analyzer", {})),
            trigger=data.get("trigger", "batch"),
            trace_retention_days=data.get("trace_retention_days", 90),
        )
    except TypeError as e:
        raise ConfigError(str(e)) from e


def load_config(path: str | Path) -> Config:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    if path.suffix in (".toml",):
        raw = _load_toml(path)
    else:
        raw = _load_yaml(path)
    if not isinstance(raw, dict):
        raise ConfigError("Config file must contain a mapping")
    raw = _deep_interpolate(raw)
    config = _build_config(raw)
    errors = validate_config(config)
    if errors:
        raise ConfigError("; ".join(errors))
    return config


def _load_yaml(path: Path) -> Any:
    with open(path) as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in config file: {e}") from e


def _load_toml(path: Path) -> Any:
    with open(path, "rb") as f:
        try:
            return tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ConfigError(f"Invalid TOML in config file: {e}") from e


def validate_config(config: Config) -> list[str]:
    errors: list[str] = []

    if config.schema_version != 1:
        errors.append(f"schema_version must be 1, got {config.schema_version}")

    if not config.project.name:
        errors.append("project.name is required")

    if config.tasks.sample_floor < 10:
        errors.append(f"sample_floor must be >= 10, got {config.tasks.sample_floor}")

    if not (0.5 <= config.ab_test.confidence_level <= 0.999):
        errors.append(
            f"confidence_level must be between 0.5 and 0.999, got {config.ab_test.confidence_level}"
        )

    if not (0 <= config.ab_test.min_effect_size <= 1):
        errors.append(
            f"min_effect_size must be between 0 and 1, got {config.ab_test.min_effect_size}"
        )

    if config.ab_test.cost_ceiling_usd <= 0:
        errors.append(
            f"cost_ceiling_usd must be > 0, got {config.ab_test.cost_ceiling_usd}"
        )

    if config.gate.max_edit_distance < 1:
        errors.append(
            f"max_edit_distance must be > 0, got {config.gate.max_edit_distance}"
        )

    if not (0 <= config.gate.drift_threshold <= 1):
        errors.append(
            f"drift_threshold must be between 0 and 1, got {config.gate.drift_threshold}"
        )

    if not (0 <= config.gate.near_miss_threshold <= 1):
        errors.append(
            f"near_miss_threshold must be between 0 and 1, got {config.gate.near_miss_threshold}"
        )

    if config.llm.provider not in ("openai", "mock"):
        errors.append(
            f"llm.provider must be 'openai' or 'mock', got '{config.llm.provider}'"
        )

    if config.analyzer.max_proposals_per_batch < 1:
        errors.append(
            f"max_proposals_per_batch must be >= 1, got {config.analyzer.max_proposals_per_batch}"
        )

    if config.analyzer.cost_ceiling_usd <= 0:
        errors.append(
            f"cost_ceiling_usd must be > 0, got {config.analyzer.cost_ceiling_usd}"
        )

    if config.trigger not in ("batch", "time", "manual"):
        errors.append(
            f"trigger must be one of: batch, time, manual, got '{config.trigger}'"
        )

    if config.trace_retention_days < 0:
        errors.append(
            f"trace_retention_days must be >= 0, got {config.trace_retention_days}"
        )

    return errors
