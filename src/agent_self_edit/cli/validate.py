"""validate command: check config + task set + registry integrity."""

import json
import sys

import click


@click.command()
@click.option("--json", "json_flag", is_flag=True, help="JSON output")
@click.option("--config", "config_path", default="agent-self-edit.yaml", help="Config file path")
def validate(json_flag: bool, config_path: str) -> None:
    """Validate config, task set, and registry integrity."""
    from typing import Any

    from ..config import ConfigError, load_config
    from ..registry import Registry, RegistryError
    from ..tasks import TaskSetError, load_task_set

    results: list[dict[str, Any]] = []
    all_pass = True
    config = None

    # Check 1: Config
    try:
        config = load_config(config_path)
        results.append({"check": "config", "passed": True, "details": "valid"})
    except (ConfigError, FileNotFoundError) as e:
        results.append({"check": "config", "passed": False, "details": str(e)})
        all_pass = False

    # Check 2: Task set
    try:
        if config and hasattr(config, "tasks") and config.tasks.task_set_path:
            ts = load_task_set(config.tasks.task_set_path)
            results.append(
                {"check": "task_set", "passed": True, "details": f"{len(ts)} tasks loaded"}
            )
        else:
            results.append(
                {"check": "task_set", "passed": True, "details": "no task set configured"}
            )
    except (TaskSetError, FileNotFoundError) as e:
        results.append({"check": "task_set", "passed": False, "details": str(e)})
        all_pass = False

    # Check 3: Registry integrity
    try:
        if config:
            registry = Registry(config.project.registry_path)
            corrupted = registry.verify_integrity()
            if corrupted:
                results.append(
                    {
                        "check": "registry",
                        "passed": False,
                        "details": f"corrupted: {', '.join(corrupted[:3])}",
                    }
                )
                all_pass = False
            else:
                results.append(
                    {
                        "check": "registry",
                        "passed": True,
                        "details": f"v{registry.current_version} intact",
                    }
                )
    except (RegistryError, Exception) as e:
        results.append({"check": "registry", "passed": False, "details": str(e)})
        all_pass = False

    if json_flag:
        click.echo(json.dumps({"all_pass": all_pass, "checks": results}, indent=2))
    else:
        for r in results:
            status = "PASS" if r["passed"] else "FAIL"
            click.echo(f"  [{status}] {r['check']}: {r['details']}")
        click.echo(f"Result: {'ALL PASS' if all_pass else 'FAILURES DETECTED'}")

    sys.exit(0 if all_pass else 2)
