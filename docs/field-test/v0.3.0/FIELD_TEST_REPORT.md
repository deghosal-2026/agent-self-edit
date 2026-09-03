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

## References

- [WBS Part 6](../wbs/v0.3.0/wbs-v0.3.0-part6-field-test.md)
- [Field Test Plan](field-test-plan.md)