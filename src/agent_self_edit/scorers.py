"""Scorer interface and implementations."""

from __future__ import annotations

import unicodedata
from abc import ABC, abstractmethod
from typing import Any

from .llm.base import LLMProvider, ProviderError
from .tasks import TaskSet


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
    if normalized in ("exact", "exactmatch", "exact_match", "singlelabel", "single_label"):
        return SingleLabelScorer(**kwargs)
    if normalized in ("exactset", "exact_set", "set"):
        return ExactSetScorer(**kwargs)
    if normalized in ("partialset", "partial_set", "partial"):
        return PartialSetScorer(**kwargs)
    if normalized in ("contains", "containsscorer"):
        return ContainsScorer(**kwargs)
    if normalized in ("structured", "struct", "extraction", "structuredextraction"):
        return StructuredExtractionScorer(**kwargs)
    if normalized in ("llmjudge", "llm_judge", "llm", "judge"):
        if judge_llm is None:
            raise ScorerError("LLMJudgeScorer requires a judge_llm provider")
        return LLMJudgeScorer(judge_llm=judge_llm, **kwargs)
    raise ScorerError(f"unknown scorer: {name!r}")


def resolve_scorer(
    task_set: TaskSet,
    judge_llm: LLMProvider | None = None,
    default: str = "exact",
    allow_mixed: bool = False,
) -> "Scorer":
    """Resolve a scorer from a ``TaskSet``.

    Resolution order:
      1. Manifest-level ``scorer`` definition (if present).
      2. Per-task ``metadata.scorer`` hints — all must agree.
      3. Fallback to ``default``.

    For LLMJudgeScorer, rubrics/anchors/dimensions are loaded from manifest
    and task metadata.

    Raises ``ScorerError`` if per-task hints are inconsistent (unless ``allow_mixed``).
    """
    manifest = task_set.manifest
    manifest_scorer = manifest.get("scorer", "") if manifest else ""

    if manifest_scorer:
        kwargs = {}
        if manifest_scorer in ("llmjudge", "llm_judge"):
            kwargs["rubric"] = manifest.get("judge_rubric", "")
            anchors = manifest.get("judge_anchors", "")
            if anchors:
                kwargs["anchors"] = anchors
            dims = manifest.get("judge_dimensions", [])
            if dims:
                kwargs["dimensions"] = dims
        return get_scorer(manifest_scorer, judge_llm=judge_llm, **kwargs)

    tasks = task_set.list_tasks()
    scorer_hints: set[str] = set()
    judge_kwargs: dict[str, Any] = {}
    for task in tasks:
        name = task.metadata.get("scorer")
        if name:
            scorer_hints.add(name.strip().lower())
        meta = task.metadata
        if meta.get("judge_rubric"):
            judge_kwargs.setdefault("rubric", meta["judge_rubric"])
        if meta.get("judge_anchors"):
            judge_kwargs.setdefault("anchors", meta["judge_anchors"])
        if meta.get("judge_dimensions"):
            judge_kwargs.setdefault("dimensions", meta["judge_dimensions"])

    if len(scorer_hints) > 1:
        if not allow_mixed:
            raise ScorerError(
                f"Mixed scorer hints in task set: {scorer_hints}. "
                "Set allow_mixed=True or use a manifest-level scorer."
            )

    if scorer_hints:
        chosen = next(iter(scorer_hints))
        return get_scorer(chosen, judge_llm=judge_llm, **judge_kwargs)

    return get_scorer(default, judge_llm=judge_llm, **judge_kwargs)


class Scorer(ABC):
    """Scores an agent output against the expected output."""

    @abstractmethod
    def score(self, expected: str, actual: str) -> tuple[bool, float]:
        """Return ``(passed, score)`` where score is 0.0 (wrong) .. 1.0 (perfect)."""
        raise NotImplementedError


class SingleLabelScorer(Scorer):
    """Strict exact match for single-label classification benchmarks.

    Same semantics as the original ``ExactMatchScorer`` — kept as a separate
    class to make benchmark contracts explicit.
    """

    def score(self, expected: str, actual: str) -> tuple[bool, float]:
        normalized_expected = expected.strip().lower()
        normalized_actual = actual.strip().lower()
        passed = normalized_expected == normalized_actual
        return (passed, 1.0 if passed else 0.0)


class ExactMatchScorer(SingleLabelScorer):
    """Alias kept for backward compatibility — delegates to ``SingleLabelScorer``."""


class ExactSetScorer(Scorer):
    """Unordered set equality for multi-label benchmarks.

    Splits ``expected`` and ``actual`` on commas, trims whitespace, and
    compares as sets. Reordered labels pass; extra/missing labels fail.
    """

    def score(self, expected: str, actual: str) -> tuple[bool, float]:
        expected_set = {s.strip().lower() for s in expected.split(",") if s.strip()}
        actual_set = {s.strip().lower() for s in actual.split(",") if s.strip()}
        passed = expected_set == actual_set
        return (passed, 1.0 if passed else 0.0)


class PartialSetScorer(Scorer):
    """Credit for overlapping labels, penalty for missing/extra labels.

    Score = Jaccard similarity of label sets:
        |intersection| / |union|

    This gives diagnostic signal: 0.5 means half the labels match.
    """

    def score(self, expected: str, actual: str) -> tuple[bool, float]:
        expected_set = {s.strip().lower() for s in expected.split(",") if s.strip()}
        actual_set = {s.strip().lower() for s in actual.split(",") if s.strip()}
        if not expected_set:
            return (True, 1.0)
        if not actual_set:
            return (False, 0.0)
        intersection = expected_set & actual_set
        union = expected_set | actual_set
        score = len(intersection) / len(union)
        return (score >= 1.0, score)


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




class StructuredExtractionScorer(Scorer):
    """Normalize field:value pairs and compare required fields precisely.

    Parses ``expected`` and ``actual`` as ``key: value`` lines and compares
    them by normalized key. Supports:

    - Nested structures via ``key.subkey`` notation
    - Null values (empty, ``null``, ``None``) — treated as missing
    - Conflicting-source precedence: latest value wins
    - Strong equivalence normalization (Unicode NFKC, strip, lower)
    """

    def _normalize_val(self, val: str) -> str:
        return unicodedata.normalize("NFKC", val.strip().lower())

    def _is_null(self, val: str) -> bool:
        return val.strip() in ("", "null", "none", "n/a", "na")

    def _parse(self, text: str) -> dict[str, str]:
        pairs: dict[str, str] = {}
        for line in text.strip().splitlines():
            line = line.strip()
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key = key.strip().lower()
            if self._is_null(val):
                continue
            pairs[key] = val.strip()
        return pairs

    def _flatten(self, d: dict[str, str]) -> dict[str, str]:
        flat: dict[str, str] = {}
        for key, val in d.items():
            if "." in key:
                parts = key.split(".")
                val = self._normalize_val(val)
                flat[".".join(parts)] = val
            else:
                flat[key] = self._normalize_val(val)
        return flat

    def _compare_nested(self, exp_key: str, act_key: str,
                        exp_val: str, act_val: str) -> bool:
        if exp_key == act_key:
            return exp_val == act_val
        if "." in exp_key and "." in act_key:
            exp_parts = exp_key.split(".")
            act_parts = act_key.split(".")
            if exp_parts[-1] == act_parts[-1]:
                return exp_val == act_val
            if len(exp_parts) > 1 and len(act_parts) > 1 \
                    and exp_parts[0] == act_parts[0]:
                return exp_val == act_val
        return False

    def score(self, expected: str, actual: str) -> tuple[bool, float]:
        exp_raw = self._parse(expected)
        act_raw = self._parse(actual)

        if not exp_raw:
            return (True, 1.0)
        if not act_raw:
            return (False, 0.0)

        exp = self._flatten(exp_raw)
        act = self._flatten(act_raw)

        matched = 0
        for exp_key, exp_val in exp.items():
            act_val = act.get(exp_key)
            if act_val is not None and act_val == exp_val:
                matched += 1
                continue
            for act_key, act_val2 in act.items():
                if act_val2 == exp_val and self._compare_nested(
                    exp_key, act_key, exp_val, act_val2
                ):
                    matched += 1
                    break

        total = len(exp)
        extras = len(act) - matched
        if extras > 0:
            penalty = extras / max(len(act), 1)
            score = max(0.0, (matched / total) - penalty)
        else:
            score = matched / total if total > 0 else 0.0
        return (matched == total and extras == 0, score)


FALLBACK_RUBRIC = "Score the actual output from 0.0 (completely wrong) to 1.0 (perfect)."


class LLMJudgeScorer(Scorer):
    """Uses a separate LLM to judge output quality (0.0 .. 1.0).

    Supports benchmark-specific rubrics, positive/negative anchors,
    and multi-dimension scoring.
    """

    def __init__(
        self,
        judge_llm: LLMProvider,
        rubric: str = "",
        anchors: str = "",
        dimensions: list[dict[str, str]] | None = None,
    ) -> None:
        self.judge_llm = judge_llm
        self.rubric = rubric
        self.anchors = anchors
        self.dimensions = dimensions

    def _build_judge_prompt(
        self, expected: str, actual: str,
    ) -> str:
        lines = ["You are evaluating an AI agent's output.",
                 "",
                 f"Expected output: {expected}",
                 "",
                 f"Actual output: {actual}",
                 "",
        ]
        if self.anchors:
            lines.append("Reference examples:")
            lines.append(self.anchors)
            lines.append("")

        if self.dimensions:
            lines.append("Evaluate the output on each dimension independently:")
            for dim in self.dimensions:
                name = dim.get("name", "")
                desc = dim.get("description", "")
                weight = dim.get("weight", "1.0")
                lines.append(f"  - {name} ({weight}x): {desc}")
            lines.append("")
            lines.append(
                "Output a JSON object with dimension names as keys "
                "and scores (0.0-1.0) as values."
            )
            lines.append(
                "Then output the weighted average on the last line "
                "prefixed with 'OVERALL:'."
            )
        else:
            rubric = self.rubric if self.rubric else FALLBACK_RUBRIC
            lines.append(rubric)
            lines.append("")
            lines.append("Output ONLY a number between 0.0 and 1.0.")

        return "\n".join(lines)

    def score(self, expected: str, actual: str) -> tuple[bool, float]:
        judge_prompt = self._build_judge_prompt(expected, actual)
        try:
            response = self.judge_llm.complete(
                prompt=judge_prompt,
                system_prompt="You are a strict but fair evaluator.",
                temperature=0.0,
            )
            score = self._parse_score(response)
        except (ValueError, ProviderError):
            return (False, 0.0)
        score = max(0.0, min(1.0, score))
        return (score >= 0.5, score)

    def _parse_score(self, response: str) -> float:
        stripped = response.strip()
        if self.dimensions:
            for line in reversed(stripped.splitlines()):
                line = line.strip()
                if line.startswith("OVERALL:"):
                    return float(line.split(":", 1)[1].strip())
            return 0.0
        return float(stripped)
