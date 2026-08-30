# WBS — AgentSelfEdit v0.1.0 Part 2: Core Engine

> Part of the v0.1.0 release. See [index](wbs-v0.1.0-index.md) for milestone overview.
>
> **Milestones:** M3 (A/B Test Engine) · M4 (Promotion Gate)
> **Dependency:** M3 → M4
> **Issue Range:** #14–#30

## M3 — A/B Test Engine (#14–#20)

**Goal:** Compare two prompt versions on the held-out task set and produce statistically valid results.

### Design

| Task | Description | Deliverable |
|---|---|---|
| D3 | Design A/B test engine | `docs/design/ab-test-engine-design.md` — statistical methodology (paired design, bootstrap 10K resamples, effect size, permutation test), scorer interface (ExactMatch, Contains, LLMJudge), task runner design, cost tracking |

### Build

| Task | Description | Deliverable |
|---|---|---|
| M3.1 | LLM provider interface | `src/agent_self_edit/llm/base.py` — `LLMProvider` ABC. `src/agent_self_edit/llm/openai.py` — `OpenAIProvider` (OpenAI-compatible transport). `complete(prompt, system_prompt, temperature) -> str` |
| M3.2 | Task runner | `run_task(task, prompt, llm_provider) -> TaskResult` — runs a task against a prompt version. Returns: output, success, latency_ms, token_count |
| M3.3 | Scorer interface | `src/agent_self_edit/scorers.py` — `Scorer` ABC. `ExactMatchScorer`, `ContainsScorer`, `LLMJudgeScorer`. Each: `score(expected, actual) -> (bool, float)` |
| M3.4 | A/B test runner | `run_ab_test(prompt_a, prompt_b, task_set, llm_provider, scorer) -> ABResult` — run N trials, each trial runs same task against both prompts (paired design). Collect win/loss/tie. |
| M3.5 | Bootstrap CI | `bootstrap_ci(scores_a, scores_b, n_resamples=10000) -> BootstrapResult` — compute 95% CI via bootstrap. |
| M3.6 | Permutation test | `permutation_test(scores_a, scores_b, n_permutations=1000) -> float` — p-value via label shuffling. |
| M3.7 | Effect size | `effect_size(scores_a, scores_b) -> float` — relative improvement = (mean_b - mean_a) / mean_a. |
| M3.8 | A/B results object | `ABResult` dataclass: winner, win_rate, ci_low, ci_high, effect_size, p_value, n_trials, per_task: list[TaskResult]. |
| M3.9 | Cost tracking | Track token_count and estimated_cost per A/B test run. Configurable cost ceiling. Abort if ceiling exceeded. |

### Tests

| Task | Description | Files |
|---|---|---|
| T3.1 | Test LLM provider | `tests/test_llm.py` — mock provider returns expected responses, OpenAI provider formats messages correctly, error handling on API failures |
| T3.2 | Test task runner | `tests/test_ab_test.py` — task returns correct output, latency and tokens tracked, provider errors are caught |
| T3.3 | Test scorers | `tests/test_scorers.py` — ExactMatch, Contains, LLMJudge each tested with exact matches, partial matches, no matches, edge cases |
| T3.4 | Test A/B test runner | `tests/test_ab_test.py` — runs with mock provider, paired design verified, win/loss/tie correctly computed, per-task breakdown accurate |
| T3.5 | Test bootstrap CI | `tests/test_ab_test.py` — bootstrap on known data (should produce expected CI), edge cases (all same scores, extreme values, small n) |
| T3.6 | Test permutation test | `tests/test_ab_test.py` — permutation on known data (should produce expected p-value), edge cases (identical distributions, small n) |
| T3.7 | Test effect size | `tests/test_ab_test.py` — zero improvement, positive improvement, negative improvement, division by zero (baseline = 0) |
| T3.8 | Test cost tracking | `tests/test_ab_test.py` — cost ceiling enforced, abort when exceeded, token count accuracy |

### M3 Exit Gate

- [ ] Design docs reviewed and committed
- [ ] LLM provider works with mock and real providers
- [ ] Task runner produces correct results
- [ ] All 3 scorers work correctly
- [ ] A/B test runner produces valid paired results
- [ ] Bootstrap CI is statistically valid
- [ ] Permutation test is statistically valid
- [ ] Effect size is correct
- [ ] Cost tracking works
- [ ] Ruff clean, mypy strict clean
- [ ] All tests pass: `pytest` → 0 failures
- [ ] Coverage > 92%: `pytest --cov=agent_self_edit --cov-fail-under=92`

---

## M4 — Promotion Gate (#21–#30)

**Goal:** The safety-critical component. Deterministic checks that must all pass before an edit is promoted.

### Design

| Task | Description | Deliverable |
|---|---|---|
| D4 | Design promotion gate | `docs/design/promotion-gate-design.md` — gate architecture, 6-check fail-fast order, near-miss classification, audit log format, rollback semantics |

### Build

| Task | Description | Deliverable |
|---|---|---|
| M4.1 | Gate interface | `PromotionGate.check(edit, ab_result, current_prompt, original_prompt) -> GateResult` |
| M4.2 | Gate result | `GateResult` dataclass: decision (promote|reject|near_miss), checks: list[CheckResult], reasoning: str |
| M4.3 | Check result | `CheckResult` dataclass: name, passed (bool), value (float), threshold (float), details (str) |
| M4.4 | Sample floor check | Verify n_trials >= configured minimum. Fail if below. |
| M4.5 | Effect size check | Verify relative improvement >= configured minimum. Fail if below. |
| M4.6 | Confidence check | Verify p-value < configured threshold. Fail if above. |
| M4.7 | Frozen section check | Diff the prompt. Verify no lines changed in frozen sections. Fail if any frozen line modified. |
| M4.8 | Edit-distance check | Count changed lines. Verify <= configured max. Fail if exceeded. |
| M4.9 | Drift check | Compute semantic similarity (TF-IDF cosine) between new prompt and original. Verify drift <= threshold. Fail if exceeded. |
| M4.10 | Near-miss classifier | If rejected but >= 50% of checks passed, classify as near-miss. |
| M4.11 | Gate audit log | Append-only JSONL log. Each entry: timestamp, edit_id, decision, all check results, edit_summary. |
| M4.12 | Gate orchestrator | `check_all(edit, ab_result, current_prompt, original_prompt, config)` — runs all 6 checks in fail-fast order, returns GateResult. |

### Tests

| Task | Description | Files |
|---|---|---|
| T4.1 | Test gate result | `tests/test_gate.py` — GateResult created correctly, check results list is immutable, decision is validated |
| T4.2 | Test sample floor check | `tests/test_gate.py` — pass (n >= min), fail (n < min), edge case (n = min) |
| T4.3 | Test effect size check | `tests/test_gate.py` — pass (improvement >= min), fail (improvement < min), edge case (improvement = min) |
| T4.4 | Test confidence check | `tests/test_gate.py` — pass (p < threshold), fail (p >= threshold), edge case (p = threshold) |
| T4.5 | Test frozen section check | `tests/test_gate.py` — pass (no frozen changes), fail (frozen line modified), pass (frozen section unchanged, other sections changed) |
| T4.6 | Test edit-distance check | `tests/test_gate.py` — pass (changes <= max), fail (changes > max), edge case (changes = max) |
| T4.7 | Test drift check | `tests/test_gate.py` — pass (drift <= threshold), fail (drift > threshold), identical prompts (drift = 0), completely different prompts (drift ≈ 1) |
| T4.8 | Test near-miss classifier | `tests/test_gate.py` — near-miss when 3-4 checks pass, reject when 0-2 checks pass, promote when all pass |
| T4.9 | Test gate audit log | `tests/test_gate.py` — log entry format, append-only, queryable by edit_id, timestamp ordering |
| T4.10 | Test gate orchestrator | `tests/test_gate.py` — all 6 checks run in order, fail-fast (first failure stops), all possible decision paths tested |
| T4.11 | Test gate edge cases | `tests/test_gate.py` — empty config, missing ab_result, missing prompts, extreme values, concurrent checks |

### M4 Exit Gate

- [ ] Design docs reviewed and committed
- [ ] All 6 checks implemented and independently tested
- [ ] Gate orchestrator runs checks in fail-fast order
- [ ] Near-miss classification works correctly
- [ ] Audit log is append-only and queryable
- [ ] Ruff clean, mypy strict clean
- [ ] All tests pass: `pytest` → 0 failures
- [ ] Coverage > 92%: `pytest --cov=agent_self_edit --cov-fail-under=92`