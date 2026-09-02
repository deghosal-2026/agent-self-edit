"""Tests for the scorer interface and implementations."""

import pytest

from agent_self_edit.llm import LLMProvider, MockProvider, ProviderError
from agent_self_edit.scorers import (
    ContainsScorer,
    ExactMatchScorer,
    ExactSetScorer,
    LLMJudgeScorer,
    PartialSetScorer,
    Scorer,
    ScorerError,
    SingleLabelScorer,
    StructuredExtractionScorer,
    get_scorer,
    resolve_scorer,
)
from agent_self_edit.tasks import Task, TaskSet


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
    assert isinstance(s, SingleLabelScorer)


def test_get_scorer_single_label():
    s = get_scorer("single_label")
    assert isinstance(s, SingleLabelScorer)


def test_get_scorer_exact_set():
    s = get_scorer("exactset")
    assert isinstance(s, ExactSetScorer)


def test_get_scorer_partial_set():
    s = get_scorer("partial")
    assert isinstance(s, PartialSetScorer)


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


# ---- SingleLabelScorer ----

def test_single_label_pass():
    s = SingleLabelScorer()
    assert s.score("urgent", "URGENT") == (True, 1.0)


def test_single_label_fail():
    s = SingleLabelScorer()
    assert s.score("urgent", "billing") == (False, 0.0)


# ---- ExactSetScorer ----

def test_exact_set_unordered_pass():
    s = ExactSetScorer()
    assert s.score("security, billing", "billing, security") == (True, 1.0)


def test_exact_set_extra_label_fails():
    s = ExactSetScorer()
    passed, _ = s.score("security, billing", "security, billing, urgent")
    assert passed is False


def test_exact_set_missing_label_fails():
    s = ExactSetScorer()
    passed, _ = s.score("security, billing", "security")
    assert passed is False


def test_exact_set_single_label():
    s = ExactSetScorer()
    assert s.score("urgent", "urgent") == (True, 1.0)


def test_exact_set_empty_actual():
    s = ExactSetScorer()
    assert s.score("urgent", "") == (False, 0.0)


def test_exact_set_reordered_labels():
    s = ExactSetScorer()
    # "technical, security" and "security, technical" are the same set
    assert s.score("technical, security", "security, technical") == (True, 1.0)


# ---- PartialSetScorer ----

def test_partial_set_full_overlap():
    s = PartialSetScorer()
    passed, score = s.score("security, billing", "billing, security")
    assert passed is True
    assert score == 1.0


def test_partial_set_half_overlap():
    s = PartialSetScorer()
    passed, score = s.score("security, billing, urgent", "security, billing")
    assert passed is False
    # 2/3 overlap = 0.67
    assert score == pytest.approx(2 / 3)


def test_partial_set_no_overlap():
    s = PartialSetScorer()
    passed, score = s.score("urgent", "billing")
    assert passed is False
    assert score == 0.0


def test_partial_set_empty_actual():
    s = PartialSetScorer()
    assert s.score("urgent", "") == (False, 0.0)


def test_partial_set_both_empty():
    s = PartialSetScorer()
    assert s.score("", "") == (True, 1.0)


def test_partial_set_extra_labels():
    s = PartialSetScorer()
    # expected={"security", "billing"}, actual=all three → 2/3 overlap
    passed, score = s.score("security, billing", "security, billing, urgent")
    assert passed is False
    assert score == pytest.approx(2 / 3)


# ---- resolve_scorer ----

def test_resolve_scorer_from_first_task():
    ts = TaskSet()
    ts.add_task(Task(id="t1", input="x", expected_output="y", metadata={"scorer": "exactset"}))
    s = resolve_scorer(ts)
    assert isinstance(s, ExactSetScorer)


def test_resolve_scorer_fallback_default():
    ts = TaskSet()
    ts.add_task(Task(id="t1", input="x", expected_output="y"))
    s = resolve_scorer(ts)
    assert isinstance(s, SingleLabelScorer)


def test_resolve_scorer_contains():
    ts = TaskSet()
    ts.add_task(Task(id="t1", input="x", expected_output="y", metadata={"scorer": "contains"}))
    s = resolve_scorer(ts)
    assert isinstance(s, ContainsScorer)


def test_resolve_scorer_empty_task_set():
    ts = TaskSet()
    s = resolve_scorer(ts)
    assert isinstance(s, SingleLabelScorer)


# ---- StructuredExtractionScorer (#126) ----

def test_structured_extraction_exact():
    s = StructuredExtractionScorer()
    passed, score = s.score("name: Alice\nemail: a@b.com", "name: Alice\nemail: a@b.com")
    assert passed is True
    assert score == 1.0


def test_structured_extraction_reordered():
    s = StructuredExtractionScorer()
    passed, score = s.score("name: Alice\nemail: a@b.com", "email: a@b.com\nname: Alice")
    assert passed is True
    assert score == 1.0


def test_structured_extraction_formatting_differences():
    s = StructuredExtractionScorer()
    passed, score = s.score("name: Alice", "name:   alice")
    assert passed is True
    assert score == 1.0


def test_structured_extraction_missing_field():
    s = StructuredExtractionScorer()
    passed, score = s.score("name: Alice\nemail: a@b.com", "name: Alice")
    assert passed is False
    assert score < 1.0


def test_structured_extraction_extra_field():
    s = StructuredExtractionScorer()
    passed, score = s.score("name: Alice", "name: Alice\nemail: a@b.com")
    assert passed is False
    assert score < 1.0


def test_structured_extraction_wrong_value():
    s = StructuredExtractionScorer()
    passed, _ = s.score("name: Alice", "name: Bob")
    assert passed is False


def test_structured_extraction_empty_actual():
    s = StructuredExtractionScorer()
    passed, _ = s.score("name: Alice", "")
    assert passed is False


def test_structured_extraction_empty_expected():
    s = StructuredExtractionScorer()
    passed, score = s.score("", "anything at all")
    assert passed is True
    assert score == 1.0
