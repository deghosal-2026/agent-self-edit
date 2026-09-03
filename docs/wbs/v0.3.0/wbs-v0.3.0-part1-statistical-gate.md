# WBS — AgentSelfEdit v0.3.0 Part 1: Statistical Engine & Gate

> **Milestones covered:** M1 (A/B Statistical Engine) · M2 (Promotion Gate & Near-Miss Logic)
> **Source:** Open bug backlog #206–#301 — statistical correctness audit + gate logic audit (field-test: 0% improvement blocked by A/B mis-evaluation)
> **Dependency:** M1 (no dep) → M2 (depends on M1 corrected stats)
> **Issue Range:** #267, #234, #244, #257–#278, #248, #277, #294 (M1: 8 issues) + #249, #251, #258, #282, #289, #298, #300, #211 (M2: 8 issues) — [M1 milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/23) · [M2 milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/24)

---

## Milestone 1: A/B Statistical Engine (8 issues)

**Objective:** Fix deterministically seeded A/B statistics, one-tailed permutation, float tie detection, and `run_task` message format. These bugs mean CI is identical regardless of data, regression path is dead code, near-identical scores become `inconclusive`, and real A/B traffic is mis-evaluated. Discovered via code audit and field-test winner='a' never exercised.

### M1 Design Documents

- **D1 — A/B statistical correction design** (`docs/design/ab-test-statistical-fix-design.md`): seeded CI calibration, two-tailed permutation, tie epsilon, `run_task` system→user format, `seed=None` production vs `seed=0` tests.

### M1 Task Checklist

| # | Issue | Build (files) | Behavior + edge cases | Issue | Verify | Status |
|---|-------|---------------|----------------------|-------|--------|--------|
| 1 | Fix `bootstrap_ci` fixed seed | `src/agent_self_edit/ab_test.py` — `bootstrap_ci(scores_a, scores_b, n_resamples, ci_level, seed=None)`; `rng = random.Random(seed)`; production `seed=None` → fresh, tests pass `seed=0` | `[0.5]*20 vs [0.5]*20` CI narrow around 0; `[0.3]*20 vs [0.8]*20` CI positive; different deltas produce different CIs | [#294](https://github.com/deghosal-2026/agent-self-edit/issues/294) | `bootstrap_ci` sensitive to data; `seed=0` only in tests | ⬜ |
| 2 | Fix `permutation_test` one-tailed → two-tailed | `src/agent_self_edit/ab_test.py` — `permutation_test(scores_a, scores_b, n_permutations, seed=None)`; count `abs(shuffled) >= abs(observed)`; permute labels | `p_pos <0.05` when B beats A; `p_neg <0.05` when A beats B (winner='a' path live); previously `winner='a'` dead code | [#278](https://github.com/deghosal-2026/agent-self-edit/issues/278), [#257](https://github.com/deghosal-2026/agent-self-edit/issues/257) | winner='a' path exercised; two-tailed p-value correct | ⬜ |
| 3 | Fix tie detection `==0.0` on floats | `src/agent_self_edit/ab_test.py` — replace `delta == 0.0` with `abs(delta) < eps` (or `math.isclose`); epsilon e.g. `1e-9` | `0.001` diff not tied; `1e-12` diff tied; `inconclusive` only for near-zero | [#244](https://github.com/deghosal-2026/agent-self-edit/issues/244) | Near-identical results not misclassified | ⬜ |
| 4 | Add bootstrap CI calibration tests | `tests/test_ab_test.py` — per `ab-test-engine-design` spec: coverage calibration, CI width vs n, false-positive rate at `p<0.05` | `10_000` resamples stable; 95% CI covers true ~95% in synthetic; documented calibration | [#234](https://github.com/deghosal-2026/agent-self-edit/issues/234) | Calibration tests pass per design spec | ⬜ |
| 5 | Fix `run_task` system prompt as user message | `src/agent_self_edit/ab_test.py`, `src/agent_self_edit/llm/base.py`, `src/agent_self_edit/llm/openai.py` — send system prompt as `system` role, task input as `user` role; mock provider matches | A/B test matches production inference format; previously system as user inflated/deflated scores | [#248](https://github.com/deghosal-2026/agent-self-edit/issues/248), [#277](https://github.com/deghosal-2026/agent-self-edit/issues/277) | Mock captures two-message format; regression test fails old single-message path | ⬜ |
| 6 | Validate winner='a' path (regression) end-to-end | `field-test/` corpus + `tests/test_field_test.py` — field-test scenario where candidate regresses vs baseline; permutation two-tailed validated | Regression correctly yields `winner='a'` with `p<0.05` not `inconclusive` | [#267](https://github.com/deghosal-2026/agent-self-edit/issues/267) | field-test winner='a' measured; previously never tested | ⬜ |

> Note: M1 has 8 issues but 6 logical tasks: permutation pair (#278/#257) and run_task pair (#248/#277) are combined — both pairs fix the same code path. Total issues covered = 8.

### M1 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Bootstrap CI sensitivity | Different data → different CI | Unit tests `ci_flat vs ci_improved` |
| Permutation two-tailed | Both directions `p<0.05` | Tests for winner='a' and 'b' |
| Tie detection | Epsilon, not `==0.0` | Near-identical fixtures |
| run_task format | system + user messages | Mock provider assertion |
| Calibration | Per `ab-test-engine-design` | Coverage tests |
| Coverage | > 91% | `--cov-fail-under=91` |

### M1 Exit Gate

- [ ] `bootstrap_ci` and `permutation_test` accept `seed=None` (production random) with `seed=0` only in tests
- [ ] Permutation is two-tailed; `winner='a'` path exercised and passes
- [ ] Tie detection uses epsilon, not `==0.0`
- [ ] CI calibration tests per `ab-test-engine-design` added
- [ ] `run_task` sends system prompt as `system` role (both #248 and #277 fixed)
- [ ] winner='a' field-test scenario validated (#267)
- [ ] Ruff clean: `ruff check .` → 0 errors
- [ ] Mypy strict clean: `mypy --strict src/agent_self_edit` → 0 errors
- [ ] All tests pass: `python3 -m pytest --ignore=tests/test_docker.py -x -q` → 0 failures
- [ ] Coverage > 91%: `pytest --cov=agent_self_edit --cov-fail-under=91`
- [ ] Documentation updated for the milestone's scope

**Dependency:** none. **Produces for M2+:** correct A/B statistics, correct winner determination, correct inference format.

---

## Milestone 2: Promotion Gate & Near-Miss Logic (8 issues)

**Objective:** Fix near-miss classification so only genuine near-promotions are labeled `near_miss`, audit `near_misses()` is usable, and stale `rejection_context` does not corrupt loop feedback. Prevents audit misreporting and analyzer re-proposing bad edits.

### M2 Design Documents

- **D2 — Gate near-miss design** (`docs/design/gate-near-miss-design.md`): threshold validation, ratio denominator semantics, audit reconstruction, rejection context lifecycle.

### M2 Task Checklist

| # | Issue | Build (files) | Behavior + edge cases | Issue | Verify | Status |
|---|-------|---------------|----------------------|-------|--------|--------|
| 1 | Validate `near_miss_threshold` >0 and <1 | `src/agent_self_edit/config.py` — `validate_config()` rejects `0.0` or `1.0`; requires `0 < threshold < 1` (or `>0` guard in gate) | `0.0` rejected at validation; `0.5` default passes; gate guard `ratio>0 and ratio>=threshold` | [#300](https://github.com/deghosal-2026/agent-self-edit/issues/300) | `0.0` validation error; 0-check rejection never `near_miss` | ⬜ |
| 2 | Fix near-miss ratio denominator (fail-fast) | `src/agent_self_edit/gate.py` — document and fix `ratio = passed/total` vs `passed/len(checks_run)`; improve reason string to name failing check | `failed at check 2` → `1/6 reject` not misleading `50%`; reason names `failed at: edit_distance` | [#298](https://github.com/deghosal-2026/agent-self-edit/issues/298), [#211](https://github.com/deghosal-2026/agent-self-edit/issues/211) | `near_miss` reason names failing check; denominator semantics documented | ⬜ |
| 3 | Fix `GateAuditLog.near_misses()` reconstruction | `src/agent_self_edit/gate.py` — `near_misses()` must reconstruct `EditProposal` with real `old_text` (from registry diff or stored proposal), not `old_text=''` | Dedup usable for analysis, not just dedup; audit tooling shows real proposals | [#258](https://github.com/deghosal-2026/agent-self-edit/issues/258) | `near_misses()` returns proposals with non-empty `old_text` | ⬜ |
| 4 | Load `near_misses` in loop (fix dead code) | `src/agent_self_edit/cli/run.py`, `propose.py`, `src/agent_self_edit/analyzer.py` — load from `GateAuditLog.near_misses()` and pass to `analyze_batch(near_misses=...)` | Previously `near_misses` always `None`; dedup dead; after fix dedup filters similar proposals | [#249](https://github.com/deghosal-2026/agent-self-edit/issues/249), [#282](https://github.com/deghosal-2026/agent-self-edit/issues/282) | Analyzer dedup active; retry of rejected edit skipped | ⬜ |
| 5 | Fix stale `rejection_context` when no proposals | `src/agent_self_edit/cli/run.py`, `trace.py` — clear or version `rejection_context` when analyzer yields 0 proposals; do not carry forward indefinitely | Empty analyzer result does not poison next iteration with old context; context TTL or reset | [#251](https://github.com/deghosal-2026/agent-self-edit/issues/251), [#289](https://github.com/deghosal-2026/agent-self-edit/issues/289) | Loop feedback not corrupted after empty analysis | ⬜ |

### M2 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Threshold validation | `0.0` rejected | `validate_config` test |
| Ratio semantics | Clear, not misleading | Gate reason tests |
| Audit reconstruction | `old_text` populated | `near_misses()` test |
| Near-miss dedup | Active, not dead code | Analyzer dedup test |
| Rejection context | Not stale after 0 proposals | Loop integration test |
| Coverage | > 91% | `--cov-fail-under=91` |

### M2 Exit Gate

- [ ] `near_miss_threshold=0` rejected at validation (or guarded `ratio>0`)
- [ ] Near-miss reason names failing check; denominator documented
- [ ] `near_misses()` returns usable proposals (not `old_text=''`)
- [ ] `near_misses` loaded and passed to analyzer (dead code fixed for both #249/#282)
- [ ] Stale `rejection_context` not carried forward (both #251/#289 fixed)
- [ ] Ruff clean: `ruff check .` → 0 errors
- [ ] Mypy strict clean: `mypy --strict src/agent_self_edit` → 0 errors
- [ ] All tests pass: `python3 -m pytest --ignore=tests/test_docker.py -x -q` → 0 failures
- [ ] Coverage > 91%: `pytest --cov=agent_self_edit --cov-fail-under=91`
- [ ] Documentation updated for the milestone's scope

**Dependency:** M1. **Produces for M3+:** correct near-miss labeling, usable audit dedup, clean loop feedback.
