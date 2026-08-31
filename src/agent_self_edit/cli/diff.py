"""diff command: show diff between two prompt versions."""

import click


@click.command()
@click.argument("v1", type=int)
@click.argument("v2", type=int)
@click.option("--inline", "inline_flag", is_flag=True, help="Inline diff (default)")
@click.option("--format", "fmt", type=click.Choice(["text", "markdown"]), default="text")
@click.option("--color", "color_mode", type=click.Choice(["auto", "always", "never"]),
              default="auto")
@click.option("--config", "config_path", default="agent-self-edit.yaml", help="Config file path")
def diff(v1: int, v2: int, inline_flag: bool, fmt: str, color_mode: str, config_path: str) -> None:
    """Show diff between prompt versions V1 and V2."""
    from ..config import load_config
    from ..registry import Registry

    config = load_config("agent-self-edit.yaml")
    registry = Registry(config.project.registry_path)

    try:
        diff_result = registry.diff(v1, v2)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        return

    if fmt == "markdown":
        from ..diff import format_markdown_diff
        click.echo(format_markdown_diff(diff_result))
    elif inline_flag:
        from ..diff import format_diff_inline
        click.echo(format_diff_inline(diff_result, color_mode))
    else:
        from ..diff import format_diff_side_by_side
        click.echo(format_diff_side_by_side(diff_result, color_mode))
