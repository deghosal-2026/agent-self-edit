"""Tests for the diff visualization module (M8, hermetic)."""


from agent_self_edit.ab_test import ABResult
from agent_self_edit.diff import (
    _color,
    format_diff_inline,
    format_diff_side_by_side,
    format_edit_density,
    format_edit_summary,
    format_guardrail_report,
    format_markdown_diff,
    format_markdown_guardrail,
    render_guardrail_table,
    render_inline,
)
from agent_self_edit.registry import DiffResult, Registry
from agent_self_edit.types import CheckResult, GateResult


def _diff(added=None, removed=None, modified=None, unchanged=0, frozen=0):
    return DiffResult(
        added=added or [],
        removed=removed or [],
        modified=modified or [],
        unchanged_count=unchanged,
        frozen_unchanged_count=frozen,
    )


def _gate(decision: str = "promote", checks=None):
    return GateResult(
        decision=decision,  # type: ignore[arg-type]
        checks=tuple(checks or ()),
        edit_id="e1",
        reason="",
    )


def _check(name, passed=True, value=1.0, threshold=0.5, details="ok"):
    return CheckResult(name=name, passed=passed, value=value, threshold=threshold, details=details)


def _ab(effect=0.124, p=0.008, n=78):
    return ABResult(
        winner="b", mean_delta=effect, ci_low=0.05, ci_high=0.2,
        p_value=p, effect_size=effect, n_trials=n,
    )


# ---- _color helper (#55) ----

def test_color_never_plain():
    assert _color("x", "never", "green") == "x"


def test_color_always_ansi():
    out = _color("x", "always", "green")
    assert "\x1b[" in out


def test_color_fg_none_plain():
    assert _color("x", "always", None) == "x"


def test_color_auto_non_tty_plain(monkeypatch):
    import io
    monkeypatch.setattr("sys.stdout", io.StringIO())
    assert _color("x", "auto", "green") == "x"


# ---- #52 inline diff ----

def test_inline_identical_no_changes():
    assert format_diff_inline(_diff()) == "no changes"


def test_inline_added_removed_prefixes():
    out = format_diff_inline(_diff(added=["a"], removed=["b"]))
    assert "- b" in out and "+ a" in out


def test_inline_modified_marked():
    out = format_diff_inline(_diff(modified=["old"]))
    assert "? old (modified)" in out


def test_inline_color_modes():
    # never = no ANSI
    assert "\x1b[" not in format_diff_inline(_diff(added=["a"]), "never")
    # always = ANSI present
    assert "\x1b[" in format_diff_inline(_diff(added=["a"]), "always")


# ---- #53 side-by-side + guardrail report ----

def test_side_by_side_identical():
    assert format_diff_side_by_side(_diff()) == "no changes"


def test_side_by_side_two_column():
    out = format_diff_side_by_side(_diff(removed=["left"], added=["right"]))
    assert "left" in out and "right" in out
    assert "|" in out


def test_side_by_side_frozen_grayed():
    out = format_diff_side_by_side(_diff(frozen=12))
    assert "(frozen)" in out
    assert "12" in out


def test_guardrail_table_format():
    g = _gate(checks=[_check("drift", passed=False, value=0.35, threshold=0.3)])
    out = format_guardrail_report(g)
    assert "drift" in out
    assert "fail" in out
    assert "Check" in out
    assert "Threshold" in out


def test_guardrail_all_passed_summary():
    g = _gate(checks=[_check("drift"), _check("sample_floor", value=78, threshold=50)])
    out = format_guardrail_report(g)
    assert "All passed" in out


def test_guardrail_some_failed_summary():
    g = _gate(checks=[_check("drift", passed=False), _check("sample_floor")])
    out = format_guardrail_report(g)
    assert "1 failed" in out
    assert "drift" in out


def test_guardrail_color_fail_red():
    g = _gate(checks=[_check("drift", passed=False)])
    out = format_guardrail_report(g, "always")
    assert "\x1b[31m" in out  # red


def test_guardrail_color_pass_green():
    g = _gate(checks=[_check("drift", passed=True)])
    out = format_guardrail_report(g, "always")
    assert "\x1b[32m" in out  # green


def test_render_guardrail_alias():
    g = _gate(checks=[_check("x")])
    assert render_guardrail_table(g) == format_guardrail_report(g)


# ---- #54 edit summary + density ----

def test_summary_promoted_one_line():
    g = _gate("promote", checks=[_check("x")])
    out = format_edit_summary(7, g, _ab())
    assert out == "Edit #7 — Promoted — +12.4% accuracy (p<0.01, n=78) — 1 line"


def test_summary_rejected_failed_names():
    g = _gate("reject", checks=[_check("drift", passed=False), _check("effect", passed=False)])
    out = format_edit_summary(8, g, None)
    assert "Rejected" in out
    assert "drift, effect" in out


def test_summary_near_miss():
    g = _gate("near_miss", checks=[_check("drift", passed=False)])
    out = format_edit_summary(9, g, None)
    assert "Near-miss" in out
    assert "drift" in out


def test_summary_no_gate_result():
    out = format_edit_summary(1, None, None)
    assert "no gate result" in out


def test_density_empty_registry(tmp_path):
    reg = Registry(tmp_path / "reg")
    assert format_edit_density(reg) == ""


def test_density_bars_present(tmp_path):
    reg = Registry(tmp_path / "reg")
    reg.create("one", hypothesis="classify rule")
    reg.create("one\ntwo", hypothesis="classify rule")
    out = format_edit_density(reg)
    assert "classify rule" in out
    assert "edits" in out


def test_density_no_changes_message(tmp_path):
    reg = Registry(tmp_path / "reg")
    reg.create("same")
    reg.create("same")
    out = format_edit_density(reg)
    assert "no changes recorded" in out


# ---- #55 markdown ----

def test_markdown_diff_code_block():
    out = format_markdown_diff(_diff(added=["a"], removed=["b"]))
    assert out.startswith("```diff")
    assert "- b" in out and "+ a" in out


def test_markdown_diff_identical():
    assert format_markdown_diff(_diff()) == "no changes"


def test_markdown_guardrail_table():
    g = _gate(checks=[_check("drift", passed=False), _check("sample_floor", passed=True)])
    out = format_markdown_guardrail(g)
    assert out.startswith("| Check | Result | Value | Threshold |")
    assert "drift" in out
    assert "**1 failed.**" in out


def test_markdown_guardrail_all_passed():
    g = _gate(checks=[_check("drift", passed=True)])
    assert "**All passed.**" in format_markdown_guardrail(g)


# ---- render alias ----

def test_render_inline_alias():
    assert render_inline(_diff()) == format_diff_inline(_diff())


# ---- type sanity ----

def test_diff_result_fields():
    d = _diff(added=["a"], removed=["b"], modified=["c"], unchanged=5, frozen=2)
    assert d.unchanged_count == 5
    assert d.frozen_unchanged_count == 2


def test_side_by_side_mismatched_lengths():
    # uneven left/right → renders as separate -/+ block
    out = format_diff_side_by_side(_diff(removed=["a", "b"], added=["c"]))
    assert "- a" in out and "- b" in out
    assert "+ c" in out


def test_side_by_side_frozen_with_no_changes():
    out = format_diff_side_by_side(_diff(frozen=12))
    assert "(frozen)" in out and "12" in out


def test_format_value_inf():
    from agent_self_edit.diff import _format_value

    assert _format_value(float("inf")) == "inf"


def test_format_value_int():
    from agent_self_edit.diff import _format_value

    assert _format_value(78.0) == "78"


def test_format_value_float():
    from agent_self_edit.diff import _format_value

    assert _format_value(0.35) == "0.35"


def test_render_density_bars_empty():
    from agent_self_edit.diff import render_density_bars

    assert render_density_bars({}) == ""


def test_render_density_bars_single():
    from agent_self_edit.diff import render_density_bars

    out = render_density_bars({"rule": 5})
    assert "rule" in out
    assert "5 edits" in out


def test_render_density_bars_multiple_ranked():
    from agent_self_edit.diff import render_density_bars

    out = render_density_bars({"a": 2, "b": 10})
    lines = out.splitlines()
    assert lines[0].startswith("  b")  # highest first
    assert lines[1].startswith("  a")
