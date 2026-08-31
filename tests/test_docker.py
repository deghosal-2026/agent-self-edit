"""Docker tests for AgentSelfEdit (marked @pytest.mark.docker).

Run with: pytest tests/test_docker.py -v -m docker
Requires: Docker daemon running.
"""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.docker

REPO_ROOT = Path(__file__).resolve().parent.parent
IMAGE_TAG = "agent-self-edit:test"


def _build_image():
    result = subprocess.run(
        ["docker", "build", "-t", IMAGE_TAG, "."],
        capture_output=True, text=True, timeout=120, cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        pytest.fail(f"docker build failed:\n{result.stdout}\n{result.stderr}")
    return result


def _run_container(args: list[str], volumes: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    cmd = ["docker", "run", "--rm"]
    if volumes:
        for host, container in volumes.items():
            cmd.extend(["-v", f"{host}:{container}"])
    cmd.extend([IMAGE_TAG] + args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


def _create_test_config(tmp_path: Path) -> Path:
    config = {
        "schema_version": 1,
        "project": {"name": "docker-test", "registry_path": "/config/registry",
                    "trace_path": "/config/traces.db"},
        "tasks": {"task_set_path": "", "batch_size": 50, "sample_floor": 10},
        "llm": {"provider": "mock", "model": "m", "api_key": "",
                "temperature": 0.0, "max_tokens": 4096, "timeout": 30},
        "ab_test": {"n_resamples": 100, "n_permutations": 100,
                    "confidence_level": 0.95, "min_effect_size": 0.05,
                    "cost_ceiling_usd": 0.10},
        "gate": {"max_edit_distance": 20, "drift_threshold": 0.3, "near_miss_threshold": 0.5},
        "analyzer": {"max_proposals_per_batch": 3, "cost_ceiling_usd": 0.50},
        "trigger": "batch", "trace_retention_days": 90,
    }
    config_path = tmp_path / "agent-self-edit.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    return config_path


# ---- Build ----

def test_docker_build():
    """Build the Docker image."""
    result = subprocess.run(
        ["docker", "build", "-t", IMAGE_TAG, "."],
        capture_output=True, text=True, timeout=120, cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"Build failed: {result.stderr}"


# ---- Smoke ----

def test_docker_help():
    """agent-self-edit --help lists all 10 commands."""
    result = _run_container(["--help"])
    assert result.returncode == 0
    for cmd in ["init", "run", "status", "diff", "rollback", "guardrails", "lineage", "propose", "ingest", "validate"]:
        assert cmd in result.stdout, f"Missing command: {cmd}"


def test_docker_validate():
    """agent-self-edit validate with a config file."""
    with tempfile.TemporaryDirectory() as tmp:
        config_path = _create_test_config(Path(tmp))
        volumes = {str(config_path.parent): "/config"}
        result = _run_container(
            ["validate", "--config", "/config/agent-self-edit.yaml"],
            volumes=volumes,
        )
        assert result.returncode in (0, 2)


def test_docker_status():
    """agent-self-edit status with config."""
    with tempfile.TemporaryDirectory() as tmp:
        config_path = _create_test_config(Path(tmp))
        volumes = {str(config_path.parent): "/config"}
        result = _run_container(
            ["status", "--config", "/config/agent-self-edit.yaml"],
            volumes=volumes,
        )
        assert result.returncode in (0, 1, 2)


# ---- Integration ----

def test_docker_run_dry_run():
    """agent-self-edit run --once --dry-run with mock providers."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config_path = _create_test_config(tmp_path)

        # Create registry and a prompt version
        from agent_self_edit.registry import Registry
        reg = Registry(str(tmp_path / "registry"))
        reg.create("You are a classifier assistant.")

        # Create a trace store with pending traces
        from agent_self_edit.trace import TraceStore
        store = TraceStore(str(tmp_path / "traces.db"), batch_size=10)
        for i in range(5):
            store.ingest({
                "task_id": f"t{i}", "task_input": "x", "final_output": "wrong",
                "expected_output": "right", "success": False,
                "timestamp": "2026-09-01T10:00:00Z",
            })

        volumes = {str(tmp_path): "/config"}
        result = _run_container(
            ["run", "--config", "/config/agent-self-edit.yaml", "--once", "--dry-run"],
            volumes=volumes,
        )
        assert result.returncode in (0, None), f"stdout: {result.stdout}\nstderr: {result.stderr}"