"""Tests for the standalone guardrail module (PRD 02-architecture §2.2.5)."""

import pytest

from agent_self_edit.guardrails import (
    EditDistance,
    FrozenSection,
    GuardrailError,
    GuardrailReport,
    check_oracle_drift,
    compute_drift_embedding,
    compute_drift_tfidf,
    compute_edit_distance,
    compute_per_section_drift,
    frozen_line_indexes,
    parse_frozen_sections,
    validate_frozen_sections,
)
from agent_self_edit.types import CheckResult, Trace

FROZEN_PROMPT = (
    "You are a classifier assistant.\n"
    "<!-- frozen -->\n"
    "When classifying, check the subject line.\n"
)


# ---- parse_frozen_sections (#39) ----

def test_parse_single_section():
    sections = parse_frozen_sections(FROZEN_PROMPT)
    assert len(sections) == 1
    assert sections[0].section_name == "core"
    assert sections[0].lines == ["When classifying, check the subject line."]
    assert sections[0].start_line == 1


def test_parse_no_frozen():
    assert parse_frozen_sections("no annotations here") == []


def test_parse_named_sections():
    prompt = (
        "<!-- frozen: role -->\n"
        "You are strict.\n"
        "Do the work.\n"
    )
    sections = parse_frozen_sections(prompt)
    assert len(sections) == 1
    assert sections[0].section_name == "role"


def test_parse_multiple_sections():
    prompt = (
        "<!-- frozen: role -->\nYou are strict.\n"
        "<!-- frozen: safety -->\nNever run destructive commands.\n"
        "<!-- frozen: format -->\nReturn JSON.\n"
    )
    sections = parse_frozen_sections(prompt)
    assert [s.section_name for s in sections] == ["role", "safety", "format"]


def test_parse_malformed_raises_guardrail_error():
    prompt = "<!-- frozen\nThis is unclosed"
    with pytest.raises(GuardrailError):
        parse_frozen_sections(prompt)


def test_frozen_section_dataclass():
    fs = FrozenSection(start_line=1, end_line=3, section_name="role", lines=["a", "b"])
    assert fs.start_line == 1
    assert fs.end_line == 3
    assert fs.section_name == "role"
    assert fs.lines == ["a", "b"]


def test_parse_section_line_numbers():
    prompt = (
        "line0\n"
        "<!-- frozen: role -->\n"  # line 1
        "line2\n"
        "line3\n"
    )
    sections = parse_frozen_sections(prompt)
    assert len(sections) == 1
    assert sections[0].start_line == 1
    assert sections[0].end_line == 3


# ---- validate_frozen_sections (#40) ----

def test_validate_all_present():
    prompt = (
        "<!-- frozen: role -->\nYou are strict.\n"
        "<!-- frozen: safety -->\nNever run destructive commands.\n"
    )
    assert validate_frozen_sections(prompt, ["role", "safety"]) is True


def test_validate_missing_section():
    prompt = "<!-- frozen: role -->\nYou are strict.\n"
    assert validate_frozen_sections(prompt, ["role", "safety"]) is False


def test_validate_section_renumbered_fails():
    # requested order differs from prompt order → renumbering → fail
    prompt = (
        "<!-- frozen: safety -->\nNever run destructive commands.\n"
        "<!-- frozen: role -->\nYou are strict.\n"
    )
    assert validate_frozen_sections(prompt, ["role", "safety"]) is False


def test_validate_duplicate_requested_fails():
    prompt = "<!-- frozen: role -->\nYou are strict.\n"
    assert validate_frozen_sections(prompt, ["role", "role"]) is False


def test_validate_empty_prompt_fails():
    assert validate_frozen_sections("", ["role"]) is False


def test_validate_no_frozen_sections_fails():
    assert validate_frozen_sections("no frozen", ["role"]) is False


# ---- compute_edit_distance (#41) ----

def test_edit_distance_identical():
    d = compute_edit_distance("a\nb", "a\nb")
    assert d.total == 0
    assert d.lines_added == 0
    assert d.lines_removed == 0
    assert d.lines_modified == 0


def test_edit_distance_change():
    d = compute_edit_distance("a\nb\nc", "a\nx\nc")
    assert d.total == 1
    assert d.lines_modified == 1


def test_edit_distance_entirely_different():
    d = compute_edit_distance("one\ntwo", "three\nfour\nfive")
    assert d.total > 0
    assert d.lines_modified >= 2


def test_edit_distance_counts_added_removed():
    d = compute_edit_distance("a\nb", "a\nb\nc\nd")
    assert d.lines_added == 2
    assert d.total == 2


def test_edit_distance_frozen_lines_changed():
    prompt_old = (
        "<!-- frozen: role -->\n"
        "You are strict.\n"
        "Do the work.\n"
        "<!-- frozen -->\n"
    )
    prompt_new = (
        "<!-- frozen: role -->\n"
        "You are LENIENT.\n"  # changed inside frozen
        "Do the work.\n"
        "<!-- frozen -->\n"
    )
    d = compute_edit_distance(prompt_old, prompt_new)
    assert d.frozen_lines_changed >= 1


def test_edit_distance_no_frozen_changed():
    prompt_old = "<!-- frozen: role -->\nYou are strict.\n<!-- frozen -->\nX\nY\n"
    prompt_new = "<!-- frozen: role -->\nYou are strict.\n<!-- frozen -->\nX\nZ\n"
    d = compute_edit_distance(prompt_old, prompt_new)
    assert d.total >= 1
    assert d.frozen_lines_changed == 0


def test_edit_distance_dataclass_fields():
    d = EditDistance(lines_added=1, lines_removed=2, lines_modified=3)
    assert d.total == 0  # explicit total not auto-summed; verify default
    assert d.frozen_lines_changed == 0


# ---- compute_drift_tfidf (#42) ----

def test_drift_identical_zero():
    assert compute_drift_tfidf("same text", "same text") == 0.0


def test_drift_different_high():
    d = compute_drift_tfidf("alpha beta gamma", "delta epsilon zeta")
    assert d > 0.5


def test_drift_similar_low():
    d = compute_drift_tfidf(
        "please classify tickets by urgency",
        "classify tickets by urgency",
    )
    assert d < 1.0


def test_drift_symmetric():
    a = "you are a helpful classifier with strong reasoning"
    b = "classify the ticket into the correct category"
    assert compute_drift_tfidf(a, b) == pytest.approx(compute_drift_tfidf(b, a))


def test_drift_empty_prompt():
    d = compute_drift_tfidf("", "anything")
    assert 0.0 <= d <= 1.0


def test_drift_range():
    pairs = [
        ("same", "same"),
        ("completely unrelated text", "another set of words"),
        ("", "anything"),
    ]
    for a, b in pairs:
        d = compute_drift_tfidf(a, b)
        assert 0.0 <= d <= 1.0


# ---- compute_drift_embedding (#43) ----

class NoEmbedProvider:
    def complete(self, prompt, system_prompt="", temperature=0.0):
        return "mock output"


class EmbedProvider:
    def __init__(self, vector_map):
        self._map = vector_map

    def complete(self, prompt, system_prompt="", temperature=0.0):
        return "mock output"

    def embed(self, prompt):
        return self._map.get(prompt, [0.0, 0.0])


class FailingEmbedProvider:
    def embed(self, prompt):
        raise RuntimeError("embeddings down")


def test_embedding_no_provider_method_falls_back():
    # provider without embed → TF-IDF fallback
    d = compute_drift_embedding("same text", "same text", NoEmbedProvider())
    assert d == 0.0


def test_embedding_identical_vectors_zero():
    provider = EmbedProvider({"a": [1.0, 0.0, 0.0], "b": [1.0, 0.0, 0.0]})
    d = compute_drift_embedding("a", "b", provider)
    assert d == 0.0


def test_embedding_different_vectors_high():
    provider = EmbedProvider({"a": [1.0, 0.0], "b": [0.0, 1.0]})
    d = compute_drift_embedding("a", "b", provider)
    assert d > 0.5


def test_embedding_failure_falls_back():
    d = compute_drift_embedding("x", "y", FailingEmbedProvider())
    # fallback to TF-IDF → within [0,1]
    assert 0.0 <= d <= 1.0


def test_embedding_mismatched_vectors_falls_back():
    provider = EmbedProvider({"a": [1.0, 0.0], "b": [1.0]})
    d = compute_drift_embedding("a", "b", provider)
    assert 0.0 <= d <= 1.0


# ---- per-section drift + report (#44) ----

def test_per_section_drift_identical():
    prompt = (
        "<!-- frozen: role -->\nYou are strict.\n"
        "<!-- frozen: safety -->\nNever run destructive commands.\n"
    )
    sections = parse_frozen_sections(prompt)
    drift = compute_per_section_drift(prompt, prompt, sections)
    assert drift == {"role": 0.0, "safety": 0.0}


def test_per_section_drift_different():
    prompt_a = (
        "<!-- frozen: role -->\nYou are strict.\n"
        "<!-- frozen: safety -->\nNever run destructive commands.\n"
    )
    prompt_b = (
        "<!-- frozen: role -->\nYou are strict.\n"
        "<!-- frozen: safety -->\nAlways run everything.\n"
    )
    sections = parse_frozen_sections(prompt_a)
    drift = compute_per_section_drift(prompt_a, prompt_b, sections)
    assert "role" in drift
    assert "safety" in drift
    assert drift["role"] == 0.0


def test_guardrail_report_str_human_readable():
    checks = [
        CheckResult(name="sample_floor", passed=True, value=12.0, threshold=10.0, details="ok"),
        CheckResult(
            name="confidence", passed=False, value=0.9, threshold=0.95, details="p too high"
        ),
    ]
    report = GuardrailReport(checks=checks, overall=False)
    text = str(report)
    assert "Guardrail report" in text
    assert "sample_floor" in text
    assert "confidence" in text
    assert "FAIL" in text
    assert "PASS" in text


def test_guardrail_report_repr_machine_readable():
    import json

    checks = [CheckResult(name="drift", passed=True, value=0.1, threshold=0.3, details="ok")]
    report = GuardrailReport(checks=checks, overall=True)
    parsed = json.loads(repr(report))
    assert parsed["overall"] is True
    assert parsed["checks"][0]["name"] == "drift"
    assert parsed["checks"][0]["passed"] is True


def test_guardrail_report_default_overall():
    report = GuardrailReport()
    assert report.overall is True
    assert report.checks == []


def test_frozen_line_indexes():
    idx = frozen_line_indexes(FROZEN_PROMPT)
    assert 2 in idx


def test_frozen_line_indexes_none():
    assert frozen_line_indexes("no markers") == set()


def test_parse_anonymous_opens_core_when_no_open_section():
    # an anonymous marker with no currently-open section opens the default "core"
    prompt = "<!-- frozen -->\nOnly this line is frozen\neditable below\n"
    sections = parse_frozen_sections(prompt)
    assert [s.section_name for s in sections] == ["core"]


def test_parse_named_then_anonymous_closes():
    prompt = (
        "<!-- frozen: role -->\nYou are strict.\n"
        "<!-- frozen -->\neditable tail\n"
    )
    sections = parse_frozen_sections(prompt)
    # role closes at the anonymous marker; the editable tail is not a section
    assert [s.section_name for s in sections] == ["role"]
    assert sections[0].lines == ["You are strict."]


def test_edit_distance_insert_only():
    d = compute_edit_distance("a\nb", "a\nb\nc\nd")
    assert d.lines_added == 2
    assert d.lines_removed == 0
    assert d.total == 2


def test_edit_distance_remove_only():
    d = compute_edit_distance("a\nb\nc", "a\nb")
    assert d.lines_removed == 1
    assert d.lines_added == 0
    assert d.total == 1


def test_drift_tfidf_non_smooth_branch():
    # exercise the non-smooth idf branch via a single-document vocabulary
    d = compute_drift_tfidf("alpha alpha beta", "beta gamma")
    assert 0.0 <= d <= 1.0


def test_embedding_zero_vector():
    provider = EmbedProvider({"a": [0.0, 0.0], "b": [1.0, 0.0]})
    d = compute_drift_embedding("a", "b", provider)
    # zero-norm and non-zero-norm: needs to be in range
    assert 0.0 <= d <= 1.0


def test_per_section_drift_ignores_anonymous_no_name():
    prompt_a = (
        "You are a classifier assistant.\n"
        "<!-- frozen -->\n"
        "Frozen core only.\n"
    )
    sections = parse_frozen_sections(prompt_a)
    # only named-ish sections are keyed; anonymous core section named "core" is included
    drift = compute_per_section_drift(prompt_a, prompt_a, sections)
    assert "core" in drift
    assert drift["core"] == 0.0


def test_guardrail_report_empty_checks():
    report = GuardrailReport(checks=[], overall=True)
    assert "Overall: PASS" in str(report)


# ---- #226: Oracle Drift Guard ----


def _trace(expected: str, task_id: str = "t1") -> Trace:
    return Trace(
        task_id=task_id, task_input="x", final_output="y",
        expected_output=expected, success=False,
        timestamp="2026-01-01T00:00:00Z",
    )


def test_oracle_drift_empty_traces_passes():
    result = check_oracle_drift([])
    assert result.passed
    assert result.value == 0.0


def test_oracle_drift_single_trace_passes():
    result = check_oracle_drift([_trace("technical")])
    assert result.passed


def test_oracle_drift_diverse_outputs_passes():
    traces = [_trace("technical"), _trace("billing"), _trace("security")]
    result = check_oracle_drift(traces)
    assert result.passed
    assert result.value < 0.8


def test_oracle_drift_all_identical_fails():
    traces = [_trace("technical") for _ in range(5)]
    result = check_oracle_drift(traces, uniformity_threshold=0.79)
    assert not result.passed
    assert result.value >= 0.79


def test_oracle_drift_majority_identical_fails():
    traces = [_trace("technical") for _ in range(4)] + [_trace("billing")]
    result = check_oracle_drift(traces, uniformity_threshold=0.79)
    assert not result.passed
    assert result.value >= 0.79


def test_oracle_drift_shared_keyword_detected():
    """All outputs are identical — identity uniformity triggers."""
    traces = [_trace("urgent") for _ in range(5)]
    result = check_oracle_drift(traces, uniformity_threshold=0.79)
    assert not result.passed
    assert result.value >= 0.79


def test_oracle_drift_shared_keyword_across_diverse_outputs_passes():
    """A shared keyword across diverse outputs is not oracle drift."""
    traces = [
        _trace("urgent: server down"),
        _trace("urgent: billing issue"),
        _trace("urgent: security breach"),
    ]
    result = check_oracle_drift(traces)
    assert result.passed, "diverse outputs with a shared keyword should pass"


def test_oracle_drift_shared_short_word_ignored():
    """Short words like 'a' or 'the' should not trigger oracle drift."""
    traces = [
        _trace("a technical issue"),
        _trace("a billing problem"),
        _trace("a security concern"),
    ]
    result = check_oracle_drift(traces, uniformity_threshold=0.80)
    assert result.passed, "short common words should not trigger oracle drift"


def test_oracle_drift_non_empty_outputs_only():
    """Empty expected outputs should be excluded from analysis."""
    traces = [_trace("") for _ in range(5)]
    result = check_oracle_drift(traces)
    assert result.passed


def test_oracle_drift_with_explicit_expected_outputs():
    """Pass expected_outputs explicitly instead of extracting from traces."""
    outputs = ["technical"] * 5 + ["billing"] * 5
    result = check_oracle_drift([], expected_outputs=outputs, uniformity_threshold=0.49)
    assert not result.passed
    assert result.value >= 0.49
