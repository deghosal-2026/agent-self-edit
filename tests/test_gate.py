"""Tests for the promotion gate: checks, orchestrator, audit log."""

import threading

import pytest

from agent_self_edit.ab_test import ABResult
from agent_self_edit.config import (
    ABTestConfig,
    Config,
    GateConfig,
    ProjectConfig,
    TasksConfig,
)
from agent_self_edit.gate import (
    GateAuditLog,
    GateError,
    PromotionGate,
    check_all,
    check_confidence,
    check_drift,
    check_edit_distance,
    check_effect_size,
    check_frozen_sections,
    check_sample_floor,
)
from agent_self_edit.guardrails import (
    compute_drift_tfidf,
    compute_edit_distance,
    frozen_line_indexes,
    parse_frozen_sections,
)
from agent_self_edit.types import CheckResult, EditProposal, GateResult


def _config(
    sample_floor: int = 10,
    min_effect: float = 0.05,
    confidence: float = 0.95,
    max_edit: int = 20,
    drift: float = 0.3,
    near_miss: float = 0.5,
) -> Config:
    return Config(
        project=ProjectConfig(name="x"),
        tasks=TasksConfig(sample_floor=sample_floor),
        ab_test=ABTestConfig(
            n_resamples=100,
            n_permutations=100,
            confidence_level=confidence,
            min_effect_size=min_effect,
        ),
        gate=GateConfig(
            max_edit_distance=max_edit,
            drift_threshold=drift,
            near_miss_threshold=near_miss,
        ),
    )


def _ab_result(n_trials=10, p=0.01, effect=0.20, winner: str = "b") -> ABResult:
    return ABResult(
        winner=winner,  # type: ignore[arg-type]
        mean_delta=effect,
        ci_low=0.1,
        ci_high=0.3,
        p_value=p,
        effect_size=effect,
        n_trials=n_trials,
    )


def _proposal(edit_id="edit-1", new_text=None, old_text=None) -> EditProposal:
    return EditProposal(
        section="role",
        old_text=old_text if old_text is not None else "You are a classifier assistant.",
        new_text=new_text if new_text is not None else "You are a classifier assistant.",
        hypothesis="clearer role",
        expected_improvement="+5%",
        evidence_traces=["t1"],
        edit_id=edit_id,
    )


# ---- Check results / types (#22) ----

def test_gate_result_decision_valid():
    r = GateResult(decision="promote")
    assert r.decision == "promote"
    assert r.checks == ()


def test_check_result_fields():
    c = CheckResult(name="x", passed=True, value=1, threshold=0.5, details="ok")
    assert c.name == "x" and c.passed is True and c.value == 1


def test_check_results_immutable():
    r = GateResult(decision="reject", checks=(CheckResult("a", True, 1.0, 0.5, "d"),))
    # CheckResult is a frozen dataclass; assignment raises FrozenInstanceError
    with pytest.raises(Exception):
        r.checks[0].passed = False  # type: ignore[misc]


# ---- Sample floor (#24) ----

def test_sample_floor_pass():
    c = check_sample_floor(_ab_result(n_trials=10), _config(sample_floor=10))
    assert c.passed is True
    assert c.value == 10


def test_sample_floor_fail():
    c = check_sample_floor(_ab_result(n_trials=5), _config(sample_floor=10))
    assert c.passed is False


def test_sample_floor_zero_fails():
    c = check_sample_floor(_ab_result(n_trials=0), _config(sample_floor=10))
    assert c.passed is False


def test_sample_floor_above():
    c = check_sample_floor(_ab_result(n_trials=12), _config(sample_floor=10))
    assert c.passed is True


# ---- Effect size (#25) ----

def test_effect_size_pass():
    c = check_effect_size(_ab_result(effect=0.1), _config(min_effect=0.05))
    assert c.passed is True


def test_effect_size_zero_fails():
    c = check_effect_size(_ab_result(effect=0.0), _config(min_effect=0.05))
    assert c.passed is False


def test_effect_size_negative_fails():
    c = check_effect_size(_ab_result(effect=-0.1), _config(min_effect=0.05))
    assert c.passed is False


def test_effect_size_inf_passes():
    c = check_effect_size(_ab_result(effect=float("inf")), _config(min_effect=0.05))
    assert c.passed is True


def test_effect_size_none_ab():
    c = check_effect_size(None, _config())
    assert c.passed is False


# ---- Confidence (#26) ----

def test_confidence_low_p_passes():
    c = check_confidence(_ab_result(p=0.01), _config(confidence=0.95))
    assert c.passed is True


def test_confidence_high_p_fails():
    c = check_confidence(_ab_result(p=0.98), _config(confidence=0.95))
    assert c.passed is False


def test_confidence_equal_edge():
    c = check_confidence(_ab_result(p=0.95), _config(confidence=0.95))
    assert c.passed is False


def test_confidence_p0_passes():
    c = check_confidence(_ab_result(p=0.0), _config(confidence=0.95))
    assert c.passed is True


def test_confidence_p1_fails():
    c = check_confidence(_ab_result(p=1.0), _config(confidence=0.95))
    assert c.passed is False


# ---- Frozen sections (#27) ----

FROZEN_PROMPT = (
    "You are a classifier assistant.\n"
    "<!-- frozen -->\n"
    "When classifying, check the subject line.\n"
)


def test_frozen_section_pass():
    # edit changes the unfrozen line, leaves frozen block intact
    p = _proposal(
        old_text="You are a classifier assistant.",
        new_text="You are a kind classifier assistant.",
    )
    c = check_frozen_sections(p, FROZEN_PROMPT)
    assert c.passed is True


def test_frozen_section_modified():
    # edit changes text inside the frozen block
    edit = _proposal(
        old_text="When classifying, check the subject line.",
        new_text="When classifying, check the body first.",
    )
    c = check_frozen_sections(edit, FROZEN_PROMPT)
    assert c.passed is False


def test_frozen_section_missing_edit():
    c = check_frozen_sections(None, FROZEN_PROMPT)
    assert c.passed is False


def test_parse_frozen_sections():
    sections = parse_frozen_sections(FROZEN_PROMPT)
    assert len(sections) == 1
    assert sections[0].section_name == "core"


def test_frozen_line_indexes():
    idx = frozen_line_indexes(FROZEN_PROMPT)
    assert 2 in idx  # "When classifying..." line


def test_frozen_sections_explicit_list():
    prompt = (
        "<!-- frozen: role -->\n"
        "You are strict.\n"
        "Perform the task.\n"
    )
    p = _proposal(old_text="You are strict.", new_text="You are lenient.")
    c = check_frozen_sections(p, prompt, frozen_sections=["role"])
    assert c.passed is False


def test_frozen_explicit_section_missing():
    p = _proposal(
        old_text="You are a classifier assistant.",
        new_text="You are a classifier assistant.",
    )
    c = check_frozen_sections(p, FROZEN_PROMPT, frozen_sections=["nonexistent"])
    assert c.passed is False


def test_frozen_no_annotations():
    p = _proposal(
        old_text="line one",
        new_text="line one changed",
    )
    c = check_frozen_sections(p, "line one\nline two")
    assert c.passed is True


# ---- Edit distance (#28) ----

def test_edit_distance_zero():
    assert compute_edit_distance("a\nb", "a\nb").total == 0


def test_edit_distance_small():
    assert compute_edit_distance("a\nb\nc", "a\nx\nc").total >= 1


def test_check_edit_distance_pass():
    p = _proposal(new_text="line1\nline2\nline3\nline4\nline5\nline6")
    c = check_edit_distance(p, "line1\nline2\nline3", _config(max_edit=10))
    assert c.passed is True


def test_check_edit_distance_fail():
    # 5-line insertion far exceeds max_edit=2
    p = _proposal(new_text="a\nb\nc\nd\ne\nf")
    c = check_edit_distance(p, "a", _config(max_edit=2))
    assert c.passed is False


def test_check_edit_distance_max_zero():
    p = _proposal(new_text="changed")
    c = check_edit_distance(p, "original", _config(max_edit=0))
    assert c.passed is False


def test_check_edit_distance_no_edit():
    c = check_edit_distance(None, "original", _config())
    assert c.passed is False


# ---- Drift (#29) ----

def test_drift_identical_zero():
    d = compute_drift_tfidf("same text", "same text")
    assert d == 0.0


def test_drift_completely_different():
    d = compute_drift_tfidf("alpha beta gamma", "delta epsilon zeta")
    assert d > 0.5


def test_drift_similar_low():
    d = compute_drift_tfidf("please classify tickets by urgency", "classify tickets by urgency")
    assert d < 1.0


def test_check_drift_pass():
    c = check_drift(
        _proposal(new_text="classify tickets"),
        "classify tickets", "classify tickets", _config(drift=0.5),
    )
    assert c.passed is True


def test_check_drift_fail():
    # completely different by design
    p = _proposal(new_text="completely different content about apples bananas")
    c = check_drift(p, "original prompt text here", "original prompt text here", _config(drift=0.1))
    assert c.passed is False


def test_check_drift_identical_prompt():
    c = check_drift(_proposal(new_text="same"), "same", "same", _config(drift=0.1))
    assert c.passed is True


# ---- Orchestrator (#30) ----

def test_check_all_promote():
    p = _proposal(old_text="same as current", new_text="same as current")
    ab = _ab_result(n_trials=10, p=0.01, effect=0.2)
    r = check_all(p, ab, "same as current", "same as current", _config())
    assert r.decision == "promote"


def test_check_all_reject_low_trials():
    p = _proposal()
    ab = _ab_result(n_trials=3, p=0.9, effect=0.0)
    r = check_all(p, ab, FROZEN_PROMPT, FROZEN_PROMPT, _config(sample_floor=10))
    # sample floor fails → 0/6 passed → reject
    assert r.decision == "reject"


def test_check_all_missing_prompts_raises():
    with pytest.raises(GateError):
        check_all(_proposal(), _ab_result(), "", "", _config())


def test_fail_fast_stops():
    # First check fails (sample floor), so remaining checks not evaluated
    p = _proposal()
    r = check_all(p, _ab_result(n_trials=0), "a", "a", _config(sample_floor=10))
    assert len(r.checks) == 1
    assert r.checks[0].name == "sample_floor"


def test_promote_all_checks_present():
    p = _proposal(old_text="stable prompt", new_text="stable prompt")
    ab = _ab_result(n_trials=15, p=0.001, effect=0.4)
    r = check_all(p, ab, "stable prompt", "stable prompt", _config())
    assert r.decision == "promote"
    assert len(r.checks) == 6


def test_near_miss_when_first_failure_at_4th_check():
    # Stats pass (3 checks), 4th check (frozen_sections) fails -> 3/6 = 50% -> near_miss
    ab = _ab_result(n_trials=10, p=0.001, effect=0.2)
    modified_frozen = _proposal(
        old_text="When classifying, check the subject line.",
        new_text="When classifying, check the body first.",
    )
    original = (
        "You are a classifier assistant.\n"
        "When classifying, check the subject line.\n"
    )
    r = check_all(
        modified_frozen,
        ab,
        FROZEN_PROMPT,
        original,
        _config(near_miss=0.5),
    )
    assert r.decision == "near_miss"
    assert len(r.checks) == 4  # sample, effect, confidence passed; frozen failed = stop


def test_reject_below_near_miss_threshold():
    # Sample floor fails first -> 0/6 passed < 0.5 -> reject
    ab = _ab_result(n_trials=5, p=0.01, effect=0.2)
    p = _proposal(old_text="stable prompt", new_text="stable prompt")
    r = check_all(p, ab, "stable prompt", "stable prompt", _config(sample_floor=10, near_miss=0.5))
    assert r.decision == "reject"
    assert len(r.checks) == 1


def test_near_miss_threshold_reject_still_promotes_when_all_pass():
    # All 6 pass -> promote regardless of near_miss threshold
    ab = _ab_result(n_trials=10, p=0.001, effect=0.2)
    p = _proposal(old_text="stable prompt", new_text="stable prompt")
    r = check_all(p, ab, "stable prompt", "stable prompt", _config(near_miss=0.9))
    assert r.decision == "promote"


# ---- PromotionGate facade (#23) ----

def test_promotion_gate_check_returns_gateresult():
    gate = PromotionGate()
    r = gate.check(
        _proposal(old_text="stable", new_text="stable"),
        _ab_result(), "stable", "stable", _config(),
    )
    assert isinstance(r, GateResult)


def test_promotion_gate_missing_fields_raise():
    gate = PromotionGate()
    with pytest.raises(GateError):
        gate.check(_proposal(), _ab_result(), "", "", _config())


# ---- Audit log (#31) ----

def test_audit_log_append(tmp_path):
    log = GateAuditLog(tmp_path / "audit.jsonl")
    log.log({"edit_id": "e1", "decision": "reject"})
    log.log({"edit_id": "e2", "decision": "promote"})
    assert log.query("e1")[0]["decision"] == "reject"
    assert len(log.list()) == 2


def test_audit_log_query_missing(tmp_path):
    log = GateAuditLog(tmp_path / "audit.jsonl")
    assert log.query("nope") == []


def test_audit_log_empty_list(tmp_path):
    log = GateAuditLog(tmp_path / "audit.jsonl")
    assert log.list() == []


def test_audit_log_limit(tmp_path):
    log = GateAuditLog(tmp_path / "audit.jsonl")
    for i in range(5):
        log.log({"idx": i})
    assert len(log.list(limit=2)) == 2
    assert log.list(limit=2)[0]["idx"] == 3


def test_audit_log_append_only(tmp_path):
    p = tmp_path / "audit.jsonl"
    log = GateAuditLog(p)
    log.log({"edit_id": "e1", "decision": "promote"})
    # Second writer appends a valid line; both must survive.
    with open(p, "a") as f:
        f.write('{"edit_id": "e2", "decision": "reject"}\n')
    entries = log.list()
    assert len(entries) == 2


def test_audit_log_concurrent_writes(tmp_path):
    log = GateAuditLog(tmp_path / "audit.jsonl")

    def worker(n):
        for i in range(20):
            log.log({"edit_id": f"{n}-{i}", "idx": i})

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    entries = log.list()
    assert len(entries) == 60


def test_audit_log_malformed_line_skipped(tmp_path):
    p = tmp_path / "audit.jsonl"
    p.write_text('{"good": true}\nnot-json\n{"good": true}\n')
    log = GateAuditLog(p)
    assert len(log.list()) == 2


def test_promotion_gate_writes_audit(tmp_path):
    gate = PromotionGate(audit_path=tmp_path / "audit.jsonl")
    assert gate.audit is not None
    gate.check(
        _proposal(old_text="stable", new_text="stable", edit_id="edit-42"),
        _ab_result(), "stable", "stable", _config(),
    )
    entries = gate.audit.list()
    assert len(entries) == 1
    assert entries[0]["edit_id"] == "edit-42"
