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
