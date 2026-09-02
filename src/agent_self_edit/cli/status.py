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
        raise click.ClickException(str(e)) from e

    registry = Registry(config.project.registry_path)
    version = registry.current_version

    # Count real edits: exclude version 1 (seed) and rollback-created copies
    lineage = registry.lineage()
    total_edits = sum(
        1 for m in lineage
        if m.version > 1 and m.rollback_target is None
    )

    total_cost = sum(
        m.token_cost or 0.0 for m in lineage if m.token_cost is not None
    )

    last_edit = None
    if version > 0:
        _, meta = registry.get(version)
        last_edit = {
            "version": meta.version,
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
            # Guardrail pass rate = promoted / (promoted + rejected)
            # near_miss is excluded as it's an intermediate state
            promoted = sum(1 for e in entries if e.get("decision") == "promote")
            rejected = sum(1 for e in entries if e.get("decision") == "reject")
            denominator = promoted + rejected
            guardrail_pass_rate = promoted / denominator if denominator > 0 else 0.0

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
            decision = last_edit.get("decision") or "none"
            click.echo(f"Last edit: {decision} (v{version})")
        click.echo(f"Guardrail pass rate: {guardrail_pass_rate:.0%}")
        click.echo(f"Total edits: {total_edits}")
        click.echo(f"Total cost: ${total_cost:.4f}")
