# Promotion Gate Design

> Gate architecture, 6-check fail-fast order, near-miss classification, audit log format, and rollback semantics for AgentSelfEdit v0.1.0.

## 1. Architecture

The promotion gate is the **safety-critical component**. It is deterministic code — never LLM-judged. Every check is verifiable, testable, and non-negotiable. An edit may only be promoted to the prompt baseline when **all six checks pass**.

```
EditProposal + ABResult + current_prompt + original_prompt
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │  PromotionGate.check_all()           │
        │  1. Sample floor    (statistical)    │
        │  2. Effect size     (statistical)    │
        │  3. Confidence      (statistical)    │
        │  4. Frozen sections (guardrail)      │
        │  5. Edit distance   (guardrail)      │
        │  6. Drift           (guardrail)      │
        └───────────────────────────────────────┘
                        │  fail-fast: first failure stops
                        ▼
              ┌─────┬────────┬───────┐
              ▼     ▼        ▼       ▼
          promote  near_miss  reject  (audit log written)
```

## 2. The 6 Checks (Fail-Fast Order)

| # | Check | Function | Pass condition | Source |
|---|-------|----------|----------------|--------|
| 1 | Sample floor | `check_sample_floor` | `n_trials >= sample_floor` | config `tasks.sample_floor` (default 10) |
| 2 | Effect size | `check_effect_size` | relative improvement `>= min_effect_size` | config `ab_test.min_effect_size` (default 0.05) |
| 3 | Confidence | `check_confidence` | `p_value < confidence_level` | config `ab_test.confidence_level` (default 0.95) |
| 4 | Frozen sections | `check_frozen_sections` | no changed line inside a frozen section | frozen annotations in prompt |
| 5 | Edit distance | `check_edit_distance` | changed lines `<= max_edit_distance` | config `gate.max_edit_distance` (default 20) |
| 6 | Drift | `check_drift` | `drift <= drift_threshold` | config `gate.drift_threshold` (default 0.3) |

**Why fail-fast:** saving compute, giving a single clear rejection reason, and simplifying near-miss classification. The first failed check stops the chain — checks are cheap to run, so a wasted compute concern is minimal, but the signal clarity matters.

## 3. Decision Logic

- **All 6 pass** → `promote`
- **Any check fails after fewer than `near_miss_threshold` fraction passed** → `reject`
- **A check fails but >= 50% (default) of checks passed** → `near_miss` — logged for human review

The `near_miss_threshold` default is 0.5 (3 of 6 checks passed): a gate that mostly passed is not silently buried — it is flagged for review so the analyzer can improve rather than repeat the same rejected edit.

## 4. Data Model

```python
@dataclass(frozen=True)
class CheckResult:
    name: str        # e.g. "sample_floor"
    passed: bool
    value: float     # observed value (e.g. 8 trials, 0.02 p-value)
    threshold: float # configured threshold
    details: str     # human-readable explanation

@dataclass(frozen=True)
class GateResult:
    decision: Literal["promote", "reject", "near_miss"]
    checks: tuple[CheckResult, ...]   # immutable
    edit_id: str | None
    reason: str
```

## 5. Audit Log

Append-only JSONL at `config.project.registry_path / audit.log`:

- `log(entry)` — appends a JSON line; refuses to modify existing lines (append-only enforced)
- `query(edit_id)` — returns all entries for one edit
- `list(limit=100)` — most recent entries, ordered

Each entry:

```json
{
  "timestamp": "2026-09-02T10:00:00Z",
  "edit_id": "edit-0001",
  "decision": "reject",
  "check": "sample_floor",
  "value": 8,
  "threshold": 10,
  "details": "n_trials (8) below sample floor (10)"
}
```

## 6. Rollback Semantics

Rollback is not the gate's concern — it is owned by the prompt registry (M5). The gate's job is only to decide pass/fail. On promotion, the registry records the `GateResult` in the version metadata. On rollback, the registry copies a prior version forward; the audit log records the event.

## 7. Design Decisions

See DD-09 (fail-fast order) and DD-10 (near-miss threshold 50%) in `design-decisions.md`.