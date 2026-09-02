# WBS — AgentSelfEdit v0.2.0 Part 2: Scorer & Analyzer Improvements

> **Milestones covered:** M2 (Scorer Contract Cleanup) · M3 (Analyzer & Regression)
> **Source:** v0.1.0 field test issues-found.md Issues 5–7, 14–19
> **Dependency:** M2 (depends on M1) → M3 (depends on M2)
> **Issue Range:** #120–#128

---

## Milestone 2: Scorer Contract Cleanup (#120–#123)

**Objective:** Make scorer selection runtime-aware per task set, split classification benchmark into meaningful subsets, define `other` semantics explicitly, and add label-set-aware scorers. Without this, non-classification benchmarks cannot be exercised by the runtime, and classification metrics lose diagnostic power.

### M2 Design Documents

- **D1 — Scorer selection design** (`docs/design/scorer-selection-design.md`): runtime scorer selection, classification subsets (single-label, multi-label, ambiguous), label-set-aware scorers, `other` semantics definition.

### M2 Task Checklist

| # | Issue | Build (files) | Behavior + edge cases | Issue | Verify | Status |
|---|-------|---------------|----------------------|-------|--------|--------|
| 1 | Make scorer selection runtime-aware | `src/agent_self_edit/scorers.py`, `src/agent_self_edit/cli/run.py`, `src/agent_self_edit/cli/propose.py`, `field-test/scripts/run_improvement_loop.py`, task-set schema | Define scorer choice at task-set or benchmark-manifest level; `get_scorer()` instead of hardcoded `ExactMatchScorer()`; support `exact`, `contains`, `llmjudge`; classification → exact, extraction → contains/structured, generation → judge | [#120](https://github.com/deghosal-2026/agent-self-edit/issues/120) | Classification selects exact; extraction selects contains; generation selects judge | ✅ |
| 2 | Split classification benchmark | `field-test/v0.1.0/corpus/synthetic/classification.yaml`, field-test runner config | Split into single-label, multi-label, and ambiguous subsets; each subset has clear semantics and appropriate scoring; single-label stays strict exact-match; multi-label uses set-based scoring | [#121](https://github.com/deghosal-2026/agent-self-edit/issues/121) | Three subsets load independently; correct scorer per subset | ✅ |
| 3 | Define `other` semantics | Baseline prompt in runner, classification prompt templates | Add precise rules and examples for `other`: praise/greetings, general informational requests, unresolved ambiguity across categories; reduce over-classification of vague inputs | [#122](https://github.com/deghosal-2026/agent-self-edit/issues/122) | `other` classification accuracy improves; over-classification reduced | ✅ |
| 4 | Add label-set-aware scorers | `src/agent_self_edit/scorers.py` | `ExactSetScorer` — unordered set equality for multi-label; `PartialSetScorer` — credit for overlap, penalty for extra labels; `SingleLabelScorer` — strict exact matching for single-label | [#123](https://github.com/deghosal-2026/agent-self-edit/issues/123) | Each scorer returns correct results on known fixtures | ✅ |

### M2 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Scorer selection | Each benchmark type auto-selects correct scorer | Integration tests |
| Classification subsets | 3 subsets load and score independently | Subset test suite |
| Label-set scorers | ExactSet, PartialSet, SingleLabel all correct | Scorer test suite |
| Coverage | > 92% | `--cov-fail-under=92` |

### M2 Exit Gate

- [x] Scorer selection is runtime-aware, not hardcoded
- [x] Classification split into single-label, multi-label, ambiguous subsets
- [x] `other` semantics explicitly defined in prompt
- [x] Three label-set-aware scorers implemented (`SingleLabelScorer`, `ExactSetScorer`, `PartialSetScorer`)
- [x] Ruff clean, mypy strict clean, all tests pass, coverage > 92%

**Dependency:** M1. **Produces for M3+:** runtime scorer selection, classification subsets, label-set-aware scorers.

---

## Milestone 3: Analyzer & Regression Improvements (#124–#128)

**Objective:** Refactor the analyzer into a staged local-friendly pipeline, expand field-test runner into per-suite modes, strengthen hermetic bad-edit rejection, replace substring-only extraction scoring, and add a regression-sentinel benchmark. The core loop needs to be more capable and more safely measurable.

### M3 Design Documents

- **D2 — Staged analyzer design** (`docs/design/staged-analyzer-design.md`): four-stage pipeline (failure summarization, prompt target selection, minimal edit synthesis, deterministic validation), per-stage config, cost tracking.

### M3 Task Checklist

| # | Issue | Build (files) | Behavior + edge cases | Issue | Verify | Status |
|---|-------|---------------|----------------------|-------|--------|--------|
| 1 | Refactor analyzer into staged pipeline | `src/agent_self_edit/analyzer.py`, analyzer call sites | Four stages: (1) failure summarization — identify recurring patterns, (2) prompt target selection — select one exact span, (3) minimal edit synthesis — produce one minimal replacement, (4) deterministic structural validation — check before A/B; reduces cognitive load on small models | [#127](https://github.com/deghosal-2026/agent-self-edit/issues/127) | Each stage independently testable; proposals are more minimal | ✅ |
| 2 | Expand field-test runner into per-suite modes | `field-test/scripts/run_improvement_loop.py` | Support suite selection: `classification`, `extraction`, `generation`, `mixed`, `adversarial`; each suite has its own task set, scorer config, and report output | [#125](https://github.com/deghosal-2026/agent-self-edit/issues/125) | All five suite modes run independently; correct scorer per suite | ✅ |
| 3 | Strengthen hermetic bad-edit rejection tests | `tests/test_field_test.py` | Require 5/5 rejection for intentionally bad edits; split cases by failure mode (frozen section, missing old-text, excessive edit-distance, insufficient statistics, malformed/empty replacement); assert expected failing check where possible | [#124](https://github.com/deghosal-2026/agent-self-edit/issues/124) | 5/5 bad edits rejected; failure-mode-specific tests exist | ✅ |
| 4 | Add structured extraction scoring | `src/agent_self_edit/scorers.py`, extraction corpus | Normalize expected and actual outputs into structured forms; compare required fields, optional fields, and extras explicitly; equivalent formatting differences do not fail valid outputs | [#126](https://github.com/deghosal-2026/agent-self-edit/issues/126) | Extraction scoring handles formatting differences correctly | ✅ |
| 5 | Add regression-sentinel benchmark | `field-test/v0.1.0/corpus/`, field-test runner | Add a small fixed sentinel benchmark (15–25 tasks) of previously-correct tasks; run on every candidate; report sentinel regressions explicitly; catch edits that fix hard tasks but break easy ones | [#128](https://github.com/deghosal-2026/agent-self-edit/issues/128) | Every candidate evaluated against sentinel; regressions reported explicitly | ✅ |

### M3 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Staged analyzer | 4 stages produce valid proposals; small models produce more minimal edits | Analyzer test suite |
| Suite modes | All 5 suites run independently with correct scoring | Field-test runner test |
| Bad-edit rejection | 5/5 rejection required; failure-mode-specific tests | Field-test test suite |
| Extraction scoring | Structured normalization works; formatting differences accepted | Scorer test suite |
| Regression sentinel | Sentinel benchmark catches regressions; reported in output | Regression test suite |
| Coverage | > 92% | `--cov-fail-under=92` |

### M3 Exit Gate

- [ ] Analyzer refactored into staged pipeline (4 stages)
- [ ] Field-test runner supports 5 suite modes
- [ ] Bad-edit rejection tests require 5/5 with failure-mode-specific cases
- [ ] Extraction scoring uses structured normalization
- [ ] Regression-sentinel benchmark exists and runs on every candidate
- [ ] Ruff clean, mypy strict clean, all tests pass, coverage > 92%
- [ ] **Design docs authored:** D2 (staged-analyzer-design)

**Dependency:** M2. **Produces for M4+:** staged analyzer, per-suite field-test runner, regression-sentinel benchmark.