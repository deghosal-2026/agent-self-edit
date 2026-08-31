"""Promotion gate: deterministic checks, orchestrator, and audit log."""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .ab_test import ABResult
from .config import Config
from .guardrails import compute_drift_tfidf, compute_edit_distance, parse_frozen_sections
from .types import CheckResult, EditProposal, GateResult, utc_now_iso

StdList = list

logger = logging.getLogger("agent_self_edit.gate")

_CHECK_ORDER = [
    "sample_floor",
    "effect_size",
    "confidence",
    "frozen_sections",
    "edit_distance",
    "drift",
]


class GateError(Exception):
    """Raised when the promotion gate receives invalid inputs."""


# ---------------------------------------------------------------------------
# Stat checks (#24, #25, #26)
# ---------------------------------------------------------------------------


def check_sample_floor(ab_result: ABResult | None, config: Config) -> CheckResult:
    threshold = float(config.tasks.sample_floor)
    n = 0 if ab_result is None else ab_result.n_trials
    passed = n >= threshold
    return CheckResult(
        name="sample_floor",
        passed=passed,
        value=float(n),
        threshold=threshold,
        details=(
            f"n_trials ({n}) {'>= sample floor' if passed else '< sample floor'} "
            f"({threshold:g})"
        ),
    )


def check_effect_size(ab_result: ABResult | None, config: Config) -> CheckResult:
    threshold = float(config.ab_test.min_effect_size)
    if ab_result is None:
        return CheckResult(
            name="effect_size",
            passed=False,
            value=0.0,
            threshold=threshold,
            details="no A/B result; effect size 0.0",
        )
    effect = ab_result.effect_size
    # inf means baseline was 0 and improvement > 0 -> pass
    passed = effect >= threshold if effect != float("inf") else True
    return CheckResult(
        name="effect_size",
        passed=passed,
        value=float(effect),
        threshold=threshold,
        details=(
            f"effect size ({effect*100:.1f}%) {'>= min' if passed else '< min'} "
            f"({threshold*100:.1f}%)"
        ),
    )


def check_confidence(ab_result: ABResult | None, config: Config) -> CheckResult:
    threshold = float(config.ab_test.confidence_level)
    if ab_result is None:
        return CheckResult(
            name="confidence",
            passed=False,
            value=1.0,
            threshold=threshold,
            details="no A/B result; p-value 1.0",
        )
    p = ab_result.p_value
    passed = p < threshold
    return CheckResult(
        name="confidence",
        passed=passed,
        value=float(p),
        threshold=threshold,
        details=(
            f"p-value ({p:.4f}) {'< confidence level' if passed else '>= confidence level'} "
            f"({threshold:.4f})"
        ),
    )


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Frozen sections + edit distance (#27, #28) — primitives live in guardrails module
# ---------------------------------------------------------------------------


def check_frozen_sections(
    edit: EditProposal | None,
    current_prompt: str,
    frozen_sections: list[str] | None = None,
) -> CheckResult:
    """Fail if the edit modifies any frozen section in ``current_prompt``.

    The proposal replaces ``old_text`` with ``new_text``; we verify that every
    frozen section's text is preserved after that replacement.
    """
    sections = parse_frozen_sections(current_prompt)
    frozen_names: set[str] = set()
    for sec in sections:
        if sec["name"] is not None:
            frozen_names.add(sec["name"])

    if frozen_sections is not None:
        requested = set(frozen_sections)
        missing = requested - frozen_names
        if missing:
            return CheckResult(
                name="frozen_sections",
                passed=False,
                value=float(len(missing)),
                threshold=0.0,
                details=f"frozen sections missing from prompt: {sorted(missing)}",
            )

    if edit is None:
        return CheckResult(
            name="frozen_sections",
            passed=False,
            value=0.0,
            threshold=0.0,
            details="no edit proposal; cannot verify frozen sections",
        )

    # Build the proposed new prompt by applying the old_text -> new_text replacement.
    if not edit.old_text or edit.old_text not in current_prompt:
        return CheckResult(
            name="frozen_sections",
            passed=False,
            value=0.0,
            threshold=0.0,
            details="edit.old_text not found in current_prompt",
        )
    proposed = current_prompt.replace(edit.old_text, edit.new_text)

    violations = 0
    violated: list[str] = []
    for sec in sections:
        if sec["name"] is None:
            continue
        if frozen_sections is not None and sec["name"] not in set(frozen_sections):
            continue
        block = "\n".join(sec["lines"]) if sec["lines"] else ""
        if block and block not in proposed:
            violations += 1
            violated.append(sec["name"] or "core")

    passed = violations == 0
    return CheckResult(
        name="frozen_sections",
        passed=passed,
        value=float(violations),
        threshold=0.0,
        details=(
            "no frozen lines modified"
            if passed
            else f"frozen sections modified: {violated}"
        ),
    )


def check_edit_distance(
    edit: EditProposal | None,
    current_prompt: str,
    config: Config | None = None,
    max_distance: int | None = None,
) -> CheckResult:
    threshold = float(
        max_distance
        if max_distance is not None
        else (config.gate.max_edit_distance if config else 20)
    )
    if edit is None:
        return CheckResult(
            name="edit_distance",
            passed=False,
            value=float("inf"),
            threshold=threshold,
            details="no edit proposal; cannot measure edit distance",
        )
    changed = compute_edit_distance(current_prompt, edit.new_text)
    passed = changed <= threshold
    return CheckResult(
        name="edit_distance",
        passed=passed,
        value=float(changed),
        threshold=threshold,
        details=f"{changed} changed lines {'<=' if passed else '>'} max ({threshold:g})",
    )


# ---------------------------------------------------------------------------
# Drift check (#29) — primitive lives in guardrails module
# ---------------------------------------------------------------------------


def check_drift(
    edit: EditProposal | None,
    current_prompt: str,
    original_prompt: str,
    config: Config | None = None,
    drift_threshold: float | None = None,
) -> CheckResult:
    threshold = (
        drift_threshold
        if drift_threshold is not None
        else (config.gate.drift_threshold if config else 0.3)
    )
    prompt_b = edit.new_text if edit else current_prompt
    drift = compute_drift_tfidf(original_prompt, prompt_b)
    passed = drift <= threshold
    return CheckResult(
        name="drift",
        passed=passed,
        value=float(drift),
        threshold=threshold,
        details=f"drift ({drift:.3f}) {'<=' if passed else '>'} threshold ({threshold:.3f})",
    )


# ---------------------------------------------------------------------------
# Orchestrator (#30)
# ---------------------------------------------------------------------------


def _run_individual_checks(
    edit: EditProposal | None,
    ab_result: ABResult | None,
    current_prompt: str,
    original_prompt: str,
    config: Config,
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    for name in _CHECK_ORDER:
        if name == "sample_floor":
            checks.append(check_sample_floor(ab_result, config))
        elif name == "effect_size":
            checks.append(check_effect_size(ab_result, config))
        elif name == "confidence":
            checks.append(check_confidence(ab_result, config))
        elif name == "frozen_sections":
            checks.append(check_frozen_sections(edit, current_prompt))
        elif name == "edit_distance":
            checks.append(check_edit_distance(edit, current_prompt, config))
        elif name == "drift":
            checks.append(check_drift(edit, current_prompt, original_prompt, config))
    return checks


def check_all(
    edit: EditProposal | None,
    ab_result: ABResult | None,
    current_prompt: str,
    original_prompt: str,
    config: Config,
) -> GateResult:
    """Run the 6 checks in fail-fast order and classify promote/reject/near-miss."""
    if not current_prompt.strip() or not original_prompt.strip():
        raise GateError("current_prompt and original_prompt are required")

    checks: list[CheckResult] = []
    passed_count = 0
    for name in _CHECK_ORDER:
        if name == "sample_floor":
            result = check_sample_floor(ab_result, config)
        elif name == "effect_size":
            result = check_effect_size(ab_result, config)
        elif name == "confidence":
            result = check_confidence(ab_result, config)
        elif name == "frozen_sections":
            result = check_frozen_sections(edit, current_prompt)
        elif name == "edit_distance":
            result = check_edit_distance(edit, current_prompt, config)
        else:  # drift
            result = check_drift(edit, current_prompt, original_prompt, config)

        checks.append(result)
        if result.passed:
            passed_count += 1
        else:
            break  # fail-fast

    total = len(_CHECK_ORDER)
    near_miss_threshold = float(config.gate.near_miss_threshold)

    if passed_count == total:
        decision: Literal["promote", "reject", "near_miss"] = "promote"
        reason = "all checks passed"
    else:
        ratio = passed_count / total
        if ratio >= near_miss_threshold:
            decision = "near_miss"
            reason = f"{passed_count}/{total} checks passed; near-miss (>= {ratio:.0%})"
        else:
            decision = "reject"
            reason = (
                f"{passed_count}/{total} checks passed; "
                f"below near-miss threshold ({near_miss_threshold:.0%})"
            )

    return GateResult(
        decision=decision,
        checks=tuple(checks),
        edit_id=edit.edit_id if edit else None,
        reason=reason,
    )


class PromotionGate:
    """Facade combining the orchestrator and the audit log."""

    def __init__(self, audit_path: str | Path | None = None) -> None:
        self.audit = GateAuditLog(audit_path) if audit_path is not None else None

    def check(
        self,
        edit: EditProposal | None,
        ab_result: ABResult | None,
        current_prompt: str,
        original_prompt: str,
        config: Config,
    ) -> GateResult:
        result = check_all(edit, ab_result, current_prompt, original_prompt, config)
        if self.audit is not None:
            entry = {
                "timestamp": utc_now_iso(),
                "edit_id": result.edit_id,
                "decision": result.decision,
                "reason": result.reason,
                "checks": [
                    {"name": c.name, "passed": c.passed, "value": c.value, "threshold": c.threshold}
                    for c in result.checks
                ],
            }
            self.audit.log(entry)
        return result


# ---------------------------------------------------------------------------
# Audit log (#31)
# ---------------------------------------------------------------------------


@dataclass
class GateAuditLog:
    path: str | Path
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _path: Path = field(default_factory=Path, init=False)

    def __post_init__(self) -> None:
        self._path = Path(self.path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, entry: dict[str, Any]) -> None:
        line = json.dumps(entry, sort_keys=True) + "\n"
        with self._lock:
            with open(self._path, "a") as f:
                f.write(line)

    def query(self, edit_id: str) -> StdList[dict[str, Any]]:
        matches = []
        for entry in self._read_lines():
            if entry.get("edit_id") == edit_id:
                matches.append(entry)
        return matches

    def list(self, limit: int = 100) -> StdList[dict[str, Any]]:
        entries = self._read_lines()
        return entries[-limit:] if limit else entries

    def _read_lines(self) -> StdList[dict[str, Any]]:
        if not self._path.exists():
            return []
        parsed: StdList[dict[str, Any]] = []
        with self._lock:
            with open(self._path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        parsed.append(json.loads(line))
                    except json.JSONDecodeError:
                        logger.warning("Skipping malformed audit line in %s", self._path)
        return parsed
