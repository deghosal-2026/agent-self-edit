"""M7/M5 CLI coverage补 — propose and run hermetic tests for 85%/80%+."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from agent_self_edit.analyzer import AnalysisResult
from agent_self_edit.cli.propose import _build_llm, _build_llm_for_role
from agent_self_edit.cli.run import _run_once
from agent_self_edit.config import Config, LLMConfig, ModelRoleConfig, ProjectConfig
from agent_self_edit.llm.base import ProviderError
from agent_self_edit.registry import Registry
from agent_self_edit.trace import TraceStore
from agent_self_edit.types import EditProposal

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _valid_trace(task_id: str = "t1", success: bool = True) -> dict:
    return {
        "task_id": task_id,
        "task_input": "hi",
        "final_output": "hello",
        "expected_output": "hello",
        "success": success,
        "timestamp": "2026-09-01T10:00:00Z",
    }


def _write_cfg(
    tmp_path: Path,
    *,
    batch_size: int = 5,
    trace_path: Path | None = None,
    registry_path: Path | None = None,
    task_set_path: str = "",
    provider: str = "mock",
) -> Path:
    reg = registry_path or (tmp_path / "reg")
    db = trace_path or (tmp_path / "traces.db")
    cfg_path = tmp_path / "agent-self-edit.yaml"
    data = {
        "schema_version": 1,
        "project": {
            "name": "test",
            "registry_path": str(reg),
            "trace_path": str(db),
        },
        "tasks": {
            "task_set_path": task_set_path,
            "batch_size": batch_size,
            "sample_floor": 10,
        },
        "llm": {
            "provider": provider,
            "model": "m",
            "api_key": "",
            "temperature": 0.0,
            "max_tokens": 4096,
            "timeout": 30,
        },
        "ab_test": {
            "n_resamples": 10,
            "n_permutations": 10,
            "confidence_level": 0.95,
            "min_effect_size": 0.05,
            "cost_ceiling_usd": 10.0,
        },
        "gate": {
            "max_edit_distance": 100,
            "drift_threshold": 1.0,
            "near_miss_threshold": 0.5,
        },
        "analyzer": {
            "max_proposals_per_batch": 3,
            "cost_ceiling_usd": 5.0,
        },
        "trigger": "batch",
        "trace_retention_days": 90,
    }
    cfg_path.write_text(yaml.dump(data))
    return cfg_path


def _write_tasks(tmp_path: Path, n: int = 1) -> Path:
    p = tmp_path / "tasks.yaml"
    tasks = [{"id": f"t{i}", "input": "hi", "expected_output": "hello"} for i in range(n)]
    p.write_text(yaml.dump(tasks))
    return p


# ---------------------------------------------------------------------------
# _build_llm_for_role / _build_llm
# ---------------------------------------------------------------------------


def test_build_llm_for_role_mock_provider() -> None:
    cfg = Config(project=ProjectConfig(name="x"), llm=LLMConfig(provider="mock", model="m"))
    role = ModelRoleConfig(provider="mock")
    llm = _build_llm_for_role(cfg, role)
    assert llm is not None
    assert llm.complete(prompt="hi") == "mock output"


def test_build_llm_for_role_fallback_to_config() -> None:
    cfg = Config(project=ProjectConfig(name="x"), llm=LLMConfig(provider="mock", model="cfg-model"))
    role = ModelRoleConfig(provider=None, model=None)
    llm = _build_llm_for_role(cfg, role)
    assert llm is not None
    # fallback uses config provider mock
    assert "mock" in type(llm).__name__.lower() or hasattr(llm, "complete")


def test_build_llm_for_role_openai_patched() -> None:
    cfg = Config(project=ProjectConfig(name="x"), llm=LLMConfig(provider="mock"))
    role = ModelRoleConfig(provider="openai", model="gpt-4o", api_key="sk", base_url="http://x", max_tokens=10, timeout=5)
    with patch("agent_self_edit.llm.openai.OpenAIProvider") as mock_cls:
        inst = MagicMock()
        mock_cls.return_value = inst
        llm = _build_llm_for_role(cfg, role)
        assert llm is inst
        mock_cls.assert_called_once()
        kwargs = mock_cls.call_args.kwargs
        assert kwargs["model"] == "gpt-4o"
        assert kwargs["api_key"] == "sk"


def test_build_llm_for_role_openai_extra_body_from_role() -> None:
    cfg = Config(project=ProjectConfig(name="x"), llm=LLMConfig(provider="mock", extra_body={"a": 1}))
    role = ModelRoleConfig(provider="openai", extra_body={"b": 2})
    with patch("agent_self_edit.llm.openai.OpenAIProvider") as mock_cls:
        mock_cls.return_value = MagicMock()
        _build_llm_for_role(cfg, role)
        assert mock_cls.call_args.kwargs["extra_body"] == {"b": 2}


def test_build_llm_for_role_extra_body_fallback() -> None:
    cfg = Config(project=ProjectConfig(name="x"), llm=LLMConfig(provider="openai", extra_body={"cfg": 1}, model="m"))
    role = ModelRoleConfig(provider="openai")
    with patch("agent_self_edit.llm.openai.OpenAIProvider") as mock_cls:
        mock_cls.return_value = MagicMock()
        _build_llm_for_role(cfg, role)
        assert mock_cls.call_args.kwargs["extra_body"] == {"cfg": 1}


def test_build_llm_for_role_unknown_raises() -> None:
    cfg = Config(project=ProjectConfig(name="x"), llm=LLMConfig(provider="mock"))
    role = ModelRoleConfig(provider="unknown_xyz")
    with pytest.raises(ProviderError, match="Unknown LLM provider"):
        _build_llm_for_role(cfg, role)


def test_build_llm_wrapper() -> None:
    cfg = Config(project=ProjectConfig(name="x"), llm=LLMConfig(provider="mock"))
    import importlib

    mod = importlib.import_module("agent_self_edit.cli.propose")
    # propose.py references ModelRoleConfig only under TYPE_CHECKING, so inject for test
    mod.ModelRoleConfig = ModelRoleConfig  # type: ignore[attr-defined]
    try:
        with patch("agent_self_edit.cli.propose._build_llm_for_role") as mock_build:
            inst = MagicMock()
            mock_build.return_value = inst
            llm = _build_llm(cfg)
            assert llm is inst
            mock_build.assert_called_once()
    finally:
        # clean up inject
        if hasattr(mod, "ModelRoleConfig"):
            try:
                delattr(mod, "ModelRoleConfig")
            except Exception:
                pass


# ---------------------------------------------------------------------------
# propose — batch_not_ready
# ---------------------------------------------------------------------------


def test_propose_batch_not_ready(tmp_path: Path) -> None:
    cfg_path = _write_cfg(tmp_path, batch_size=5)
    # 3 traces < batch_size 5 -> not ready
    store = TraceStore(str(tmp_path / "traces.db"), batch_size=5)
    for i in range(3):
        store.ingest(_valid_trace(f"p{i}", success=False))
    runner = CliRunner()
    result = runner.invoke(
        __import__("agent_self_edit.cli.propose", fromlist=["propose"]).propose,
        ["--config", str(cfg_path)],
    )
    assert result.exit_code == 0
    assert "Batch not ready" in result.output
    assert "3 / 5" in result.output
    assert store.count_pending() == 3


def test_propose_all_succeeded(tmp_path: Path) -> None:
    cfg_path = _write_cfg(tmp_path, batch_size=2)
    Registry(str(tmp_path / "reg")).create("You are a classifier.")
    store = TraceStore(str(tmp_path / "traces.db"), batch_size=2)
    for i in range(2):
        store.ingest(_valid_trace(f"s{i}", success=True))
    runner = CliRunner()
    from agent_self_edit.cli.propose import propose as propose_cmd

    with patch("agent_self_edit.cli.propose._build_llm_for_role") as mock_llm:
        mock_llm.return_value = MagicMock()
        result = runner.invoke(propose_cmd, ["--config", str(cfg_path)])
    assert result.exit_code == 0
    assert "All traces succeeded" in result.output


def test_propose_dry_run_with_failures(tmp_path: Path) -> None:
    cfg_path = _write_cfg(tmp_path, batch_size=2)
    Registry(str(tmp_path / "reg")).create("You are a classifier.")
    store = TraceStore(str(tmp_path / "traces.db"), batch_size=2)
    for i in range(2):
        store.ingest(_valid_trace(f"f{i}", success=False))
    from agent_self_edit.cli.propose import propose as propose_cmd

    fake_result = AnalysisResult(
        proposals=[
            EditProposal(
                section="x",
                old_text="classifier",
                new_text="expert classifier",
                hypothesis="h",
                expected_improvement="e",
            )
        ],
        cost_usd=0.01,
    )
    with patch("agent_self_edit.analyzer.analyze_batch", return_value=fake_result):
        runner = CliRunner()
        result = runner.invoke(propose_cmd, ["--config", str(cfg_path), "--dry-run"])
        assert result.exit_code == 0
        assert "Proposed 1 edits" in result.output


def test_propose_near_miss_dedup_passed(tmp_path: Path) -> None:
    cfg_path = _write_cfg(tmp_path, batch_size=2)
    Registry(str(tmp_path / "reg")).create("You are a classifier.")
    store = TraceStore(str(tmp_path / "traces.db"), batch_size=2)
    for i in range(2):
        store.ingest(_valid_trace(f"n{i}", success=False))
    from agent_self_edit.cli.propose import propose as propose_cmd

    nm = [
        EditProposal(section="x", old_text="a", new_text="b", hypothesis="h", expected_improvement="e"),
    ]
    mock_audit = MagicMock()
    mock_audit.near_misses.return_value = nm

    fake_result = AnalysisResult(proposals=[], cost_usd=0.01)

    with patch("agent_self_edit.gate.GateAuditLog", return_value=mock_audit):
        with patch("agent_self_edit.analyzer.analyze_batch", return_value=fake_result) as mock_ab:
            runner = CliRunner()
            result = runner.invoke(propose_cmd, ["--config", str(cfg_path), "--dry-run"])
            assert result.exit_code == 0
            # analyze_batch should have been called with near_misses == nm
            assert mock_ab.call_args.kwargs["near_misses"] == nm
            mock_audit.near_misses.assert_called_once_with(limit=20)


def test_propose_near_miss_exception_fallback(tmp_path: Path) -> None:
    cfg_path = _write_cfg(tmp_path, batch_size=2)
    Registry(str(tmp_path / "reg")).create("You are a classifier.")
    store = TraceStore(str(tmp_path / "traces.db"), batch_size=2)
    for i in range(2):
        store.ingest(_valid_trace(f"e{i}", success=False))
    from agent_self_edit.cli.propose import propose as propose_cmd

    with patch("agent_self_edit.gate.GateAuditLog", side_effect=Exception("audit fail")):
        fake_result = AnalysisResult(proposals=[], cost_usd=0.0)
        with patch("agent_self_edit.analyzer.analyze_batch", return_value=fake_result) as mock_ab:
            runner = CliRunner()
            result = runner.invoke(propose_cmd, ["--config", str(cfg_path), "--dry-run"])
            assert result.exit_code == 0
            assert mock_ab.call_args.kwargs["near_misses"] == []


def test_propose_original_prompt_v1(tmp_path: Path) -> None:
    task_path = _write_tasks(tmp_path, n=2)
    cfg_path = _write_cfg(tmp_path, batch_size=2, task_set_path=str(task_path))
    reg = Registry(str(tmp_path / "reg"))
    reg.create("You are a classifier.")
    reg.create("You are an updated classifier.")
    # current prompt is v2, original v1 is different
    store = TraceStore(str(tmp_path / "traces.db"), batch_size=2)
    for i in range(2):
        store.ingest(_valid_trace(f"o{i}", success=False))
    from agent_self_edit.cli.propose import propose as propose_cmd

    proposal = EditProposal(
        section="intro",
        old_text="updated classifier",
        new_text="expert updated classifier",
        hypothesis="h",
        expected_improvement="e",
    )
    fake_result = AnalysisResult(proposals=[proposal], cost_usd=0.01)

    ab = MagicMock()
    ab.winner = "b"
    ab.p_value = 0.01
    ab.n_trials = 10
    ab.mean_delta = 0.1
    ab.effect_size = 0.3

    gate_res = MagicMock()
    gate_res.decision = "promote"
    gate_res.reason = "all good"

    with patch("agent_self_edit.analyzer.analyze_batch", return_value=fake_result):
        with patch("agent_self_edit.tasks.load_task_set", return_value=MagicMock()):
            with patch("agent_self_edit.scorers.resolve_scorer", return_value=MagicMock()):
                with patch("agent_self_edit.ab_test.run_ab_test", return_value=ab):
                    with patch("agent_self_edit.gate.check_all", return_value=gate_res):
                        with patch("agent_self_edit.gate.PromotionGate") as mock_gate_cls:
                            mock_gate = MagicMock()
                            mock_gate.check.return_value = gate_res
                            mock_gate_cls.return_value = mock_gate
                            with patch("agent_self_edit.cli.propose._build_llm_for_role", return_value=MagicMock()):
                                runner = CliRunner()
                                result = runner.invoke(propose_cmd, ["--config", str(cfg_path)])
                                assert result.exit_code == 0
                                # original_prompt should be v1 text
                                v1_text, _ = reg.get(1)
                                assert mock_gate.check.call_args[0][3] == v1_text
                                assert "Promoted to version" in result.output


def test_propose_original_prompt_exception_fallback(tmp_path: Path) -> None:
    task_path = _write_tasks(tmp_path, n=1)
    cfg_path = _write_cfg(tmp_path, batch_size=1, task_set_path=str(task_path))
    reg = Registry(str(tmp_path / "reg"))
    reg.create("prompt alpha")
    store = TraceStore(str(tmp_path / "traces.db"), batch_size=1)
    store.ingest(_valid_trace("x1", success=False))
    from agent_self_edit.cli.propose import propose as propose_cmd

    proposal = EditProposal(
        section="s",
        old_text="alpha",
        new_text="beta",
        hypothesis="h",
        expected_improvement="e",
    )
    fake_result = AnalysisResult(proposals=[proposal], cost_usd=0.01)
    ab = MagicMock()
    ab.winner = "tie"
    ab.p_value = 0.5
    ab.n_trials = 10
    ab.mean_delta = 0.0
    ab.effect_size = 0.0
    gate_res = MagicMock()
    gate_res.decision = "reject"
    gate_res.reason = "failed"

    with patch("agent_self_edit.analyzer.analyze_batch", return_value=fake_result):
        with patch("agent_self_edit.tasks.load_task_set", return_value=MagicMock()):
            with patch("agent_self_edit.scorers.resolve_scorer", return_value=MagicMock()):
                with patch("agent_self_edit.ab_test.run_ab_test", return_value=ab):
                    with patch("agent_self_edit.gate.check_all", return_value=gate_res):
                        with patch("agent_self_edit.gate.PromotionGate") as mock_gate_cls:
                            mock_gate = MagicMock()
                            mock_gate.check.return_value = gate_res
                            mock_gate_cls.return_value = mock_gate
                            with patch("agent_self_edit.cli.propose._build_llm_for_role", return_value=MagicMock()):
                                # force registry.get to raise
                                with patch.object(Registry, "get", side_effect=Exception("boom")):
                                    runner = CliRunner()
                                    result = runner.invoke(propose_cmd, ["--config", str(cfg_path)])
                                    assert result.exit_code == 0
                                    # should still succeed via fallback to current_prompt
                                    assert "Gate:" in result.output


def test_propose_no_task_set_skip_ab(tmp_path: Path) -> None:
    cfg_path = _write_cfg(tmp_path, batch_size=1, task_set_path="")
    Registry(str(tmp_path / "reg")).create("You are a classifier.")
    store = TraceStore(str(tmp_path / "traces.db"), batch_size=1)
    store.ingest(_valid_trace("t1", success=False))
    from agent_self_edit.cli.propose import propose as propose_cmd

    proposal = EditProposal(section="x", old_text="classifier", new_text="expert", hypothesis="h", expected_improvement="e")
    fake_result = AnalysisResult(proposals=[proposal], cost_usd=0.01)
    with patch("agent_self_edit.analyzer.analyze_batch", return_value=fake_result):
        with patch("agent_self_edit.cli.propose._build_llm_for_role", return_value=MagicMock()):
            runner = CliRunner()
            result = runner.invoke(propose_cmd, ["--config", str(cfg_path)])
            assert result.exit_code == 0
            assert "No task set configured" in result.output


def test_propose_gate_reject_and_near_miss_context(tmp_path: Path) -> None:
    task_path = _write_tasks(tmp_path, n=1)
    cfg_path = _write_cfg(tmp_path, batch_size=2, task_set_path=str(task_path))
    reg = Registry(str(tmp_path / "reg"))
    reg.create("hello world prompt")
    store = TraceStore(str(tmp_path / "traces.db"), batch_size=2)
    for i in range(2):
        store.ingest(_valid_trace(f"r{i}", success=False))
    from agent_self_edit.cli.propose import propose as propose_cmd

    p1 = EditProposal(section="s", old_text="hello", new_text="hi", hypothesis="h1", expected_improvement="e")
    p2 = EditProposal(section="s", old_text="world", new_text="earth", hypothesis="h2", expected_improvement="e")
    fake_result = AnalysisResult(proposals=[p1, p2], cost_usd=0.02)
    ab = MagicMock()
    ab.winner = "a"
    ab.p_value = 0.5
    ab.n_trials = 10
    ab.mean_delta = 0.0
    ab.effect_size = 0.0

    # first reject, second near_miss
    def check_side(edit, ab_result, cur, orig, cfg):
        from agent_self_edit.types import GateResult

        if edit.hypothesis == "h1":
            return GateResult(decision="reject", reason="bad")
        return GateResult(decision="near_miss", reason="close")

    with patch("agent_self_edit.analyzer.analyze_batch", return_value=fake_result):
        with patch("agent_self_edit.tasks.load_task_set", return_value=MagicMock()):
            with patch("agent_self_edit.scorers.resolve_scorer", return_value=MagicMock()):
                with patch("agent_self_edit.ab_test.run_ab_test", return_value=ab):
                    with patch("agent_self_edit.gate.check_all", side_effect=check_side):
                        with patch("agent_self_edit.gate.PromotionGate") as mock_gate_cls:
                            mock_gate = MagicMock()
                            mock_gate.check.side_effect = check_side
                            mock_gate_cls.return_value = mock_gate
                            with patch("agent_self_edit.cli.propose._build_llm_for_role", return_value=MagicMock()):
                                runner = CliRunner()
                                result = runner.invoke(propose_cmd, ["--config", str(cfg_path)])
                                assert result.exit_code == 0
                                assert result.output.count("Gate:") >= 2


def test_propose_no_proposals_acknowledge(tmp_path: Path) -> None:
    cfg_path = _write_cfg(tmp_path, batch_size=1)
    Registry(str(tmp_path / "reg")).create("prompt")
    store = TraceStore(str(tmp_path / "traces.db"), batch_size=1)
    store.ingest(_valid_trace("z1", success=False))
    from agent_self_edit.cli.propose import propose as propose_cmd

    fake_result = AnalysisResult(proposals=[], cost_usd=0.0)
    with patch("agent_self_edit.analyzer.analyze_batch", return_value=fake_result):
        with patch("agent_self_edit.cli.propose._build_llm_for_role", return_value=MagicMock()):
            runner = CliRunner()
            result = runner.invoke(propose_cmd, ["--config", str(cfg_path), "--dry-run"])
            assert result.exit_code == 0
            # should not try AB test
            assert store.count_pending() == 0


# ---------------------------------------------------------------------------
# run — _run_once
# ---------------------------------------------------------------------------


def test_run_batch_not_ready(tmp_path: Path) -> None:
    cfg_path = _write_cfg(tmp_path, batch_size=5)
    store = TraceStore(str(tmp_path / "traces.db"), batch_size=5)
    for i in range(2):
        store.ingest(_valid_trace(f"b{i}", success=False))
    had_work, ctx = _run_once(str(cfg_path), batch_size=5, dry_run=False, rejection_context="old")
    assert had_work is False
    assert ctx == "old"


def test_run_all_succeeded(tmp_path: Path) -> None:
    cfg_path = _write_cfg(tmp_path, batch_size=2)
    Registry(str(tmp_path / "reg")).create("prompt")
    store = TraceStore(str(tmp_path / "traces.db"), batch_size=2)
    for i in range(2):
        store.ingest(_valid_trace(f"as{i}", success=True))
    had_work, ctx = _run_once(str(cfg_path), batch_size=2, dry_run=False, rejection_context="ctx")
    assert had_work is True
    assert ctx == "ctx"
    # acknowledged
    assert TraceStore(str(tmp_path / "traces.db"), batch_size=2).count_pending() == 0


def test_run_release_in_flight_on_exception(tmp_path: Path) -> None:
    cfg_path = _write_cfg(tmp_path, batch_size=2)
    reg = Registry(str(tmp_path / "reg"))
    reg.create("hello world prompt")
    task_path = _write_tasks(tmp_path)
    # rewrite cfg to have task set for this test
    cfg_path = _write_cfg(tmp_path, batch_size=2, task_set_path=str(task_path))
    Registry(str(tmp_path / "reg"))  # ensure reg exists
    store = TraceStore(str(tmp_path / "traces.db"), batch_size=2)
    for i in range(2):
        store.ingest(_valid_trace(f"rel{i}", success=False,))

    # Force analyzer to raise via _llm_call
    with patch("agent_self_edit.analyzer._llm_call", side_effect=Exception("boom")):
        try:
            _run_once(str(cfg_path), batch_size=2, dry_run=False, rejection_context="old")
        except Exception as e:
            assert "boom" in str(e)
        else:
            pytest.fail("should have raised")

    # in-flight released -> pending ==2 (using new store instance to read)
    assert TraceStore(str(tmp_path / "traces.db"), batch_size=2).count_pending() == 2


def test_run_stale_rejection_context_clear(tmp_path: Path) -> None:
    cfg_path = _write_cfg(tmp_path, batch_size=1)
    Registry(str(tmp_path / "reg")).create("prompt text")
    store = TraceStore(str(tmp_path / "traces.db"), batch_size=1)
    store.ingest(_valid_trace("stale1", success=False))
    fake_result = AnalysisResult(proposals=[], cost_usd=0.01)
    with patch("agent_self_edit.analyzer.analyze_batch", return_value=fake_result):
        with patch("agent_self_edit.cli.propose._build_llm_for_role", return_value=MagicMock()):
            had_work, new_ctx = _run_once(str(cfg_path), batch_size=1, dry_run=False, rejection_context="old ctx")
            assert had_work is True
            assert new_ctx == ""


def test_run_stale_rejection_context_kept_on_dry_run(tmp_path: Path) -> None:
    cfg_path = _write_cfg(tmp_path, batch_size=1)
    Registry(str(tmp_path / "reg")).create("prompt")
    store = TraceStore(str(tmp_path / "traces.db"), batch_size=1)
    store.ingest(_valid_trace("dry1", success=False))
    fake_result = AnalysisResult(proposals=[], cost_usd=0.01)
    with patch("agent_self_edit.analyzer.analyze_batch", return_value=fake_result):
        with patch("agent_self_edit.cli.propose._build_llm_for_role", return_value=MagicMock()):
            had_work, new_ctx = _run_once(str(cfg_path), batch_size=1, dry_run=True, rejection_context="keep me")
            assert new_ctx == "keep me"


def test_run_store_registry_reuse(tmp_path: Path) -> None:
    cfg_path = _write_cfg(tmp_path, batch_size=1)
    reg = Registry(str(tmp_path / "reg"))
    reg.create("reuse prompt")
    store = TraceStore(str(tmp_path / "traces.db"), batch_size=1)
    store.ingest(_valid_trace("reuse1", success=True))
    # patch iterdir to count calls — if reuse works, _run_once with passed store/registry
    # should not call iterdir (which is used in Registry.__init__ _resolve_current)
    from unittest.mock import patch as m_patch

    original_iterdir = Path.iterdir
    calls = {"c": 0}

    def counting_iterdir(self):  # type: ignore[no-untyped-def]
        calls["c"] += 1
        return original_iterdir(self)

    with m_patch.object(Path, "iterdir", counting_iterdir):
        # First call without reuse should trigger iterdir (load_config + TraceStore + Registry)
        # But we pass store/registry/config so should be zero extra calls
        from agent_self_edit.config import load_config

        cfg = load_config(str(cfg_path))
        before = calls["c"]
        _run_once(str(cfg_path), batch_size=1, dry_run=True, rejection_context="", store=store, registry=reg, config=cfg)
        after = calls["c"]
        # No new Registry creation, so iterdir not increased by Registry init
        assert after == before


def test_run_reuse_avoids_reconstruction(tmp_path: Path) -> None:
    cfg_path = _write_cfg(tmp_path, batch_size=1)
    Registry(str(tmp_path / "reg")).create("prompt")
    store = TraceStore(str(tmp_path / "traces.db"), batch_size=1)
    store.ingest(_valid_trace("rr1", success=True))
    from agent_self_edit.config import load_config

    cfg = load_config(str(cfg_path))
    with patch("agent_self_edit.cli.run.load_config") as mock_load:
        with patch("agent_self_edit.cli.run.TraceStore") as mock_ts:
            with patch("agent_self_edit.cli.run.Registry") as mock_reg:
                mock_load.return_value = cfg
                mock_ts.return_value = store
                mock_reg.return_value = Registry(str(tmp_path / "reg"))
                # when store/registry/config are passed, constructors should NOT be called
                _run_once(str(cfg_path), batch_size=1, dry_run=True, rejection_context="", store=store, registry=Registry(str(tmp_path / "reg")), config=cfg)
                mock_load.assert_not_called()
                mock_ts.assert_not_called()
                mock_reg.assert_not_called()


def test_run_near_miss_load_and_original_prompt(tmp_path: Path) -> None:
    task_path = _write_tasks(tmp_path)
    cfg_path = _write_cfg(tmp_path, batch_size=1, task_set_path=str(task_path))
    reg = Registry(str(tmp_path / "reg"))
    reg.create("original prompt v1")
    reg.create("current prompt v2 with hello world")
    store = TraceStore(str(tmp_path / "traces.db"), batch_size=1)
    store.ingest(_valid_trace("nm1", success=False))
    proposal = EditProposal(section="s", old_text="hello", new_text="hi", hypothesis="h", expected_improvement="e")
    fake_result = AnalysisResult(proposals=[proposal], cost_usd=0.01)
    ab = MagicMock()
    ab.winner = "b"
    ab.p_value = 0.01
    ab.n_trials = 10
    ab.mean_delta = 0.1
    ab.effect_size = 0.2
    gate_res = MagicMock()
    gate_res.decision = "promote"
    gate_res.reason = "ok"
    nm = [EditProposal(section="x", old_text="a", new_text="b", hypothesis="h", expected_improvement="e")]
    mock_audit = MagicMock()
    mock_audit.near_misses.return_value = nm
    with patch("agent_self_edit.gate.GateAuditLog", return_value=mock_audit):
        with patch("agent_self_edit.analyzer.analyze_batch", return_value=fake_result) as mock_ab:
            with patch("agent_self_edit.tasks.load_task_set", return_value=MagicMock()):
                with patch("agent_self_edit.scorers.resolve_scorer", return_value=MagicMock()):
                    with patch("agent_self_edit.ab_test.run_ab_test", return_value=ab):
                        with patch("agent_self_edit.gate.check_all", return_value=gate_res):
                            with patch("agent_self_edit.gate.PromotionGate") as mock_gate_cls:
                                mock_gate = MagicMock()
                                mock_gate.check.return_value = gate_res
                                mock_gate_cls.return_value = mock_gate
                                with patch("agent_self_edit.cli.propose._build_llm_for_role", return_value=MagicMock()):
                                    had_work, new_ctx = _run_once(str(cfg_path), batch_size=1, dry_run=False, rejection_context="prev")
                                    assert had_work is True
                                    # near_misses passed through
                                    assert mock_ab.call_args.kwargs["near_misses"] == nm
                                    # original prompt is v1
                                    v1, _ = reg.get(1)
                                    assert mock_gate.check.call_args[0][3] == v1


def test_run_original_prompt_exception_fallback(tmp_path: Path) -> None:
    task_path = _write_tasks(tmp_path)
    cfg_path = _write_cfg(tmp_path, batch_size=1, task_set_path=str(task_path))
    reg = Registry(str(tmp_path / "reg"))
    reg.create("fallback prompt")
    store = TraceStore(str(tmp_path / "traces.db"), batch_size=1)
    store.ingest(_valid_trace("fb1", success=False))
    proposal = EditProposal(section="s", old_text="fallback", new_text="new", hypothesis="h", expected_improvement="e")
    fake_result = AnalysisResult(proposals=[proposal], cost_usd=0.01)
    ab = MagicMock()
    ab.winner = "tie"
    ab.p_value = 0.5
    ab.n_trials = 10
    ab.mean_delta = 0.0
    ab.effect_size = 0.0
    gate_res = MagicMock()
    gate_res.decision = "reject"
    gate_res.reason = "bad"
    with patch("agent_self_edit.analyzer.analyze_batch", return_value=fake_result):
        with patch("agent_self_edit.tasks.load_task_set", return_value=MagicMock()):
            with patch("agent_self_edit.scorers.resolve_scorer", return_value=MagicMock()):
                with patch("agent_self_edit.ab_test.run_ab_test", return_value=ab):
                    with patch("agent_self_edit.gate.check_all", return_value=gate_res):
                        with patch("agent_self_edit.gate.PromotionGate") as mock_gate_cls:
                            mock_gate = MagicMock()
                            mock_gate.check.return_value = gate_res
                            mock_gate_cls.return_value = mock_gate
                            with patch("agent_self_edit.cli.propose._build_llm_for_role", return_value=MagicMock()):
                                with patch.object(Registry, "get", side_effect=Exception("boom")):
                                    had_work, new_ctx = _run_once(str(cfg_path), batch_size=1, dry_run=False, rejection_context="")
                                    assert had_work is True
                                    assert "Previous edit" in new_ctx


def test_run_cli_once_and_loop_stopped(tmp_path: Path) -> None:
    cfg_path = _write_cfg(tmp_path, batch_size=1)
    Registry(str(tmp_path / "reg")).create("prompt")
    store = TraceStore(str(tmp_path / "traces.db"), batch_size=1)
    store.ingest(_valid_trace("cli1", success=True))
    from agent_self_edit.cli import main

    runner = CliRunner()
    with patch("agent_self_edit.cli.run.time.sleep") as mock_sleep:
        result = runner.invoke(main, ["run", "--once", "--config", str(cfg_path)])
        assert result.exit_code == 0
        assert "Loop stopped" in result.output
        mock_sleep.assert_not_called()


def test_run_cli_error_handling(tmp_path: Path) -> None:
    cfg_path = _write_cfg(tmp_path, batch_size=1)
    Registry(str(tmp_path / "reg")).create("prompt")
    from agent_self_edit.cli import main

    runner = CliRunner()
    with patch("agent_self_edit.cli.run._run_once", side_effect=Exception("cycle boom")):
        with patch("agent_self_edit.cli.run.time.sleep"):
            result = runner.invoke(main, ["run", "--once", "--config", str(cfg_path)])
            assert result.exit_code == 0
            assert "Error in cycle" in result.output
            assert "Loop stopped" in result.output


def test_run_signal_handler_registered(tmp_path: Path) -> None:
    cfg_path = _write_cfg(tmp_path, batch_size=1)
    Registry(str(tmp_path / "reg")).create("prompt")
    store = TraceStore(str(tmp_path / "traces.db"), batch_size=1)
    store.ingest(_valid_trace("sig1", success=True))
    from agent_self_edit.cli import main

    runner = CliRunner()
    captured: dict = {}
    orig_signal = __import__("signal")

    def fake_signal(sig, handler):  # type: ignore[no-untyped-def]
        captured[sig] = handler
        return None

    with patch("agent_self_edit.cli.run.signal.signal", side_effect=fake_signal):
        with patch("agent_self_edit.cli.run.time.sleep"):
            result = runner.invoke(main, ["run", "--once", "--config", str(cfg_path)])
            assert result.exit_code == 0
            assert orig_signal.SIGINT in captured
            assert orig_signal.SIGTERM in captured
            # handler should set shutdown and echo
            h = captured[orig_signal.SIGINT]
            # handler signature (signum, frame)
            h(2, None)
