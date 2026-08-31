"""propose command: analyze failed traces and propose prompt edits via LLM."""

import click


def _build_llm(config):
    """Build the LLM provider from config file settings."""
    from ..llm.base import ProviderError
    from ..llm.mock import MockProvider

    if config.llm.provider == "mock":
        return MockProvider(responses="mock output")
    if config.llm.provider == "openai":
        from ..llm.openai import OpenAIProvider

        return OpenAIProvider(
            model=config.llm.model,
            api_key=config.llm.api_key or None,
            base_url=config.llm.base_url or None,
            timeout=config.llm.timeout,
            max_tokens=config.llm.max_tokens,
        )
    raise ProviderError(f"Unknown LLM provider: {config.llm.provider}")


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

    batch = store.get_batch(min(config.tasks.batch_size, store.count_pending()))
    if not batch:
        click.echo("No pending traces to analyze.")
        return

    failed = [t for t in batch if not t.success]
    click.echo(f"Analyzing {len(failed)} failed traces (of {len(batch)} in batch)")

    if not failed:
        store.acknowledge([t.task_id for t in batch])
        click.echo("All traces succeeded; no proposals needed.")
        return

    llm = _build_llm(config)
    result = analyze_batch(
        failed, registry.current_prompt, None, llm,
        max_proposals=config.analyzer.max_proposals_per_batch,
        config=config,
    )

    click.echo(f"Proposed {len(result.proposals)} edits (cost=${result.cost_usd:.4f})")
    for p in result.proposals:
        click.echo(f"  - [{p.section}] {p.hypothesis}")

    if dry_run or not result.proposals:
        store.acknowledge([t.task_id for t in batch])
        return

    from ..ab_test import run_ab_test
    from ..gate import PromotionGate, check_all
    from ..scorers import ExactMatchScorer
    from ..tasks import load_task_set

    task_set = load_task_set(config.tasks.task_set_path) if config.tasks.task_set_path else None
    scorer = ExactMatchScorer()

    for proposal in result.proposals:
        ab_result = run_ab_test(
            registry.current_prompt, proposal.new_text, task_set, llm, scorer, config
        )
        click.echo(
            f"  A/B: {ab_result.winner} (p={ab_result.p_value:.4f}, n={ab_result.n_trials})"
        )

        gate = PromotionGate(audit_path=config.project.registry_path + "/audit.jsonl")
        gate_result = check_all(
            proposal, ab_result, registry.current_prompt, registry.current_prompt, config
        )
        click.echo(f"  Gate: {gate_result.decision}")

        if gate_result.decision == "promote":
            registry.create(
                proposal.new_text,
                hypothesis=proposal.hypothesis,
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

        gate.check(proposal, ab_result, registry.current_prompt, registry.current_prompt, config)

    store.acknowledge([t.task_id for t in batch])
