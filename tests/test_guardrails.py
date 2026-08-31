"""Tests for the standalone guardrail module (PRD 02-architecture §2.2.5)."""

import pytest

from agent_self_edit.guardrails import (
    compute_drift_tfidf,
    compute_edit_distance,
    frozen_line_indexes,
    parse_frozen_sections,
)

FROZEN_PROMPT = (
    "You are a classifier assistant.\n"
    "<!-- frozen -->\n"
    "When classifying, check the subject line.\n"
)


# ---- parse_frozen_sections ----

def test_parse_single_section():
    sections = parse_frozen_sections(FROZEN_PROMPT)
    assert len(sections) == 1
    assert sections[0]["name"] == "core"
    assert sections[0]["lines"] == ["When classifying, check the subject line."]


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
    assert sections[0]["name"] == "role"


def test_parse_multiple_sections():
    prompt = (
        "<!-- frozen: role -->\nYou are strict.\n"
        "<!-- frozen: safety -->\nNever run destructive commands.\n"
        "<!-- frozen: format -->\nReturn JSON.\n"
    )
    sections = parse_frozen_sections(prompt)
    assert [s["name"] for s in sections] == ["role", "safety", "format"]


def test_frozen_line_indexes():
    idx = frozen_line_indexes(FROZEN_PROMPT)
    assert 2 in idx


def test_frozen_line_indexes_none():
    assert frozen_line_indexes("no markers") == set()


# ---- compute_edit_distance ----

def test_edit_distance_identical():
    assert compute_edit_distance("a\nb", "a\nb") == 0


def test_edit_distance_change():
    assert compute_edit_distance("a\nb\nc", "a\nx\nc") >= 2


def test_edit_distance_entirely_different():
    assert compute_edit_distance("one\ntwo", "three\nfour\nfive") > 0


# ---- compute_drift_tfidf ----

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
