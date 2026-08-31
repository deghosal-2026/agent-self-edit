"""Tests for the scorer interface and implementations."""

import pytest

from agent_self_edit.llm import LLMProvider, MockProvider, ProviderError
from agent_self_edit.scorers import (
    ContainsScorer,
    ExactMatchScorer,
    LLMJudgeScorer,
    Scorer,
    ScorerError,
    get_scorer,
)


class FailingJudge(LLMProvider):
    def complete(self, prompt, system_prompt="", temperature=0.0):
        raise ProviderError("down")


# ---- ExactMatchScorer ----

def test_exact_match_pass():
    s = ExactMatchScorer()
    assert s.score("Cat A", "cat a") == (True, 1.0)


def test_exact_match_whitespace():
    s = ExactMatchScorer()
    assert s.score("  cat  ", "CAT") == (True, 1.0)


def test_exact_match_fail():
    s = ExactMatchScorer()
    passed, score = s.score("cat", "dog")
    assert passed is False
    assert score == 0.0


def test_exact_match_empty_actual():
    s = ExactMatchScorer()
    passed, score = s.score("cat", "")
    assert passed is False and score == 0.0


def test_exact_match_both_empty():
    s = ExactMatchScorer()
    assert s.score("", "") == (True, 1.0)


# ---- ContainsScorer ----

def test_contains_exact():
    s = ContainsScorer()
    assert s.score("date: 2026", "the date: 2026 yes") == (True, 1.0)


def test_contains_partial():
    s = ContainsScorer()
    passed, score = s.score("alpha\nbeta\ngamma", "only beta present")
    assert passed is False
    assert score == pytest.approx(1 / 3)


def test_contains_empty_actual():
    s = ContainsScorer()
    assert s.score("alpha", "") == (False, 0.0)


def test_contains_required_fields_missing():
    s = ContainsScorer(required_fields=["name", "email"])
    # "name" present but "email" missing -> fail
    passed, _ = s.score("name: x", "just name: x")
    assert passed is False


def test_contains_required_fields_present():
    s = ContainsScorer(required_fields=["name", "email"])
    assert s.score("name: x", "name: x, email: y@z") == (True, 1.0)


def test_contains_requires_expected_content():
    s = ContainsScorer()
    # Expected empty => pass regardless if actual non-empty
    assert s.score("", "anything") == (True, 1.0)


# ---- LLMJudgeScorer ----

def test_llm_judge_numeric():
    judge = MockProvider(responses="0.87")
    s = LLMJudgeScorer(judge_llm=judge)
    passed, score = s.score("gold", "agent out")
    assert passed is True
    assert score == pytest.approx(0.87)


def test_llm_judge_low_score_fails():
    judge = MockProvider(responses="0.2")
    s = LLMJudgeScorer(judge_llm=judge)
    passed, score = s.score("gold", "agent out")
    assert passed is False
    assert score == pytest.approx(0.2)


def test_llm_judge_non_numeric_defaults_zero():
    judge = MockProvider(responses="good work!")
    s = LLMJudgeScorer(judge_llm=judge)
    passed, score = s.score("gold", "out")
    assert passed is False and score == 0.0


def test_llm_judge_clamps_over_one():
    judge = MockProvider(responses="5.0")
    s = LLMJudgeScorer(judge_llm=judge)
    _, score = s.score("gold", "out")
    assert score == 1.0


def test_llm_judge_clamps_negative():
    judge = MockProvider(responses="-3.0")
    s = LLMJudgeScorer(judge_llm=judge)
    _, score = s.score("gold", "out")
    assert score == 0.0


def test_llm_judge_provider_failure():
    judge = FailingJudge()
    s = LLMJudgeScorer(judge_llm=judge)
    passed, score = s.score("gold", "out")
    assert passed is False and score == 0.0


# ---- Factory / errors ----

def test_get_scorer_exact():
    s = get_scorer("exact")
    assert isinstance(s, ExactMatchScorer)


def test_get_scorer_contains():
    s = get_scorer("Contains")
    assert isinstance(s, ContainsScorer)


def test_get_scorer_llmjudge():
    s = get_scorer("llmjudge", judge_llm=MockProvider("0.5"))
    assert isinstance(s, LLMJudgeScorer)


def test_get_scorer_llmjudge_missing_judge():
    with pytest.raises(ScorerError):
        get_scorer("llmjudge")


def test_get_scorer_unknown():
    with pytest.raises(ScorerError):
        get_scorer("nope")


def test_scorer_abstract_cannot_instantiate():
    with pytest.raises(TypeError):
        Scorer()  # type: ignore[abstract]
