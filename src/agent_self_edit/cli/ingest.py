"""ingest command: ingest a trace file."""

import json

import click


@click.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--format", "fmt", type=click.Choice(["json"]), default="json")
@click.option("--config", "config_path", default="agent-self-edit.yaml", help="Config file path")
def ingest(file: str, fmt: str, config_path: str) -> None:
    """Ingest a trace FILE (JSON lines or single JSON object)."""
    from ..config import load_config
    from ..trace import TraceStore

    config = load_config(config_path)
    store = TraceStore(config.project.trace_path, batch_size=config.tasks.batch_size)

    ingested = 0
    errors = 0
    with open(file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if isinstance(data, list):
                    for item in data:
                        try:
                            store.ingest(item)
                            ingested += 1
                        except ValueError as e:
                            click.echo(f"Skipping trace: {e}", err=True)
                            errors += 1
                else:
                    store.ingest(data)
                    ingested += 1
            except json.JSONDecodeError:
                click.echo(f"Skipping malformed line: {line[:80]}", err=True)
                errors += 1

    click.echo(f"Ingested {ingested} traces ({errors} errors)")
