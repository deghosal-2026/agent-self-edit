"""Tests for Trace dataclass and validate_trace."""

import pytest

from agent_self_edit.types import Trace, validate_trace

VALID_TRACE = {
    "task_id": "t1",
    "task_input": "classify this",
    "final_output": "cat_a",
    "expected_output": "cat_a",
    "success": True,
    "timestamp": "2026-09-01T10:00:00Z",
}


def test_valid_trace_deserializes():
    trace = validate_trace(VALID_TRACE)
    assert isinstance(trace, Trace)
    assert trace.task_id == "t1"
    assert trace.success is True


def test_extra_fields_ignored():
    data = {**VALID_TRACE, "extra": "ignored", "something_nested": {"a": 1}}
    trace = validate_trace(data)
    assert trace.task_id == "t1"


def test_missing_required_field():
    required = ("task_id", "task_input", "final_output", "expected_output", "success", "timestamp")
    for field in required:
        data = {k: v for k, v in VALID_TRACE.items() if k != field}
        with pytest.raises(ValueError, match="missing required field"):
            validate_trace(data)


def test_wrong_type_raises():
    data = dict(VALID_TRACE)
    data["success"] = "yes"  # string, not bool
    with pytest.raises(ValueError, match="must be a bool"):
        validate_trace(data)


def test_timestamp_malformed():
    data = dict(VALID_TRACE)
    data["timestamp"] = "2026-09-01"  # date only, not ISO 8601 time
    with pytest.raises(ValueError, match="ISO 8601"):
        validate_trace(data)


def test_timestamp_naive_offset():
    data = dict(VALID_TRACE)
    data["timestamp"] = "2026-09-01T10:00:00+05:00"
    trace = validate_trace(data)
    assert trace.timestamp.endswith("+05:00")


def test_steps_optional():
    trace = validate_trace(VALID_TRACE)
    assert trace.steps == []


def test_steps_parsed():
    data = {**VALID_TRACE, "steps": [{"action": "classify", "confidence": 0.9}, {"action": "done"}]}
    trace = validate_trace(data)
    assert len(trace.steps) == 2
    assert trace.steps[0]["action"] == "classify"


def test_steps_wrong_type():
    data = {**VALID_TRACE, "steps": "not a list"}
    with pytest.raises(ValueError, match="must be a list"):
        validate_trace(data)


def test_failure_reason_optional():
    trace = validate_trace(VALID_TRACE)
    assert trace.failure_reason is None
    data = {**VALID_TRACE, "success": False, "failure_reason": "misclassified"}
    trace = validate_trace(data)
    assert trace.failure_reason == "misclassified"


def test_failure_reason_wrong_type():
    data = {**VALID_TRACE, "failure_reason": 42}
    with pytest.raises(ValueError, match="failure_reason"):
        validate_trace(data)


def test_prompt_version_optional():
    trace = validate_trace(VALID_TRACE)
    assert trace.prompt_version is None
    data = {**VALID_TRACE, "prompt_version": 3}
    trace = validate_trace(data)
    assert trace.prompt_version == 3


def test_prompt_version_wrong_type():
    data = {**VALID_TRACE, "prompt_version": "three"}
    with pytest.raises(ValueError, match="prompt_version"):
        validate_trace(data)


def test_to_dict_round_trip():
    trace = validate_trace(VALID_TRACE)
    d = trace.to_dict()
    re_parsed = validate_trace(d)
    assert re_parsed == trace
