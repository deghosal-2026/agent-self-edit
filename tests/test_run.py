"""Tests for M10: _run_once() unit tests (#247)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from agent_self_edit.ab_test import ABResult
from agent_self_edit.config import (
    ABTestConfig,
    AnalyzerConfig,
    Config,
    GateConfig,
    LLMConfig,
    ProjectConfig,
    TasksConfig,
)
from agent_self_edit.gate import GateResult
from agent_self_edit.llm.mock import MockProvider
from agent_self_edit.registry import Registry
from agent_self_edit.trace import TraceStore
from agent_self_edit.types import CheckResult, EditProposal, Trace


def _config(tmp_path: Path) -> Config:
    return Config(
        project=ProjectConfig(
            name="test",
            registry_path=str(tmp_path / "registry"),
            trace_path=str(tmp_path / "traces.db"),
        ),
        tasks=TasksConfig(task_set_path="", batch_size=5, sample_floor=3),
        llm=LLMConfig(provider="mock", model="mock-model"),
        ab_test=ABTestConfig(
            n_resamples=10, n_permutations=10,
            confidence_level=0.95, min_effect_size=0.05,
            cost_ceiling_usd=10.0,
        ),
        gate=GateConfig(
            max_edit_distance=20, drift_threshold=0.3, near_miss_threshold=0.5,
        ),
        analyzer=AnalyzerConfig(max_proposals_per_batch=3, cost_ceiling_usd=10.0),
    )


def _seed_traces(store: TraceStore, n: int = 5, success: bool = False) -> None:
    for i in range(n):
        store.store(Trace(
            task_id=f"t{i}", task_input="x", final_output="y",
            expected_output="y", success=success,
            timestamp="2026-01-01T00:00:00Z",
        ))


def test_run_once_batch_not_ready():
    """_run_once returns early without calling analyzer when batch not ready."""
    from agent_self_edit.cli.run import _run_once

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        store = TraceStore(str(tmp_path / "traces.db"), batch_size=10)
        reg = Registry(str(tmp_path / "registry"))
        reg.create("prompt v1")
        cfg = _config(tmp_path)

        # Batch size 10, only 0 traces → not ready
        had_work, ctx = _run_once(
            "dummy.yaml", 10, False, "", store=store, registry=reg, config=cfg,
        )
        assert not had_work
        assert ctx == ""


def test_run_once_no_failed_traces():
    """_run_once acknowledges batch when no traces failed."""
    from agent_self_edit.cli.run import _run_once

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        store = TraceStore(str(tmp_path / "traces.db"), batch_size=5)
        _seed_traces(store, n=5, success=True)
        reg = Registry(str(tmp_path / "registry"))
        reg.create("prompt v1")
        cfg = _config(tmp_path)

        had_work, ctx = _run_once(
            "dummy.yaml", 5, True, "", store=store, registry=reg, config=cfg,
        )
        assert had_work
        assert store.count_pending() == 0


def test_run_once_no_proposals_clears_context():
    """When analyzer produces no proposals, stale rejection_context is cleared."""
    from agent_self_edit.cli.run import _run_once

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        store = TraceStore(str(tmp_path / "traces.db"), batch_size=5)
        _seed_traces(store, n=5, success=False)
        reg = Registry(str(tmp_path / "registry"))
        reg.create("prompt v1")
        cfg = _config(tmp_path)

        had_work, ctx = _run_once(
            "dummy.yaml", 5, False, "stale rejection context",
            store=store, registry=reg, config=cfg,
        )
        # With mock analyzer producing no proposals, context should be cleared
        assert had_work
        assert ctx == "", "stale context should be cleared when no proposals"


def test_run_once_promotion_increments_version():
    """Promotion path increments registry version."""
    from agent_self_edit.cli.run import _run_once

    proposal = EditProposal(
        section="test", old_text="prompt v1", new_text="prompt v2",
        hypothesis="fix test", expected_improvement="better",
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        store = TraceStore(str(tmp_path / "traces.db"), batch_size=5)
        _seed_traces(store, n=5, success=False)
        reg = Registry(str(tmp_path / "registry"))
        reg.create("prompt v1")
        initial_version = reg.current_version
        cfg = _config(tmp_path)

        with (
            patch("agent_self_edit.cli.propose._build_llm_for_role", return_value=MockProvider()),
            patch("agent_self_edit.tasks.load_task_set"),
            patch("agent_self_edit.scorers.resolve_scorer"),
            patch("agent_self_edit.analyzer.analyze_batch") as mock_analyze,
            patch("agent_self_edit.ab_test.run_ab_test") as mock_ab,
            patch("agent_self_edit.gate.PromotionGate") as mock_gate_cls,
        ):
            from agent_self_edit.analyzer import AnalysisResult

            mock_analyze.return_value = AnalysisResult(
                proposals=[proposal], tokens_used=10, cost_usd=0.01,
            )
            mock_ab.return_value = ABResult(
                winner="b", mean_delta=0.2, ci_low=0.01, ci_high=0.4,
                p_value=0.03, effect_size=0.2, n_trials=5,
            )
            mock_gate = mock_gate_cls.return_value
            mock_gate.check.return_value = GateResult(
                decision="promote",
                checks=(CheckResult(name="all", passed=True, value=1.0, threshold=0.0, details="ok"),),
                reason="all checks passed",
            )

            _, ctx = _run_once(
                "dummy.yaml", 5, False, "", store=store, registry=reg, config=cfg,
            )

        assert reg.current_version > initial_version


def test_run_once_rejection_updates_context():
    """Rejection path updates rejection_context."""
    from agent_self_edit.cli.run import _run_once

    proposal = EditProposal(
        section="test", old_text="prompt v1", new_text="prompt v2",
        hypothesis="fix test", expected_improvement="better",
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        store = TraceStore(str(tmp_path / "traces.db"), batch_size=5)
        _seed_traces(store, n=5, success=False)
        reg = Registry(str(tmp_path / "registry"))
        reg.create("prompt v1")
        cfg = _config(tmp_path)

        with (
            patch("agent_self_edit.cli.propose._build_llm_for_role", return_value=MockProvider()),
            patch("agent_self_edit.tasks.load_task_set"),
            patch("agent_self_edit.scorers.resolve_scorer"),
            patch("agent_self_edit.analyzer.analyze_batch") as mock_analyze,
            patch("agent_self_edit.ab_test.run_ab_test") as mock_ab,
            patch("agent_self_edit.gate.PromotionGate") as mock_gate_cls,
        ):
            from agent_self_edit.analyzer import AnalysisResult

            mock_analyze.return_value = AnalysisResult(
                proposals=[proposal], tokens_used=10, cost_usd=0.01,
            )
            mock_ab.return_value = ABResult(
                winner="inconclusive", mean_delta=0.0, ci_low=-0.1, ci_high=0.1,
                p_value=0.5, effect_size=0.0, n_trials=5,
            )
            mock_gate = mock_gate_cls.return_value
            mock_gate.check.return_value = GateResult(
                decision="reject",
                checks=(CheckResult(name="effect_size", passed=False, value=0.0, threshold=0.05, details="low"),),
                reason="effect size too small",
            )

            _, ctx = _run_once(
                "dummy.yaml", 5, False, "", store=store, registry=reg, config=cfg,
            )

        assert "reject" in ctx or "Previous edit" in ctx


def test_run_once_exception_releases_in_flight():
    """Exception path releases in-flight traces for retry."""
    from agent_self_edit.cli.run import _run_once

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        store = TraceStore(str(tmp_path / "traces.db"), batch_size=5)
        _seed_traces(store, n=5, success=False)
        reg = Registry(str(tmp_path / "registry"))
        reg.create("prompt v1")
        cfg = _config(tmp_path)

        with patch("agent_self_edit.cli.propose._build_llm_for_role", side_effect=ValueError("boom")):
            try:
                _run_once(
                    "dummy.yaml", 5, False, "", store=store, registry=reg, config=cfg,
                )
            except ValueError:
                pass

        # In-flight traces should be released back to pending
        pending = store.count_pending()
        assert pending > 0, "in-flight traces should be released on exception"
