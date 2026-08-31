"""rollback command: roll back to a previous prompt version."""

import click


@click.command()
@click.argument("version", type=int)
@click.option("--reason", default="", help="Reason for rollback")
@click.option("--config", "config_path", default="agent-self-edit.yaml", help="Config file path")
def rollback(version: int, reason: str, config_path: str) -> None:
    """Roll back to a previous prompt VERSION."""
    from ..config import load_config
    from ..registry import Registry

    config = load_config(config_path)
    registry = Registry(config.project.registry_path)

    try:
        v = registry.rollback(version, reason or "rollback")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        return

    click.echo(f"Rolled back to v{version}. Created new version {v}.")
    if reason:
        click.echo(f"Reason: {reason}")
