"""Targeted tests to hit every uncovered line in analyzer.py."""
import json
from unittest.mock import patch

import pytest

from agent_self_edit.analyzer import (
    AnalyzerError,
    MockAnalyzer,
    StagedAnalyzer,
    _analyze_with_response,
    _extract_json,
    analyze_batch,
    build_stage1_prompt,
    build_stage2_prompt,
    build_stage3_prompt,
    deduplicate_proposals,
    validate_proposal,
)
from agent_self_edit.config import AnalyzerConfig, Config, ProjectConfig
from agent_self_edit.llm import MockProvider
from agent_self_edit.types import EditProposal, Trace


def _trace(task_id="t1", success=False):
    return Trace(
        task_id=task_id,
        task_input=f"input {task_id}",
        final_output="wrong",
        expected_output="right",
        success=success,
        timestamp="2026-09-01T10:00:00Z",
        failure_reason="failed",
    )


def _proposal(**kw):
    base = dict(
        section="classify",
        old_text="classify by subject",
        new_text="classify by subject and body",
        hypothesis="body helps disambiguate",
        expected_improvement="+5%",
        evidence_traces=["t1"],
    )
    base.update(kw)
    return EditProposal(**base)


# ---- build_stage1/2/3 prompt ----

def test_build_stage1_prompt_with_rejection():
    t = _trace()
    prompt = build_stage1_prompt([t], rejection_context="prev fix failed")
    assert "prev fix failed" in prompt


def test_build_stage1_prompt_empty():
    prompt = build_stage1_prompt([])
    assert "Failed traces" in prompt


def test_build_stage2_prompt_with_rejection():
    prompt = build_stage2_prompt("hello world", "pattern: x", rejection_context="prev")
    assert "prev" in prompt
    assert "pattern: x" in prompt


def test_build_stage2_prompt_no_rejection():
    prompt = build_stage2_prompt("hello", "pattern: y")
    assert "pattern: y" in prompt
    assert "Previous iteration feedback" not in prompt


def test_build_stage3_prompt_with_rejection():
    prompt = build_stage3_prompt(
        "hello world", "section1", "fix it", "pattern: z",
        rejection_context="prev rejection",
    )
    assert "prev rejection" in prompt
    assert "section1" in prompt
    assert "pattern: z" in prompt


def test_build_stage3_prompt_no_rejection():
    prompt = build_stage3_prompt("hello", "section1", "fix it", "pattern: a")
    assert "pattern: a" in prompt


# ---- _extract_json ----

def test_extract_json_inner_python_code_preserved():
    text = '```json\n{"section": "x", "old_text": "a", "new_text": "b", "hypothesis": "h"}\n```'
    result = _extract_json(text)
    assert isinstance(result, dict)
    assert result["section"] == "x"


def test_extract_json_python_fences_not_stripped():
    code = '{"section": "x", "old_text": "a", "new_text": "b", "hypothesis": "h"}'
    text = f"```python\n{code}\n```"
    result = _extract_json(text)
    assert isinstance(result, dict)
    assert result["section"] == "x"


def test_extract_json_no_fences():
    text = '{"section": "x"}'
    result = _extract_json(text)
    assert result == {"section": "x"}


def test_extract_json_dict_response():
    text = '{"section": "x", "rationale": "best"}'
    result = _extract_json(text)
    assert result == {"section": "x", "rationale": "best"}


def test_extract_json_unexpected_type_raises():
    text = '"just a string"'
    with pytest.raises(AnalyzerError, match="unexpected JSON type"):
        _extract_json(text)


# ---- _fuzzy_fix_old_text Strategy2 window offset ----

def test_fuzzy_fix_strategy2_better_than_strategy1():
    """Strategy 2 with different window finds a match when same-length window misses."""
    prompt = "a\nb\nc\nd\ne"
    old_text = "b\nc\nd\ne\nf"
    proposal = _proposal(old_text=old_text, section="s1")
    result = StagedAnalyzer._fuzzy_fix_old_text(proposal, prompt)
    assert result is not None
    assert "b\nc\nd\ne" in result.old_text


# ---- _fuzzy_fix_old_text Strategy3 re.error ----

def test_fuzzy_fix_strategy3_re_error():
    """Strategy 3 regex error handling (except re.error: pass)."""
    import re as real_re

    orig_search = real_re.search

    def raisy_search(pattern, string, flags=0):
        if len(pattern) > 100000:
            raise real_re.error("pattern too complex")
        return orig_search(pattern, string, flags)

    with patch("re.search", raisy_search):
        old_text = "x " * 50000 + "x"
        prompt = "short text"
        proposal = _proposal(old_text=old_text, section="s1")
        result = StagedAnalyzer._fuzzy_fix_old_text(proposal, prompt)
    assert result is None
    """Strategy 3: prompt has double spaces, old_text uses single spaces.
    The regex should find the substring from the original prompt."""
    prompt = "classify  by  subject  line"
    old_text = "classify by subject line"
    proposal = _proposal(old_text=old_text, section="s1")
    result = StagedAnalyzer._fuzzy_fix_old_text(proposal, prompt)
    assert result is not None
    assert result.old_text == "classify  by  subject  line"


def test_fuzzy_fix_no_match_returns_none():
    prompt = "completely different text here"
    old_text = "not in prompt at all"
    proposal = _proposal(old_text=old_text, section="s1")
    result = StagedAnalyzer._fuzzy_fix_old_text(proposal, prompt)
    assert result is None


def test_fuzzy_fix_strategy1_exact_window():
    """Strategy 1: same-length line window finds a close match."""
    prompt = "line A\nline B\nline C\nline D"
    old_text = "line B\nline C"
    proposal = _proposal(old_text=old_text, section="s1")
    result = StagedAnalyzer._fuzzy_fix_old_text(proposal, prompt)
    assert result is not None
    assert result.old_text == "line B\nline C"


def test_fuzzy_fix_strategy2_varying_window():
    """Strategy 2: +/-2 line windows."""
    prompt = "a\nb\nc\nd\ne"
    old_text = "x\ny\nz"
    proposal = _proposal(old_text=old_text, section="s1")
    result = StagedAnalyzer._fuzzy_fix_old_text(proposal, prompt)
    assert result is None


def test_fuzzy_fix_ratio_threshold():
    """Below 0.80 ratio returns None."""
    prompt = "aaaa bbbb cccc dddd"
    old_text = "wwww xxxx yyyy zzzz"
    proposal = _proposal(old_text=old_text, section="s1")
    result = StagedAnalyzer._fuzzy_fix_old_text(proposal, prompt)
    assert result is None


# ---- StagedAnalyzer stage1/2/3/4 ----

STAGE1_DICT_RESPONSE = json.dumps({"pattern": "single", "description": "just one", "trace_ids": ["t1"]})


def test_stage1_summarize_list():
    llm = MockProvider(responses=json.dumps([
        {"pattern": "p1", "description": "d1", "trace_ids": ["t1"]},
    ]))
    sa = StagedAnalyzer(llm)
    result = sa.stage1_summarize([_trace()])
    parsed = json.loads(result)
    assert isinstance(parsed, list)
    assert parsed[0]["pattern"] == "p1"


def test_stage1_summarize_non_list():
    """When _extract_json returns a dict, stage1 returns raw response."""
    llm = MockProvider(responses=STAGE1_DICT_RESPONSE)
    sa = StagedAnalyzer(llm)
    result = sa.stage1_summarize([_trace()])
    assert result == STAGE1_DICT_RESPONSE


def test_stage2_select_returns_tuple():
    llm = MockProvider(responses=json.dumps({"section": "intro", "rationale": "best section"}))
    sa = StagedAnalyzer(llm)
    section, rationale = sa.stage2_select("prompt text", "patterns")
    assert section == "intro"
    assert rationale == "best section"


def test_stage2_select_non_dict_returns_empty():
    llm = MockProvider(responses=json.dumps(["not", "a", "dict"]))
    sa = StagedAnalyzer(llm)
    section, rationale = sa.stage2_select("prompt", "patterns")
    assert section == ""
    assert rationale == ""


def test_stage3_synthesize_returns_proposal():
    llm = MockProvider(responses=json.dumps({
        "section": "classify",
        "old_text": "classify by subject",
        "new_text": "classify by subject and body",
        "hypothesis": "body helps",
        "expected_improvement": "+5%",
    }))
    sa = StagedAnalyzer(llm)
    result = sa.stage3_synthesize("classify by subject", "classify", "fix", "pattern: x")
    assert result is not None
    assert result.section == "classify"
    assert result.new_text == "classify by subject and body"


def test_stage3_synthesize_non_dict_returns_none():
    llm = MockProvider(responses=json.dumps(["not", "a", "dict"]))
    sa = StagedAnalyzer(llm)
    result = sa.stage3_synthesize("prompt", "section", "rationale", "patterns")
    assert result is None


def test_stage4_validate_fuzzy_success():
    """old_text not in prompt, but fuzzy match fixes it."""
    prompt = "classify  by  subject"
    old_text = "classify by subject"
    proposal = _proposal(old_text=old_text, section="classify", new_text="classify by subject and body")
    sa = StagedAnalyzer(MockProvider(""))
    errors, corrected = sa.stage4_validate(proposal, prompt, None)
    assert errors == []
    assert corrected.old_text == "classify  by  subject"


def test_stage4_validate_fuzzy_fails():
    """Fuzzy match can't find anything -> returns original errors."""
    prompt = "something completely unrelated"
    proposal = _proposal(old_text="not here", section="x", new_text="new")
    sa = StagedAnalyzer(MockProvider(""))
    errors, corrected = sa.stage4_validate(proposal, prompt, None)
    assert len(errors) >= 1
    assert corrected is proposal


# ---- StagedAnalyzer.analyze ----

def test_staged_analyze_empty_traces():
    sa = StagedAnalyzer(MockProvider(""))
    proposals, reason = sa.analyze([], "prompt", None)
    assert proposals == []
    assert reason is None


def test_staged_analyze_no_section():
    """Stage2 returns no section -> abort."""
    llm = MockProvider(responses=[
        json.dumps([{"pattern": "p1", "description": "d1", "trace_ids": ["t1"]}]),
        json.dumps({"section": "", "rationale": ""}),
    ])
    sa = StagedAnalyzer(llm)
    proposals, reason = sa.analyze([_trace()], "prompt", None)
    assert proposals == []


def test_staged_analyze_no_proposal():
    """Stage3 returns None -> abort."""
    llm = MockProvider(responses=[
        json.dumps([{"pattern": "p1", "description": "d1", "trace_ids": ["t1"]}]),
        json.dumps({"section": "intro", "rationale": "best"}),
        json.dumps(["not a dict"]),
    ])
    sa = StagedAnalyzer(llm)
    proposals, _ = sa.analyze([_trace()], "prompt", None)
    assert proposals == []
    """Stage4 returns errors -> empty result."""
    llm = MockProvider(responses=[
        json.dumps([{"pattern": "p1", "description": "d1", "trace_ids": ["t1"]}]),
        json.dumps({"section": "intro", "rationale": "best"}),
        json.dumps({
            "section": "intro",
            "old_text": "not in prompt",
            "new_text": "new",
            "hypothesis": "h",
            "expected_improvement": "+5%",
        }),
    ])
    sa = StagedAnalyzer(llm)
    proposals, _ = sa.analyze([_trace()], "some prompt", None)
    assert proposals == []


def test_staged_analyze_exception_returns_empty():
    """AnalyzerError during staged pipeline -> empty list."""
    class FailingProvider(MockProvider):
        def complete(self, prompt, system_prompt="", temperature=0.0):
            from agent_self_edit.analyzer import AnalyzerError
            raise AnalyzerError("LLM call failed")

    sa = StagedAnalyzer(FailingProvider())
    proposals, _ = sa.analyze([_trace()], "prompt", None)
    assert proposals == []


def test_staged_analyze_llm_provider_override():
    """When llm_provider override is given, use it instead of self.llm."""
    provider_a = MockProvider("")
    provider_b = MockProvider(responses=[
        json.dumps([{"pattern": "p1", "description": "d1", "trace_ids": ["t1"]}]),
        json.dumps({"section": "classify", "rationale": "best"}),
        json.dumps({
            "section": "classify",
            "old_text": "classify by subject",
            "new_text": "classify by subject and body",
            "hypothesis": "h",
            "expected_improvement": "+5%",
        }),
    ])
    sa = StagedAnalyzer(provider_a)
    proposals, _ = sa.analyze([_trace()], "classify by subject", None, llm_provider=provider_b)
    assert len(proposals) == 1
    assert provider_a.calls == []
    assert len(provider_b.calls) == 3


def test_staged_analyze_override_restores_original():
    """After analyze with override, self.llm is restored."""
    provider_a = MockProvider("")
    provider_b = MockProvider(responses=[
        json.dumps([{"pattern": "p1", "description": "d1", "trace_ids": ["t1"]}]),
        json.dumps({"section": "classify", "rationale": "best"}),
        json.dumps({
            "section": "classify",
            "old_text": "classify by subject",
            "new_text": "classify by subject and body",
            "hypothesis": "h",
            "expected_improvement": "+5%",
        }),
    ])
    sa = StagedAnalyzer(provider_a)
    sa.analyze([_trace()], "classify by subject", None, llm_provider=provider_b)
    assert sa.llm is provider_a

    # ---- Validate proposal: line count ----

def test_validate_edit_span_too_large():
    """11-line old_text exceeds default max_edit_lines=10."""
    old = "\n".join(f"line {i}" for i in range(11))
    new = "\n".join(f"line {i}" for i in range(11))
    p = _proposal(old_text=old, new_text=new, section="x")
    errors = validate_proposal(p, old, None)
    assert any("edit span too large" in e for e in errors)


def test_validate_edit_span_from_config():
    """max_edit_lines from config is used."""
    old = "\n".join(f"line {i}" for i in range(5))
    new = "\n".join(f"line {i}" for i in range(5))
    p = _proposal(old_text=old, new_text=new, section="x")
    cfg = Config(project=ProjectConfig(name="x"), analyzer=AnalyzerConfig(max_edit_lines=3))
    errors = validate_proposal(p, old, None, config=cfg)
    assert any("edit span too large" in e for e in errors)


def test_validate_edit_span_with_blanks():
    """5 lines with blanks -> total 11 lines > 10."""
    old = "a\n\nb\n\nc\nd\ne\nf\ng\nh\ni"
    new = old
    p = _proposal(old_text=old, new_text=new, section="x")
    errors = validate_proposal(p, old, None)
    assert any("edit span too large" in e for e in errors)


# ---- Deduplicate proposals ----

def test_dedup_near_miss_high_similarity_skipped():
    """Similarity > 0.85 -> near_miss skip."""
    nm = _proposal(new_text="classify tickets")
    p = _proposal(new_text="classify tickets!")
    result = deduplicate_proposals([p], [nm], threshold=0.85)
    assert result == []


def test_dedup_new_text_seen_skipped():
    """new_text already seen -> skip."""
    p1 = _proposal(new_text="same text")
    p2 = _proposal(new_text="same text")
    result = deduplicate_proposals([p1, p2], [])
    assert len(result) == 1


# ---- analyze_batch staged branch ----

def test_analyze_batch_staged_no_proposals():
    """Staged analyzer produces no proposals."""
    cfg = Config(project=ProjectConfig(name="x"), analyzer=AnalyzerConfig(cost_ceiling_usd=1.0))
    result = analyze_batch(
        [_trace()],
        "some prompt",
        None,
        MockProvider(responses=[
            json.dumps([{"pattern": "p1", "description": "d1", "trace_ids": ["t1"]}]),
            json.dumps({"section": "", "rationale": ""}),
        ]),
        config=cfg,
        staged=True,
    )
    assert result.proposals == []
    assert result.failure_reason == "staged analyzer produced no proposals"


def test_analyze_batch_staged_success():
    """Staged analyzer produces proposals -> dedup + return path (lines 607-609)."""
    cfg = Config(project=ProjectConfig(name="x"), analyzer=AnalyzerConfig(cost_ceiling_usd=1.0))
    result = analyze_batch(
        [_trace()],
        "classify by subject",
        None,
        MockProvider(responses=[
            json.dumps([{"pattern": "p1", "description": "d1", "trace_ids": ["t1"]}]),
            json.dumps({"section": "classify", "rationale": "fix subject-only approach"}),
            json.dumps({
                "section": "classify",
                "old_text": "classify by subject",
                "new_text": "classify by subject and body",
                "hypothesis": "body helps",
                "expected_improvement": "+5%",
            }),
        ]),
        config=cfg,
        staged=True,
    )
    assert len(result.proposals) == 1
    assert result.proposals[0].new_text == "classify by subject and body"
    assert result.cost_aborted is False


def test_analyze_batch_staged_cost_ceiling_exceeded():
    """Staged cost exceeds ceiling."""
    cfg = Config(project=ProjectConfig(name="x"), analyzer=AnalyzerConfig(cost_ceiling_usd=0.0))
    result = analyze_batch([_trace()], "prompt", None, MockProvider(""), config=cfg, staged=True)
    assert result.cost_aborted is True
    assert result.failure_reason == "cost ceiling exceeded"


# ---- analyze_batch non-staged pre-cost ceiling ----

def test_analyze_batch_non_staged_cost_ceiling_aborts():
    """Non-staged pre-call cost exceeds ceiling."""
    huge_prompt = "x" * 200000
    cfg = Config(project=ProjectConfig(name="x"), analyzer=AnalyzerConfig(cost_ceiling_usd=0.001))
    result = analyze_batch([_trace()], huge_prompt, None, MockProvider(""), config=cfg, staged=False)
    assert result.cost_aborted is True
    assert result.failure_reason == "cost ceiling exceeded"


# ---- analyze_batch non-staged post-cost ceiling ----

def test_analyze_batch_non_staged_post_cost_warning():
    """Non-staged post-call cost exceeds ceiling but partial results returned."""
    llm = MockProvider(responses=json.dumps([{
        "section": "classify",
        "old_text": "classify by",
        "new_text": "classify by subject",
        "hypothesis": "h",
        "expected_improvement": "+5%",
    }]))
    # Ceiling chosen so pre_cost (~0.000825 for ~1000-char prompt) passes
    # but total_cost (~0.00095 including response tokens) exceeds it.
    cfg = Config(project=ProjectConfig(name="x"), analyzer=AnalyzerConfig(cost_ceiling_usd=0.00084))
    result = analyze_batch(
        [_trace()],
        "classify by something",
        None,
        llm,
        config=cfg,
        staged=False,
    )
    assert result.cost_aborted is True


# ---- _analyze_with_response non-array ----

def test_analyze_with_response_non_array_raises():
    llm = MockProvider(responses='{"a": 1}')
    with pytest.raises(AnalyzerError, match="non-array"):
        _analyze_with_response([_trace()], "prompt", None, llm)


# ---- MockAnalyzer analyze_batch ----

def test_mock_analyzer_batch_method():
    m = MockAnalyzer(proposals=[_proposal()])
    result = m.analyze_batch([_trace()], "prompt", None, MockProvider(""), max_proposals=3)
    assert len(result.proposals) == 1
    assert m.calls == 1
    assert result.cost_aborted is False


# ---- analyze_batch empty failed list ----

def test_analyze_batch_all_success_returns_empty():
    traces = [_trace("t1", success=True)]
    result = analyze_batch(traces, "prompt", None, MockProvider(""))
    assert result.proposals == []
    assert result.tokens_used == 0
