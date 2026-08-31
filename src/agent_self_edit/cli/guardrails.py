"""guardrails command: show guardrail history."""

import json

import click


@click.command()
@click.option("--last", "last_n", type=int, default=10, help="Number of recent entries")
@click.option("--edit", "edit_id", help="Filter by edit ID")
@click.option("--json", "json_flag", is_flag=True, help="JSON output")
@click.option("--config", "config_path", default="agent-self-edit.yaml", help="Config file path")
def guardrails(last_n: int, edit_id: str | None, json_flag: bool, config_path: str) -> None:
    """Show guardrail history."""
    from pathlib import Path

    from ..config import load_config
    from ..gate import GateAuditLog

    config = load_config(config_path)
    audit_path = config.project.registry_path + "/audit.jsonl"

    if not Path(audit_path).exists():
        click.echo("No guardrail history found.")
        return

    alog = GateAuditLog(audit_path)

    if edit_id:
        entries = alog.query(edit_id)
    else:
        entries = alog.list(limit=last_n)

    if not entries:
        click.echo("No data")
        return

    if json_flag:
        click.echo(json.dumps(entries, indent=2))
    else:
        for e in entries:
            click.echo(
                f"Edit #{e.get('edit_id', '?')} — {e.get('decision', '?')} — "
                f"{e.get('reason', '')}"
            )
