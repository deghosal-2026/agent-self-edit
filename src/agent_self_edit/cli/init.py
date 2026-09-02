"""init command: scaffold config, registry, task set, initial prompt version."""

import click
import yaml


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
        # Write a starter config to disk
        config_data = {
            "schema_version": 1,
            "project": {"name": config.project.name, "registry_path": config.project.registry_path,
                        "trace_path": config.project.trace_path},
            "tasks": {"task_set_path": str(tasks) if tasks else "",
                      "batch_size": 50, "sample_floor": 10},
            "llm": {"provider": "mock", "model": "mock-model", "api_key": "",
                    "temperature": 0.0, "max_tokens": 4096, "timeout": 30},
            "ab_test": {"n_resamples": 100, "n_permutations": 100,
                        "confidence_level": 0.95, "min_effect_size": 0.05,
                        "cost_ceiling_usd": 0.10},
            "gate": {"max_edit_distance": 20, "drift_threshold": 0.3, "near_miss_threshold": 0.5},
            "analyzer": {"max_proposals_per_batch": 3, "cost_ceiling_usd": 0.50},
            "trigger": "batch", "trace_retention_days": 90,
        }
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)
        click.echo(f"Config written to {config_path}")

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
        raise click.ClickException("init requires --prompt to create a runnable registry")
