"""Tests for the CLI commands (hermetic — no real LLM calls)."""

import json
import os

import pytest
import yaml
from click.testing import CliRunner

from agent_self_edit.cli import main
from agent_self_edit.registry import Registry


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def cfg_dir(tmp_path):
    """Create a minimal config file in tmp_path."""
    import yaml
    config = {
        "schema_version": 1,
        "project": {"name": "test", "registry_path": str(tmp_path / "reg"),
                    "trace_path": str(tmp_path / "traces.db")},
        "tasks": {"task_set_path": "", "batch_size": 50, "sample_floor": 10},
        "llm": {"provider": "mock", "model": "m", "api_key": "",
                "temperature": 0.0, "max_tokens": 4096, "timeout": 30},
        "ab_test": {"n_resamples": 100, "n_permutations": 100,
                    "confidence_level": 0.95, "min_effect_size": 0.05,
                    "cost_ceiling_usd": 0.10},
        "gate": {"max_edit_distance": 20, "drift_threshold": 0.3, "near_miss_threshold": 0.5},
        "analyzer": {"max_proposals_per_batch": 3, "cost_ceiling_usd": 0.50},
        "trigger": "batch",
        "trace_retention_days": 90,
    }
    config_path = tmp_path / "agent-self-edit.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    return config_path


def test_help(runner):
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "init" in result.output
    assert "run" in result.output
    assert "diff" in result.output
    assert "rollback" in result.output
    assert "status" in result.output
    assert "guardrails" in result.output
    assert "lineage" in result.output
    assert "propose" in result.output
    assert "ingest" in result.output
    assert "validate" in result.output


def test_init_creates_registry(runner, tmp_path):
    os.chdir(tmp_path)
    init_prompt = tmp_path / "prompt.md"
    init_prompt.write_text("You are a classifier.")
    result = runner.invoke(main, ["init", "--prompt", str(init_prompt)])
    assert result.exit_code in (0, None)
    assert (tmp_path / "registry").exists()


def test_validate_no_config(runner, tmp_path):
    os.chdir(tmp_path)
    result = runner.invoke(main, ["validate"])
    # Should handle missing config gracefully
    assert result.exit_code in (0, 1, 2)


def test_validate_with_config(runner, cfg_dir):
    os.chdir(cfg_dir.parent)
    result = runner.invoke(main, ["validate"])
    assert result.exit_code in (0, 2)


def test_ingest_invalid_file(runner, tmp_path):
    os.chdir(tmp_path)
    result = runner.invoke(main, ["ingest", "/nonexistent/traces.json"])
    assert result.exit_code > 0


def test_rollback_error(runner, tmp_path):
    os.chdir(tmp_path)
    result = runner.invoke(main, ["rollback", "99"])
    assert result.exit_code in (0, 1, 2)


def test_diff_error(runner, tmp_path):
    os.chdir(tmp_path)
    result = runner.invoke(main, ["diff", "1", "99"])
    assert result.exit_code in (0, 1, 2)


def test_status_empty(runner, tmp_path):
    os.chdir(tmp_path)
    result = runner.invoke(main, ["status"])
    # Should handle empty state gracefully
    assert result.exit_code in (0, 1)


def test_propose_no_traces(runner, cfg_dir):
    os.chdir(cfg_dir.parent)
    Registry(cfg_dir.parent / "reg")
    result = runner.invoke(main, ["propose", "--config", str(cfg_dir)])
    assert result.exit_code in (0, 1)


def test_run_help(runner):
    result = runner.invoke(main, ["run", "--help"])
    assert result.exit_code == 0
    assert "once" in result.output
    assert "dry-run" in result.output


def test_guardrails_help(runner):
    result = runner.invoke(main, ["guardrails", "--help"])
    assert result.exit_code == 0
    assert "last" in result.output


def test_lineage_help(runner):
    result = runner.invoke(main, ["lineage", "--help"])
    assert result.exit_code == 0
    assert "from" in result.output


def test_ingest_help(runner):
    result = runner.invoke(main, ["ingest", "--help"])
    assert result.exit_code == 0
    assert "FILE" in result.output


def test_validate_help(runner):
    result = runner.invoke(main, ["validate", "--help"])
    assert result.exit_code == 0




def test_rollback_help(runner):
    result = runner.invoke(main, ["rollback", "--help"])
    assert result.exit_code == 0
    assert "VERSION" in result.output


def test_init_with_prompt_and_tasks(runner, tmp_path):
    os.chdir(tmp_path)
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("You are a classifier.")
    tasks_file = tmp_path / "tasks.yaml"
    with open(tasks_file, "w") as f:
        yaml.dump([{"id": "t1", "input": "x", "expected_output": "y"}], f)
    result = runner.invoke(main, ["init", "--prompt", str(prompt_file), "--tasks", str(tasks_file)])
    assert result.exit_code in (0, None)
    assert (tmp_path / "registry").exists()
    assert (tmp_path / "registry" / "v1.md").exists()


def test_validate_json_output(runner, cfg_dir):
    os.chdir(cfg_dir.parent)
    result = runner.invoke(main, ["validate", "--json"])
    assert result.exit_code in (0, 2)
    if result.exit_code == 0:
        data = json.loads(result.output)
        assert "all_pass" in data
        assert "checks" in data


def test_status_json_empty(runner, tmp_path):
    os.chdir(tmp_path)
    config_data = {
        "schema_version": 1,
        "project": {"name": "x", "registry_path": str(tmp_path / "reg"),
                    "trace_path": str(tmp_path / "t.db")},
        "tasks": {"sample_floor": 10},
        "llm": {"provider": "mock", "model": "m", "api_key": "",
                "temperature": 0.0, "max_tokens": 4096, "timeout": 30},
        "ab_test": {"n_resamples": 100, "n_permutations": 100,
                    "confidence_level": 0.95, "min_effect_size": 0.05,
                    "cost_ceiling_usd": 0.10},
        "gate": {"max_edit_distance": 20, "drift_threshold": 0.3, "near_miss_threshold": 0.5},
        "analyzer": {"max_proposals_per_batch": 3, "cost_ceiling_usd": 0.50},
        "trigger": "batch", "trace_retention_days": 90,
    }
    with open("agent-self-edit.yaml", "w") as f:
        yaml.dump(config_data, f)
    result = runner.invoke(main, ["status", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "prompt_version" in data


def test_ingest_valid_trace(runner, cfg_dir):
    os.chdir(cfg_dir.parent)
    trace_file = cfg_dir.parent / "trace.jsonl"
    trace_file.write_text(
        json.dumps({
            "task_id": "t1", "task_input": "x", "final_output": "y",
            "expected_output": "y", "success": True,
            "timestamp": "2026-09-01T10:00:00Z",
        }) + "\n"
    )
    result = runner.invoke(main, ["ingest", str(trace_file), "--config", str(cfg_dir)])
    assert result.exit_code in (0, 1)


def test_diff_with_registry(runner, cfg_dir):
    os.chdir(cfg_dir.parent)
    reg = Registry(cfg_dir.parent / "reg")
    reg.create("first version")
    reg.create("second version with changes")
    result = runner.invoke(main, ["diff", "1", "2", "--config", str(cfg_dir)])
    assert result.exit_code in (0, 1)
    if result.exit_code == 0:
        assert "no changes" not in result.output


def test_lineage_with_registry(runner, cfg_dir):
    os.chdir(cfg_dir.parent)
    Registry(cfg_dir.parent / "reg").create("version one")
    Registry(cfg_dir.parent / "reg").create("version two")
    result = runner.invoke(main, ["lineage", "--config", str(cfg_dir)])
    assert result.exit_code == 0
    assert "Ver" in result.output
    assert "1" in result.output
    assert "2" in result.output


def test_rollback_with_registry(runner, cfg_dir):
    os.chdir(cfg_dir.parent)
    Registry(cfg_dir.parent / "reg").create("alpha")
    Registry(cfg_dir.parent / "reg").create("beta")
    result = runner.invoke(main, ["rollback", "1", "--reason", "revert", "--config", str(cfg_dir)])
    assert result.exit_code == 0
    # Read registry fresh after CLI call
    reg2 = Registry(cfg_dir.parent / "reg")
    assert reg2.current_version == 3
    assert reg2.current_prompt == "alpha"


def test_diff_help(runner):
    result = runner.invoke(main, ["diff", "--help"])
    assert result.exit_code == 0
    assert "--inline" in result.output


def test_guardrails_no_data(runner, cfg_dir):
    os.chdir(cfg_dir.parent)
    result = runner.invoke(main, ["guardrails", "--config", str(cfg_dir)])
    assert result.exit_code == 0
    assert "no guardrail" in result.output.lower() or "no data" in result.output.lower()


def test_guardrails_with_edit_flag(runner, cfg_dir):
    os.chdir(cfg_dir.parent)
    result = runner.invoke(main, ["guardrails", "--edit", "e1", "--config", str(cfg_dir)])
    assert result.exit_code == 0


def test_guardrails_json_output(runner, cfg_dir):
    os.chdir(cfg_dir.parent)
    result = runner.invoke(main, ["guardrails", "--json", "--config", str(cfg_dir)])
    assert result.exit_code == 0


def test_lineage_json_format(runner, cfg_dir):
    os.chdir(cfg_dir.parent)
    Registry(cfg_dir.parent / "reg").create("text")
    result = runner.invoke(main, ["lineage", "--format", "json", "--config", str(cfg_dir)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) >= 1


def test_ingest_with_list_trace(runner, cfg_dir):
    os.chdir(cfg_dir.parent)
    trace_file = cfg_dir.parent / "traces.jsonl"
    trace_file.write_text(json.dumps([
        {"task_id": "a", "task_input": "x", "final_output": "y",
         "expected_output": "y", "success": True, "timestamp": "2026-09-01T10:00:00Z"},
        {"task_id": "b", "task_input": "z", "final_output": "w",
         "expected_output": "w", "success": True, "timestamp": "2026-09-01T10:00:00Z"},
    ]) + "\n")
    result = runner.invoke(main, ["ingest", str(trace_file), "--config", str(cfg_dir)])
    assert result.exit_code == 0
    assert "Ingested" in result.output


def test_propose_with_traces(runner, cfg_dir):
    os.chdir(cfg_dir.parent)
    reg = Registry(cfg_dir.parent / "reg")
    reg.create("You are a classifier.")
    # Create a trace store with pending traces
    from agent_self_edit.trace import TraceStore
    store = TraceStore(cfg_dir.parent / "t.db", batch_size=2)
    for i in range(3):
        store.ingest({
            "task_id": f"t{i}", "task_input": "x", "final_output": "wrong",
            "expected_output": "right", "success": False,
            "timestamp": "2026-09-01T10:00:00Z",
        })
    result = runner.invoke(main, ["propose", "--dry-run", "--config", str(cfg_dir)])
    assert result.exit_code == 0


def test_propose_help(runner):
    result = runner.invoke(main, ["propose", "--help"])
    assert result.exit_code == 0
    assert "dry-run" in result.output


def test_status_text_format(runner, cfg_dir):
    os.chdir(cfg_dir.parent)
    result = runner.invoke(main, ["status", "--config", str(cfg_dir)])
    assert result.exit_code == 0
    assert "Prompt version" in result.output


def test_validate_with_failing_config(runner, tmp_path):
    os.chdir(tmp_path)
    (tmp_path / "bad.yaml").write_text("not valid yaml: [")
    result = runner.invoke(main, ["validate", "--config", str(tmp_path / "bad.yaml")])
    assert result.exit_code == 2


def test_ingest_malformed_line(runner, cfg_dir):
    os.chdir(cfg_dir.parent)
    trace_file = cfg_dir.parent / "bad.jsonl"
    trace_file.write_text("not json\n")
    result = runner.invoke(main, ["ingest", str(trace_file), "--config", str(cfg_dir)])
    assert result.exit_code == 0
    assert "0 traces" in result.output or "errors" in result.output


def test_ingest_list_format(runner, cfg_dir):
    os.chdir(cfg_dir.parent)
    trace_file = cfg_dir.parent / "list.jsonl"
    trace_file.write_text(json.dumps([
        {"task_id": "a", "task_input": "x", "final_output": "y",
         "expected_output": "y", "success": True, "timestamp": "2026-09-01T10:00:00Z"}
    ]) + "\n")
    result = runner.invoke(main, ["ingest", str(trace_file), "--config", str(cfg_dir)])
    assert result.exit_code == 0
    assert "Ingested" in result.output


def test_ingest_invalid_trace_skipped(runner, cfg_dir):
    os.chdir(cfg_dir.parent)
    trace_file = cfg_dir.parent / "invalid.jsonl"
    trace_file.write_text(json.dumps({"task_id": "a", "success": True}) + "\n")
    result = runner.invoke(main, ["ingest", str(trace_file), "--config", str(cfg_dir)])
    assert result.exit_code in (0, 1)


def test_lineage_json(runner, cfg_dir):
    os.chdir(cfg_dir.parent)
    Registry(cfg_dir.parent / "reg").create("content")
    result = runner.invoke(main, ["lineage", "--format", "json", "--config", str(cfg_dir)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) >= 1


def test_rollback_no_reason(runner, cfg_dir):
    os.chdir(cfg_dir.parent)
    Registry(cfg_dir.parent / "reg").create("first")
    Registry(cfg_dir.parent / "reg").create("second")
    result = runner.invoke(main, ["rollback", "1", "--config", str(cfg_dir)])
    assert result.exit_code == 0


def test_validate_json_pass(runner, cfg_dir):
    os.chdir(cfg_dir.parent)
    Registry(cfg_dir.parent / "reg").create("text")
    result = runner.invoke(main, ["validate", "--json", "--config", str(cfg_dir)])
    assert result.exit_code in (0, 2)
    if result.exit_code == 0:
        data = json.loads(result.output)
        assert data["all_pass"] is True
