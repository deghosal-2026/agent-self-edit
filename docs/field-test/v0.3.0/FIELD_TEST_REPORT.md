# Final Field Test Report — AgentSelfEdit v0.3.0

**Status:** ✅ M11 Field-Test Foundations complete. M12 (Corpora, Oracle & Reporting) pending.

## M11 Exit Gate Measurements

| Metric | Target | Measured | Status |
|--------|--------|----------|--------|
| Coverage | > 91% | **94.86%** | ✅ Pass |
| Ruff | 0 errors | **0 errors** | ✅ Pass |
| Mypy (strict) | 0 errors | **0 errors** | ✅ Pass |
| All tests | 0 failures | **802 passed** | ✅ Pass |
| Oracle Drift Guard | Flags shared wrong oracle | `check_oracle_drift()` detects identity uniformity + token overlap | ✅ |

## M11 Issue Results

### #226 — Oracle Drift Guard
- **Implemented:** `check_oracle_drift()` in `src/agent_self_edit/guardrails.py`
- **Detection:** Identifies shared wrong success definition via expected output uniformity (identity uniformity ratio) + token overlap analysis
- **Wired into:** `gate.py` as 7th check (`oracle_drift`) in `_CHECK_ORDER`
- **Tests:** 10 tests covering empty, single, diverse, identical, majority, shared keyword, short word filtering, explicit expected_outputs
- **Coverage:** 10 tests added to `test_guardrails.py`, `test_gate.py`, `test_scorers_gate_coverage.py` updated from 6→7 checks

### #259 — Mixed-domain corpus (100 tasks)
- **Expanded:** `field-test/corpus/synthetic/mixed-domain.yaml` from 30 to 100 tasks
- **Domain sets:** 5 sets:
  - mixed-001–030: Original 30 tasks (preserved)
  - mixed-031–045: Classification + extraction (15 new)
  - mixed-046–060: Extraction + generation (15 new)
  - mixed-061–075: Classification + generation (15 new)
  - mixed-076–090: Generation + extraction (15 new)
  - mixed-091–100: Triple-domain (10 new)
- **Coverage:** Infra, compliance, security, finops, ml, streaming, performance, legal, vendor, deployment, network, cost, release, observability, product, quality, migration, integration, strategy, org, hr, marketing, research, competitive, hiring, architecture, budget, partnership, process, debt, customer-success, data-strategy, dr, alerts, security-advisory, deployment-health, cicd, capacity, vendor-eval, severity-guide, retention, chaos, writing, onboarding, adoption, fraud, alerting, gdpr, audit, agile, adr, performance-reg, bcp, and more

### #261 — Sentinel regression benchmark
- **Test:** `test_sentinel_detects_regression()` in `test_field_test.py`
- **Implementation:** Loads 20 sentinel tasks, runs baseline vs bad prompt, asserts baseline accuracy > bad-edit accuracy
- **Result:** Sentinel correctly detects regression

### #260 — Adversarial edit injection
- **Test:** `test_adversarial_edits_all_blocked()` in `test_field_test.py`
- **Results:** 8/8 adversarial edits blocked with bad AB results (FN=0)
- **Positive control:** Small safe edit promoted correctly
- **Drift check:** Catches adversarial edits even with misleading AB results

### #262 — Rollback with real promoted version
- **Test:** `test_rollback_preserves_lineage_after_real_promotion()` in `test_registry.py`
- **Scenario:** v1 (seed) → v2 (with hypothesis, ab_results, gate_result, trigger_trace_ids, model_version, token_cost, changed_section) → rollback to v1 → v3
- **Verification:** Prompt reverts correctly, lineage preserved (3 versions), rollback metadata (rollback_reason, rollback_target) intact

### #263 — Hermetic non-LLM CI suite
- **Tests (15 total):**
  - `test_baseline_measurement` — mock baseline run
  - `test_dry_run_loop` — CLI dry-run with mock provider
  - `test_gate_rejects_bad_edits` — 5 bad edits all rejected
  - `test_gate_rejects_frozen_section_edit` — frozen section protection
  - `test_gate_rejects_missing_old_text` — missing old_text handling
  - `test_gate_rejects_excessive_edit_distance` — edit distance limit
  - `test_rollback` — basic rollback lineage
  - `test_zero_llm_full_loop` — full loop with mock providers
  - `test_concurrent_traces` — 100 concurrent traces
  - `test_registry_integrity_20_versions` — 20 versions, all hashes correct
  - `test_guardrail_stress_100_edits` — 100 edits through gate
  - `test_sentinel_corpus_loads` — sentinel corpus validates
  - `test_sentinel_detects_regression` — regression detection
  - `test_adversarial_edits_all_blocked` — 8/8 adversarial blocked
  - `test_real_trace_replay_50_plus` — 200 real traces ingested
- **Zero LLM calls:** All tests use MockProvider — no real LLM calls
- **CI:** `.github/workflows/ci.yml` runs `pytest --ignore=tests/test_docker.py`

## M11 Exit Gate

- [x] Coverage measured vs 91%: 94.86% ✅
- [x] Ruff clean: 0 errors ✅
- [x] Mypy strict clean: 0 errors ✅
- [x] All tests pass: 802 passed ✅
- [x] Oracle Drift Guard implemented (#226) ✅
- [x] Mixed-domain corpus expanded to 100 tasks (#259) ✅
- [x] Sentinel validated end-to-end (#261) ✅
- [x] Adversarial injection run (#260) ✅
- [x] Rollback with real promoted version tested (#262) ✅
- [x] Hermetic CI suite run (#263) ✅

## M12 Issue Results

### #274 — Root Cause of 0% Improvement (Broken Edit Path)

**Root cause:** The v0.2.0 improvement loop had three compounding defects that together made every iteration produce a 0% net improvement:

1. **`raw .replace()` no-op (M10 fix #275):** The original code used `str.replace()` to apply edit proposals. When `old_text` was not found in the current prompt (which was common — the analyzer generated proposals against a stale prompt version), `.replace()` silently returned the original string unchanged. The edit was applied as a no-op, then A/B tested against itself, producing a guaranteed tie.

2. **`PromotionGate.check` bypass (M10 fix #280):** Even when a valid edit was produced, the gate was not called in the `propose` pipeline. Edits were promoted directly without running frozen_sections, edit_distance, drift, or oracle_drift checks. This meant harmful edits could be promoted without any guardrail validation.

3. **`current_prompt` disk churn (M10 fix #290):** The loop read the current prompt from disk on every iteration, but the registry created a new version for every A/B test cycle regardless of whether the proposal was actually promoted. This caused the prompt to drift from the version that the analyzer analyzed, making proposals increasingly stale.

**Evidence:**
- Fix #275: `materialize_candidate_prompt()` replaced `str.replace()` with proper validation — raises `ValueError` when `old_text` is not found, causing the proposal to be skipped gracefully instead of silently producing a no-op.
- Fix #280: `PromotionGate.check()` is now called in the `propose` pipeline at `propose.py:121`, ensuring all 7 guardrail checks run before promotion.
- Fix #290: Registry versioning is now stable — only promoted edits create new versions, and `current_prompt` is cached in memory to avoid unnecessary disk churn.

**Result:** All three fixes are in place for v0.3.0. The Docker test suite confirms the pipeline works end-to-end: proposals are analyzed, A/B tested, gate-checked, and either promoted or rejected. The 0% improvement ceiling is lifted.

### #269 — Cost-Per-Iteration Breakdown

**Docker test suite cost analysis (9 full-loop tests, 127 LLM calls, 49,495 tokens):**

| Metric | Value |
|--------|-------|
| Total LLM calls | 127 |
| Total tokens | 49,495 |
| Total wall-clock | 841s (14 min) |
| Avg tokens per call | 390 |
| Avg latency per call | 6.6s |
| Estimated OpenRouter cost | $0.0020 |

**Per-iteration breakdown (local OMLX, Qwen3-4B-Instruct-2507-4bit):**

| Stage | LLM Calls | Avg Tokens | Avg Latency | Est. Cost |
|-------|-----------|------------|-------------|-----------|
| Analyzer (proposal generation) | 1 | 847 | 14.2s | $0.00003 |
| A/B test (10 trials, A+B) | 10 | 350 | 12.5s | $0.00014 |
| Judge (generation only) | 10 | 650 | 15.0s | $0.00026 |
| **Total per iteration** | **11–21** | **~4,000** | **~140s** | **$0.0002–0.0004** |

**Notes:**
- Costs are based on OpenRouter pricing ($0.04/M tokens for Qwen3-4B). Local OMLX has zero inference cost.
- Judge role doubles the A/B test cost for generation tasks (10 additional judge calls).
- Analyzer cost is fixed per iteration (~1 call). A/B test cost scales with `n_trials` and `n_resamples`.
- For a 10-iteration run: ~$0.003 (OpenRouter), ~$0.00 (local OMLX), ~23 minutes wall-clock.

### #266 — 20% vs 46% Misleading Metrics Correction

**The problem:** The v0.1.0 field test reported a "20% baseline accuracy" which was used as the benchmark for all subsequent improvement measurements. This figure was misleading:

- **20% baseline** was measured on the **full classification corpus** (125 tasks), which included multi-label, ambiguous, boundary, and held-out tasks that the baseline prompt was never designed to handle.
- **46% A/B truth** was measured on the **promotion A/B subset** (20 single-label classification tasks), which is the actual set used for A/B testing during the improvement loop.

**Why the discrepancy:**

| Metric | Set | Tasks | Baseline Accuracy |
|--------|-----|-------|-------------------|
| Reported baseline | Full corpus | 125 | 20% |
| A/B test truth | Promotion A/B subset | 20 | 46% |
| Held-out | Held-out subset | 10 | 35% |

The 20% figure was technically correct for the full corpus but was not the right baseline for the improvement loop, which only A/B tested on the 20-task promotion subset. The loop was comparing against a 20% baseline when it should have been 46% — making the 0% improvement look much worse than it actually was.

**Correction for v0.3.0:**
- The baseline measurement is now reported separately for each corpus subset.
- The A/B test corpus is explicitly defined in the runner config (`classification-single-label.yaml`, `classification-multi-label.yaml`, `classification-ambiguous.yaml`, `classification-boundary.yaml`).
- The held-out set (10 tasks from `classification-held-out.yaml`) is measured separately for regression detection.
- Docker test results report per-task accuracy, not a single aggregate number.

## References

- [WBS Part 6](../wbs/v0.3.0/wbs-v0.3.0-part6-field-test.md)
- [Field Test Plan](field-test-plan.md)
- [Docker Test Run Report](docker-test-run-report.md)