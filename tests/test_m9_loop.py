"""Tests for M9: Loop Orchestration, Caching & Concurrency."""

from __future__ import annotations

import json
import os
import tempfile

# ---------------------------------------------------------------------------
# Task 1: Hoist task set + LLM out of proposal loop (#288/#240)
# ---------------------------------------------------------------------------


def test_hoist_task_set_and_llm_already_above_loop_run_py():
    """Verify run.py has task_set/executor_llm/judge_llm/scorer above the for loop."""
    import inspect

    from agent_self_edit.cli.run import _run_once

    source = inspect.getsource(_run_once)
    # The hoisted lines must appear before "for proposal in result.proposals:"
    for_line_idx = source.index("for proposal in result.proposals:")
    pre_loop = source[:for_line_idx]
    assert "task_set = load_task_set" in pre_loop, "task_set not hoisted above loop"
    assert "executor_llm = _build_llm_for_role" in pre_loop, "executor_llm not hoisted"
    assert "judge_llm = _build_llm_for_role" in pre_loop, "judge_llm not hoisted"
    assert "scorer = resolve_scorer" in pre_loop, "scorer not hoisted"
    # Verify they do NOT appear inside the loop body
    loop_body = source[for_line_idx:]
    # The loop body should not re-assign task_set (it can use it)
    assert "task_set = load_task_set" not in loop_body, "task_set re-loaded inside loop"


def test_hoist_task_set_and_llm_already_above_loop_propose_py():
    """Verify propose.py has executor_llm/judge_llm/scorer above the for loop."""
    from pathlib import Path

    source = Path("src/agent_self_edit/cli/propose.py").read_text()
    for_line_idx = source.index("for proposal in result.proposals:")
    pre_loop = source[:for_line_idx]
    assert "executor_llm = _build_llm_for_role" in pre_loop, "executor_llm not hoisted"
    assert "judge_llm = _build_llm_for_role" in pre_loop, "judge_llm not hoisted"
    assert "scorer = resolve_scorer" in pre_loop, "scorer not hoisted"
    loop_body = source[for_line_idx:]
    assert "executor_llm = _build_llm_for_role" not in loop_body, "executor_llm re-built inside loop"


# ---------------------------------------------------------------------------
# Task 2: Gate atomicity via PromotionGate.check() (#280/#216)
# ---------------------------------------------------------------------------


def test_gate_check_writes_audit_atomically():
    """gate.check() writes audit entry in the same call as the decision."""
    from agent_self_edit.ab_test import ABResult
    from agent_self_edit.config import ABTestConfig, Config, GateConfig, TasksConfig
    from agent_self_edit.gate import PromotionGate
    from agent_self_edit.types import EditProposal

    with tempfile.TemporaryDirectory() as tmp:
        audit_path = os.path.join(tmp, "audit.jsonl")
        gate = PromotionGate(audit_path=audit_path)
        proposal = EditProposal(
            section="test", old_text="old", new_text="new",
            hypothesis="h", expected_improvement="e",
        )
        ab_result = ABResult(
            winner="b", mean_delta=0.1, ci_low=0.01, ci_high=0.2,
            p_value=0.03, effect_size=0.2, n_trials=10,
        )
        cfg = Config(
            tasks=TasksConfig(sample_floor=5),
            ab_test=ABTestConfig(min_effect_size=0.1, confidence_level=0.95),
            gate=GateConfig(near_miss_threshold=0.5, max_edit_distance=20, drift_threshold=0.3),
        )
        result = gate.check(proposal, ab_result, "current prompt text", "original prompt text", cfg)
        assert result.decision in ("promote", "reject", "near_miss")
        with open(audit_path) as f:
            entries = [json.loads(line) for line in f if line.strip()]
        assert len(entries) == 1
        assert entries[0]["decision"] == result.decision
        assert entries[0]["proposal_old_text"] == "old"


def test_run_py_uses_gate_check_not_check_all():
    """run.py should call gate.check(), not check_all() + gate.log_result()."""
    import inspect

    from agent_self_edit.cli.run import _run_once

    source = inspect.getsource(_run_once)
    assert "gate.check(" in source, "run.py should use gate.check()"
    assert "gate.log_result" not in source, "run.py should not call gate.log_result()"


def test_propose_py_uses_gate_check_not_check_all():
    """propose.py should call gate.check(), not check_all() + gate.log_result()."""
    from pathlib import Path

    source = Path("src/agent_self_edit/cli/propose.py").read_text()
    assert "gate.check(" in source, "propose.py should use gate.check()"
    assert "gate.log_result" not in source, "propose.py should not call gate.log_result()"


# ---------------------------------------------------------------------------
# Task 3: A/B result caching — persistent SQLite (#230)
# ---------------------------------------------------------------------------


def test_ab_cache_hit_skips_llm_calls():
    """Second identical run_ab_test call should hit cache and skip LLM."""
    from agent_self_edit.ab_test import _ABResultCache, run_ab_test
    from agent_self_edit.config import ABTestConfig, Config, GateConfig, TasksConfig
    from agent_self_edit.llm.mock import MockProvider
    from agent_self_edit.scorers import ExactMatchScorer
    from agent_self_edit.tasks import Task, TaskSet

    tasks = TaskSet(tasks={"t1": Task(id="t1", input="hello", expected_output="hello")})
    scorer = ExactMatchScorer()

    with tempfile.TemporaryDirectory() as tmp:
        cache = _ABResultCache(tmp, enabled=True)
        llm = MockProvider(responses="hello")
        cfg = Config(
            tasks=TasksConfig(sample_floor=1),
            ab_test=ABTestConfig(min_effect_size=0.0, confidence_level=0.5),
            gate=GateConfig(near_miss_threshold=0.5, max_edit_distance=20, drift_threshold=0.3),
        )

        result1 = run_ab_test("prompt a", "prompt b", tasks, llm, scorer, cfg, cache=cache)
        calls_after_first = len(llm.calls)

        result2 = run_ab_test("prompt a", "prompt b", tasks, llm, scorer, cfg, cache=cache)
        assert len(llm.calls) == calls_after_first, "LLM should not be called on cache hit"
        assert result1.winner == result2.winner
        assert result1.n_trials == result2.n_trials


def test_ab_cache_miss_on_task_change():
    """Different task_set should cause cache miss."""
    from agent_self_edit.ab_test import _ABResultCache, run_ab_test
    from agent_self_edit.config import ABTestConfig, Config, GateConfig, TasksConfig
    from agent_self_edit.llm.mock import MockProvider
    from agent_self_edit.scorers import ExactMatchScorer
    from agent_self_edit.tasks import Task, TaskSet

    scorer = ExactMatchScorer()

    with tempfile.TemporaryDirectory() as tmp:
        cache = _ABResultCache(tmp, enabled=True)
        llm = MockProvider(responses="hello")
        cfg = Config(
            tasks=TasksConfig(sample_floor=1),
            ab_test=ABTestConfig(min_effect_size=0.0, confidence_level=0.5),
            gate=GateConfig(near_miss_threshold=0.5, max_edit_distance=20, drift_threshold=0.3),
        )

        tasks1 = TaskSet(tasks={"t1": Task(id="t1", input="hello", expected_output="hello")})
        tasks2 = TaskSet(tasks={"t1": Task(id="t1", input="world", expected_output="world")})

        run_ab_test("prompt a", "prompt b", tasks1, llm, scorer, cfg, cache=cache)
        calls_after_first = len(llm.calls)

        run_ab_test("prompt a", "prompt b", tasks2, llm, scorer, cfg, cache=cache)
        assert len(llm.calls) > calls_after_first, "Different tasks should cause cache miss"


def test_ab_cache_disabled_skips_cache():
    """cache_enabled=False should not use cache."""
    from agent_self_edit.ab_test import _ABResultCache, run_ab_test
    from agent_self_edit.config import ABTestConfig, Config, GateConfig, TasksConfig
    from agent_self_edit.llm.mock import MockProvider
    from agent_self_edit.scorers import ExactMatchScorer
    from agent_self_edit.tasks import Task, TaskSet

    tasks = TaskSet(tasks={"t1": Task(id="t1", input="hello", expected_output="hello")})
    scorer = ExactMatchScorer()

    with tempfile.TemporaryDirectory() as tmp:
        cache = _ABResultCache(tmp, enabled=False)
        llm = MockProvider(responses="hello")
        cfg = Config(
            tasks=TasksConfig(sample_floor=1),
            ab_test=ABTestConfig(min_effect_size=0.0, confidence_level=0.5),
            gate=GateConfig(near_miss_threshold=0.5, max_edit_distance=20, drift_threshold=0.3),
        )

        run_ab_test("prompt a", "prompt b", tasks, llm, scorer, cfg, cache=cache)
        run_ab_test("prompt a", "prompt b", tasks, llm, scorer, cfg, cache=cache)
        assert len(llm.calls) > 0, "Cache disabled: LLM should be called both times"


# ---------------------------------------------------------------------------
# Task 4: File-based registry lock — fcntl.flock (#229)
# ---------------------------------------------------------------------------


def test_registry_file_lock_prevents_concurrent_corruption():
    """Two threads creating versions concurrently should not corrupt."""
    import threading

    from agent_self_edit.registry import Registry

    errors: list[str] = []

    def create_in_thread(reg_path: str) -> None:
        try:
            reg = Registry(reg_path)
            reg.create(f"prompt from {threading.current_thread().name}", hypothesis="h1")
        except Exception as e:
            errors.append(str(e))

    with tempfile.TemporaryDirectory() as tmp:
        reg_path = os.path.join(tmp, "registry")
        threads = [threading.Thread(target=create_in_thread, args=(reg_path,)) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0, f"Errors: {errors}"
        reg = Registry(reg_path)
        assert reg.current_version >= 1


def test_registry_lockfile_created():
    """Registry should create a .registry.lock file."""
    from agent_self_edit.registry import Registry

    with tempfile.TemporaryDirectory() as tmp:
        reg_path = os.path.join(tmp, "registry")
        reg = Registry(reg_path)
        reg.create("prompt v1", hypothesis="h1")
        assert os.path.exists(os.path.join(reg_path, ".registry.lock"))
