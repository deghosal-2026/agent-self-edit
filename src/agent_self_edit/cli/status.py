"""status command: show current state."""

import json

import click


@click.command()
@click.option("--config", "config_path", default="agent-self-edit.yaml", help="Config file path")
@click.option("--json", "json_flag", is_flag=True, help="JSON output")
def status(config_path: str, json_flag: bool) -> None:
    """Show current state: prompt version, last edit, guardrail pass rate, total edits, cost."""
    from ..config import load_config
    from ..registry import Registry

    try:
        config = load_config(config_path)
    except Exception as e:
        click.echo(f"Error loading config: {e}", err=True)
        return

    registry = Registry(config.project.registry_path)
    version = registry.current_version

    total_edits = version
    total_cost = sum(
        m.token_cost or 0.0 for m in registry.lineage() if m.token_cost is not None
    )

    last_edit = None
    if version > 0:
        _, meta = registry.get(version)
        last_edit = {
            "edit_id": meta.version,
            "decision": meta.gate_result.get("decision") if meta.gate_result else None,
            "timestamp": meta.timestamp,
            "hypothesis": meta.hypothesis,
        }

    guardrail_pass_rate = 0.0
    audit_path = config.project.registry_path + "/audit.jsonl"
    from pathlib import Path
    if Path(audit_path).exists():
        from ..gate import GateAuditLog
        alog = GateAuditLog(audit_path)
        entries = alog.list()
        if entries:
            passed = sum(1 for e in entries if e.get("decision") == "promote")
            guardrail_pass_rate = passed / len(entries)

    if json_flag:
        data = {
            "prompt_version": version,
            "last_edit": last_edit,
            "guardrail_pass_rate": round(guardrail_pass_rate, 2),
            "total_edits": total_edits,
            "total_cost_usd": round(total_cost, 4),
        }
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo(f"Prompt version: {version}")
        if last_edit:
            click.echo(f"Last edit: {last_edit.get('decision') or 'none'} (v{version})")
        click.echo(f"Guardrail pass rate: {guardrail_pass_rate:.0%}")
        click.echo(f"Total edits: {total_edits}")
        click.echo(f"Total cost: ${total_cost:.4f}")
