"""run command: start the self-improvement loop."""

import signal
import time

import click

from ..config import load_config
from ..registry import Registry
from ..trace import TraceStore


def _run_once(config_path: str, batch_size: int | None, dry_run: bool) -> None:
    config = load_config(config_path)
    store = TraceStore(config.project.trace_path, batch_size=batch_size or config.tasks.batch_size)
    registry = Registry(config.project.registry_path)

    if not store.batch_ready():
        click.echo("No pending traces ready for analysis.")
        return

    batch = store.get_batch(min(batch_size or config.tasks.batch_size, store.count_pending()))
    if not batch:
        return

    failed = [t for t in batch if not t.success]
    click.echo(f"Processing {len(batch)} traces ({len(failed)} failed)")

    if not failed:
        store.acknowledge([t.task_id for t in batch])
        click.echo("All traces succeeded; no analysis needed.")
        return

    from ..analyzer import analyze_batch
    from ..llm.mock import MockProvider

    llm = MockProvider(responses="[]")
    result = analyze_batch(
        failed, registry.current_prompt, None, llm,
        max_proposals=config.analyzer.max_proposals_per_batch,
        config=config,
    )

    click.echo(f"Analysis complete: {len(result.proposals)} proposals, cost=${result.cost_usd:.4f}")

    if dry_run or not result.proposals:
        store.acknowledge([t.task_id for t in batch])
        return

    for proposal in result.proposals:
        from ..ab_test import run_ab_test
        from ..gate import PromotionGate, check_all
        from ..scorers import ExactMatchScorer

        task_set = None  # would need config.tasks.task_set_path
        from ..tasks import load_task_set
        task_set = load_task_set(config.tasks.task_set_path)

        scorer = ExactMatchScorer()
        ab_result = run_ab_test(
            registry.current_prompt, proposal.new_text, task_set, llm, scorer, config
        )
        click.echo(
            f"  A/B test: {ab_result.winner} "
            f"(p={ab_result.p_value:.4f}, n={ab_result.n_trials})"
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


@click.command()
@click.option("--config", "config_path", default="agent-self-edit.yaml", help="Config file path")
@click.option("--batch-size", type=int, help="Override batch size")
@click.option("--once", "once_flag", is_flag=True, help="Run one cycle and exit")
@click.option("--dry-run", "dry_run", is_flag=True, help="Analyze only, no A/B test or gate")
def run(config_path: str, batch_size: int | None, once_flag: bool, dry_run: bool) -> None:
    """Start the self-improvement loop."""
    shutdown = False

    def _handler(signum: int, frame: object) -> None:
        nonlocal shutdown
        shutdown = True
        click.echo("Shutdown signal received; finishing current cycle...")

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)

    while not shutdown:
        try:
            _run_once(config_path, batch_size, dry_run)
        except Exception as e:
            click.echo(f"Error in cycle: {e}", err=True)

        if once_flag or shutdown:
            break

        time.sleep(5)

    click.echo("Loop stopped.")
