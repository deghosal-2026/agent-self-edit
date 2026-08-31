"""Diff visualization: inline/side-by-side diffs, guardrail reports, summaries (F-08).

The transparency layer that shows exactly what changed, what stayed the same,
and why — making the self-improvement loop trustworthy.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import click

from .types import GateResult

if TYPE_CHECKING:
    from .ab_test import ABResult
    from .registry import DiffResult, Registry


# ---------------------------------------------------------------------------
# Color helper (#55, §6.4)
# ---------------------------------------------------------------------------


def _color(text: str, mode: str, fg: str | None) -> str:
    """Wrap ``text`` in ANSI color per the active mode.

    - ``never`` → plain text (no ANSI).
    - ``auto`` → color only when stdout is a TTY.
    - ``always`` → force color.
    """
    if mode == "never" or fg is None:
        return text
    if mode == "auto" and not sys.stdout.isatty():
        return text
    return click.style(text, fg=fg)


# ---------------------------------------------------------------------------
# #52 — Inline diff
# ---------------------------------------------------------------------------


def format_diff_inline(diff_result: "DiffResult", color: str = "never") -> str:
    """Render an inline diff as ``- removed`` / ``+ added`` lines.

    Identical prompts → single line ``no changes``.
    """
    if not diff_result.added and not diff_result.removed and not diff_result.modified:
        return "no changes"

    lines: list[str] = []
    for line in diff_result.removed:
        lines.append(_color(f"- {line}", color, "red"))
    for line in diff_result.added:
        lines.append(_color(f"+ {line}", color, "green"))
    for line in diff_result.modified:
        lines.append(_color(f"? {line} (modified)", color, "yellow"))
    return "\n".join(lines)


def render_inline(diff_result: "DiffResult", color: str = "never") -> str:
    """Alias for :func:`format_diff_inline` (implementation-contract name)."""
    return format_diff_inline(diff_result, color)


# ---------------------------------------------------------------------------
# #53 — Side-by-side diff + guardrail report
# ---------------------------------------------------------------------------


def format_diff_side_by_side(diff_result: "DiffResult", color: str = "never") -> str:
    """Render a side-by-side (before | after) diff.

    Frozen lines are grayed. Falls back to inline-style when the diff is
    identical (nothing to compare).
    """
    left = diff_result.removed + [f"? {m}" for m in diff_result.modified]
    right = diff_result.added + [f"? {m}" for m in diff_result.modified]

    if not left and not right:
        if diff_result.frozen_unchanged_count:
            return _color(
                f"(frozen) {diff_result.frozen_unchanged_count} lines unchanged",
                color,
                "bright_black",
            )
        return "no changes"

    col_width = max([len(x) for x in left + right] + [0])
    lines: list[str] = []
    if len(left) == len(right):
        for left_line, right_line in zip(left, right):
            lc = _color(
                left_line.ljust(col_width),
                color,
                "red" if left_line.startswith("- ") else "yellow",
            )
            rc = _color(
                right_line,
                color,
                "green" if right_line.startswith("+ ") else "yellow",
            )
            lines.append(f"{lc}  |  {rc}")
    else:
        for left_line in left:
            lines.append(_color(f"- {left_line}".ljust(col_width + 2), color, "red"))
        for right_line in right:
            lines.append(_color(f"+ {right_line}", color, "green"))

    if diff_result.frozen_unchanged_count:
        lines.append(
            _color(
                f"(frozen) {diff_result.frozen_unchanged_count} lines unchanged",
                color,
                "bright_black",
            )
        )
    return "\n".join(lines)


def format_guardrail_report(gate_result: GateResult, color: str = "never") -> str:
    """Render a guardrail report as an aligned text table (PRD M8.2).

    Columns: check name, passed/failed (Result), value, threshold. Summary
    line ``All passed`` or ``N failed``.
    """
    rows: list[tuple[str, bool, str, str]] = []
    for check in gate_result.checks:
        value = _format_value(check.value)
        threshold = _format_value(check.threshold)
        rows.append((check.name, check.passed, value, threshold))

    name_w = max([len(r[0]) for r in rows] + [len("Check")])
    result_w = max([len("pass" if r[1] else "fail") for r in rows] + [len("Result")])
    value_w = max([len(r[2]) for r in rows] + [len("Value")])
    threshold_w = max([len(r[3]) for r in rows] + [len("Threshold")])

    header = (
        f"  {'Check'.ljust(name_w)}  {'Result'.rjust(result_w)}  "
        f"{'Value'.rjust(value_w)}  {'Threshold'.rjust(threshold_w)}"
    )

    lines: list[str] = []
    lines.append("Guardrail check:")
    lines.append(header)
    lines.append(f"  {'-'*name_w}  {'-'*result_w}  {'-'*value_w}  {'-'*threshold_w}")
    lines.extend(
        f"  {n.ljust(name_w)}  "
        f"{_color(('pass' if p else 'fail').rjust(result_w), color, 'green' if p else 'red')}  "
        f"{v.rjust(value_w)}  {t.rjust(threshold_w)}"
        for n, p, v, t in rows
    )

    failed = sum(1 for r in rows if not r[1])
    if failed == 0:
        lines.append("  All passed.")
    else:
        names = ", ".join(r[0] for r in rows if not r[1])
        lines.append(f"  {failed} failed: {names}.")

    return "\n".join(lines)


def render_guardrail_table(gate_result: GateResult, color: str = "never") -> str:
    """Alias for :func:`format_guardrail_report` (implementation-contract name)."""
    return format_guardrail_report(gate_result, color)


def _format_value(value: float) -> str:
    if value == float("inf"):
        return "inf"
    if value == int(value):
        return str(int(value))
    return f"{value:.3f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------
# #54 — Edit summary + density
# ---------------------------------------------------------------------------


def format_edit_summary(
    edit_id: str | int,
    gate_result: GateResult | None,
    ab_result: "ABResult | None",
) -> str:
    """Render a one-line edit summary (PRD M8.3).

    ``Edit #{N} — {decision} — {±X.X%} accuracy (p<{val}, n={trials}) — {N} line(s)``
    """
    # Line count: derive from failed check count as a stand-in; caller may
    # want the diff's changed-line count, but the signature has no diff here.
    if gate_result is None:
        return f"Edit #{edit_id} — (no gate result)"

    decision = {
        "promote": "Promoted",
        "reject": "Rejected",
        "near_miss": "Near-miss",
    }.get(gate_result.decision, gate_result.decision)

    parts: list[str] = [f"Edit #{edit_id}", f"— {decision}"]

    if gate_result.decision == "promote" and ab_result is not None:
        effect = ab_result.effect_size
        sign = "+" if effect >= 0 else "-"
        eff_str = f"{sign}{abs(effect)*100:.1f}%"
        parts.append(f"— {eff_str} accuracy (p<{ab_result.p_value:.2f}, n={ab_result.n_trials})")
    elif gate_result.decision in ("reject", "near_miss"):
        failed = [c.name for c in gate_result.checks if not c.passed]
        parts.append(f"— ({', '.join(failed) if failed else 'no failed checks'})")

    n_checks = len(gate_result.checks)
    suffix = "line" if n_checks == 1 else "lines"
    parts.append(f"— {n_checks} {suffix}")

    return " ".join(parts)


def format_edit_density(registry: "Registry", window: int = 20) -> str:
    """Render a text-based bar chart of per-section edit frequency.

    Uses the registry's lineage metadata (``diff_from_previous``) to count
    changed lines per version, bucketed by section label if present; else a
    single ``edits-per-version`` bar. Empty registry → empty chart.
    """
    meta_list = registry.lineage()[-window:] if window > 0 else registry.lineage()
    if not meta_list:
        return ""

    # Count changed lines per version from diff_from_previous metadata.
    per_section: dict[str, int] = {}
    n_versions = len(meta_list)
    for meta in meta_list:
        diff = meta.diff_from_previous
        if diff:
            total = int(diff.get("total", 0))
            section = meta.hypothesis or "edits"
            per_section[section] = per_section.get(section, 0) + total

    if not per_section:
        return f"  Edit density (last {n_versions} versions): no changes recorded"
    if not any(per_section.values()):
        return f"  Edit density (last {n_versions} versions): no changes recorded"

    max_count = max(per_section.values()) or 1
    bar_width = 20
    lines: list[str] = [f"  Edit density (last {n_versions} versions):"]
    for section, count in sorted(per_section.items(), key=lambda kv: -kv[1]):
        filled = int(bar_width * count / max_count)
        bar = "█" * filled + "░" * (bar_width - filled)
        lines.append(f"  {section:<24} {bar}  {count} edits")
    return "\n".join(lines)


def render_density_bars(per_section: dict[str, int]) -> str:
    """Render bar-chart lines for a per-section count dict (implementation name)."""
    if not per_section:
        return ""
    max_count = max(per_section.values()) or 1
    bar_width = 20
    lines: list[str] = []
    for section, count in sorted(per_section.items(), key=lambda kv: -kv[1]):
        filled = int(bar_width * count / max_count)
        bar = "█" * filled + "░" * (bar_width - filled)
        lines.append(f"  {section:<24} {bar}  {count} edits")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# #55 — Markdown output
# ---------------------------------------------------------------------------


def format_markdown_diff(diff_result: "DiffResult") -> str:
    """Render a fenced ``diff`` code block (markdown) for an inline diff."""
    if not diff_result.added and not diff_result.removed and not diff_result.modified:
        return "no changes"
    body = format_diff_inline(diff_result, "never")
    return f"```diff\n{body}\n```"


def format_markdown_guardrail(gate_result: GateResult) -> str:
    """Render the guardrail report as a markdown table."""
    rows = ["| Check | Result | Value | Threshold |", "|------|--------|-------|-----------|"]
    for check in gate_result.checks:
        result = "✅ pass" if check.passed else "❌ fail"
        rows.append(
            f"| {check.name} | {result} | {_format_value(check.value)} "
            f"| {_format_value(check.threshold)} |"
        )
    failed = sum(1 for c in gate_result.checks if not c.passed)
    summary = "All passed." if failed == 0 else f"{failed} failed."
    rows.append("")
    rows.append(f"**{summary}**")
    return "\n".join(rows)
