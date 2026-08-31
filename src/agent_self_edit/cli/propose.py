"""propose command: manually trigger analysis on traces."""

import click


@click.command()
@click.option("--dry-run", "dry_run", is_flag=True, help="Propose without A/B test or gate")
@click.option("--config", "config_path", default="agent-self-edit.yaml", help="Config file path")
def propose(dry_run: bool, config_path: str) -> None:
    """Manually trigger analysis on current traces."""
    from ..analyzer import analyze_batch
    from ..config import load_config
    from ..llm.mock import MockProvider
    from ..registry import Registry
    from ..trace import TraceStore

    config = load_config(config_path)
    store = TraceStore(config.project.trace_path, batch_size=config.tasks.batch_size)
    registry = Registry(config.project.registry_path)

    if not store.batch_ready():
        click.echo("No pending traces ready for analysis.")
        return

    batch = store.get_batch(min(config.tasks.batch_size, store.count_pending()))
    failed = [t for t in batch if not t.success]

    if not failed:
        click.echo("All traces succeeded; no analysis needed.")
        store.acknowledge([t.task_id for t in batch])
        return

    llm = MockProvider(responses="[]")
    result = analyze_batch(
        failed, registry.current_prompt, None, llm,
        max_proposals=config.analyzer.max_proposals_per_batch,
        config=config,
    )

    click.echo(f"Analysis produced {len(result.proposals)} proposals (cost=${result.cost_usd:.4f})")
    for i, p in enumerate(result.proposals, 1):
        click.echo(f"  {i}. [{p.section}] {p.hypothesis}")

    if not dry_run:
        store.acknowledge([t.task_id for t in batch])
