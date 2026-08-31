"""Core datatypes common across AgentSelfEdit."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

_ISO_8601 = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})$"
)

_REQUIRED_TRACE_FIELDS = {
    "task_id": str,
    "task_input": str,
    "final_output": str,
    "expected_output": str,
    "success": bool,
    "timestamp": str,
}


@dataclass(frozen=True)
class Trace:
    """A single execution trace from the agent."""

    task_id: str
    task_input: str
    final_output: str
    expected_output: str
    success: bool
    timestamp: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    failure_reason: str | None = None
    prompt_version: int | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "task_id": self.task_id,
            "task_input": self.task_input,
            "final_output": self.final_output,
            "expected_output": self.expected_output,
            "success": self.success,
            "timestamp": self.timestamp,
        }
        if self.steps:
            data["steps"] = self.steps
        if self.failure_reason is not None:
            data["failure_reason"] = self.failure_reason
        if self.prompt_version is not None:
            data["prompt_version"] = self.prompt_version
        return data


def _validate_timestamp(value: str) -> None:
    if not _ISO_8601.match(value):
        raise ValueError(f"timestamp must be ISO 8601, got: {value!r}")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as e:
        raise ValueError(f"timestamp must be ISO 8601, got: {value!r}") from e


def validate_trace(trace: dict[str, Any]) -> Trace:
    """Validate a trace dict and build a :class:`Trace`.

    Extra fields are ignored. Required fields that are missing or of the
    wrong type raise :class:`ValueError`.
    """
    if not isinstance(trace, dict):
        raise ValueError(f"trace must be a dict, got {type(trace).__name__}")

    for field_name, expected_type in _REQUIRED_TRACE_FIELDS.items():
        if field_name not in trace:
            raise ValueError(f"missing required field: {field_name}")
        value = trace[field_name]
        # bool is a subclass of int; validate explicitly
        if expected_type is bool:
            if not isinstance(value, bool):
                raise ValueError(
                    f"field '{field_name}' must be a bool, got {type(value).__name__}"
                )
        elif not isinstance(value, expected_type):
            raise ValueError(
                f"field '{field_name}' must be a {expected_type.__name__}, "
                f"got {type(value).__name__}"
            )

    _validate_timestamp(trace["timestamp"])

    steps = trace.get("steps")
    if steps is None:
        steps = []
    elif not isinstance(steps, list):
        raise ValueError(f"field 'steps' must be a list, got {type(steps).__name__}")

    failure_reason = trace.get("failure_reason")
    if failure_reason is not None and not isinstance(failure_reason, str):
        raise ValueError(
            "field 'failure_reason' must be a string, "
            f"got {type(failure_reason).__name__}"
        )

    prompt_version = trace.get("prompt_version")
    if prompt_version is not None and not isinstance(prompt_version, int):
        raise ValueError(
            "field 'prompt_version' must be an int, "
            f"got {type(prompt_version).__name__}"
        )

    return Trace(
        task_id=trace["task_id"],
        task_input=trace["task_input"],
        final_output=trace["final_output"],
        expected_output=trace["expected_output"],
        success=trace["success"],
        timestamp=trace["timestamp"],
        steps=[dict(s) if isinstance(s, dict) else s for s in steps],
        failure_reason=failure_reason,
        prompt_version=prompt_version,
    )


def utc_now_iso() -> str:
    """Current UTC time as an ISO 8601 string (UTC, second precision)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class EditProposal:
    """A candidate prompt edit proposed by the feedback analyzer."""

    section: str
    old_text: str
    new_text: str
    hypothesis: str
    expected_improvement: str
    evidence_traces: list[str] = field(default_factory=list)
    edit_id: str | None = None


@dataclass(frozen=True)
class CheckResult:
    """Outcome of a single promotion-gate check."""

    name: str
    passed: bool
    value: float
    threshold: float
    details: str


@dataclass(frozen=True)
class GateResult:
    """Overall decision of the promotion gate."""

    decision: Literal["promote", "reject", "near_miss"]
    checks: tuple[CheckResult, ...] = field(default_factory=tuple)
    edit_id: str | None = None
    reason: str = ""
