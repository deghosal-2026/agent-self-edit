"""CLI entry point — all 10 commands wired via Click groups."""

from __future__ import annotations

import sys

import click

from .diff import diff
from .guardrails import guardrails
from .ingest import ingest
from .init import init
from .lineage import lineage
from .propose import propose
from .rollback import rollback
from .run import run
from .status import status
from .validate import validate


@click.group()
def main() -> None:
    """AgentSelfEdit — A self-improving agent prompt optimizer."""


main.add_command(init)
main.add_command(run)
main.add_command(status)
main.add_command(diff)
main.add_command(rollback)
main.add_command(guardrails)
main.add_command(lineage)
main.add_command(propose)
main.add_command(ingest)
main.add_command(validate)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
