"""init command: scaffold config, registry, task set, initial prompt version."""

import click


@click.command()
@click.option("--prompt", type=click.Path(exists=True), help="Path to initial prompt file")
@click.option("--tasks", type=click.Path(exists=True), help="Path to held-out task set file")
def init(prompt: str | None, tasks: str | None) -> None:
    """Scaffold config, registry, task set, and initial prompt version."""
    from pathlib import Path

    from ..config import Config, load_config
    from ..registry import Registry
    from ..tasks import load_task_set

    config_path = Path("agent-self-edit.yaml")
    if config_path.exists():
        config = load_config(str(config_path))
        click.echo(f"Config loaded from {config_path}")
    else:
        config = Config.defaults()
        click.echo("No config found; using defaults. Run `agent-self-edit init` later.")

    registry = Registry(config.project.registry_path)
    click.echo(f"Registry initialized at {config.project.registry_path}")

    if tasks:
        ts = load_task_set(tasks)
        click.echo(f"Task set loaded: {len(ts)} tasks")
    else:
        click.echo("No task set provided; use --tasks <path>")

    if prompt:
        prompt_text = Path(prompt).read_text()
        v = registry.create(prompt_text)
        click.echo(f"Prompt version {v} created from {prompt}")
    else:
        click.echo("No initial prompt provided; use --prompt <path>")
