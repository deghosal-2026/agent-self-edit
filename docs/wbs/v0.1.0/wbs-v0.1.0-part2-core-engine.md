# WBS — AgentSelfEdit v0.1.0 Part 2: Core Engine

> **Milestones covered:** M3 (A/B Test Engine) · M4 (Promotion Gate)
> **PRD coverage:** [F-03](../../design/prd/05-features.md) (A/B test), [F-04](../../design/prd/05-features.md) (promotion gate), [F-11](../../design/prd/05-features.md) (near-miss logging)
> **CUJs covered:** CUJ 1 (deploy, observe, improve — A/B test), CUJ 2 (catch a bad edit — gate)
> **Dependency:** M3 (depends on M1) → M4 (depends on M3)
> **Issue Range:** #14–#30

---

## Milestone 3: A/B Test Engine (#14–#20)

**Objective:** Compare two prompt versions on the held-out task set and produce statistically valid results. The core measurement capability — everything downstream depends on this.

### M3 Design Documents

- **D3 — A/B test engine design** (`docs/design/ab-test-engine-design.md`): statistical methodology (paired design, bootstrap 10K resamples, effect size, permutation test), scorer interface (ExactMatch, Contains, LLMJudge), task runner design, cost tracking.
- **D13 — Design decisions:** DD-06 (paired design), DD-07 (bootstrap 10K resamples), DD-08 (scorer interface).

### M3 Task Checklist

| # | Task | Build (files) | Behavior + edge cases | Feature | Verify | Status |
|---|------|---------------|----------------------|---------|--------|--------|
| 1 | LLM provider interface | `src/agent_self_edit/llm/base.py`: `LLMProvider` ABC; `src/agent_self_edit/llm/openai.py`: `OpenAIProvider`; `src/agent_self_edit/llm/mock.py`: `MockProvider` | `complete(prompt, system_prompt, temperature) -> str`; `MockProvider` returns predetermined responses; `OpenAIProvider` formats messages correctly; timeout raises `ProviderError` | F-03 | mock provider in CI; real provider manually | [#14](https://github.com/deghosal-2026/agent-self-edit/issues/14) · ⬜ |
| 2 | Task runner | `src/agent_self_edit/ab_test.py`: `run_task(task, prompt, llm_provider) -> TaskResult` | `TaskResult`: output, success, latency_ms, token_count; provider error → `TaskResult(success=False)`; empty prompt returns empty output | F-03 | task runs with mock provider; latency + tokens tracked | [#15](https://github.com/deghosal-2026/agent-self-edit/issues/15) · ⬜ |
| 3 | Scorer interface | `src/agent_self_edit/scorers.py`: `Scorer` ABC, `ExactMatchScorer`, `ContainsScorer`, `LLMJudgeScorer` | `score(expected, actual) -> (bool, float)`; ExactMatch: exact string compare; Contains: substring match; LLMJudge: LLM call with scoring rubric; scorer not found → `ScorerError` | F-03 | each scorer with exact/partial/no-match fixtures | [#16](https://github.com/deghosal-2026/agent-self-edit/issues/16) · ⬜ |
| 4 | A/B test runner | `run_ab_test(prompt_a, prompt_b, task_set, llm_provider, scorer) -> ABResult` | Paired design: same task run against both prompts; collects win/loss/tie per task; per-task breakdown in results; empty task set → empty result | F-03 | paired design verified; win/loss/tie correct; per-task breakdown | [#17](https://github.com/deghosal-2026/agent-self-edit/issues/17) · ⬜ |
| 5 | Bootstrap CI | `bootstrap_ci(scores_a, scores_b, n_resamples=10000) -> BootstrapResult` | 95% CI from 2.5th/97.5th percentiles; 10K resamples; identical scores → CI = [0, 0]; single trial → wide CI; all scores identical → zero variance | F-03 | known data produces expected CI; identical scores; single trial | [#18](https://github.com/deghosal-2026/agent-self-edit/issues/18) · ⬜ |
| 6 | Permutation test | `permutation_test(scores_a, scores_b, n_permutations=1000) -> float` | p-value via label shuffling; identical distributions → p ≈ 1.0; very different → p ≈ 0.0; n_permutations configurable | F-03 | known distributions; identical; very different; small n | [#19](https://github.com/deghosal-2026/agent-self-edit/issues/19) · ⬜ |
| 7 | Effect size + cost tracking | `effect_size(scores_a, scores_b) -> float`; `ABResult.cost_usd` | Relative improvement = (new - old) / old; baseline=0 → inf handled; cost ceiling enforced; abort if ceiling exceeded | F-03 | division by zero; ceiling abort; cost accuracy | [#20](https://github.com/deghosal-2026/agent-self-edit/issues/20) · ⬜ |

### M3 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| A/B test runner | 100% correct paired design on mock data | A/B test suite |
| Bootstrap CI | 95% CI covers true mean 95% of time on synthetic data | bootstrap calibration test |
| Permutation test | p-value calibrated on synthetic null/alternative | permutation calibration test |
| Scorer accuracy | each scorer returns correct result on known fixtures | scorer test suite |
| Cost tracking | ceiling enforced, abort works | cost ceiling test |
| Coverage | > 92% | `--cov-fail-under=92` |

### M3 Out of Scope

- Promotion gate (M4), prompt registry (M5), guardrails (M6), feedback analyzer (M7)

### M3 Exit Gate

- [ ] LLM provider works with mock and real providers
- [ ] Task runner produces correct results
- [ ] All 3 scorers work correctly
- [ ] A/B test runner produces valid paired results
- [ ] Bootstrap CI is statistically valid
- [ ] Permutation test is statistically valid
- [ ] Effect size is correct; cost tracking enforced
- [ ] Ruff clean, mypy strict clean, all tests pass, coverage > 92%
- [ ] **Design docs authored:** D3 (ab-test-engine), D13 (DD-06/07/08)

**Dependency:** M1. **Produces for M4+:** `ABResult`, `TaskResult`, `Scorer` interface, `bootstrap_ci()`, `permutation_test()`, `effect_size()`, `LLMProvider` interface.

---

## Milestone 4: Promotion Gate (#21–#30)

**Objective:** The safety-critical component. Deterministic checks that must all pass before an edit is promoted. This is the hardest part of the product — prove one prompt is better than another, safely.

### M4 Design Documents

- **D4 — Promotion gate design** (`docs/design/promotion-gate-design.md`): gate architecture, 6-check fail-fast order, near-miss classification, audit log format, rollback semantics.
- **D13 — Design decisions:** DD-09 (fail-fast order), DD-10 (near-miss threshold 50%).

### M4 Task Checklist

| # | Task | Build (files) | Behavior + edge cases | Feature | Verify | Status |
|---|------|---------------|----------------------|---------|--------|--------|
| 1 | Gate result types | `src/agent_self_edit/types.py`: `GateResult`, `CheckResult` dataclasses | `GateResult.decision in {promote, reject, near_miss}`; `CheckResult`: name, passed, value, threshold, details; list is immutable | F-04 | all decisions valid; check results frozen | [#21](https://github.com/deghosal-2026/agent-self-edit/issues/21) · ⬜ |
| 2 | Gate interface | `PromotionGate.check(edit, ab_result, current_prompt, original_prompt, config) -> GateResult` | Accepts `EditProposal`, `ABResult`, two prompt strings, `Config`; returns `GateResult`; missing fields raise `GateError` | F-04 | valid/invalid inputs; partial config | [#22](https://github.com/deghosal-2026/agent-self-edit/issues/22) · ⬜ |
| 3 | Sample floor check | `check_sample_floor(ab_result, config) -> CheckResult` | Pass if n_trials >= min; fail if below; n=0 always fails; n=min passes | F-04 | below/at/above threshold; zero trials | [#23](https://github.com/deghosal-2026/agent-self-edit/issues/23) · ⬜ |
| 4 | Effect size check | `check_effect_size(ab_result, config) -> CheckResult` | Pass if relative improvement >= min; fail if below; improvement = 0 fails; very large improvement passes | F-04 | zero/positive/negative/edge | [#24](https://github.com/deghosal-2026/agent-self-edit/issues/24) · ⬜ |
| 5 | Confidence check | `check_confidence(ab_result, config) -> CheckResult` | Pass if p-value < threshold; fail if above; p=0 always passes; p=1 always fails | F-04 | p < threshold, p = threshold, p > threshold | [#25](https://github.com/deghosal-2026/agent-self-edit/issues/25) · ⬜ |
| 6 | Frozen section check | `check_frozen_sections(edit, current_prompt, frozen_sections) -> CheckResult` | Diff prompt; fail if any frozen line modified; pass if no frozen changes; frozen section missing → fail | F-06 | frozen line modified; other sections changed; empty frozen list | [#26](https://github.com/deghosal-2026/agent-self-edit/issues/26) · ⬜ |
| 7 | Edit-distance check | `check_edit_distance(edit, current_prompt, config) -> CheckResult` | Count changed lines; pass if <= max; fail if exceeded; 0 changes always passes; max=0 means no changes allowed | F-07 | 0/at/above max; max=0 | [#27](https://github.com/deghosal-2026/agent-self-edit/issues/27) · ⬜ |
| 8 | Drift check | `check_drift(edit, current_prompt, original_prompt, config) -> CheckResult` | TF-IDF cosine similarity; drift = 1 - similarity; pass if drift <= threshold; fail if above; identical prompts → drift=0; completely different → drift≈1 | F-04 | identical/different/similar; TF-IDF vs embedding | [#28](https://github.com/deghosal-2026/agent-self-edit/issues/28) · ⬜ |
| 9 | Gate orchestrator + near-miss | `check_all(edit, ab_result, current_prompt, original_prompt, config) -> GateResult` | Run 6 checks fail-fast; if >= 50% passed → near-miss; else → reject; all pass → promote; audit log appended | F-04, F-11 | all decision paths; fail-fast verified; near-miss at 50% | [#29](https://github.com/deghosal-2026/agent-self-edit/issues/29) · ⬜ |
| 10 | Gate audit log | `GateAuditLog(path)`: append-only JSONL; `log(entry)`, `query(edit_id)`, `list(limit=100)` | Append-only enforced; file rotation; concurrent writes safe; query returns correct entry; list returns ordered | F-11 | append-only test; concurrent writes; query/list | [#30](https://github.com/deghosal-2026/agent-self-edit/issues/30) · ⬜ |

### M4 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Check correctness | 100% of 6 checks pass/fail correctly on known fixtures | check test suite |
| Gate orchestrator | all 3 decisions (promote/reject/near-miss) reachable | orchestrator test suite |
| Fail-fast ordering | first failure stops execution; no further checks run | fail-fast order test |
| Near-miss classification | 50% threshold correctly classifies | near-miss boundary test |
| Audit log integrity | append-only verified; query returns correct entries | audit log test suite |
| Coverage | > 92% | `--cov-fail-under=92` |

### M4 Out of Scope

- Prompt registry (M5), guardrail module (M6), feedback analyzer (M7), CLI (M9)

### M4 Exit Gate

- [ ] All 6 checks implemented and independently tested
- [ ] Gate orchestrator runs checks in fail-fast order
- [ ] All 3 decision paths (promote/reject/near-miss) reachable
- [ ] Near-miss classification works correctly
- [ ] Audit log is append-only and queryable
- [ ] Ruff clean, mypy strict clean, all tests pass, coverage > 92%
- [ ] **Design docs authored:** D4 (promotion-gate), D13 (DD-09/10)

**Dependency:** M3. **Produces for M5+:** `GateResult`, `CheckResult`, `PromotionGate.check()`, `check_all()`, `GateAuditLog`, `frozen_section_check()`, `edit_distance_check()`, `drift_check()`.