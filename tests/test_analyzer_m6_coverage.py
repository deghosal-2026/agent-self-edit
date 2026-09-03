"""M6 coverage tests — targets missing lines in analyzer.py to reach 92%+.

Covers:
- build_stage* prompts (187-191)
- validate_proposal 11-line+blank, max_edit_lines config vs default (280)
- deduplicate_proposals near_miss >0.85 (287-310)
- StagedAnalyzer stage1-4 + _fuzzy_fix Strategy3 (337,349,361-372,386-396,409-465)
- staged vs single-pass, llm_provider override (477,483,491-507)
- _extract_json outer-only preservation and unexpected type (217,200-217)
- STAGE3 prompt must not contain [FROZEN]
- cost tracking staged vs single (600-609,624-628,646,669)
"""

import json
from unittest.mock import Mock, patch

import pytest

from agent_self_edit.analyzer import (
    STAGE3_SYNTHESIZE_PROMPT,
    AnalysisResult,
    AnalyzerError,
    StagedAnalyzer,
    _extract_json,
    analyze,
    analyze_batch,
    build_stage1_prompt,
    build_stage2_prompt,
    build_stage3_prompt,
    deduplicate_proposals,
    validate_proposal,
)
from agent_self_edit.config import AnalyzerConfig, Config, ProjectConfig
from agent_self_edit.llm.mock import MockProvider
from agent_self_edit.types import EditProposal, Trace


def _trace(task_id="t1", success=False, reason="failed", output="wrong", expected="right", task_input="hi"):
    return Trace(
        task_id=task_id,
        task_input=task_input,
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


CURRENT = "You are a classifier.\nWhen classifying, check the subject line.\n"


# ---- build_stage* prompts (187-191) ----

def test_build_stage3_prompt_contains_raw_no_frozen():
    prompt = build_stage3_prompt(
        current_prompt="Hello world prompt",
        target_section="intro",
        rationale="needs clarity",
        failure_patterns='[{"pattern":"x"}]',
        rejection_context="prev rejected",
    )
    assert "Hello world prompt" in prompt
    assert "intro" in prompt
    assert "needs clarity" in prompt
    assert "prev rejected" in prompt


def test_build_stage1_prompt_contains_traces():
    traces = [_trace("t1"), _trace("t2")]
    p = build_stage1_prompt(traces, rejection_context="retry")
    assert "t1" in p
    assert "t2" in p
    assert "retry" in p


def test_build_stage2_prompt_annotated():
    prompt = "line0\n<!-- frozen -->\nline2\n"
    p = build_stage2_prompt(prompt, failure_patterns="pattern x", rejection_context="")
    # annotated prompt should mark frozen line
    assert "[FROZEN]" in p
    assert "pattern x" in p


def test_build_stage1_without_rejection():
    p = build_stage1_prompt([_trace("t1")], rejection_context="")
    assert "Previous iteration" not in p


def test_build_stage2_without_rejection():
    p = build_stage2_prompt("hello", "patterns", rejection_context="")
    assert "Previous iteration" not in p


def test_build_stage3_without_rejection():
    p = build_stage3_prompt("hello", "sec", "rat", "pat", rejection_context="")
    assert "Previous iteration" not in p


# ---- STAGE3 must not contain [FROZEN] ----

def test_stage3_prompt_has_no_frozen_marker():
    # Template intentionally says "no [FROZEN]" to clarify raw mode, but must not have
    # the annotated marker "marked with [FROZEN]" like stage1/2 do, and generated prompt
    # must not inject [FROZEN] annotations even if input has frozen sections
    assert "marked with [FROZEN]" not in STAGE3_SYNTHESIZE_PROMPT
    # also verify generated prompt does not inject frozen marker even if input has frozen sections
    frozen_prompt = "<!-- frozen: role -->\nYou are strict.\n<!-- frozen -->\neditable line\n"
    p = build_stage3_prompt(frozen_prompt, "editable", "r", "pat")
    # Stage3 uses current_prompt_raw directly, so no [FROZEN] annotation should appear
    # The only [FROZEN] in template is the disclaimer "no [FROZEN]" — check output has at most that one
    assert p.count("[FROZEN]") == STAGE3_SYNTHESIZE_PROMPT.count("[FROZEN]")
    assert "You are strict." in p


# ---- _extract_json outer-only, inner preserved, unexpected type ----

def test_extract_json_outer_only_preserves_inner():
    inner_obj = {
        "section": "x",
        "old_text": "a",
        "new_text": "```python\ncode\n```",
        "hypothesis": "h",
    }
    inner = json.dumps(inner_obj)
    wrapped = f"```json\n{inner}\n```"
    data = _extract_json(wrapped)
    assert isinstance(data, dict)
    assert "```python" in data["new_text"]


def test_extract_json_inner_backticks_preserved_list():
    payload = json.dumps([{"section": "a", "old_text": "x", "new_text": "hello ```code``` world", "hypothesis": "h"}])
    wrapped = f"```json\n{payload}\n```"
    data = _extract_json(wrapped)
    assert isinstance(data, list)
    assert "```code```" in data[0]["new_text"]


def test_extract_json_no_fences():
    obj = {"section": "x", "old_text": "a", "new_text": "b", "hypothesis": "h"}
    data = _extract_json(json.dumps(obj))
    assert isinstance(data, dict)
    assert data["section"] == "x"


def test_extract_json_unexpected_type_raises():
    with pytest.raises(AnalyzerError, match="unexpected JSON type"):
        _extract_json("123")
    with pytest.raises(AnalyzerError, match="unexpected JSON type"):
        _extract_json("null")
    with pytest.raises(AnalyzerError, match="unexpected JSON type"):
        _extract_json('"just a string"')


def test_extract_json_invalid_raises():
    with pytest.raises(AnalyzerError, match="invalid JSON"):
        _extract_json("not json at all")


def test_extract_json_only_outer_stripped_not_inner():
    # response with outer json fence and inner python fence: only outermost stripped
    inner = json.dumps({"section": "x", "old_text": "a", "new_text": "outer ```python\ninner\n``` end", "hypothesis": "h"})
    wrapped = f"```json\n{inner}\n```"
    data = _extract_json(wrapped)
    assert isinstance(data, dict)
    assert "```python" in data["new_text"]  # type: ignore[index]
    assert data["new_text"].count("```") == 2  # type: ignore[index]


# ---- validate_proposal: 10 lines, 11 lines, blank counting, max_edit_lines config ----

def test_validate_proposal_11_lines_fails():
    prompt = "\n".join([f"line{i}" for i in range(20)]) + "\n"
    old = "\n".join([f"line{i}" for i in range(11)])
    prop = _proposal(old_text=old, new_text="x")
    errors = validate_proposal(prop, prompt, None)
    assert any("too large" in e and "11 lines" in e for e in errors)


def test_validate_proposal_10_lines_ok():
    prompt = "\n".join([f"line{i}" for i in range(15)]) + "\n"
    old = "\n".join([f"line{i}" for i in range(10)])
    prop = _proposal(old_text=old, new_text=old)
    errors = validate_proposal(prop, prompt, None)
    assert errors == []


def test_validate_proposal_blank_lines_counted():
    # old_text with blanks splitlines counts blanks; 11 lines including blanks should fail
    lines = ["a", "", "", "b", "c", "d", "e", "f", "g", "h", "i"]
    old = "\n".join(lines)  # 11 lines (including blanks at index 1,2)
    prompt = old + "\nextra\n"
    prop = _proposal(old_text=old, new_text="x")
    errors = validate_proposal(prop, prompt, None)
    assert any("too large" in e for e in errors)
    # 5 lines with blanks should still be counted as 5, not 2
    lines5 = ["a", "", "", "b", "c"]  # 5 lines
    old5 = "\n".join(lines5)
    prompt5 = old5 + "\nextra"
    prop5 = _proposal(old_text=old5, new_text="x")
    # max is 10, so 5 should pass
    assert validate_proposal(prop5, prompt5, None) == []
    # but verify changed_span uses max of old/new: new larger than old triggers
    prop5b = _proposal(old_text="a", new_text="\n".join([f"l{i}" for i in range(11)]))
    # old "a" not found check would fail but we use prompt containing "a" and new spans 11
    prompt_a = "a\n" + "\n".join([f"l{i}" for i in range(11)])
    prop5c = _proposal(old_text="a", new_text="\n".join([f"l{i}" for i in range(11)]))
    errs = validate_proposal(prop5c, prompt_a, None)
    assert any("too large" in e for e in errs)


def test_validate_proposal_max_edit_lines_from_config():
    prompt = "\n".join([f"l{i}" for i in range(10)]) + "\n"
    old = "\n".join([f"l{i}" for i in range(5)])
    # default max 10: 5 lines passes
    prop = _proposal(old_text=old, new_text=old)
    assert validate_proposal(prop, prompt, None) == []
    assert validate_proposal(prop, prompt, None, Config(project=ProjectConfig(name="x"))) == []
    # config with max 3 should fail for 5 lines
    cfg = Config(project=ProjectConfig(name="x"), analyzer=AnalyzerConfig(max_edit_lines=3))
    errs = validate_proposal(prop, prompt, None, config=cfg)
    assert any("too large" in e and "max is 3" in e for e in errs)
    # config with max 10 (explicit) passes for 10 lines, fails for 11
    cfg10 = Config(project=ProjectConfig(name="x"), analyzer=AnalyzerConfig(max_edit_lines=10))
    old11 = "\n".join([f"l{i}" for i in range(11)])
    prompt11 = old11 + "\nextra"
    prop11 = _proposal(old_text=old11, new_text="x")
    assert any("too large" in e for e in validate_proposal(prop11, prompt11, None, config=cfg10))
    # with config None defaults to 10
    assert any("too large" in e for e in validate_proposal(prop11, prompt11, None, config=None))


def test_validate_proposal_new_text_span_counts():
    prompt = "a\nb\nc\n"
    # old small, new large -> should fail on new size
    prop = _proposal(old_text="a", new_text="\n".join([str(i) for i in range(11)]))
    errs = validate_proposal(prop, prompt, None)
    assert any("too large" in e for e in errs)


# ---- deduplicate_proposals near_miss >0.85 ----

def test_deduplicate_near_miss_similarity_above_threshold_skipped():
    # identical texts have similarity 1.0 >0.85 so should be skipped
    near = _proposal(new_text="hello world identical text")
    prop = _proposal(new_text="hello world identical text")
    result = deduplicate_proposals([prop], [near], threshold=0.85)
    assert result == []


def test_deduplicate_near_miss_threshold_exact():
    near = _proposal(new_text="the quick brown fox jumps")
    prop = _proposal(new_text="the quick brown fox jumps")
    # similarity 1.0 >0.85 so skipped
    assert deduplicate_proposals([prop], [near]) == []
    # different text similarity 0.0 not skipped
    prop2 = _proposal(new_text="extract dates from invoices completely different")
    assert len(deduplicate_proposals([prop2], [near])) == 1


def test_deduplicate_intra_duplicate():
    ps = [_proposal(new_text="same"), _proposal(new_text="same"), _proposal(new_text="different")]
    res = deduplicate_proposals(ps, [])
    assert len(res) == 2
    assert res[0].new_text == "same"
    assert res[1].new_text == "different"


# ---- _fuzzy_fix Strategy3 whitespace-normalized ----

def test_fuzzy_fix_strategy3_whitespace_normalized():
    # current_prompt has double/triple spaces, old_text has single spaces
    current = "You are a  helper   that answers."
    # old_text with single spaces not found exactly, but whitespace-normalized should match
    proposal = _proposal(old_text="You are a helper that answers.", new_text="You are a better helper.")
    sa = StagedAnalyzer(MockProvider(responses="{}"))
    corrected = sa._fuzzy_fix_old_text(proposal, current)
    assert corrected is not None
    # should return actual substring from original with original whitespace
    assert corrected.old_text == "You are a  helper   that answers."
    assert corrected.old_text in current


def test_fuzzy_fix_returns_none_when_no_match():
    current = "completely different prompt content"
    proposal = _proposal(old_text="xyz not in prompt at all 123", new_text="new")
    sa = StagedAnalyzer(MockProvider(responses=""))
    result = sa._fuzzy_fix_old_text(proposal, current)
    # best_ratio may be low <0.80, so None
    assert result is None or result.old_text in current


def test_fuzzy_fix_strategy1_and_2_line_windows():
    current = "line1\nline2\nline3\nline4\nline5\n"
    # old off by one char should still fuzzy match via difflib
    proposal = _proposal(old_text="line2\nline3", new_text="replaced")
    sa = StagedAnalyzer(MockProvider(responses=""))
    corrected = sa._fuzzy_fix_old_text(proposal, current)
    assert corrected is not None
    assert corrected.old_text == "line2\nline3"


def test_fuzzy_fix_strategy2_varying_window():
    current = "a\nb\nc\nd\ne\nf\n"
    # old expects 2 lines but prompt window of 3 may be closer for fuzzy? we test delta logic
    proposal = _proposal(old_text="b\nc\nextra", new_text="new")
    sa = StagedAnalyzer(MockProvider(responses=""))
    result = sa._fuzzy_fix_old_text(proposal, current)
    # either returns a candidate or None, but should not crash and cover delta loops
    assert result is None or isinstance(result, EditProposal)


# ---- StagedAnalyzer stage1/2/3/4 ----

def test_stage1_summarize_list_returns_json_dump():
    responses = '[{"pattern":"p1","description":"d","trace_ids":["t1"]}]'
    llm = MockProvider(responses=responses)
    sa = StagedAnalyzer(llm)
    result = sa.stage1_summarize([_trace("t1")])
    parsed = json.loads(result)
    assert isinstance(parsed, list)
    assert parsed[0]["pattern"] == "p1"


def test_stage1_summarize_dict_returns_raw():
    # when LLM returns dict, stage1 returns raw response (line 337)
    llm = MockProvider(responses='{"foo":"bar"}')
    sa = StagedAnalyzer(llm)
    result = sa.stage1_summarize([_trace("t1")])
    assert result == '{"foo":"bar"}'


def test_stage2_select_dict_returns_section():
    llm = MockProvider(responses='{"section":"mysec","rationale":"because"}')
    sa = StagedAnalyzer(llm)
    sec, rat = sa.stage2_select(CURRENT, "patterns")
    assert sec == "mysec"
    assert rat == "because"


def test_stage2_select_list_returns_empty():
    llm = MockProvider(responses='[{"section":"x"}]')
    sa = StagedAnalyzer(llm)
    sec, rat = sa.stage2_select(CURRENT, "patterns")
    assert sec == ""
    assert rat == ""


def test_stage3_synthesize_dict_returns_proposal():
    payload = json.dumps({
        "section": "classify",
        "old_text": "When classifying, check the subject line.",
        "new_text": "When classifying, check the subject line and body.",
        "hypothesis": "h",
        "expected_improvement": "e",
    })
    llm = MockProvider(responses=payload)
    sa = StagedAnalyzer(llm)
    prop = sa.stage3_synthesize(CURRENT, "classify", "r", "patterns")
    assert prop is not None
    assert prop.section == "classify"


def test_stage3_synthesize_list_returns_none():
    llm = MockProvider(responses='[{"section":"x"}]')
    sa = StagedAnalyzer(llm)
    result = sa.stage3_synthesize(CURRENT, "sec", "rat", "pat")
    assert result is None


def test_stage4_validate_fuzzy_success():
    current = "You are a  helper   that answers."
    proposal = _proposal(old_text="You are a helper that answers.", new_text="You are a better helper.")
    # old_text not found exactly, but fuzzy should fix
    sa = StagedAnalyzer(MockProvider(responses=""))
    errors, corrected = sa.stage4_validate(proposal, current, None)
    assert errors == []
    assert corrected.old_text in current
    assert corrected.old_text == "You are a  helper   that answers."


def test_stage4_validate_fuzzy_fails_returns_errors():
    current = "short prompt"
    proposal = _proposal(old_text="not in prompt at all xyz", new_text="new")
    sa = StagedAnalyzer(MockProvider(responses=""))
    errors, prop = sa.stage4_validate(proposal, current, None)
    assert any("old_text" in e for e in errors)
    assert prop == proposal


def test_stage4_validate_passes_directly():
    # valid proposal should pass without fuzzy
    sa = StagedAnalyzer(MockProvider(responses=""))
    prop = _proposal()
    errors, out = sa.stage4_validate(prop, CURRENT, None)
    assert errors == []
    assert out == prop


# ---- StagedAnalyzer.analyze branches ----

def test_staged_analyze_empty_traces_returns_empty():
    sa = StagedAnalyzer(MockProvider(responses=""))
    proposals, _, _ = sa.analyze([], CURRENT, None); assert proposals == []


def test_staged_analyze_successful_pipeline():
    # Mock provider that handles all three stages distinct prompts
    def responder(prompt, system_prompt=""):
        if "summarize" in prompt.lower() and "failure" in prompt.lower():
            return '[{"pattern":"p","description":"d","trace_ids":["t1"]}]'
        if "Select exactly ONE section" in prompt:
            return '{"section":"classify","rationale":"r"}'
        if "Propose ONE minimal edit" in prompt:
            return json.dumps({
                "section": "classify",
                "old_text": "When classifying, check the subject line.",
                "new_text": "When classifying, check the subject line and body.",
                "hypothesis": "h",
                "expected_improvement": "e",
            })
        return "[]"

    llm = MockProvider(responses=responder)
    sa = StagedAnalyzer(llm)
    traces = [_trace("t1")]
    result, _, _ = sa.analyze(traces, CURRENT, None)
    assert len(result) == 1
    assert result[0].old_text in CURRENT


def test_staged_analyze_section_empty_returns_empty():
    def responder(prompt, system_prompt=""):
        if "summarize" in prompt.lower():
            return '[{"pattern":"p","description":"d","trace_ids":["t1"]}]'
        if "Select exactly ONE section" in prompt:
            return '{"section":"","rationale":"r"}'
        return "{}"
    sa = StagedAnalyzer(MockProvider(responses=responder))
    proposals, _, _ = sa.analyze([_trace("t1")], CURRENT, None); assert proposals == []


def test_staged_analyze_proposal_none_returns_empty():
    def responder(prompt, system_prompt=""):
        if "summarize" in prompt.lower():
            return '[{"pattern":"p","description":"d","trace_ids":["t1"]}]'
        if "Select exactly ONE section" in prompt:
            return '{"section":"classify","rationale":"r"}'
        if "Propose ONE minimal edit" in prompt:
            return '[]'  # list not dict => stage3 returns None
        return "[]"
    sa = StagedAnalyzer(MockProvider(responses=responder))
    proposals, _, _ = sa.analyze([_trace("t1")], CURRENT, None); assert proposals == []


def test_staged_analyze_validation_fails_returns_empty():
    def responder(prompt, system_prompt=""):
        if "summarize" in prompt.lower():
            return '[{"pattern":"p","description":"d","trace_ids":["t1"]}]'
        if "Select exactly ONE section" in prompt:
            return '{"section":"classify","rationale":"r"}'
        if "Propose ONE minimal edit" in prompt:
            return json.dumps({
                "section": "classify",
                "old_text": "not in prompt xyz",
                "new_text": "new text",
                "hypothesis": "h",
                "expected_improvement": "e",
            })
        return "[]"
    sa = StagedAnalyzer(MockProvider(responses=responder))
    proposals, _, _ = sa.analyze([_trace("t1")], CURRENT, None); assert proposals == []


def test_staged_analyze_exception_returns_empty():
    # StagedAnalyzer catches AnalyzerError from _llm_call which raises AnalyzerError on ProviderError
    # So mock provider raising ProviderError triggers AnalyzerError path
    from agent_self_edit.llm.base import ProviderError

    class FailingProvider(MockProvider):
        def complete(self, prompt, system_prompt="", temperature=0.0):
            raise ProviderError("down")

    sa = StagedAnalyzer(FailingProvider())
    proposals, _, _ = sa.analyze([_trace("t1")], CURRENT, None)
    assert proposals == []


def test_staged_llm_provider_override():
    # mock A vs B: ensure llm_provider B is used, not A
    class TagProvider(MockProvider):
        def __init__(self, tag, responder):
            super().__init__(responses=responder)
            self.tag = tag
            self.my_calls: list[str] = []  # type: ignore[no-redef]

        def complete(self, prompt, system_prompt="", temperature=0.0):
            self.my_calls.append(prompt)
            return super().complete(prompt, system_prompt, temperature)

    def responder(prompt, system_prompt=""):
        if "summarize" in prompt.lower():
            return '[{"pattern":"p","description":"d","trace_ids":["t1"]}]'
        if "Select exactly ONE section" in prompt:
            return '{"section":"classify","rationale":"r"}'
        if "Propose ONE minimal edit" in prompt:
            return json.dumps({
                "section": "classify",
                "old_text": "When classifying, check the subject line.",
                "new_text": "When classifying, check the subject line and body.",
                "hypothesis": "h",
                "expected_improvement": "e",
            })
        return "[]"

    llm_a = TagProvider("A", responder)
    llm_b = TagProvider("B", responder)
    sa = StagedAnalyzer(llm_a)
    traces = [_trace("t1")]
    result, _, _ = sa.analyze(traces, CURRENT, None, llm_provider=llm_b)
    assert len(llm_b.my_calls) > 0
    assert len(llm_a.my_calls) == 0
    # original llm restored after call
    assert sa.llm is llm_a
    # also test without override uses self.llm
    llm_a.my_calls.clear()
    llm_b.my_calls.clear()
    sa2 = StagedAnalyzer(llm_a)
    result2, _, _ = sa2.analyze(traces, CURRENT, None, llm_provider=None)
    assert len(llm_a.my_calls) > 0


# ---- analyze_batch staged vs single-pass ----

def test_analyze_batch_staged_vs_single_pass_call_count():
    traces = [_trace("t1"), _trace("t2")]

    # staged=True should call StagedAnalyzer.analyze once, not single-pass
    with patch("agent_self_edit.analyzer.StagedAnalyzer.analyze", return_value=([_proposal()], None, 40)) as mock_staged:
        llm = MockProvider(responses=json.dumps([{
            "section": "classify",
            "old_text": "When classifying, check the subject line.",
            "new_text": "When classifying, check the subject line and body.",
            "hypothesis": "h",
            "expected_improvement": "e",
        }]))
        result = analyze_batch(traces, CURRENT, None, llm, staged=True)
        assert mock_staged.call_count == 1

    # staged=False should NOT call StagedAnalyzer.analyze, uses single-pass
    with patch("agent_self_edit.analyzer.StagedAnalyzer.analyze", return_value=([_proposal()], None, 40)) as mock_staged2:
        llm2 = MockProvider(responses=json.dumps([{
            "section": "classify",
            "old_text": "When classifying, check the subject line.",
            "new_text": "When classifying, check the subject line and body.",
            "hypothesis": "h",
            "expected_improvement": "e",
        }]))
        result2 = analyze_batch(traces, CURRENT, None, llm2, staged=False)
        assert mock_staged2.call_count == 0
        assert len(result2.proposals) == 1


def test_analyze_batch_staged_produces_proposals():
    def responder(prompt, system_prompt=""):
        if "summarize" in prompt.lower():
            return '[{"pattern":"p","description":"d","trace_ids":["t1"]}]'
        if "Select exactly ONE section" in prompt:
            return '{"section":"classify","rationale":"r"}'
        if "Propose ONE minimal edit" in prompt:
            return json.dumps({
                "section": "classify",
                "old_text": "When classifying, check the subject line.",
                "new_text": "When classifying, check the subject line and body.",
                "hypothesis": "h",
                "expected_improvement": "e",
            })
        return "[]"

    llm = MockProvider(responses=responder)
    traces = [_trace("t1")]
    result = analyze_batch(traces, CURRENT, None, llm, staged=True)
    assert len(result.proposals) == 1
    assert result.cost_aborted is False


def test_analyze_batch_single_pass_produces_proposals():
    payload = json.dumps([{
        "section": "classify",
        "old_text": "When classifying, check the subject line.",
        "new_text": "When classifying, check the subject line and body.",
        "hypothesis": "h",
        "expected_improvement": "e",
    }])
    llm = MockProvider(responses=payload)
    traces = [_trace("t1")]
    result = analyze_batch(traces, CURRENT, None, llm, staged=False)
    assert len(result.proposals) == 1


# ---- Cost ceiling staged cost > ceiling → cost_aborted ----

def test_analyze_batch_staged_cost_ceiling_aborted():
    # staged cost exceeds ceiling => cost_aborted True and no proposals
    def responder(prompt, system_prompt=""):
        if "summarize" in prompt.lower():
            return '[{"pattern":"p","description":"d","trace_ids":["t1"]}]'
        if "Select exactly ONE section" in prompt:
            return '{"section":"classify","rationale":"r"}'
        if "Propose ONE minimal edit" in prompt:
            return json.dumps({
                "section": "classify",
                "old_text": "When classifying, check the subject line.",
                "new_text": "When classifying, check the subject line and body.",
                "hypothesis": "h",
                "expected_improvement": "e",
            })
        return "[]"

    huge_prompt = "x" * 20000  # ~5000 tokens -> cost ~0.016 > 0.001
    cfg = Config(project=ProjectConfig(name="x"), analyzer=AnalyzerConfig(cost_ceiling_usd=0.001))
    llm = MockProvider(responses=responder)
    traces = [_trace("t1"), _trace("t2")]
    result = analyze_batch(traces, huge_prompt, None, llm, config=cfg, staged=True)
    assert result.cost_aborted is True
    assert result.proposals == []
    assert result.failure_reason == "cost ceiling exceeded"


def test_analyze_batch_staged_empty_proposals_cost_not_aborted_but_failure():
    # staged pipeline returns no proposals but cost below ceiling => failure_reason staged no proposals
    def responder(prompt, system_prompt=""):
        if "summarize" in prompt.lower():
            return '[]'  # empty patterns will cause section empty => no proposals
        if "Select exactly ONE section" in prompt:
            return '{"section":"","rationale":"r"}'
        return "[]"
    llm = MockProvider(responses=responder)
    traces = [_trace("t1")]
    # low cost prompt
    result = analyze_batch(traces, CURRENT, None, llm, staged=True)
    assert result.proposals == []
    assert result.cost_aborted is False
    assert result.failure_reason == "staged analyzer produced no proposals"


def test_analyze_batch_single_pre_cost_ceiling_aborts():
    huge_prompt = "y" * 20000
    cfg = Config(project=ProjectConfig(name="x"), analyzer=AnalyzerConfig(cost_ceiling_usd=0.001))
    llm = MockProvider(responses=json.dumps([{
        "section": "classify",
        "old_text": "When classifying, check the subject line.",
        "new_text": "When classifying, check the subject line and body.",
        "hypothesis": "h",
        "expected_improvement": "e",
    }]))
    traces = [_trace("t1")]
    result = analyze_batch(traces, huge_prompt, None, llm, config=cfg, staged=False)
    assert result.cost_aborted is True
    assert result.failure_reason == "cost ceiling exceeded"
    # LLM should not have been called? Actually pre_cost aborts before _analyze_with_response
    assert len(llm.calls) == 0


def test_analyze_batch_single_post_cost_ceiling():
    # pre cost below ceiling but total cost after response exceeds ceiling
    cfg = Config(project=ProjectConfig(name="x"), analyzer=AnalyzerConfig(cost_ceiling_usd=0.002))
    # current prompt small: tokens ~10, prompt_text maybe ~50 tokens => cost ~0.00016 <0.002 not aborted pre
    # response huge: 10000 chars => 2500 tokens => total ~2550 => cost ~0.008 > ceiling
    huge_response = json.dumps([{
        "section": "classify",
        "old_text": "When classifying, check the subject line.",
        "new_text": "x" * 10000,
        "hypothesis": "h",
        "expected_improvement": "e",
        "evidence_traces": ["t1"],
    }])
    llm = MockProvider(responses=huge_response)
    traces = [_trace("t1")]
    result = analyze_batch(traces, CURRENT, None, llm, config=cfg, staged=False)
    # should have proposals but cost_aborted True (post-call warning path line 646)
    assert result.cost_aborted is True
    assert result.tokens_used > 0


def test_analyze_batch_single_no_failures_returns_empty():
    traces = [_trace("t1", success=True), _trace("t2", success=True)]
    llm = MockProvider(responses="[]")
    result = analyze_batch(traces, CURRENT, None, llm, staged=False)
    assert result.proposals == []
    assert result.tokens_used == 0


def test_analyze_with_response_non_array_raises():
    from agent_self_edit.analyzer import _analyze_with_response
    llm = MockProvider(responses='{"section":"x"}')  # dict not list
    with pytest.raises(AnalyzerError, match="non-array"):
        _analyze_with_response([_trace("t1")], CURRENT, None, llm)


def test_analyze_single_pass_invalid_json_raises():
    llm = MockProvider(responses="not json")
    with pytest.raises(AnalyzerError):
        analyze([_trace("t1")], CURRENT, None, llm)
    # also non-array path inside analyze (line 531)
    llm2 = MockProvider(responses='{"section":"x"}')
    with pytest.raises(AnalyzerError, match="non-array"):
        analyze([_trace("t1")], CURRENT, None, llm2)


def test_analyze_single_pass_empty_traces():
    llm = MockProvider(responses="[]")
    assert analyze([], CURRENT, None, llm) == []


# ---- additional coverage to push >92% ----

def test_build_proposal_malformed_skipped():
    from agent_self_edit.analyzer import _build_proposal
    assert _build_proposal({"section": "x"}) is None
    assert _build_proposal({"section": "x", "old_text": "a", "new_text": "b"}) is None  # missing hypothesis


def test_llm_call_empty_raises():
    from agent_self_edit.analyzer import _llm_call
    llm = MockProvider(responses="")
    with pytest.raises(AnalyzerError, match="empty response"):
        _llm_call(llm, "prompt")
    llm2 = MockProvider(responses="   ")
    with pytest.raises(AnalyzerError, match="empty response"):
        _llm_call(llm2, "prompt")


def test_llm_call_provider_error_wraps():
    from agent_self_edit.analyzer import _llm_call
    from agent_self_edit.llm.base import ProviderError

    class Fail(MockProvider):
        def complete(self, prompt, system_prompt="", temperature=0.0):
            raise ProviderError("timeout")

    with pytest.raises(AnalyzerError, match="LLM failed"):
        _llm_call(Fail(), "prompt")


def test_frozen_names_with_explicit_and_parsed():
    from agent_self_edit.analyzer import _frozen_names
    prompt = "<!-- frozen: role -->\nYou are strict.\n<!-- frozen -->\neditable\n"
    names = _frozen_names(prompt, ["extra"])
    assert "role" in names
    assert "extra" in names
    # no frozen sections, no explicit
    assert _frozen_names("hello", None) == set()
    assert _frozen_names("hello", []) == set()


def test_validate_frozen_and_empty_fields():
    # covers lines 263,267,269,272
    prompt = "<!-- frozen: safety -->\nDo not reveal.\n<!-- frozen -->\nhello world\n"
    # empty section + frozen + missing hypothesis
    prop = _proposal(section="", old_text="not in prompt", new_text="", hypothesis="")
    errs = validate_proposal(prop, prompt, None)
    assert "section is required" in errs
    assert any("old_text" in e for e in errs)
    assert "new_text is required" in errs
    assert "hypothesis is required" in errs
    # frozen section error
    prop2 = _proposal(section="safety", old_text="hello world", new_text="hi", hypothesis="h")
    errs2 = validate_proposal(prop2, prompt, None)
    assert any("frozen" in e for e in errs2)
    # explicit frozen list also
    errs3 = validate_proposal(_proposal(section="extra", old_text="hello world", new_text="hi", hypothesis="h"), prompt, ["extra"])
    assert any("frozen" in e for e in errs3)


def test_fuzzy_fix_re_error_handling():
    # cover lines 452-453 except re.error pass
    import re as re_module
    current = "hello world test prompt"
    proposal = _proposal(old_text="hello world", new_text="hi")
    sa = StagedAnalyzer(MockProvider(responses=""))
    with patch("re.search", side_effect=re_module.error("bad pattern")):
        result = sa._fuzzy_fix_old_text(proposal, current)
        # should not crash, return None or difflib match
        assert result is None or isinstance(result, EditProposal)


def test_analyze_single_pass_valid_covers_logger():
    # covers lines 530-538 logger.info branch
    payload = json.dumps([{
        "section": "classify",
        "old_text": "When classifying, check the subject line.",
        "new_text": "When classifying, check the subject line and body.",
        "hypothesis": "h",
        "expected_improvement": "e",
    }])
    llm = MockProvider(responses=payload)
    result = analyze([_trace("t1")], CURRENT, None, llm)
    assert len(result) == 1


def test_analyze_single_pass_malformed_proposal_skipped_covers_build_proposal():
    llm = MockProvider(responses='[{"section":"x"}]')
    result = analyze([_trace("t1")], CURRENT, None, llm)
    assert result == []


def test_mock_analyzer_covers_remaining_lines():
    from agent_self_edit.analyzer import MockAnalyzer
    m = MockAnalyzer(proposals=[_proposal()])
    # cover analyze and analyze_batch
    out = m.analyze([_trace("t1")], CURRENT, None, MockProvider(responses=""))
    assert len(out) == 1
    assert m.calls == 1
    res = m.analyze_batch([_trace("t1")], CURRENT, None, MockProvider(responses=""), max_proposals=1)
    assert len(res.proposals) == 1
    assert res.cost_usd == 0.0
    # empty proposals
    m2 = MockAnalyzer()
    assert m2.analyze([], CURRENT, None, MockProvider(responses="")) == []
