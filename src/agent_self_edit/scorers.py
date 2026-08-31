"""Scorer interface and implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .llm.base import LLMProvider, ProviderError


class ScorerError(Exception):
    """Raised when a scorer is not found / misconfigured."""


ScorerKey = str


def get_scorer(
    name: str,
    judge_llm: LLMProvider | None = None,
    **kwargs: Any,
) -> "Scorer":
    """Factory: resolve a scorer by name or raise :class:`ScorerError`."""
    normalized = name.strip().lower()
    if normalized in ("exact", "exactmatch", "exact_match"):
        return ExactMatchScorer(**kwargs)
    if normalized in ("contains", "containsscorer"):
        return ContainsScorer(**kwargs)
    if normalized in ("llmjudge", "llm_judge", "llm", "judge"):
        if judge_llm is None:
            raise ScorerError("LLMJudgeScorer requires a judge_llm provider")
        return LLMJudgeScorer(judge_llm=judge_llm, **kwargs)
    raise ScorerError(f"unknown scorer: {name!r}")


class Scorer(ABC):
    """Scores an agent output against the expected output."""

    @abstractmethod
    def score(self, expected: str, actual: str) -> tuple[bool, float]:
        """Return ``(passed, score)`` where score is 0.0 (wrong) .. 1.0 (perfect)."""
        raise NotImplementedError


class ExactMatchScorer(Scorer):
    """Exact string match after strip + lowercase."""

    def score(self, expected: str, actual: str) -> tuple[bool, float]:
        normalized_expected = expected.strip().lower()
        normalized_actual = actual.strip().lower()
        passed = normalized_expected == normalized_actual
        return (passed, 1.0 if passed else 0.0)


class ContainsScorer(Scorer):
    """Checks expected content appears in the actual output (substring match)."""

    def __init__(self, required_fields: list[str] | None = None) -> None:
        self.required_fields = required_fields

    def score(self, expected: str, actual: str) -> tuple[bool, float]:
        if not actual.strip():
            return (False, 0.0)
        expected_lines = expected.strip().split("\n")
        found = 0
        for line in expected_lines:
            if line and line.lower() in actual.lower():
                found += 1
        # Nothing required to match -> trivially correct.
        non_empty = [line for line in expected_lines if line]
        if not non_empty:
            return (True, 1.0)
        if self.required_fields:
            missing = not all(
                f.lower() in actual.lower() for f in self.required_fields if f
            )
            if missing:
                return (False, found / len(expected_lines) if expected_lines else 0.0)
        if not expected_lines:
            return (True, 1.0)
        score = found / len(expected_lines)
        return (score >= 1.0, score)


FALLBACK_RUBRIC = "Score the actual output from 0.0 (completely wrong) to 1.0 (perfect)."


class LLMJudgeScorer(Scorer):
    """Uses a separate LLM to judge output quality (0.0 .. 1.0)."""

    def __init__(self, judge_llm: LLMProvider, rubric: str = "") -> None:
        self.judge_llm = judge_llm
        self.rubric = rubric

    def score(self, expected: str, actual: str) -> tuple[bool, float]:
        judge_prompt = f"""You are evaluating an AI agent's output.

Expected output: {expected}

Actual output: {actual}

{self.rubric if self.rubric else FALLBACK_RUBRIC}

Output ONLY a number between 0.0 and 1.0."""
        try:
            response = self.judge_llm.complete(
                prompt=judge_prompt,
                system_prompt="You are a strict but fair evaluator.",
                temperature=0.0,
            )
            score = float(response.strip())
        except (ValueError, ProviderError):
            return (False, 0.0)
        score = max(0.0, min(1.0, score))
        return (score >= 0.5, score)
