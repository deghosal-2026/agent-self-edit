"""Feedback analyzer: reviews traces, proposes minimal prompt edits (F-02).

The analyzer is the creative engine — it has no authority. Every proposal
goes through the A/B test engine and promotion gate before promotion.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from .ab_test import estimate_cost, estimate_tokens
from .config import Config
from .guardrails import compute_drift_tfidf, frozen_line_indexes, parse_frozen_sections
from .llm.base import LLMProvider, ProviderError
from .types import EditProposal, Trace

logger = logging.getLogger("agent_self_edit.analyzer")


class AnalyzerError(Exception):
    """Raised on analyzer LLM failure or malformed response."""


# ---------------------------------------------------------------------------
# #46 — System prompt template + helpers
# ---------------------------------------------------------------------------

ANALYZER_SYSTEM_PROMPT = """You are a prompt optimization analyst. You review
execution traces where an agent failed and propose minimal, concrete edits to
the agent's system prompt.

Current prompt (frozen sections marked with [FROZEN]):
{current_prompt_with_annotations}

Failed traces (batch of {N}):
{traces}

For each failure pattern you identify, propose ONE edit:
- Which section of the prompt to change
- The exact old text (must match current prompt)
- The exact new text (minimal change)
- Why this change should help (hypothesis grounded in trace evidence)
- Which traces support this hypothesis

Do NOT propose changes to [FROZEN] sections.
Do NOT propose more than {max_proposals} edits per batch.
Each edit must be minimal — change the fewest lines possible.

Respond as a JSON array of objects with keys:
section, old_text, new_text, hypothesis, evidence_traces, expected_improvement"""


def annotate_prompt(prompt_text: str) -> str:
    """Prefix every frozen line with ``[FROZEN]`` so the LLM sees it."""
    frozen_idx = frozen_line_indexes(prompt_text)
    lines = prompt_text.splitlines()
    annotated = []
    for i, line in enumerate(lines):
        if i in frozen_idx:
            annotated.append(f"[FROZEN] {line}")
        else:
            annotated.append(line)
    return "\n".join(annotated)


def format_traces(traces: list[Trace]) -> str:
    """Format traces as a compact text block for the analyzer prompt."""
    lines = []
    for i, t in enumerate(traces, 1):
        reason = t.failure_reason or "unknown"
        lines.append(
            f'Trace {i}: task_id={t.task_id}, input="{t.task_input}", '
            f'output="{t.final_output}", expected="{t.expected_output}", '
            f'failure_reason="{reason}"'
        )
    return "\n".join(lines)


def build_analyzer_prompt(
    current_prompt: str,
    traces: list[Trace],
    max_proposals: int = 3,
) -> str:
    """Assemble the full analyzer prompt (annotated prompt + traces + format)."""
    annotated = annotate_prompt(current_prompt)
    formatted = format_traces(traces)
    return ANALYZER_SYSTEM_PROMPT.format(
        current_prompt_with_annotations=annotated,
        N=len(traces),
        traces=formatted,
        max_proposals=max_proposals,
    )


# ---------------------------------------------------------------------------
# #47 — Analyzer runner
# ---------------------------------------------------------------------------


def _extract_json(response: str) -> list[dict[str, Any]]:
    """Parse the LLM response into a JSON list, stripping markdown fences."""
    text = response.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise AnalyzerError(f"analyzer returned invalid JSON: {e}") from e
    if not isinstance(data, list):
        raise AnalyzerError("analyzer returned non-array JSON")
    return data


def _build_proposal(obj: dict[str, Any]) -> EditProposal | None:
    """Map a parsed JSON object to an EditProposal; return None if malformed."""
    try:
        return EditProposal(
            section=obj["section"],
            old_text=obj["old_text"],
            new_text=obj["new_text"],
            hypothesis=obj["hypothesis"],
            expected_improvement=obj.get("expected_improvement", ""),
            evidence_traces=obj.get("evidence_traces", []),
        )
    except (KeyError, TypeError) as e:
        logger.warning("Skipping malformed proposal: %s", e)
        return None


def analyze(
    traces: list[Trace],
    current_prompt: str,
    frozen_sections: list[str] | None,
    llm_provider: LLMProvider,
) -> list[EditProposal]:
    """Run the analyzer over ``traces`` and return structured proposals.

    Empty traces → ``[]`` (no LLM call). LLM failure → :class:`AnalyzerError`.
    """
    if not traces:
        return []

    prompt_text = build_analyzer_prompt(current_prompt, traces)
    try:
        response = llm_provider.complete(
            prompt=prompt_text,
            system_prompt="",
            temperature=0.0,
        )
    except ProviderError as e:
        raise AnalyzerError(f"analyzer LLM failed: {e}") from e

    if not response or not response.strip():
        raise AnalyzerError("analyzer returned empty response")

    data = _extract_json(response)
    proposals: list[EditProposal] = []
    for obj in data:
        proposal = _build_proposal(obj)
        if proposal is not None:
            proposals.append(proposal)
    logger.info("Analyzer: produced %d proposals from %d traces", len(proposals), len(traces))
    return proposals


# ---------------------------------------------------------------------------
# #48 — Proposal validation
# ---------------------------------------------------------------------------


def _frozen_names(
    current_prompt: str, frozen_sections: list[str] | None
) -> set[str]:
    names: set[str] = set()
    for sec in parse_frozen_sections(current_prompt):
        if sec.section_name is not None:
            names.add(sec.section_name)
    if frozen_sections:
        names.update(frozen_sections)
    return names


def validate_proposal(
    proposal: EditProposal,
    current_prompt: str,
    frozen_sections: list[str] | None,
) -> list[str]:
    """Return a list of error messages; empty means the proposal is valid."""
    errors: list[str] = []

    if not proposal.section:
        errors.append("section is required")

    if not proposal.old_text or proposal.old_text not in current_prompt:
        errors.append("old_text not found in current prompt")

    if not proposal.new_text:
        errors.append("new_text is required")

    if not proposal.hypothesis:
        errors.append("hypothesis is required")

    frozen = _frozen_names(current_prompt, frozen_sections)
    if proposal.section in frozen:
        errors.append(
            f"section '{proposal.section}' is frozen and cannot be modified"
        )

    return errors


# ---------------------------------------------------------------------------
# #49 — Proposal deduplication (TF-IDF similarity per DD-19)
# ---------------------------------------------------------------------------


def deduplicate_proposals(
    proposals: list[EditProposal],
    near_misses: list[EditProposal],
    threshold: float = 0.85,
) -> list[EditProposal]:
    """Skip proposals too similar to a near-miss and dedup within the list."""
    result: list[EditProposal] = []
    for proposal in proposals:
        is_dup = False
        for nm in near_misses:
            drift = compute_drift_tfidf(proposal.new_text, nm.new_text)
            similarity = 1.0 - drift
            if similarity > threshold:
                is_dup = True
                logger.info(
                    "Dedup: skipping proposal (similarity=%.2f vs near-miss)",
                    similarity,
                )
                break
        if not is_dup:
            result.append(proposal)

    seen: list[str] = []
    final: list[EditProposal] = []
    for p in result:
        if p.new_text not in seen:
            seen.append(p.new_text)
            final.append(p)
    return final


# ---------------------------------------------------------------------------
# #50 — Batch analysis + #51 — cost tracking
# ---------------------------------------------------------------------------


@dataclass
class AnalysisResult:
    """Result of a batch analysis, including cost tracking."""

    proposals: list[EditProposal] = field(default_factory=list)
    tokens_used: int = 0
    cost_usd: float = 0.0
    cost_aborted: bool = False


def analyze_batch(
    traces: list[Trace],
    current_prompt: str,
    frozen_sections: list[str] | None,
    llm_provider: LLMProvider,
    max_proposals: int = 3,
    near_misses: list[EditProposal] | None = None,
    config: Config | None = None,
) -> AnalysisResult:
    """Filter failed traces, analyze, validate, dedup, truncate, track cost.

    Returns an :class:`AnalysisResult` with proposals and cost info.
    """
    failed = [t for t in traces if not t.success]
    if not failed:
        return AnalysisResult()

    ceiling = config.analyzer.cost_ceiling_usd if config else 0.50
    prompt_text = build_analyzer_prompt(current_prompt, failed, max_proposals)
    prompt_tokens = estimate_tokens(prompt_text)
    pre_cost = estimate_cost(prompt_tokens)

    if pre_cost > ceiling:
        logger.warning(
            "Analyzer: pre-call cost %.4f exceeds ceiling %.4f — aborting",
            pre_cost,
            ceiling,
        )
        return AnalysisResult(cost_aborted=True, tokens_used=prompt_tokens, cost_usd=pre_cost)

    response, proposals = _analyze_with_response(
        failed, current_prompt, frozen_sections, llm_provider
    )
    total_tokens = prompt_tokens + estimate_tokens(response)
    total_cost = estimate_cost(total_tokens)

    validated = [
        p
        for p in proposals[:max_proposals]
        if not validate_proposal(p, current_prompt, frozen_sections)
    ]
    validated = deduplicate_proposals(validated, near_misses or [])

    cost_aborted = total_cost > ceiling
    if cost_aborted:
        logger.warning(
            "Analyzer: post-call cost %.4f exceeds ceiling %.4f — partial results",
            total_cost,
            ceiling,
        )

    return AnalysisResult(
        proposals=validated,
        tokens_used=total_tokens,
        cost_usd=total_cost,
        cost_aborted=cost_aborted,
    )


def _analyze_with_response(
    traces: list[Trace],
    current_prompt: str,
    frozen_sections: list[str] | None,
    llm_provider: LLMProvider,
) -> tuple[str, list[EditProposal]]:
    """Call analyze() but also capture the LLM response text for cost tracking.

    Returns ``(response_text, proposals)``.
    """
    prompt_text = build_analyzer_prompt(current_prompt, traces)
    try:
        response = llm_provider.complete(
            prompt=prompt_text,
            system_prompt="",
            temperature=0.0,
        )
    except ProviderError as e:
        raise AnalyzerError(f"analyzer LLM failed: {e}") from e

    if not response or not response.strip():
        raise AnalyzerError("analyzer returned empty response")

    data = _extract_json(response)
    proposals: list[EditProposal] = []
    for obj in data:
        proposal = _build_proposal(obj)
        if proposal is not None:
            proposals.append(proposal)
    return response, proposals


# ---------------------------------------------------------------------------
# #51 — MockAnalyzer
# ---------------------------------------------------------------------------


class MockAnalyzer:
    """Returns predetermined proposals; never calls an LLM (hermetic CI)."""

    def __init__(self, proposals: list[EditProposal] | None = None) -> None:
        self._proposals = proposals or []
        self.calls = 0
        self.total_tokens = 0
        self.total_cost = 0.0

    def analyze(
        self,
        traces: list[Trace],
        current_prompt: str,
        frozen_sections: list[str] | None,
        llm_provider: LLMProvider,
    ) -> list[EditProposal]:
        self.calls += 1
        return list(self._proposals)

    def analyze_batch(
        self,
        traces: list[Trace],
        current_prompt: str,
        frozen_sections: list[str] | None,
        llm_provider: LLMProvider,
        max_proposals: int = 3,
        near_misses: list[EditProposal] | None = None,
        config: Config | None = None,
    ) -> AnalysisResult:
        self.calls += 1
        return AnalysisResult(
            proposals=list(self._proposals)[:max_proposals],
            tokens_used=0,
            cost_usd=0.0,
            cost_aborted=False,
        )
