"""propose command: analyze failed traces and propose prompt edits via LLM."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from ..config import Config, ModelRoleConfig
    from ..llm.base import LLMProvider


def _build_llm_for_role(config: Config, role_cfg: ModelRoleConfig) -> LLMProvider:
    """Build a provider for a specific model role, falling back to the default ``llm`` config."""
    provider = role_cfg.provider or config.llm.provider
    model = role_cfg.model or config.llm.model
    api_key = role_cfg.api_key or config.llm.api_key
    base_url = role_cfg.base_url or config.llm.base_url
    max_tokens = role_cfg.max_tokens or config.llm.max_tokens
    timeout = role_cfg.timeout or config.llm.timeout
    extra_body = role_cfg.extra_body if role_cfg.extra_body is not None else config.llm.extra_body
    from ..llm.base import ProviderError
    from ..llm.mock import MockProvider
    if provider == "mock":
        return MockProvider(responses="mock output")
    if provider == "openai":
        from ..llm.openai import OpenAIProvider
        return OpenAIProvider(
            model=model,
            api_key=api_key or None,
            base_url=base_url or None,
            timeout=timeout,
            max_tokens=max_tokens,
            extra_body=extra_body,
        )
    raise ProviderError(f"Unknown LLM provider: {provider}")


def _build_llm(config: Config) -> LLMProvider:
    """Build the default LLM provider from config file settings."""
    return _build_llm_for_role(config, ModelRoleConfig())


@click.command()
@click.option("--config", "config_path", default="agent-self-edit.yaml", help="Config file path")
@click.option("--dry-run", "dry_run", is_flag=True, help="Analyze only, no promotion")
def propose(config_path: str, dry_run: bool) -> None:
    """Analyze pending failed traces and propose minimal prompt edits."""
    from ..analyzer import analyze_batch
    from ..config import load_config
    from ..registry import Registry
    from ..trace import TraceStore

    config = load_config(config_path)
    store = TraceStore(config.project.trace_path, batch_size=config.tasks.batch_size)
    registry = Registry(config.project.registry_path)

    if not store.batch_ready():
        click.echo(f"Batch not ready: {store.count_pending()} / {config.tasks.batch_size} traces")
        return

    batch = store.get_batch(min(config.tasks.batch_size, store.count_pending()))
    if not batch:
        click.echo("No pending traces to analyze.")
        return

    failed = [t for t in batch if not t.success]
    click.echo(f"Analyzing {len(failed)} failed traces (of {len(batch)} in batch)")

    if not failed:
        store.acknowledge_rows(batch)
        click.echo("All traces succeeded; no proposals needed.")
        return

    analyzer_llm = _build_llm_for_role(config, config.analyzer_role)
    from ..gate import GateAuditLog

    audit_path = config.project.registry_path + "/audit.jsonl"
    try:
        near_misses = GateAuditLog(audit_path).near_misses(limit=20)
    except Exception:
        near_misses = []
    result = analyze_batch(
        failed, registry.current_prompt, None, analyzer_llm,
        max_proposals=config.analyzer.max_proposals_per_batch,
        config=config,
        near_misses=near_misses,
    )

    click.echo(f"Proposed {len(result.proposals)} edits (cost=${result.cost_usd:.4f})")
    for p in result.proposals:
        click.echo(f"  - [{p.section}] {p.hypothesis}")

    if dry_run or not result.proposals:
        store.acknowledge_rows(batch)
        return

    from ..ab_test import run_ab_test
    from ..gate import PromotionGate
    from ..scorers import resolve_scorer
    from ..tasks import load_task_set

    task_set = load_task_set(config.tasks.task_set_path) if config.tasks.task_set_path else None
    if task_set is None:
        click.echo("No task set configured — skipping A/B test.", err=True)
        return

    rejection_context_lines: list[str] = []

    # Drift must be measured against original v1, not current (fix 276/206)
    try:
        original_prompt = (
            registry.get(1)[0]
            if registry.current_version >= 1
            else registry.current_prompt
        )
    except Exception:
        original_prompt = registry.current_prompt

    executor_llm = _build_llm_for_role(config, config.executor_role)
    judge_llm = _build_llm_for_role(config, config.judge_role)
    scorer = resolve_scorer(task_set, judge_llm=judge_llm)

    for proposal in result.proposals:
        from ..types import materialize_candidate_prompt

        try:
            candidate_prompt = materialize_candidate_prompt(registry.current_prompt, proposal)
        except ValueError as e:
            click.echo(f"  Skipping proposal: {e}", err=True)
            continue
        ab_result = run_ab_test(
            registry.current_prompt, candidate_prompt, task_set, executor_llm, scorer, config
        )
        click.echo(
            f"  A/B: {ab_result.winner} (p={ab_result.p_value:.4f}, n={ab_result.n_trials})"
        )

        gate = PromotionGate(audit_path=config.project.registry_path + "/audit.jsonl")
        gate_result = gate.check(
            proposal, ab_result, registry.current_prompt, original_prompt, config
        )
        click.echo(f"  Gate: {gate_result.decision}")

        if gate_result.decision in ("reject", "near_miss"):
            rejection_context_lines.append(
                f"Previous edit '{proposal.hypothesis}' was {gate_result.decision}: "
                f"{gate_result.reason}"
            )

        if gate_result.decision == "promote":
            registry.create(
                candidate_prompt,
                hypothesis=proposal.hypothesis,
                changed_section=proposal.section,
                ab_results={
                    "winner": ab_result.winner,
                    "mean_delta": ab_result.mean_delta,
                    "p_value": ab_result.p_value,
                    "effect_size": ab_result.effect_size,
                    "n_trials": ab_result.n_trials,
                },
                gate_result={"decision": gate_result.decision, "reason": gate_result.reason},
            )
            click.echo(f"  Promoted to version {registry.current_version}")

    store.acknowledge_rows(batch)
