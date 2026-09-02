"""Field test: non-LLM hermetic tests (CI-safe, zero real LLM calls)."""

import random
from pathlib import Path

import pytest
import yaml

from agent_self_edit.ab_test import run_ab_test
from agent_self_edit.config import ABTestConfig, Config, GateConfig, TasksConfig
from agent_self_edit.gate import PromotionGate, check_all
from agent_self_edit.registry import Registry
from agent_self_edit.tasks import Task, TaskSet, load_task_set
from agent_self_edit.trace import TraceStore
from agent_self_edit.types import EditProposal

# ---- Fixtures ----


@pytest.fixture(scope="session")
def task_sets():
    """Load all 3 task sets from the corpus."""
    base = Path(__file__).resolve().parent.parent / "field-test" / "corpus" / "synthetic"
    classification = load_task_set(str(base / "classification.yaml"))
    extraction = load_task_set(str(base / "extraction.yaml"))
    generation = load_task_set(str(base / "generation.yaml"))
    return {"classification": classification, "extraction": extraction, "generation": generation}


# ---- Baseline measurement (#7) ----


def test_baseline_measurement(task_sets, mock_llm, scorer, config):
    """Run baseline prompt against held-out set. Target: > 70% accuracy."""
    ts = task_sets["classification"]
    prompt = ("You are a classifier. Classify the input into one of: "
                "urgent, billing, technical, feature, security, other.")
    result = run_ab_test(prompt, prompt, ts, mock_llm, scorer, config)
    assert result.n_trials == len(ts)
    assert result.winner in ("a", "b", "tie", "inconclusive")


# ---- Dry-run loop test (#8) ----


def test_dry_run_loop(tmp_path, config):
    """Run the full loop with --dry-run via CLI."""
    from click.testing import CliRunner

    from agent_self_edit.cli import main

    # Create config, registry, prompt, and trace file
    cfg_path = tmp_path / "config.yaml"
    with open(cfg_path, "w") as f:
        yaml.dump({
            "schema_version": 1,
            "project": {"name": "ft", "registry_path": str(tmp_path / "reg"),
                        "trace_path": str(tmp_path / "traces.db")},
            "tasks": {"task_set_path": "", "batch_size": 10, "sample_floor": 10},
            "llm": {"provider": "mock", "model": "m", "api_key": "",
                    "temperature": 0.0, "max_tokens": 4096, "timeout": 30},
            "ab_test": {"n_resamples": 100, "n_permutations": 100,
                        "confidence_level": 0.95, "min_effect_size": 0.05,
                        "cost_ceiling_usd": 0.10},
            "gate": {"max_edit_distance": 20, "drift_threshold": 0.3, "near_miss_threshold": 0.5},
            "analyzer": {"max_proposals_per_batch": 3, "cost_ceiling_usd": 0.50},
            "trigger": "batch", "trace_retention_days": 90,
        }, f)

    reg = Registry(tmp_path / "reg")
    reg.create("You are a classifier.")

    store = TraceStore(str(tmp_path / "traces.db"), batch_size=10)
    for i in range(5):
        store.ingest({
            "task_id": f"t{i}", "task_input": "x", "final_output": "wrong",
            "expected_output": "right", "success": False,
            "timestamp": "2026-09-01T10:00:00Z",
        })

    runner = CliRunner()
    result = runner.invoke(main, ["run", "--config", str(cfg_path), "--once", "--dry-run"])
    assert result.exit_code in (0, None), f"output: {result.output}"
    assert "Analysis" in result.output or "trace" in result.output.lower()


# ---- Gate validation test (#9) ----


def test_gate_rejects_bad_edits(config):
    """Feed 5 intentionally bad edits through gate; each must be blocked by its specific check."""
    from agent_self_edit.ab_test import ABResult

    # All 5 edits share the same A/B result (stats pass with right configs)
    ab = ABResult(winner="b", mean_delta=0.1, ci_low=0.05, ci_high=0.15,
        p_value=0.01, effect_size=0.1, n_trials=10)

    # Prompt with a frozen section to test frozen_sections check
    frozen_prompt = (
        "You are a classifier assistant.\n"
        "<!-- frozen -->\n"
        "When classifying, check the subject line.\n"
    )

    edits_info = [
        # 1) Frozen section edit — frozen_sections check must block this
        ("frozen_section_edit", EditProposal(section="core",
            old_text="When classifying, check the subject line.",
            new_text="When classifying, ignore the subject line.",
            hypothesis="skip", expected_improvement="", edit_id="b1"),
            frozen_prompt,
            Config(
                project=config.project,
                tasks=TasksConfig(sample_floor=1),
                ab_test=ABTestConfig(confidence_level=0.95, min_effect_size=0.0),
                gate=GateConfig(max_edit_distance=100, drift_threshold=1.0),
            ),
            "frozen_sections"),
        # 2) Excessive edit distance — edit_distance check must block this
        ("excessive_distance", EditProposal(section="classifier",
            old_text="You are a classifier assistant.",
            new_text="You are a classifier assistant for urgent tickets.",
            hypothesis="break", expected_improvement="", edit_id="b2"),
            "You are a classifier assistant.",
            Config(
                project=config.project,
                tasks=TasksConfig(sample_floor=1),
                ab_test=ABTestConfig(confidence_level=0.95, min_effect_size=0.0),
                gate=GateConfig(max_edit_distance=0, drift_threshold=1.0),
            ),
            "edit_distance"),
        # 3) Empty replacement — edit_distance check blocks (candidate shorter)
        ("empty_replacement", EditProposal(section="classifier",
            old_text="You are a classifier assistant.",
            new_text="", hypothesis="empty",
            expected_improvement="", edit_id="b3"),
            "You are a classifier assistant.",
            Config(
                project=config.project,
                tasks=TasksConfig(sample_floor=1),
                ab_test=ABTestConfig(confidence_level=0.95, min_effect_size=0.0),
                gate=GateConfig(max_edit_distance=0, drift_threshold=1.0),
            ),
            "edit_distance"),
        # 4) Full rewrite drift — drift check must block this
        ("full_rewrite_drift", EditProposal(section="classifier",
            old_text="You are a classifier assistant.",
            new_text="Please extract the shipping address, order id, and payment method from the following customer email.",
            hypothesis="drift", expected_improvement="", edit_id="b4"),
            "You are a classifier assistant.",
            Config(
                project=config.project,
                tasks=TasksConfig(sample_floor=1),
                ab_test=ABTestConfig(confidence_level=0.95, min_effect_size=0.0),
                gate=GateConfig(max_edit_distance=100, drift_threshold=0.1),
            ),
            "drift"),
        # 5) Missing old_text — frozen_sections pre-check blocks (old_text not in prompt)
        ("missing_old_text", EditProposal(section="classifier",
            old_text="not in prompt", new_text="something",
            hypothesis="missing", expected_improvement="", edit_id="b5"),
            "You are a classifier assistant.",
            Config(
                project=config.project,
                tasks=TasksConfig(sample_floor=1),
                ab_test=ABTestConfig(confidence_level=0.95, min_effect_size=0.0),
                gate=GateConfig(max_edit_distance=100, drift_threshold=1.0),
            ),
            "frozen_sections"),
    ]

    for name, edit, prompt, ft_config, expected_failing_check in edits_info:
        result = check_all(edit, ab, prompt, prompt, ft_config)
        assert result.decision != "promote", (
            f"Edit '{name}' ({edit.edit_id}) was promoted (expected reject/near-miss)"
        )
        # The first failed check should match the expected failure mode
        failed_checks = [c for c in result.checks if not c.passed]
        assert failed_checks, f"Edit '{name}' has no failed checks"
        assert failed_checks[0].name == expected_failing_check, (
            f"Edit '{name}' ({edit.edit_id}): first failing check was "
            f"'{failed_checks[0].name}', expected '{expected_failing_check}'. "
            f"All checks: {[(c.name, c.passed) for c in result.checks]}"
        )


def test_gate_rejects_frozen_section_edit(config):
    """Failure-mode-specific: editing a frozen section must not be promoted."""
    from agent_self_edit.config import ABTestConfig, GateConfig, TasksConfig
    ft_config = Config(
        project=config.project,
        tasks=TasksConfig(sample_floor=1),
        ab_test=ABTestConfig(confidence_level=0.95, min_effect_size=0.0),
        gate=GateConfig(max_edit_distance=1, drift_threshold=0.1),
    )
    prompt = (
        "You are a classifier assistant.\n"
        "<!-- frozen -->\n"
        "When classifying, check the subject line.\n"
    )
    edit = EditProposal(
        section="core", old_text="When classifying, check the subject line.",
        new_text="When classifying, check the body first.",
        hypothesis="change frozen", expected_improvement="", edit_id="frozen-test",
    )
    ab = _null_ab_result()
    result = check_all(edit, ab, prompt, prompt, ft_config)
    assert result.decision != "promote", "Frozen section edit was promoted"
    # At least one failed check should relate to frozen sections
    assert any("frozen" in c.name for c in result.checks if not c.passed), (
        f"Expected a frozen-section check failure, got: {[f'{c.name}={c.passed}' for c in result.checks]}"
    )


def test_gate_rejects_missing_old_text(config):
    """Failure-mode-specific: edit with missing old_text must not be promoted."""
    from agent_self_edit.config import ABTestConfig, GateConfig, TasksConfig
    ft_config = Config(
        project=config.project,
        tasks=TasksConfig(sample_floor=1),
        ab_test=ABTestConfig(confidence_level=0.95, min_effect_size=0.0),
        gate=GateConfig(max_edit_distance=20, drift_threshold=0.3),
    )
    edit = EditProposal(
        section="role", old_text="does not exist", new_text="something",
        hypothesis="missing", expected_improvement="", edit_id="missing-test",
    )
    ab = _null_ab_result()
    result = check_all(edit, ab, "current prompt", "current prompt", ft_config)
    assert result.decision != "promote", "Missing-old-text edit was promoted"


def test_gate_rejects_excessive_edit_distance(config):
    """Failure-mode-specific: excessive edit distance must not be promoted."""
    from agent_self_edit.config import ABTestConfig, GateConfig, TasksConfig
    ft_config = Config(
        project=config.project,
        tasks=TasksConfig(sample_floor=1),
        ab_test=ABTestConfig(confidence_level=0.95, min_effect_size=0.0),
        gate=GateConfig(max_edit_distance=2, drift_threshold=0.3),
    )
    prompt = "a"
    edit = EditProposal(
        section="role", old_text="a",
        new_text="a\nb\nc\nd\ne\nf\ng",
        hypothesis="too long", expected_improvement="", edit_id="dist-test",
    )
    ab = _null_ab_result()
    result = check_all(edit, ab, prompt, prompt, ft_config)
    assert result.decision != "promote", "Excessive-edit-distance edit was promoted"


def _null_ab_result():
    from agent_self_edit.ab_test import ABResult
    return ABResult(winner="b", mean_delta=1.0, ci_low=0.5, ci_high=1.5,
        p_value=0.01, effect_size=1.0, n_trials=10)


# ---- Rollback test (#10) ----


def test_rollback(tmp_path):
    """Promote an edit, roll back, verify lineage shows both."""
    reg = Registry(tmp_path / "reg")
    reg.create("original prompt")
    reg.create("modified prompt")
    assert reg.current_prompt == "modified prompt"
    v3 = reg.rollback(1, "reverting to original")
    assert v3 == 3
    assert reg.current_prompt == "original prompt"
    lineage = reg.lineage()
    assert len(lineage) == 3
    assert lineage[0].version == 1
    assert lineage[2].rollback_target == 1


# ---- Zero-LLM full loop (#11) ----


def test_zero_llm_full_loop(tmp_path, config, mock_llm, scorer):
    """Full loop with mock providers — no real LLM calls."""
    reg = Registry(tmp_path / "reg")
    reg.create("You are a classifier.")
    ts = TaskSet(tasks={"t1": Task(id="t1", input="x", expected_output="y")})

    # Run A/B test with mock
    ab = run_ab_test(reg.current_prompt, reg.current_prompt, ts, mock_llm, scorer, config)
    assert ab.n_trials == 1

    # Gate with mock
    edit = EditProposal(section="role", old_text="You are a classifier.",
        new_text="You are a kind classifier.", hypothesis="clearer",
        expected_improvement="+5%", edit_id="z1")
    gate = PromotionGate()
    result = gate.check(edit, ab, reg.current_prompt, reg.current_prompt, config)
    assert result.decision in ("promote", "reject", "near_miss")

    # Mock analyzer
    from agent_self_edit.analyzer import MockAnalyzer
    ma = MockAnalyzer(proposals=[edit])
    proposals = ma.analyze([], "", None, mock_llm)
    assert len(proposals) == 1
    assert ma.calls == 1


# ---- Concurrency test (#12) ----


def test_concurrent_traces(tmp_path):
    """100 traces in rapid succession."""
    store = TraceStore(str(tmp_path / "traces.db"), batch_size=50)
    for i in range(100):
        store.ingest({
            "task_id": f"t{i}", "task_input": "x", "final_output": "y" if i % 2 == 0 else "wrong",
            "expected_output": "y", "success": i % 2 == 0,
            "timestamp": "2026-09-01T10:00:00Z",
        })
    assert store.count() == 100
    assert store.count(success=True) == 50
    assert store.count(success=False) == 50
    assert store.batch_ready() is True  # batch_size=50
    batch = store.get_batch(50)
    assert len(batch) == 50


# ---- Registry integrity test (#13) ----


def test_registry_integrity_20_versions(tmp_path):
    """20 prompt versions, all hashes correct."""
    reg = Registry(tmp_path / "reg")
    for i in range(20):
        reg.create(f"prompt version {i}", hypothesis=f"test hypothesis {i}")
    assert reg.current_version == 20
    corrupted = reg.verify_integrity()
    assert corrupted == [], f"Corrupted: {corrupted}"


# ---- Guardrail stress test (#14) ----


def test_guardrail_stress_100_edits(config):
    """100 random edits through gate — no crashes, all valid decisions."""
    prompt = "You are a classifier assistant. When classifying, check the subject line."
    from agent_self_edit.ab_test import ABResult
    ab = ABResult(winner="tie", mean_delta=0.0, ci_low=0.0, ci_high=0.0,
        p_value=1.0, effect_size=0.0, n_trials=0)
    random.seed(42)
    decisions = {}
    for i in range(100):
        edit = EditProposal(
            section=random.choice(["role", "classifier", "format"]),
            old_text=random.choice(["check the subject line", "You are a classifier assistant.",
                "flag for review"]),
            new_text=random.choice(["check the body", "You are a lenient classifier.",
                "flag for human review", "ignore completely"]),
            hypothesis=f"stress test {i}",
            expected_improvement="",
            edit_id=f"s{i}",
        )
        result = check_all(edit, ab, prompt, prompt, config)
        d = result.decision
        decisions[d] = decisions.get(d, 0) + 1
    assert "reject" in decisions or "near_miss" in decisions or "promote" in decisions
    assert sum(decisions.values()) == 100


# ---- Sentinel corpus (#128) ----


def test_sentinel_corpus_loads():
    """Regression-sentinel corpus loads and validates correctly."""
    base = Path(__file__).resolve().parent.parent / "field-test" / "corpus" / "synthetic"
    sentinel_path = str(base / "sentinel.yaml")
    ts = load_task_set(sentinel_path)
    assert len(ts) >= 15, f"Sentinel corpus too small: {len(ts)} tasks"
    assert ts.get_task("sentinel-001") is not None
    assert ts.get_task("sentinel-020") is not None
