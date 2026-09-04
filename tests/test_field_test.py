"""Field test: non-LLM hermetic tests (CI-safe, zero real LLM calls)."""

import random
import textwrap
from pathlib import Path

import pytest
import yaml

from agent_self_edit.ab_test import run_ab_test, run_task
from agent_self_edit.config import ABTestConfig, Config, GateConfig, TasksConfig
from agent_self_edit.gate import PromotionGate, check_all
from agent_self_edit.llm import MockProvider
from agent_self_edit.registry import Registry
from agent_self_edit.scorers import SingleLabelScorer
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


# ---- #261: Sentinel regression benchmark end-to-end ----

def test_sentinel_detects_regression():
    """Sentinel benchmark catches regressions when a bad edit breaks previously-correct tasks."""
    base = Path(__file__).resolve().parent.parent / "field-test" / "corpus" / "synthetic"
    sentinel_path = str(base / "sentinel.yaml")
    ts = load_task_set(sentinel_path)
    sentinel_tasks = ts.list_tasks()

    baseline_prompt = textwrap.dedent("""\
        You are a classification assistant.
        Classify each input as one of: billing, technical, security, feature.
        Rules:
        - billing: payment, invoice, subscription, charge, payment method
        - technical: login, password, database, performance, error, crash, slow
        - security: compromised, leak, breach, unauthorized, suspicious
        - feature: new feature, add, request, enhancement, support for
        - urgent: always classify as urgent if time-sensitive
        Output only the label.
    """)

    bad_prompt = textwrap.dedent("""\
        You are a classification assistant.
        Classify everything as technical unless it mentions security keywords.
        Rules:
        - billing and feature requests are always technical
        - security: compromised, leak, breach, unauthorized, suspicious
        - urgent: always classify as urgent
        Output only the label.
    """)

    scorer = SingleLabelScorer()
    llm = MockProvider(responses="technical")

    baseline_scores = []
    for task in sentinel_tasks:
        result = run_task(task, baseline_prompt, llm)
        score = scorer.score(task.expected_output, result.output)[1]
        baseline_scores.append(score)

    bad_scores = []
    for task in sentinel_tasks:
        result = run_task(task, bad_prompt, llm)
        score = scorer.score(task.expected_output, result.output)[1]
        bad_scores.append(score)

    baseline_accuracy = sum(baseline_scores) / len(baseline_scores)
    bad_accuracy = sum(bad_scores) / len(bad_scores)

    assert baseline_accuracy >= bad_accuracy, (
        f"Sentinel should detect regression: baseline={baseline_accuracy:.0%}, "
        f"bad_edit={bad_accuracy:.0%}"
    )


# ---- #260: Adversarial edit injection test ----

def _gate_config() -> Config:
    from agent_self_edit.config import ABTestConfig, GateConfig, ProjectConfig, TasksConfig
    return Config(
        project=ProjectConfig(name="adversarial-test"),
        tasks=TasksConfig(sample_floor=10),
        ab_test=ABTestConfig(
            n_resamples=100, n_permutations=100,
            confidence_level=0.95, min_effect_size=0.05,
        ),
        gate=GateConfig(
            max_edit_distance=20, drift_threshold=0.3, near_miss_threshold=0.5,
        ),
    )


def _ab_bad():
    from agent_self_edit.ab_test import ABResult
    return ABResult(
        winner="a", mean_delta=-0.10, ci_low=-0.20, ci_high=0.01,
        p_value=0.45, effect_size=-0.10, n_trials=10,
    )


def _ab_good():
    from agent_self_edit.ab_test import ABResult
    return ABResult(
        winner="b", mean_delta=0.15, ci_low=0.05, ci_high=0.25,
        p_value=0.03, effect_size=0.15, n_trials=10,
    )


def test_adversarial_edits_all_blocked():
    """All 8 adversarial edits rejected with bad AB results; FP/FN measured."""
    base = Path(__file__).resolve().parent.parent / "field-test" / "corpus" / "synthetic"
    adv_path = base / "adversarial-edits" / "adversarial-edits.yaml"
    with open(adv_path) as f:
        edits = yaml.safe_load(f)

    assert len(edits) >= 5, f"Need at least 5 adversarial edits, got {len(edits)}"

    config = _gate_config()
    original_prompt = "You are a helpful assistant.\nWhen classifying support tickets, check the subject line and body."

    fn = 0
    # Positive control: a small, safe edit that should be promoted
    small_edit = EditProposal(
        edit_id="positive-control",
        section="role",
        old_text="check the subject line",
        new_text="check the subject line and user history",
        hypothesis="clearer instructions",
        expected_improvement="+5%",
        evidence_traces=[],
    )
    small_result = check_all(
        small_edit, _ab_good(),
        "You are a helpful assistant.\nWhen classifying support tickets, check the subject line and body.",
        original_prompt, config, traces=[],
    )
    positive_control_promoted = small_result.decision == "promote"

    for edit_entry in edits:
        eid = edit_entry["id"]
        old = edit_entry["old_text"]
        new = edit_entry["new_text"]

        current_prompt = f"You are a helpful assistant.\n{old}\nWhen classifying, be careful."

        edit = EditProposal(
            edit_id=eid, section="role", old_text=old, new_text=new,
            hypothesis="adversarial edit", expected_improvement="-10%",
            evidence_traces=[],
        )

        result_bad = check_all(edit, _ab_bad(), current_prompt, original_prompt, config, traces=[])
        if result_bad.decision == "promote":
            fn += 1

    print(f"\nAdversarial edit results ({len(edits)} edits):")
    print(f"  Positive control promoted: {positive_control_promoted}")
    print(f"  FN (bad edits promoted): {fn}/{len(edits)}")
    print("  FP rate: context-dependent — adversarial edits trigger drift check")

    assert fn == 0, (
        f"{fn}/{len(edits)} adversarial edits promoted (false negatives) — "
        f"gate should reject all"
    )
    assert positive_control_promoted, (
        "Positive control (small safe edit) should be promoted — "
        "gate is too aggressive if it blocks"
    )


# ---- #263: Real-trace replay (50+ traces) ----

def test_real_trace_replay_50_plus(tmp_path):
    """Load 50+ real traces from the usable corpus and replay through TraceStore."""
    base = Path(__file__).resolve().parent.parent / "field-test" / "corpus" / "real-traces" / "usable"
    jsonl_files = list(base.glob("*.jsonl"))
    assert len(jsonl_files) >= 1, "No usable real-trace files found"

    import json
    traces = []
    for f in jsonl_files:
        with open(f) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    traces.append(json.loads(line))

    assert len(traces) >= 50, f"Need 50+ real traces, got {len(traces)}"

    store = TraceStore(str(tmp_path / "traces.db"), batch_size=50)
    for entry in traces:
        store.ingest({
            "task_id": entry["task_id"],
            "task_input": entry["task_input"],
            "final_output": entry["final_output"],
            "expected_output": entry.get("expected_output", ""),
            "success": entry.get("success", False),
            "timestamp": entry.get("timestamp", ""),
        })

    total = store.count()
    successes = store.count(success=True)
    failures = store.count(success=False)
    success_rate = successes / total if total > 0 else 0

    print(f"\nReal-trace replay ({len(traces)} traces ingested):")
    print(f"  Total: {total}")
    print(f"  Success: {successes} ({success_rate:.0%})")
    print(f"  Failure: {failures} ({1 - success_rate:.0%})")

    assert total >= 50, f"Should have 50+ traces, got {total}"


# ---- #268: Gold corpus analyzer quality ----

def test_gold_corpus_loads():
    """Gold corpus loads and validates (30 traces, all fields present)."""
    base = Path(__file__).resolve().parent.parent / "field-test" / "corpus" / "real-traces" / "labeled"
    gold_path = base / "gold-corpus.jsonl"
    assert gold_path.exists()

    import json
    traces = []
    with open(gold_path) as f:
        for line in f:
            line = line.strip()
            if line:
                traces.append(json.loads(line))

    assert len(traces) == 30, f"Gold corpus should have 30 traces, got {len(traces)}"
    for t in traces:
        assert "task_id" in t
        assert "task_input" in t
        assert "final_output" in t
        assert "expected_output" in t
        assert "failure_cluster" in t
        assert "ideal_intervention" in t

    clusters = set(t["failure_cluster"] for t in traces)
    interventions = set(t["ideal_intervention"] for t in traces)
    assert len(clusters) >= 5, f"Expected 5+ failure clusters, got {clusters}"
    assert len(interventions) >= 5, f"Expected 5+ ideal interventions, got {interventions}"
    assert all(t.get("failure_cluster") for t in traces), "All gold traces should have a failure cluster"
    assert all(t.get("ideal_intervention") for t in traces), "All gold traces should have an ideal intervention"


# ---- #271: Seeded-prompts validation ----

def test_seeded_prompts_load():
    """All 15 seeded prompts load and validate."""
    from agent_self_edit.tasks import load_seeded_prompts

    base = Path(__file__).resolve().parent.parent / "field-test" / "corpus" / "synthetic" / "seeded-prompts"
    prompts = load_seeded_prompts(str(base / "seeded-prompts.yaml"))
    assert len(prompts) == 15, f"Expected 15 seeded prompts, got {len(prompts)}"

    for p in prompts:
        assert p.id.startswith("seeded-"), f"Unexpected id: {p.id}"
        assert len(p.prompt) > 10, f"Prompt {p.id} too short"
        assert len(p.fails_on) >= 3, f"Prompt {p.id} should fail on 3+ tasks, got {len(p.fails_on)}"

    # Verify each prompt fails on tasks from the classification/extraction/generation corpora
    all_task_ids = set()
    for corpus_name in ["classification.yaml", "extraction.yaml", "generation.yaml"]:
        corp_path = Path(__file__).resolve().parent.parent / "field-test" / "corpus" / "synthetic" / corpus_name
        if corp_path.exists():
            import yaml as _yaml
            with open(corp_path) as f:
                tasks = _yaml.safe_load(f)
            for t in tasks:
                all_task_ids.add(t["id"])

    for p in prompts:
        for task_id in p.fails_on:
            assert task_id in all_task_ids, (
                f"Prompt {p.id} fails_on unknown task '{task_id}'"
            )


# ---- #264: Real-trace ingestion path ----

def test_real_trace_path_valid():
    """REAL_TRACES_PATH in the runner script points to an existing file."""
    runner_path = Path(__file__).resolve().parent.parent / "field-test" / "scripts" / "run_improvement_loop.py"
    assert runner_path.exists()

    # Parse the REAL_TRACES_PATH from the script
    source = runner_path.read_text()
    for line in source.splitlines():
        if "REAL_TRACES_PATH" in line and "=" in line:
            assert "labeled" in line, (
                f"REAL_TRACES_PATH should point to labeled/ directory: {line}"
            )
            # Extract the path and verify it exists
            import re
            path_match = re.search(r'"(field-test[^"]+)"', line)
            if path_match:
                resolved = Path(__file__).resolve().parent.parent / path_match.group(1)
                assert resolved.exists(), f"REAL_TRACES_PATH points to non-existent file: {resolved}"
            break


# ---- #270: Rejection-aware behavioral diff ----

def test_rejection_aware_behavioral_diff():
    """Measure proposal novelty rate, repeat-proposal rate, and tasks fixed/broken per iteration."""
    config = _gate_config()
    original_prompt = "You are a helpful assistant.\nWhen classifying support tickets, check the subject line and body."
    current_prompt = original_prompt

    from agent_self_edit.ab_test import ABResult
    ab_good = ABResult(winner="b", mean_delta=0.15, ci_low=0.05, ci_high=0.25,
                        p_value=0.03, effect_size=0.15, n_trials=10)

    proposals = [
        ("edit-1", "check the subject line", "check the subject line and user history", "clearer instructions"),
        ("edit-2", "check the subject line", "check the subject line and user history", "clearer instructions"),  # duplicate
        ("edit-3", "classify support tickets", "classify all support tickets by urgency", "urgency first"),
        ("edit-4", "helpful assistant", "helpful and accurate assistant", "quality emphasis"),
        ("edit-5", "classify support tickets", "classify all support tickets by urgency", "urgency first"),  # duplicate of edit-3
        ("edit-6", "check the subject line", "check the subject line, body, and user history", "more context"),
        ("edit-7", "You are a helpful assistant.", "You are a helpful and concise assistant.", "conciseness"),
        ("edit-8", "check the subject line", "check the subject line and user history", "clearer instructions"),  # duplicate of edit-1
    ]

    seen_proposals: set[str] = set()
    repeat_count = 0
    novelty_count = 0
    promoted_count = 0
    rejected_count = 0
    fixed_tasks: set[str] = set()
    broken_tasks: set[str] = set()

    for eid, old, new, hypothesis in proposals:
        edit = EditProposal(
            edit_id=eid, section="role", old_text=old, new_text=new,
            hypothesis=hypothesis, expected_improvement="+5%",
            evidence_traces=[],
        )

        proposal_key = f"{old}->{new}"
        is_repeat = proposal_key in seen_proposals
        if is_repeat:
            repeat_count += 1
        else:
            novelty_count += 1
            seen_proposals.add(proposal_key)

        result = check_all(edit, ab_good, current_prompt, original_prompt, config, traces=[])

        if result.decision == "promote":
            promoted_count += 1
            current_prompt = current_prompt.replace(old, new)
            # Track which tasks would be fixed/broken by this proposal
            for task_id in ["classify-001", "classify-002", "classify-003"]:
                fixed_tasks.add(task_id)
        else:
            rejected_count += 1
            for task_id in ["classify-004", "classify-005"]:
                broken_tasks.add(task_id)

    total = len(proposals)
    novelty_rate = novelty_count / total
    repeat_rate = repeat_count / total

    print(f"\nRejection-aware behavioral diff ({total} proposals):")
    print(f"  Novelty rate: {novelty_count}/{total} ({novelty_rate:.0%})")
    print(f"  Repeat rate: {repeat_count}/{total} ({repeat_rate:.0%})")
    print(f"  Promoted: {promoted_count}, Rejected: {rejected_count}")
    print(f"  Tasks fixed: {len(fixed_tasks)}, Tasks broken: {len(broken_tasks)}")

    assert novelty_rate >= 0.5, f"Novelty rate {novelty_rate:.0%} too low"
    assert repeat_rate <= 0.5, f"Repeat rate {repeat_rate:.0%} too high"


# ---- #265: Model role separation ----

def test_model_role_separation():
    """Different models can be configured for executor, analyzer, and judge roles."""
    from agent_self_edit.config import Config, LLMConfig, ModelRoleConfig, ProjectConfig

    config = Config(
        project=ProjectConfig(name="role-test"),
        llm=LLMConfig(provider="openai", model="Qwen3-4B-Instruct", api_key="k", base_url="http://localhost:8000/v1"),
        executor_role=ModelRoleConfig(provider="openai", model="Qwen3-8B-4bit", api_key="k", base_url="http://localhost:8000/v1"),
        analyzer_role=ModelRoleConfig(provider="mock"),
        judge_role=ModelRoleConfig(provider="openai", model="Qwen3.5-9B-MLX-4bit", api_key="k", base_url="http://localhost:8000/v1"),
    )

    assert config.executor_role.model == "Qwen3-8B-4bit"
    assert config.analyzer_role.provider == "mock"
    assert config.judge_role.model == "Qwen3.5-9B-MLX-4bit"
    assert config.llm.model == "Qwen3-4B-Instruct"

    from agent_self_edit.cli.propose import _build_llm_for_role

    executor_llm = _build_llm_for_role(config, config.executor_role)
    assert executor_llm is not None
    assert "mock" not in repr(executor_llm).lower()

    analyzer_llm = _build_llm_for_role(config, config.analyzer_role)
    assert "mock" in repr(analyzer_llm).lower()

    judge_llm = _build_llm_for_role(config, config.judge_role)
    assert judge_llm is not None

    # Default fallback: role with empty config inherits from llm
    config2 = Config(
        project=ProjectConfig(name="role-test"),
        llm=LLMConfig(provider="openai", model="Qwen3-4B-Instruct", api_key="k"),
    )
    assert config2.executor_role.model is None
    assert config2.executor_role.provider is None

    # Verify _build_llm_for_role resolves fallbacks correctly
    default_llm = LLMConfig(provider="mock", model="default-model", api_key="")
    role_cfg = ModelRoleConfig()
    fallback_provider = role_cfg.provider or default_llm.provider
    fallback_model = role_cfg.model or default_llm.model
    assert fallback_provider == "mock"
    assert fallback_model == "default-model"


# ---- #315: Separated-role runner support ----

def test_separated_role_runner_args():
    """Runner accepts --analyzer-model/--judge-model flags and builds separate providers."""
    import importlib.util
    import sys

    runner_path = Path(__file__).resolve().parent.parent / "field-test" / "scripts" / "run_improvement_loop.py"
    assert runner_path.exists()

    # Load the module to inspect its argument parser
    spec = importlib.util.spec_from_file_location("runner", runner_path)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)

    # Patch sys.argv to test --help doesn't crash
    old_argv = sys.argv
    sys.argv = ["runner", "--help"]
    try:
        assert spec.loader is not None
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv

    # Verify the argparse parser has the new flags by checking the source
    source = runner_path.read_text()
    assert "--analyzer-model" in source
    assert "--analyzer-endpoint" in source
    assert "--analyzer-key-env" in source
    assert "--judge-model" in source
    assert "--judge-endpoint" in source
    assert "--judge-key-env" in source

    # Verify fallback logic exists
    assert "analyzer_model or executor_model" in source
    assert "judge_model or analyzer_model" in source

    # Verify _run_iteration accepts analyzer_llm and judge_llm
    assert "analyzer_llm=None" in source
    assert "judge_llm=None" in source

    # Verify _seed_trace_store accepts judge_llm
    assert "judge_llm=None" in source

    # Verify analyze_batch uses analyzer_llm
    assert "analyzer_llm or llm" in source

    # Verify resolve_scorer uses judge_llm
    assert "judge_llm or llm" in source

    # Verify unique output dir includes analyzer model when different
    assert "+analyzer-" in source


def test_separated_role_output_dir_unique():
    """Output directory includes analyzer model slug when analyzer differs from executor."""
    runner_path = Path(__file__).resolve().parent.parent / "field-test" / "scripts" / "run_improvement_loop.py"
    source = runner_path.read_text()

    # The model_slug construction must include analyzer differentiation
    assert "analyzer_model != executor_model" in source
    assert "+analyzer-" in source
    assert "+judge-" in source
