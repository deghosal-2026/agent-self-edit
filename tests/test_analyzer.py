"""Tests for the feedback analyzer (hermetic — no real LLM calls)."""

import json

import pytest

from agent_self_edit.analyzer import (
    AnalysisResult,
    AnalyzerError,
    MockAnalyzer,
    analyze,
    analyze_batch,
    annotate_prompt,
    build_analyzer_prompt,
    deduplicate_proposals,
    format_traces,
    validate_proposal,
)
from agent_self_edit.config import Config, ProjectConfig
from agent_self_edit.llm import MockProvider, ProviderError
from agent_self_edit.types import EditProposal, Trace


def _trace(task_id="t1", success=False, reason="failed", output="wrong", expected="right"):
    return Trace(
        task_id=task_id,
        task_input=f"input {task_id}",
        final_output=output,
        expected_output=expected,
        success=success,
        timestamp="2026-09-01T10:00:00Z",
        failure_reason=reason,
    )


def _proposal(**kwargs):
    base = {
        "section": "classify",
        "old_text": "When classifying, check the subject line.",
        "new_text": "When classifying, check the subject line and body.",
        "hypothesis": "subject-only misses ambiguity",
        "expected_improvement": "+5%",
        "evidence_traces": ["t1"],
    }
    base.update(kwargs)
    return EditProposal(**base)


def _config():
    return Config(project=ProjectConfig(name="x"))


def _json_response(proposals):
    return json.dumps(
        [
            {
                "section": p.section,
                "old_text": p.old_text,
                "new_text": p.new_text,
                "hypothesis": p.hypothesis,
                "evidence_traces": p.evidence_traces,
                "expected_improvement": p.expected_improvement,
            }
            for p in proposals
        ]
    )


# ---- #45: EditProposal dataclass ----

def test_edit_proposal_dataclass_exists():
    p = EditProposal(
        section="foo",
        old_text="a",
        new_text="b",
        hypothesis="h",
        expected_improvement="+1%",
    )
    assert p.section == "foo"
    assert p.evidence_traces == []
    assert p.edit_id is None


def test_edit_proposal_optional_evidence():
    p = _proposal(evidence_traces=["t1", "t2"])
    assert p.evidence_traces == ["t1", "t2"]


# ---- #46: prompt helpers ----

def test_annotate_prompt_no_frozen():
    assert annotate_prompt("no frozen here") == "no frozen here"


def test_annotate_prompt_with_frozen():
    prompt = "line0\n<!-- frozen -->\nline2\n"
    annotated = annotate_prompt(prompt)
    assert "[FROZEN] line0" not in annotated
    assert "[FROZEN] line2" in annotated


def test_format_traces():
    traces = [_trace("t1", reason="misclassified")]
    text = format_traces(traces)
    assert "t1" in text
    assert "misclassified" in text


def test_build_analyzer_prompt_contains_sections():
    traces = [_trace("t1")]
    prompt = build_analyzer_prompt("You are a classifier.\n", traces, max_proposals=3)
    assert "You are a classifier" in prompt
    assert "t1" in prompt
    assert "3" in prompt
    assert "JSON array" in prompt


# ---- #47: analyze() runner ----

def test_analyze_empty_traces_no_call():
    llm = MockProvider(responses="{}")
    assert analyze([], "prompt", None, llm) == []


def test_analyze_valid_json():
    proposal = _proposal()
    llm = MockProvider(responses=_json_response([proposal]))
    result = analyze([_trace("t1")], "a prompt", None, llm)
    assert len(result) == 1
    assert result[0].section == "classify"
    assert result[0].new_text == proposal.new_text


def test_analyze_markdown_fences():
    proposal = _proposal()
    fenced = "```json\n" + _json_response([proposal]) + "\n```"
    llm = MockProvider(responses=fenced)
    result = analyze([_trace("t1")], "a prompt", None, llm)
    assert len(result) == 1


def test_analyze_invalid_json_raises():
    llm = MockProvider(responses="this is not json")
    with pytest.raises(AnalyzerError, match="invalid JSON"):
        analyze([_trace("t1")], "a prompt", None, llm)


def test_analyze_non_array_json_raises():
    llm = MockProvider(responses='{"a": 1}')
    with pytest.raises(AnalyzerError, match="non-array"):
        analyze([_trace("t1")], "a prompt", None, llm)


def test_analyze_empty_response_raises():
    llm = MockProvider(responses="")
    with pytest.raises(AnalyzerError, match="empty response"):
        analyze([_trace("t1")], "a prompt", None, llm)


def test_analyze_malformed_proposal_skipped():
    llm = MockProvider(responses='[{"section": "x"}]')  # missing old_text/new_text
    result = analyze([_trace("t1")], "a prompt", None, llm)
    assert result == []


def test_analyze_llm_failure_raises():
    class FailingProvider(MockProvider):
        def complete(self, prompt, system_prompt="", temperature=0.0):
            raise ProviderError("timeout")

    with pytest.raises(AnalyzerError, match="LLM failed"):
        analyze([_trace("t1")], "a prompt", None, FailingProvider())


# ---- #48: validate_proposal ----

CURRENT = "You are a classifier.\nWhen classifying, check the subject line.\n"


def test_validate_valid():
    errors = validate_proposal(_proposal(), CURRENT, None)
    assert errors == []


def test_validate_empty_section():
    errors = validate_proposal(_proposal(section=""), CURRENT, None)
    assert "section is required" in errors


def test_validate_old_text_not_found():
    errors = validate_proposal(_proposal(old_text="not in prompt"), CURRENT, None)
    assert any("old_text" in e for e in errors)


def test_validate_empty_new_text():
    errors = validate_proposal(_proposal(new_text=""), CURRENT, None)
    assert "new_text is required" in errors


def test_validate_empty_hypothesis():
    errors = validate_proposal(_proposal(hypothesis=""), CURRENT, None)
    assert "hypothesis is required" in errors


def test_validate_frozen_section():
    prompt = "<!-- frozen: role -->\nYou are strict.\n<!-- frozen -->\neditable\n"
    errors = validate_proposal(_proposal(section="role"), prompt, None)
    assert any("frozen" in e for e in errors)


def test_validate_all_errors_together():
    errors = validate_proposal(_proposal(old_text="x", new_text="", section=""), CURRENT, None)
    assert len(errors) >= 3


def test_validate_explicit_frozen_sections():
    errors = validate_proposal(_proposal(section="safety"), CURRENT, ["safety"])
    assert any("frozen" in e for e in errors)


# ---- #49: deduplicate_proposals ----

def test_dedup_no_near_misses_keeps_all():
    ps = [_proposal(new_text="a"), _proposal(new_text="b")]
    assert deduplicate_proposals(ps, []) == ps


def test_dedup_identical_intra():
    ps = [_proposal(new_text="the same"), _proposal(new_text="the same")]
    result = deduplicate_proposals(ps, [])
    assert len(result) == 1


def test_dedup_similar_to_near_miss_skipped():
    near_miss = _proposal(new_text="please classify every ticket carefully")
    proposal = _proposal(new_text="please classify each ticket carefully")
    result = deduplicate_proposals([proposal], [near_miss], threshold=0.5)
    assert result == []


def test_dedup_different_kept():
    near_miss = _proposal(new_text="classify tickets by urgency")
    proposal = _proposal(new_text="extract dates from invoices")
    result = deduplicate_proposals([proposal], [near_miss], threshold=0.85)
    assert len(result) == 1


def test_dedup_empty_proposals():
    assert deduplicate_proposals([], []) == []


# ---- #50: analyze_batch ----

def test_analyze_batch_no_failures():
    traces = [_trace("t1", success=True)]
    result = analyze_batch(traces, CURRENT, None, MockProvider(responses="[]"))
    assert result.proposals == []
    assert result.tokens_used == 0


def test_analyze_batch_only_failed_traces():
    proposal = _proposal()
    llm = MockProvider(responses=_json_response([proposal]))
    traces = [_trace("ok", success=True), _trace("bad", success=False)]
    result = analyze_batch(traces, CURRENT, None, llm, staged=False)
    # only 'bad' failed → still produces proposals
    assert len(result.proposals) == 1


def test_analyze_batch_max_proposals():
    ps = [_proposal(new_text=f"v{i}") for i in range(5)]
    llm = MockProvider(responses=_json_response(ps))
    traces = [_trace(f"t{i}") for i in range(5)]
    result = analyze_batch(traces, CURRENT, None, llm, max_proposals=3, staged=False)
    assert len(result.proposals) <= 3


def test_analyze_batch_validates():
    # proposal with old_text not in prompt → dropped
    bad = _proposal(old_text="not in prompt")
    llm = MockProvider(responses=_json_response([bad]))
    result = analyze_batch([_trace("t1")], CURRENT, None, llm, staged=False)
    assert result.proposals == []


def test_analyze_batch_cost_tracked():
    proposal = _proposal()
    llm = MockProvider(responses=_json_response([proposal]))
    result = analyze_batch([_trace("t1")], CURRENT, None, llm, staged=False)
    assert result.tokens_used > 0
    assert result.cost_usd > 0
    assert result.cost_aborted is False


def test_analyze_batch_cost_ceiling_aborts():
    proposal = _proposal()
    llm = MockProvider(responses=_json_response([proposal]))
    cfg = Config(project=ProjectConfig(name="x"))
    # set a tiny ceiling via AnalyzerConfig override is hard (frozen); use
    # a huge prompt to push pre-cost above a small ceiling.
    huge_prompt = "x" * 200000
    traces = [_trace("t1")]
    from agent_self_edit.config import AnalyzerConfig

    cfg = Config(project=ProjectConfig(name="x"), analyzer=AnalyzerConfig(cost_ceiling_usd=0.001))
    result = analyze_batch(traces, huge_prompt, None, llm, config=cfg)
    assert result.cost_aborted is True


def test_analyze_batch_llm_failure_raises():
    class FailingProvider(MockProvider):
        def complete(self, prompt, system_prompt="", temperature=0.0):
            raise ProviderError("down")

    with pytest.raises(AnalyzerError):
        analyze_batch([_trace("t1")], CURRENT, None, FailingProvider(), staged=False)


# ---- #51: MockAnalyzer ----

def test_mock_analyzer_returns_predetermined():
    ps = [_proposal()]
    m = MockAnalyzer(proposals=ps)
    result = m.analyze([], "prompt", None, MockProvider(""))
    assert result == ps
    assert m.calls == 1


def test_mock_analyzer_batch():
    ps = [_proposal(), _proposal(new_text="second"), _proposal(new_text="third")]
    m = MockAnalyzer(proposals=ps)
    result = m.analyze_batch([_trace("t1")], "prompt", None, MockProvider(""), max_proposals=2)
    assert len(result.proposals) == 2
    assert m.calls == 1


def test_mock_analyzer_zero_cost():
    m = MockAnalyzer(proposals=[_proposal()])
    result = m.analyze_batch([_trace("t1")], "prompt", None, MockProvider(""))
    assert result.cost_usd == 0.0
    assert result.tokens_used == 0
    assert result.cost_aborted is False


def test_mock_analyzer_no_llm():
    m = MockAnalyzer(proposals=[_proposal()])
    m.analyze([_trace("t1")], "prompt", None, MockProvider(""))
    # no LLM provider has been touched (would require a MockProvider call)
    assert m.calls == 1


def test_analysis_result_dataclass():
    r = AnalysisResult(proposals=[], tokens_used=0, cost_usd=0.0, cost_aborted=False)
    assert r.proposals == []
    assert r.cost_aborted is False
    assert r.failure_reason is None


def test_analysis_result_with_failure_reason():
    r = AnalysisResult(proposals=[], tokens_used=0, cost_usd=0.0, cost_aborted=False,
                        failure_reason="cost ceiling exceeded")
    assert r.failure_reason == "cost ceiling exceeded"
