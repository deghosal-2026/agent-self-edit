"""lineage command: show full prompt version history."""

import json

import click


@click.command()
@click.option("--from", "from_version", type=int, help="Starting version")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
@click.option("--config", "config_path", default="agent-self-edit.yaml", help="Config file path")
def lineage(from_version: int | None, fmt: str, config_path: str) -> None:
    """Show full prompt version history."""
    from ..config import load_config
    from ..registry import Registry

    config = load_config(config_path)
    registry = Registry(config.project.registry_path)
    metas = registry.lineage(from_version=from_version)

    if not metas:
        click.echo("No data")
        return

    if fmt == "json":
        click.echo(json.dumps([m.to_dict() for m in metas], indent=2, default=str))
    else:
        click.echo(f"{'Ver':<5} {'Timestamp':<22} {'Hypothesis/Reason':<40} {'Hash':<10}")
        click.echo("-" * 80)
        for m in metas:
            label = (m.hypothesis or m.rollback_reason or "")[:40]
            click.echo(f"{m.version:<5} {m.timestamp:<22} {label:<40} {m.sha256_hash[:8]:<10}")
