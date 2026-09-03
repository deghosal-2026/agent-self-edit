"""Feedback analyzer: reviews traces, proposes minimal prompt edits (F-02)."""

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


ANALYZER_SYSTEM_PROMPT = """You are a prompt optimization analyst. You review
execution traces where an agent failed and propose minimal, concrete edits to
the agent's system prompt.

Current prompt (frozen sections marked with [FROZEN]):
{current_prompt_with_annotations}

Failed traces (batch of {N}):
{traces}
{rejection_context}

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

STAGE1_SUMMARIZE_PROMPT = """You are analyzing execution traces where a prompt-based
agent failed. Summarize the recurring failure patterns.

Failed traces:
{traces}
{rejection_context}

Identify the top 2-3 distinct failure patterns. For each pattern, describe:
- What went wrong (1 sentence)
- Which traces exhibit this pattern
- What the prompt likely lacks or misdirects

Respond as a JSON array of objects with keys: pattern, description, trace_ids."""

STAGE2_SELECT_PROMPT = """You are choosing which part of a prompt to edit.

Current prompt (frozen sections marked with [FROZEN]):
{current_prompt_with_annotations}

Failure patterns identified in the traces:
{failure_patterns}
{rejection_context}

Select exactly ONE section of the prompt to modify. Choose the section whose
change would address the most failure patterns with the smallest edit.

Do NOT choose the same section and same edit intent if the previous proposal was rejected.

Respond as JSON: {{"section": "...", "rationale": "..."}}"""

STAGE3_SYNTHESIZE_PROMPT = """You are making a minimal edit to a prompt.

Current prompt (exact text — copy old_text verbatim, raw — no [FROZEN]):
{current_prompt_raw}

Target section: {target_section}
Rationale: {rationale}

Failure patterns to address:
{failure_patterns}
{rejection_context}

Propose ONE minimal edit:
- old_text: copy the EXACT text from the current prompt above that you want to replace
- new_text: replacement text (change the fewest characters possible)
- hypothesis: why this specific change helps (1-2 sentences)
- expected_improvement: measurable expectation

Small-edit rule:
- Prefer changing 1 line only
- Never change more than 2 lines unless absolutely necessary
- Prefer adding one short clause over rewriting a whole block

IMPORTANT: The old_text MUST be copied verbatim from the current prompt.
Do not paraphrase or reformat it.

If previous feedback shows this exact edit family was rejected, produce a materially different edit.

Respond as JSON: {{"section": "...", "old_text": "...", "new_text": "...",
"hypothesis": "...", "expected_improvement": "..."}}"""


def annotate_prompt(prompt_text: str) -> str:
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
    rejection_context: str = "",
) -> str:
    annotated = annotate_prompt(current_prompt)
    formatted = format_traces(traces)
    rejection_section = (
        f"\nPrevious iteration feedback:\n{rejection_context}\n"
        if rejection_context else ""
    )
    return ANALYZER_SYSTEM_PROMPT.format(
        current_prompt_with_annotations=annotated,
        N=len(traces),
        traces=formatted,
        rejection_context=rejection_section,
        max_proposals=max_proposals,
    )


def build_stage1_prompt(traces: list[Trace], rejection_context: str = "") -> str:
    rejection_section = (
        f"\nPrevious iteration feedback:\n{rejection_context}\n"
        if rejection_context else ""
    )
    return STAGE1_SUMMARIZE_PROMPT.format(
        traces=format_traces(traces),
        rejection_context=rejection_section,
    )


def build_stage2_prompt(
    current_prompt: str, failure_patterns: str, rejection_context: str = ""
) -> str:
    rejection_section = (
        f"\nPrevious iteration feedback:\n{rejection_context}\n"
        if rejection_context else ""
    )
    return STAGE2_SELECT_PROMPT.format(
        current_prompt_with_annotations=annotate_prompt(current_prompt),
        failure_patterns=failure_patterns,
        rejection_context=rejection_section,
    )


def build_stage3_prompt(
    current_prompt: str,
    target_section: str,
    rationale: str,
    failure_patterns: str,
    rejection_context: str = "",
) -> str:
    rejection_section = (
        f"\nPrevious iteration feedback:\n{rejection_context}\n"
        if rejection_context else ""
    )
    return STAGE3_SYNTHESIZE_PROMPT.format(
        current_prompt_raw=current_prompt,
        target_section=target_section,
        rationale=rationale,
        failure_patterns=failure_patterns,
        rejection_context=rejection_section,
    )


def _extract_json(response: str) -> list[dict[str, Any]] | dict[str, Any]:
    text = response.strip()
    # Only strip outermost fences, not inner backtick lines containing code (fix 224)
    lines = text.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    text = "\n".join(lines)
    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError as e:
        raise AnalyzerError(f"analyzer returned invalid JSON: {e}") from e
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        return data
    raise AnalyzerError(f"analyzer returned unexpected JSON type: {type(data).__name__}")


def _build_proposal(obj: dict[str, Any]) -> EditProposal | None:
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


def _llm_call(llm: LLMProvider, prompt: str) -> str:
    try:
        response = llm.complete(prompt=prompt, system_prompt="", temperature=0.0)
    except ProviderError as e:
        raise AnalyzerError(f"analyzer LLM failed: {e}") from e
    if not response or not response.strip():
        raise AnalyzerError("analyzer returned empty response")
    return response


def _frozen_names(current_prompt: str, frozen_sections: list[str] | None) -> set[str]:
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
    config: Config | None = None,
) -> list[str]:
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
        errors.append(f"section '{proposal.section}' is frozen and cannot be modified")

    # Count all lines including blank (fix 243) and use configurable limit (fix 287)
    old_lines = proposal.old_text.splitlines()
    new_lines = proposal.new_text.splitlines()
    changed_span = max(len(old_lines), len(new_lines))
    max_lines = config.analyzer.max_edit_lines if config else 10
    if changed_span > max_lines:
        errors.append(
            f"edit span too large ({changed_span} lines); "
            f"max is {max_lines} lines"
        )
    return errors


def deduplicate_proposals(
    proposals: list[EditProposal],
    near_misses: list[EditProposal],
    threshold: float = 0.85,
) -> list[EditProposal]:
    result: list[EditProposal] = []
    for proposal in proposals:
        is_dup = False
        for nm in near_misses:
            drift = compute_drift_tfidf(proposal.new_text, nm.new_text)
            similarity = 1.0 - drift
            if similarity > threshold:
                is_dup = True
                logger.info("Dedup: skipping proposal (similarity=%.2f vs near-miss)", similarity)
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
# Staged analyzer pipeline (#127)
# ---------------------------------------------------------------------------


class StagedAnalyzer:
    """Four-stage analyzer pipeline that reduces cognitive load per call.

    Stage 1 — Failure summarization: identify recurring failure patterns.
    Stage 2 — Prompt target selection: select one exact span to modify.
    Stage 3 — Minimal edit synthesis: produce one minimal replacement.
    Stage 4 — Deterministic structural validation: check before A/B.
    """

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    def stage1_summarize(self, traces: list[Trace], rejection_context: str = "") -> str:
        """Return a JSON string of failure patterns."""
        prompt = build_stage1_prompt(traces, rejection_context=rejection_context)
        response = _llm_call(self.llm, prompt)
        data = _extract_json(response)
        if isinstance(data, list):
            return json.dumps(data, indent=2)
        return response

    def stage2_select(
        self, current_prompt: str, failure_patterns: str, rejection_context: str = ""
    ) -> tuple[str, str]:
        """Return (section, rationale) for the chosen edit target."""
        prompt = build_stage2_prompt(
            current_prompt, failure_patterns, rejection_context=rejection_context
        )
        response = _llm_call(self.llm, prompt)
        data = _extract_json(response)
        if isinstance(data, dict):
            return data.get("section", ""), data.get("rationale", "")
        return "", ""

    def stage3_synthesize(
        self,
        current_prompt: str,
        target_section: str,
        rationale: str,
        failure_patterns: str,
        rejection_context: str = "",
    ) -> EditProposal | None:
        """Produce one minimal edit proposal."""
        prompt = build_stage3_prompt(
            current_prompt,
            target_section,
            rationale,
            failure_patterns,
            rejection_context=rejection_context,
        )
        response = _llm_call(self.llm, prompt)
        data = _extract_json(response)
        if isinstance(data, dict):
            return _build_proposal(data)
        return None

    def stage4_validate(
        self,
        proposal: EditProposal,
        current_prompt: str,
        frozen_sections: list[str] | None,
        config: Config | None = None,
    ) -> tuple[list[str], EditProposal]:
        """Deterministic validation before A/B.

        Returns (errors, corrected_proposal). If fuzzy matching fixes
        old_text, the corrected proposal is returned with an empty error list.
        """
        errors = validate_proposal(proposal, current_prompt, frozen_sections, config)
        if errors and "old_text not found in current prompt" in errors:
            corrected = self._fuzzy_fix_old_text(proposal, current_prompt)
            if corrected is not None:
                errors = validate_proposal(corrected, current_prompt, frozen_sections, config)
                if not errors:
                    logger.info(
                        "Stage 4 fuzzy match: old_text corrected successfully"
                    )
                    return [], corrected
        return errors, proposal

    @staticmethod
    def _fuzzy_fix_old_text(
        proposal: EditProposal, current_prompt: str
    ) -> EditProposal | None:
        """Try to find the closest match for old_text in the prompt.

        Uses multiple strategies:
        1. Exact substring (already failed if we're here)
        2. Line-window matching with difflib
        3. Substring search with varying window sizes
        """
        import difflib

        old_text = proposal.old_text
        prompt_lines = current_prompt.splitlines()
        old_lines = old_text.splitlines()
        old_len = len(old_lines)

        best_ratio = 0.0
        best_match = ""

        # Strategy 1: same-length line windows
        if old_len <= len(prompt_lines):
            for i in range(len(prompt_lines) - old_len + 1):
                candidate = "\n".join(prompt_lines[i:i + old_len])
                ratio = difflib.SequenceMatcher(None, old_text, candidate).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = candidate

        # Strategy 2: try windows of varying sizes (±2 lines)
        for delta in (-2, -1, 1, 2):
            window = old_len + delta
            if window < 1 or window > len(prompt_lines):
                continue
            for i in range(len(prompt_lines) - window + 1):
                candidate = "\n".join(prompt_lines[i:i + window])
                ratio = difflib.SequenceMatcher(None, old_text, candidate).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = candidate

        # Strategy 3: whitespace-normalized substring search (fix 279/207)
        # Extract actual substring from original prompt with flexible whitespace
        import re

        parts = old_text.split()
        if parts:
            pattern = r"\s+".join(re.escape(p) for p in parts)
            try:
                m = re.search(pattern, current_prompt)
                if m:
                    best_ratio = 1.0
                    best_match = m.group(0)
            except re.error:
                pass

        if best_ratio > 0.80 and best_match:
            return EditProposal(
                section=proposal.section,
                old_text=best_match,
                new_text=proposal.new_text,
                hypothesis=proposal.hypothesis,
                expected_improvement=proposal.expected_improvement,
                evidence_traces=proposal.evidence_traces,
                edit_id=proposal.edit_id,
            )
        return None

    def analyze(
        self,
        traces: list[Trace],
        current_prompt: str,
        frozen_sections: list[str] | None,
        llm_provider: LLMProvider | None = None,
        rejection_context: str = "",
    ) -> tuple[list[EditProposal], str | None]:
        """Run the full staged pipeline. Returns (proposals, failure_reason)."""
        if not traces:
            return [], None

        effective_llm = llm_provider if llm_provider is not None else self.llm
        orig_llm = self.llm
        if effective_llm is not self.llm:
            self.llm = effective_llm
        try:
            patterns = self.stage1_summarize(traces, rejection_context=rejection_context)
            section, rationale = self.stage2_select(
                current_prompt, patterns, rejection_context=rejection_context
            )
            if not section:
                return [], None
            proposal = self.stage3_synthesize(
                current_prompt,
                section,
                rationale,
                patterns,
                rejection_context=rejection_context,
            )
            if proposal is None:
                return [], None
            errors, proposal = self.stage4_validate(proposal, current_prompt, frozen_sections)
            if errors:
                return [], f"validation failed: {errors}"
            return [proposal], None
        except AnalyzerError as e:
            return [], f"staged analyzer error: {e}"
        finally:
            self.llm = orig_llm


# ---------------------------------------------------------------------------
# Legacy single-pass analyze (kept for backward compatibility)
# ---------------------------------------------------------------------------


def analyze(
    traces: list[Trace],
    current_prompt: str,
    frozen_sections: list[str] | None,
    llm_provider: LLMProvider,
) -> list[EditProposal]:
    """Run the analyzer (single-pass or staged depending on config)."""
    if not traces:
        return []

    prompt_text = build_analyzer_prompt(current_prompt, traces)
    response = _llm_call(llm_provider, prompt_text)
    data = _extract_json(response)
    if not isinstance(data, list):
        raise AnalyzerError("analyzer returned non-array JSON")
    proposals: list[EditProposal] = []
    for obj in data:
        proposal = _build_proposal(obj)
        if proposal is not None:
            proposals.append(proposal)
    logger.info("Analyzer: produced %d proposals from %d traces", len(proposals), len(traces))
    return proposals


# ---------------------------------------------------------------------------
# Batch analysis (+ cost tracking)
# ---------------------------------------------------------------------------


@dataclass
class AnalysisResult:
    proposals: list[EditProposal] = field(default_factory=list)
    tokens_used: int = 0
    cost_usd: float = 0.0
    cost_aborted: bool = False
    failure_reason: str | None = None


def analyze_batch(
    traces: list[Trace],
    current_prompt: str,
    frozen_sections: list[str] | None,
    llm_provider: LLMProvider,
    max_proposals: int = 3,
    near_misses: list[EditProposal] | None = None,
    rejection_context: str = "",
    config: Config | None = None,
    staged: bool = True,
) -> AnalysisResult:
    """Filter failed traces, analyze (staged or single-pass), validate, dedup, track cost."""
    failed = [t for t in traces if not t.success]
    if not failed:
        return AnalysisResult()

    if staged:
        # Staged path: early branch, no single-pass prompt (fix 285)
        sa = StagedAnalyzer(llm_provider)
        proposals, stage_reason = sa.analyze(
            failed,
            current_prompt,
            frozen_sections,
            llm_provider,
            rejection_context=rejection_context,
        )
        # Approximate cost for staged (4 LLM calls) — use failed count as proxy
        total_tokens = estimate_tokens(current_prompt) + sum(
            estimate_tokens(t.task_input) for t in failed
        )
        total_cost = estimate_cost(total_tokens)
        ceiling = config.analyzer.cost_ceiling_usd if config else 0.50
        if total_cost > ceiling:
            logger.warning(
                "Analyzer: staged cost %.4f exceeds ceiling %.4f — partial",
                total_cost,
                ceiling,
            )
            return AnalysisResult(
                proposals=[],
                tokens_used=total_tokens,
                cost_usd=total_cost,
                cost_aborted=True,
                failure_reason="cost ceiling exceeded",
            )
        if not proposals:
            return AnalysisResult(
                proposals=[],
                tokens_used=total_tokens,
                cost_usd=total_cost,
                failure_reason=stage_reason or "staged analyzer produced no proposals",
            )
        validated = deduplicate_proposals(proposals, near_misses or [])
        cost_aborted = total_cost > ceiling
        return AnalysisResult(
            proposals=validated,
            tokens_used=total_tokens,
            cost_usd=total_cost,
            cost_aborted=cost_aborted,
        )

    ceiling = config.analyzer.cost_ceiling_usd if config else 0.50
    prompt_text = build_analyzer_prompt(
        current_prompt, failed, max_proposals, rejection_context=rejection_context,
    )
    prompt_tokens = estimate_tokens(prompt_text)
    pre_cost = estimate_cost(prompt_tokens)

    if pre_cost > ceiling:
        logger.warning(
            "Analyzer: pre-call cost %.4f exceeds ceiling %.4f — aborting",
            pre_cost, ceiling,
        )
        return AnalysisResult(
            cost_aborted=True, tokens_used=prompt_tokens, cost_usd=pre_cost,
            failure_reason="cost ceiling exceeded",
        )

    response, proposals = _analyze_with_response(
        failed, current_prompt, frozen_sections, llm_provider,
    )
    total_tokens = prompt_tokens + estimate_tokens(response)
    total_cost = estimate_cost(total_tokens)
    proposals = [
        p for p in proposals[:max_proposals]
        if not validate_proposal(p, current_prompt, frozen_sections, config)
    ]

    validated = deduplicate_proposals(proposals, near_misses or [])
    cost_aborted = total_cost > ceiling
    if cost_aborted:
        logger.warning(
            "Analyzer: post-call cost %.4f exceeds ceiling %.4f — partial results",
            total_cost, ceiling,
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
    prompt_text = build_analyzer_prompt(current_prompt, traces)
    response = _llm_call(llm_provider, prompt_text)
    data = _extract_json(response)
    if not isinstance(data, list):
        raise AnalyzerError("analyzer returned non-array JSON")
    proposals: list[EditProposal] = []
    for obj in data:
        proposal = _build_proposal(obj)
        if proposal is not None:
            proposals.append(proposal)
    return response, proposals


class MockAnalyzer:
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
