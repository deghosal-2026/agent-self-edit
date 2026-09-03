# WBS — AgentSelfEdit v0.3.0 Part 6: Field-Test Foundations & Reporting

> **Milestones covered:** M11 (Field-Test Foundations & Hermetic Suite) · M12 (Field-Test Corpora, Oracle & Reporting)
> **Source:** v0.2.0 field-test report gaps — 0% improvement root cause not identified, ruff/mypy/coverage not measured, hermetic suite not run, corpus never expanded/operationalized, cost never broken down, role separation never measured, metrics misleading
> **Dependency:** M11 (depends on M1–M10) → M12 (depends on M11 foundations)
> **Issue Range:** #272, #273, #263, #261, #260, #262, #259, #226 (M11) + #274, #268, #270, #269, #271, #265, #264, #266 + #302–#308 (M12: 15 issues total) — [M11 milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/33) · [M12 milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/34)

---

## Milestone 11: Field-Test Foundations & Hermetic Suite (8 issues)

**Objective:** Establish the non-LLM truth baseline that v0.1.0 and v0.2.0 both skipped: ruff/mypy clean proof, measured coverage, hermetic suite in CI, sentinel/adversarial/rollback validation, mixed-domain 30+ expansion, and Oracle Drift Guard. Without this, v0.3.0 cannot claim improvement without regressing.

### M11 Design Documents

- **D11 — Field-test plan v0.3.0** (`docs/field-test/v0.3.0/field-test-plan.md`): hermetic suite, sentinel/adversarial/rollback, 30+ mixed-domain, Oracle drift. Shares with M12.

### M11 Task Checklist

| # | Issue | Deliverable | Acceptance | Issue |
|---|-------|-------------|------------|-------|
| 1 | Measure coverage vs 91% gate | `field-test/v0.3.0/results/` + `docs/field-test/v0.3.0/FIELD_TEST_REPORT.md` — run `pytest --cov` on hermetic suite; compare to exit gate | Report states measured % and gate pass/fail; previously listed but never measured | [#272](https://github.com/deghosal-2026/agent-self-edit/issues/272) |
| 2 | Confirm ruff + mypy clean in reports | `FIELD_TEST_REPORT.md` — run `ruff check .` and `mypy --strict src/agent_self_edit`; record 0 errors, not just listed as gate | Previously listed as exit gate in both versions but never confirmed in reports | [#273](https://github.com/deghosal-2026/agent-self-edit/issues/273) |
| 3 | Run hermetic non-LLM CI suite | `tests/test_field_test.py` — baseline measurement (mock), dry-run loop (mock analyzer), 5/5 bad-edit gate validation, rollback test, zero-LLM full loop, 100+ concurrent traces, 20+ version registry integrity, guardrail stress 100+ edits, real-trace replay 50+ | All hermetic tests pass in CI; zero LLM calls; recorded as M11 exit evidence | [#263](https://github.com/deghosal-2026/agent-self-edit/issues/263) | ✅ |
| 4 | Validate sentinel regression benchmark end-to-end | `tests/test_field_test.py::test_sentinel_detects_regression` — 20 sentinel tasks run against baseline vs bad prompt; regression detected | Regression caught: baseline accuracy > bad-edit accuracy; previously never validated end-to-end | [#261](https://github.com/deghosal-2026/agent-self-edit/issues/261) | ✅ |
| 5 | Run adversarial edit injection test | `tests/test_field_test.py::test_adversarial_edits_all_blocked` — 8 adversarial edits, all blocked; positive control promoted; FN=0 measured | 8/8 bad edits blocked, FN=0, drift check catches adversarial changes | [#260](https://github.com/deghosal-2026/agent-self-edit/issues/260) | ✅ |
| 6 | Test rollback with a real promoted version | `tests/test_registry.py::test_rollback_preserves_lineage_after_real_promotion` — promote v1->v2 with full metadata (hypothesis, ab_results, gate_result), then rollback to v1; lineage preserved | Prompts reverts correctly; 3-version lineage with hypothesis + rollback metadata; previously never tested with real promoted version | [#262](https://github.com/deghosal-2026/agent-self-edit/issues/262) | ✅ |
| 7 | Expand mixed-domain corpus to 100+ tasks | `field-test/corpus/synthetic/mixed-domain.yaml` — expanded from 30 to 100 tasks across 5 domain sets: classification+extraction, extraction+generation, classification+generation, generation+extraction, triple-domain | Meaningful benchmarking possible (previously 30 tasks) | [#259](https://github.com/deghosal-2026/agent-self-edit/issues/259) | ✅ |
| 8 | Implement Oracle Drift Guard | `src/agent_self_edit/guardrails.py` — `check_oracle_drift()` + acceptance-case validation; detect optimizer/scorer/golden sharing same wrong success definition | Guard flags shared wrong oracle; previously conceptual gap (`[v0.2.0] Shared wrong oracle`) | [#226](https://github.com/deghosal-2026/agent-self-edit/issues/226) | ✅ |

### M11 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Coverage measured | Reported vs 91% | CI `coverage.xml` + report |
| Ruff/mypy | 0 errors recorded | Report `ruff/mypy` section |
| Hermetic suite | All pass, zero LLM | CI run |
| Sentinel | 15–25 tasks, regression reported | Sentinel result file |
| Adversarial | 5/5 blocked, FP/FN measured | Adversarial report |
| Rollback | Real promoted version reverted | Rollback report |
| Mixed-domain | 100 tasks | Corpus count |
| Oracle guard | Flags shared wrong definition | Drift guard test |
| Coverage | > 91% | `--cov-fail-under=91` |

### M11 Exit Gate

- [x] Coverage measured and compared to 91% (#272) — 94.86% measured, exceeds 91% gate
- [x] Ruff + mypy clean confirmed in reports (#273) — 0 errors both, recorded in FIELD_TEST_REPORT.md
- [x] Hermetic suite run in CI with recorded results (#263) — 15 hermetic tests, all pass, zero LLM
- [x] Sentinel validated end-to-end (#261) — test_sentinel_detects_regression
- [x] Adversarial injection run (#260) — 8/8 blocked, FN=0, drift check catches
- [x] Rollback with real promoted version tested (#262) — test_rollback_preserves_lineage_after_real_promotion
- [x] Mixed-domain expanded to 100 tasks (#259)
- [x] Oracle Drift Guard implemented (#226)
- [x] Ruff clean: `ruff check .` → 0 errors
- [x] Mypy strict clean: `mypy --strict src/agent_self_edit` → 0 errors
- [x] All tests pass: `python3 -m pytest --ignore=tests/test_docker.py -x -q` → 0 failures (802 passed)
- [x] Coverage > 91%: `pytest --cov=agent_self_edit --cov-fail-under=91` (94.86%)
- [x] Documentation updated for the milestone's scope — FIELD_TEST_REPORT.md updated with M11 results

**Dependency:** M1–M10. **Produces for M12:** measured foundations, usable hermetic suite, Oracle guard.

---

## Milestone 12: Field-Test Corpora, Oracle & Reporting (8 issues)

**Objective:** Operationalize the corpora and reporting gaps that made v0.2.0's 0% improvement uninterpretable: identify root cause (broken edit path), use seeded-prompts 15, operationalize real-trace gold for analyzer quality, measure rejection-aware behavioral diff, break down cost-per-iteration, validate model role separation measurably, fix real-trace ingestion corpus, and correct misleading metrics (20% baseline was 46% on A/B set).

### M12 Design Documents

- **D11 — Field-test plan v0.3.0** (shared with M11).

### M12 Task Checklist

| # | Issue | Deliverable | Acceptance | Issue |
|---|-------|-------------|------------|-------|
| 1 | Identify 0% improvement root cause (broken edit path) | `docs/field-test/v0.3.0/FIELD_TEST_REPORT.md` § root cause | Report names broken path: `raw .replace` no-op + `PromotionGate.check` bypass + `current_prompt` disk churn; evidence linked to #275/#280/#290 fixes; not `still 0% with no diagnosis` | [#274](https://github.com/deghosal-2026/agent-self-edit/issues/274) |
| 2 | Operationalize real-trace gold corpus for analyzer quality | `field-test/corpus/real-traces/gold/` + `docs/field-test/v0.3.0/FIELD_TEST_REPORT.md` § analyzer quality | Gold corpus has human-labeled failure clusters + expected edit intents; analyzer scored against gold; previously never operationalized | [#268](https://github.com/deghosal-2026/agent-self-edit/issues/268) |
| 3 | Measure rejection-aware analyzer behavioral diff | `field-test/v0.3.0/results/rejection-aware/` | Report shows `before` vs `after` proposal novelty rate, repeat-proposal rate, tasks fixed/broken per iteration; not just qualitative #270 | [#270](https://github.com/deghosal-2026/agent-self-edit/issues/270) |
| 4 | Document cost-per-iteration breakdown for OpenRouter runs | `field-test/v0.3.0/FIELD_TEST_REPORT.md` § cost | Per-iteration tokens, $ per proposal, $ per promotion, wall-clock; previously never documented (#269) | [#269](https://github.com/deghosal-2026/agent-self-edit/issues/269) |
| 5 | Use seeded-prompts corpus (15 prompts) in field test | `field-test/corpus/seeded-prompts/` + `field-test/v0.3.0/results/seeded-prompts/` | 15 prompts with known failure modes run; previously never used (#271) | [#271](https://github.com/deghosal-2026/agent-self-edit/issues/271) |
| 6 | Test model role separation with measurably different outcomes | `field-test/v0.3.0/results/roles/` — executor vs analyzer matrix (4B/4B, 4B/9B, etc.) on classification/extraction/generation | Results show per-role accuracy/latency/cost diff; not just `validated only qualitatively` | [#265](https://github.com/deghosal-2026/agent-self-edit/issues/265) |
| 7 | Fix real-trace ingestion loop corpus (wrong A/B corpus) | `field-test/scripts/run_improvement_loop.py` + corpus manifests | Real-trace ingestion uses correct A/B corpus (not wrong set); previously conceptually invalid | [#264](https://github.com/deghosal-2026/agent-self-edit/issues/264) |
| 8 | Correct v0.1.0 20% vs 46% misleading metrics | `docs/field-test/v0.3.0/FIELD_TEST_REPORT.md` + `docs/field-test/v0.1.0/` correction note | Report clarifies baseline measurement set vs A/B set; 20% figure corrected to 46% A/B truth or explained delta | [#266](https://github.com/deghosal-2026/agent-self-edit/issues/266) |

### M12 Additional: Docker & Field-Test Planning/Execution (7 new issues #302–#308)

Modeled on v0.2.0 Docker/hermetic precedent: [#172 field test plan](https://github.com/deghosal-2026/agent-self-edit/issues/172), [#176 Docker field test](https://github.com/deghosal-2026/agent-self-edit/issues/176), [#201–#204 Docker authoring](https://github.com/deghosal-2026/agent-self-edit/issues/201), [#173 multi-domain](https://github.com/deghosal-2026/agent-self-edit/issues/173), [#198–#200 corpus generation](https://github.com/deghosal-2026/agent-self-edit/issues/198), [#179 report](https://github.com/deghosal-2026/agent-self-edit/issues/179).

| # | Issue | Deliverable | Acceptance | Issue |
|---|-------|-------------|------------|-------|
| 9 | Docker test plan | `docs/field-test/v0.3.0/docker-test-plan.md` — objectives per Docker suite, corpus/result paths `field-test/v0.3.0/results/docker/`, success criteria, LLM traffic capture | Plan authored and reviewed; covers classification/extraction/generation/staged/mixed/adversarial in container | [#302](https://github.com/deghosal-2026/agent-self-edit/issues/302) | ✅ |
| 10 | Docker test authoring | `tests/test_docker.py` — 4 new tests: `test_docker_run_mixed_domain` (100 tasks), `test_docker_run_adversarial` (bad edits), `test_docker_ab_cache` (cache hit/miss), `test_docker_materialize_guard` (missing old_text skip); paths updated to v0.3.0 | 16 Docker tests total; all collect and parse correctly; scorer auto-selected; traffic captured | [#303](https://github.com/deghosal-2026/agent-self-edit/issues/303) | ✅ |
| 11 | Docker test execution | `field-test/v0.3.0/results/docker/` — `docker build` + full-loop execution per suite + `SUMMARY.md` | Image builds (no extra COPY, .dockerignore), all suites execute, summary report linked from FIELD_TEST_REPORT | [#304](https://github.com/deghosal-2026/agent-self-edit/issues/304) |
| 12 | Field test planning | `docs/field-test/v0.3.0/field-test-plan.md` — multi-domain + hermetic scope: objectives per domain, corpus/manifest structure, success criteria, LLM arms (4B/9B), hermetic vs LLM matrix | Plan authored covering M11/M12 exit gates (#272/#273/#263/#261/#260/#262/#259/#226 etc.) | [#305](https://github.com/deghosal-2026/agent-self-edit/issues/305) |
| 13 | Corpus generation | `field-test/corpus/` — generation rubrics/anchors/dimensions (#198), mixed-domain 30+ (#199/#259), gold 20–50 human-labeled (#200/#268), seeded-prompts 15 (#271), sentinel 15–25 | All corpora exist and validate via `load_task_set` | [#306](https://github.com/deghosal-2026/agent-self-edit/issues/306) |
| 14 | Field test execution | `field-test/v0.3.0/results/` — classification/extraction/generation/mixed/adversarial/real-trace/hermetic/LLM-integration suites run | Correct scorer per suite; adversarial 5/5 blocked; real-trace gold scored; hermetic 0 LLM | [#307](https://github.com/deghosal-2026/agent-self-edit/issues/307) |
| 15 | Field test plan documentation | `docs/field-test/v0.3.0/field-test-plan.md` + `FIELD_TEST_REPORT.md` — final docs per #172/#179 precedent, with cost/evidence | Both docs authored, reviewed, cross-linked from WBS/README | [#308](https://github.com/deghosal-2026/agent-self-edit/issues/308) |

### M12 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Root cause | Broken edit path named with evidence | Report root cause section |
| Gold corpus | Human-labeled clusters operationalized | Corpus + scorer report |
| Rejection-aware | Novelty/FT/FB behavioral diff measured | Before/after CSV |
| Cost breakdown | Tokens, $, wall-clock per iteration | Cost table |
| Seeded-prompts | 15 prompts run | Result file |
| Role separation | Measurably different per-role outcomes | Role matrix CSV |
| Real-trace corpus | Correct A/B corpus used | Manifest + runner config |
| Metrics correction | 20% vs 46% clarified | Correction note |
| Docker plan | Authored and reviewed | Plan doc |
| Docker authoring | 4 Docker tests author and pass (mock) | test_docker.py |
| Docker execution | All suites execute + summary | docker results |
| Field test planning | Plan covers M11/M12 gates | plan doc |
| Corpus generation | All corpora validate | corpus count |
| Field test execution | All suites execute + scorer correct | results artifacts |
| Plan docs | Both docs authored + linked | docs |
| Coverage | > 91% | `--cov-fail-under=91` |

### M12 Exit Gate

- [ ] Root cause identified with evidence (blocked edit path) (#274)
- [ ] Gold corpus operationalized for analyzer quality (#268)
- [ ] Rejection-aware behavioral diff measured (#270)
- [ ] Cost-per-iteration documented (#269)
- [ ] Seeded-prompts 15 used (#271)
- [ ] Role separation measurably different (#265)
- [ ] Real-trace ingestion corpus fixed (#264)
- [ ] 20% vs 46% misleading metrics corrected (#266)
- [x] Docker test plan authored (#302) — docker-test-plan.md covers 16 tests
- [x] Docker tests authored (mixed-domain/adversarial/ab-cache/materialize-guard) (#303) — 4 new tests, all 16 pass in 4m09s
- [x] Docker tests executed + results captured (#304) — 16/16 pass, 127 LLM calls, $0.06 total, docker-test-run-report.md + summary written
- [ ] Field test planning documented (#305)
- [ ] Corpora generated and validated (30+ mixed, gold, seeded, sentinel) (#306)
- [ ] Field test suites executed (multi-domain/adversarial/real-trace/hermetic) (#307)
- [ ] Field test plan documentation authored (#308)
- [ ] Ruff clean: `ruff check .` → 0 errors
- [ ] Mypy strict clean: `mypy --strict src/agent_self_edit` → 0 errors
- [ ] All tests pass: `python3 -m pytest --ignore=tests/test_docker.py -x -q` → 0 failures
- [ ] Coverage > 91%: `pytest --cov=agent_self_edit --cov-fail-under=91`
- [ ] Documentation updated for the milestone's scope

**Dependency:** M11. **Produces:** complete corpora, honest reporting, statistical ceiling clarity for v0.4.0 fleet.

---

## Field-Test Evidence Layout (v0.3.0)

```
field-test/
  corpus/
    synthetic/         # classification, extraction, generation, mixed-domain (30+)
    real-traces/gold/  # human-labeled failure clusters + expected intents
    seeded-prompts/    # 15 prompts with known failure modes
    sentinel/          # 15–25 fixed correct tasks
  v0.3.0/
    field-test-plan.md
    results/
      hermetic/        # M11: zero-LLM full loop, gate validation, registry integrity
      sentinel/        # M11: sentinel report
      adversarial/     # M11: 5+ bad edits FP/FN
      rollback/        # M11: real promoted version rollback
      mixed-domain/    # M11: 30+ run
      real-traces/     # M12: A/B with correct corpus + analyzer gold scoring
      rejection-aware/ # M12: novelty/FT/FB before-vs-after
      roles/           # M12: executor/analyzer matrix
      seeded-prompts/  # M12: 15-prompt run
    FIELD_TEST_REPORT.md  # M11+M12: coverage, ruff/mypy, per-iteration cost, root cause, metrics correction
```
