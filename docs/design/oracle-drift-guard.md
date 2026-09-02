# Oracle Drift Guard: Shared-Oracle Problem and Isolation Strategy

> The problem of the oracle (scorer / judge) being shared between the optimizer (analyzer) and the evaluator (A/B test + gate), and how to detect and contain acceptance-case drift.

## 1. The Shared-Oracle Problem

The self-improvement loop uses scoring/ judging in two roles:
- **Evaluator role:** The A/B test engine scores task outputs against expected outputs to determine which prompt is better. This is the "ground truth" that gates promotions.
- **Analyzer role:** The analyzer examines failed traces to propose prompt edits. Implicitly, it learns the scoring function's behavior — it knows what kinds of outputs will score well.

When the same scoring function (oracle) is shared between both roles, a subtle failure mode arises: **the optimizer can learn to game the evaluator**. If the analyzer discovers a pattern that the scorer considers correct but a human would not, it can optimize for that pattern, producing prompts that score well on the evaluator's oracle but fail in real use.

### 1.1 Concrete Example

Consider an `ExactMatchScorer` for classification. The evaluator checks `expected_output == llm_output`. The analyzer sees failed traces where the model said "billing" but the expected was "technical". It could learn: "the scorer only checks exact string match on category names." An edit that works around this might teach the model to output "technical" for billing-related inputs — the scorer passes, but the classification is wrong in production.

## 2. Severity by Scorer Type

| Scorer | Gaming risk | Explanation |
|--------|-------------|-------------|
| `ExactMatchScorer` | Low | Exact string match is unambiguous. The expected output is ground truth. Gaming would require changing the expected output itself. |
| `ExactSetScorer` | Low | Same as ExactMatch but for sets. Order-independent but still ground-truth-bound. |
| `ContainsScorer` | Medium | A substring check can be gamed. The model could include the expected substring anywhere in its output, even while getting the task wrong. |
| `LLMJudgeScorer` | High | An LLM judge is itself a model. The analyzer could learn the judge's blind spots and optimize for "what the judge likes" rather than "what is correct." This is the most dangerous case. |
| `StructuredExtractionScorer` | Medium-High | Nested field matching with normalization. The analyzer could learn normalization patterns and produce technically parseable but semantically wrong outputs. |

## 3. Proposed Isolation Strategy: Acceptance Case Separation

The core defense is to ensure that **what the gate evaluates** (acceptance cases) is structurally separated from **what the analyzer learns from** (training traces). This prevents the analyzer from fitting its edits to the evaluator's specific scoring patterns.

### 3.1 Three-Case Architecture

```
Training set (analyzer input)     — traces where baseline fails
                                 — analyzed to propose edits
                                 — scorer-visible to analyzer

A/B task set (evaluator input)    — held-out tasks, never seen by analyzer
                                 — scored with same scorer as training
                                 — gates promotion decisions

Acceptance case set (oracle check) — tasks where scorer correctness is verified offline
                                   — scored by a DIFFERENT oracle (human, separate LLM judge)
                                   — used to detect drift between evaluator and real correctness
```

The acceptance case set is **not** used in the A/B test or gate. It is a separate verification step run after each promotion to answer: "Did the edit actually improve task performance, or did it just learn to score well on the evaluator's oracle?"

### 3.2 Acceptance Case Requirements

- **At least 5-10 tasks per domain** (classification, extraction, generation)
- **Scored by a different oracle** — ideally human-labeled, or an LLM judge with a different rubric/prompt, or a different model
- **Not accessible to the analyzer** — stored separately, never passed to `analyze_batch()`
- **Run after every promotion** — if acceptance accuracy declines, the promotion is suspect

### 3.3 When to Act

If acceptance accuracy declines while A/B accuracy improves, the system has likely drifted into scorer gaming territory. Actions:
1. Flag the promotion version in the registry (metadata: `acceptance_drift: true`)
2. Log detailed comparison: A/B accuracy vs acceptance accuracy, per-task deltas, scorer type analysis
3. If acceptance accuracy drops > 10% relative, trigger manual review before the next iteration

## 4. Gate Check for Oracle Drift Detection

A deterministic gate check (check 7, after promotion) that compares A/B accuracy against acceptance accuracy:

```
Check: oracle_drift
Pass: |ab_accuracy - acceptance_accuracy| <= oracle_tolerance (default 0.15)
Fail: |ab_accuracy - acceptance_accuracy| > oracle_tolerance
```

This check is not part of the promotion gate itself (which must remain fast and LLM-free). It runs **asynchronously after promotion** and logs to the audit trail.

### 4.1 Tolerance Rationale

A small gap between A/B accuracy and acceptance accuracy is expected (different task sets, different scoring). The tolerance of 0.15 means:
- If A/B = 80% and acceptance = 70%, gap = 10% → pass
- If A/B = 80% and acceptance = 55%, gap = 25% → fail → drift flagged

The tolerance is configurable via `gate.oracle_tolerance` in the config file.

### 4.2 Audit Log Entry

```json
{
  "timestamp": "2026-09-15T10:00:00Z",
  "edit_id": "edit-0042",
  "check": "oracle_drift",
  "ab_accuracy": 0.80,
  "acceptance_accuracy": 0.55,
  "gap": 0.25,
  "tolerance": 0.15,
  "passed": false,
  "scorer_type": "LLMJudgeScorer",
  "action": "flagged_for_review"
}
```

## 5. Implementation Plan

| Step | What | When |
|------|------|------|
| 1 | Define acceptance case set format (YAML, same structure as task sets, stored under `field-test/acceptance/`) | v0.2.0 |
| 2 | Add `oracle_tolerance` to `GateConfig` dataclass | v0.2.0 |
| 3 | Wire acceptance case scoring into `Registry.create()` metadata | v0.2.0 |
| 4 | Implement `check_oracle_drift()` in gate module | v0.2.0 |
| 5 | Add acceptance case CLI command: `agent-self-edit verify-acceptance` | v0.2.0+ |
| 6 | Document acceptance case creation process for field test operators | v0.2.0 |

### 5.1 Acceptance Case File Format

```yaml
# field-test/acceptance/classification-acceptance.yaml
# Tasks scored by a DIFFERENT oracle than the A/B test evaluator
- id: "accept-classify-001"
  input: "My account shows a charge I don't recognize."
  expected_output: "security"
  oracle: "human"  # or "llm_judge_v2", or model name
  notes: "Human-labeled: this is a security concern, not billing"
- id: "accept-classify-002"
  input: "The new dashboard is slow after the update."
  expected_output: "technical"
  oracle: "human"
```

### 5.2 Promotion Metadata

Extended `v{N}.meta.json` to include oracle drift status:

```json
{
  "version": 5,
  "parent_version": 4,
  "prompt_hash": "sha256:...",
  "edit_id": "edit-0042",
  "ab_accuracy": 0.80,
  "acceptance_accuracy": 0.55,
  "oracle_drift": {
    "gap": 0.25,
    "tolerance": 0.15,
    "passed": false,
    "flagged": true
  }
}
```

## 6. Design Decisions

### DD-Oracle-01: Post-promotion, not pre-promotion
The oracle drift check runs **after** promotion, not as a pre-promotion gate. Rationale: the acceptance case set is small (5-10 tasks) and requires a different oracle, which may involve human review or a separate LLM call. Making it blocking would slow the loop. Post-promotion flagging preserves fast iteration while catching drift retroactively.

### DD-Oracle-02: Acceptance cases are hardcoded, not learned
Acceptance cases should be static across iterations. If they change, the drift comparison is invalid. New acceptance cases can be added in version increments, not per-iteration.

### DD-Oracle-03: Different oracle does NOT mean better oracle
The acceptance oracle is not necessarily more accurate than the evaluator's oracle. It is **different** — structurally separated so the analyzer cannot learn its patterns. If both oracles agree, confidence is high. If they disagree, further investigation is needed.