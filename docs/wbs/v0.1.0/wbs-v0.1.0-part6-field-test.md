# WBS — AgentSelfEdit v0.1.0 Part 6: Field Test

> **Milestone covered:** M10 (Field Test)
> **PRD coverage:** [F-14](../../design/prd/05-features.md) (Docker), [07-success-metrics](../../design/prd/07-success-metrics.md) (reliability targets)
> **CUJs covered:** CUJ 1 (deploy, observe, improve), CUJ 2 (catch bad edit), CUJ 4 (rollback)
> **Dependency:** M10 depends on M9 (CLI) — needs the CLI to run the loop
> **Issue Range:** #64–#69 (+ #93 D10 design doc, #94 field test report)

---

## Milestone 10: Field Test (#64–#69)

**Objective:** Validate the loop end-to-end on a synthetic task suite. Prove improvement is measurable and guardrails work. Test with and without LLM calls.

### M10 Design Documents

- **D10 — Field test plan** (`docs/design/field-test-plan.md`): test objectives, synthetic task suite design, baseline measurement methodology, improvement measurement methodology, guardrail validation methodology, rollback validation, cost analysis, non-LLM vs LLM testing strategy, test matrix.

### M10 Task Checklist

#### Corpus & Infrastructure

| # | Task | Build (files) | Behavior + edge cases | Feature | Design Ref | Verify | Status |
|---|------|---------------|----------------------|---------|------------|--------|--------|
| 1 | Classification task set | `docs/field-test/v0.1.0/corpus/classification.yaml` | 20 tasks; input: text string; expected output: category label; scorer: ExactMatch; includes ambiguous boundary cases, missing categories, multi-label inputs | — | [D10 §0](../../design/ab-test-engine-design.md#1–ab-testing-vs-field-testing--how-to-conceptualize-this) | tasks load, scorer works, edge cases present | [#64](https://github.com/deghosal-2026/agent-self-edit/issues/64) · ⬜ |
| 2 | Extraction task set | `docs/field-test/v0.1.0/corpus/extraction.yaml` | 15 tasks; input: text; expected output: structured fields; scorer: Contains; includes missing fields, wrong format, extra fields | — | [D10 §0](../../design/ab-test-engine-design.md#1–ab-testing-vs-field-testing--how-to-conceptualize-this) | tasks load, scorer works, all edge cases | [#64](https://github.com/deghosal-2026/agent-self-edit/issues/64) · ⬜ |
| 3 | Generation task set | `docs/field-test/v0.1.0/corpus/generation.yaml` | 15 tasks; input: topic + constraints; expected output: generated text; scorer: LLMJudge; includes off-topic, wrong tone, missing constraints | — | [D10 §0](../../design/ab-test-engine-design.md#1–ab-testing-vs-field-testing--how-to-conceptualize-this) | tasks load, scorer works, all edge cases | [#64](https://github.com/deghosal-2026/agent-self-edit/issues/64) · ⬜ |
| 4 | Seeded failure prompts | `docs/field-test/v0.1.0/corpus/seeded-prompts/` | 10 prompts with known failure modes; each fails on 3-5 specific tasks; covers all 3 domains | — | [D10 §12.4](../../design/ab-test-engine-design.md#125–field-test-ab-calibration-test-script) | prompts produce expected failures on task sets | [#65](https://github.com/deghosal-2026/agent-self-edit/issues/65) · ⬜ |
| 5 | Adversarial test cases | `docs/field-test/v0.1.0/corpus/adversarial-edits/` | 5 intentionally bad edits; each improves one task type but degrades another; used to verify guardrails catch tradeoff failures | — | [D10 §12.3](../../design/ab-test-engine-design.md#124–what-the-field-test-validates-about-the-ab-test-engine) | edits have expected improvement/degradation profile | [#65](https://github.com/deghosal-2026/agent-self-edit/issues/65) · ⬜ |
| 6 | Trace generation script | `scripts/generate_traces.py` | Generates synthetic traces from a task set and prompt; runs offline (no LLM); produces: success traces, failure traces, mixed batches | — | [D10 §14.1](../../design/ab-test-engine-design.md#142–unit-tests-hermetic-ci-safe) | traces are valid; failures included; mixed batches | [#66](https://github.com/deghosal-2026/agent-self-edit/issues/66) · ⬜ |

#### Non-LLM Tests (Hermetic, CI-safe)

| # | Task | Behavior + edge cases | Feature | Design Ref | Verify | Status |
|---|-------|----------------------|---------|------------|--------|--------|
| 7 | Baseline measurement | Run baseline prompt against held-out set; measure: accuracy, per-task scores, cost; target: > 70% baseline accuracy | — | [D10 §12.1](../../design/ab-test-engine-design.md#122–field-test-structure) | baseline recorded; all metrics captured | [#66](https://github.com/deghosal-2026/agent-self-edit/issues/66) · ⬜ |
| 8 | Dry-run loop test | `agent-self-edit run --dry-run --once` with mock analyzer; verify: loop doesn't crash, proposals generated, A/B test runs, gate decisions produced | — | [D10 §12.2](../../design/ab-test-engine-design.md#123–per-iteration-ab-test-flow) | loop completes; all stages produce output | [#66](https://github.com/deghosal-2026/agent-self-edit/issues/66) · ⬜ |
| 9 | Gate validation test | Feed 5 intentionally bad edits through gate; verify all 5 rejected; each rejection includes correct guardrail failure reason | — | [D10 §12.3](../../design/ab-test-engine-design.md#124–what-the-field-test-validates-about-the-ab-test-engine) | 5/5 bad edits rejected; correct reasons | [#66](https://github.com/deghosal-2026/agent-self-edit/issues/66) · ⬜ |
| 10 | Rollback test | Promote an edit, verify promoted; roll back; verify prompt reverts; verify lineage shows both events | — | [D10 §12.3](../../design/ab-test-engine-design.md#124–what-the-field-test-validates-about-the-ab-test-engine) | promote succeeds; rollback reverts; lineage accurate | [#66](https://github.com/deghosal-2026/agent-self-edit/issues/66) · ⬜ |
| 11 | Zero-LLM test | Full loop with mock analyzer, mock LLM provider, mock scorer; verify: no real LLM calls, all decisions correct, loop completes | — | [D10 §14.1](../../design/ab-test-engine-design.md#142–unit-tests-hermetic-ci-safe) | zero real LLM calls; all decisions valid | [#66](https://github.com/deghosal-2026/agent-self-edit/issues/66) · ⬜ |
| 12 | Concurrency test | 100 traces in rapid succession; verify: trace store handles load, batching triggers correctly, loop processes correctly | — | [D10 §14.2](../../design/ab-test-engine-design.md#143–integration-tests-hermetic-ci-safe) | no data loss; correct ordering | [#67](https://github.com/deghosal-2026/agent-self-edit/issues/67) · ⬜ |
| 13 | Registry integrity test | Create 20 prompt versions; verify: all stored, all hashes correct, no corruption | — | [D10 §14.2](../../design/ab-test-engine-design.md#143–integration-tests-hermetic-ci-safe) | 20/20 versions intact; 0 corruption | [#67](https://github.com/deghosal-2026/agent-self-edit/issues/67) · ⬜ |
| 14 | Guardrail stress test | Generate 100 random edits; run through gate; verify: no crashes, all decisions valid, near-miss rate is rational | — | [D10 §14.1](../../design/ab-test-engine-design.md#142–unit-tests-hermetic-ci-safe) | 0 crashes; 100 valid decisions | [#67](https://github.com/deghosal-2026/agent-self-edit/issues/67) · ⬜ |

#### LLM Tests (Requires API Key, CI-skipped)

| # | Task | Behavior + edge cases | Feature | Design Ref | Verify | Status |
|---|-------|----------------------|---------|------------|--------|--------|
| 15 | Full loop integration test | `agent-self-edit run --once` with real LLM provider; verify: analyzer produces valid proposals, A/B test produces results, gate makes a decision | — | [D10 §14.4](../../design/ab-test-engine-design.md#145–llm-tests-requires-api-key-ci-skipped) | all stages produce valid output | [#68](https://github.com/deghosal-2026/agent-self-edit/issues/68) · ⬜ |
| 16 | 10-iteration improvement test | 10 self-improvement iterations; measure: accuracy improvement per iteration, guardrail pass rate, rejection rate, near-miss rate, cost per iteration; target: 10%+ improvement | — | [D10 §12.1](../../design/ab-test-engine-design.md#122–field-test-structure) | 10+% improvement; cost tracked; no regressions | [#68](https://github.com/deghosal-2026/agent-self-edit/issues/68) · ⬜ |
| 17 | Multi-domain improvement test | Loop on each domain independently; measure: per-domain improvement, guardrail behavior, cost | — | [D10 §12.1](../../design/ab-test-engine-design.md#122–field-test-structure) | improvement in all 3 domains | [#68](https://github.com/deghosal-2026/agent-self-edit/issues/68) · ⬜ |
| 18 | Adversarial edit test | Inject 5 intentionally bad edits via prompt file; verify: all 5 caught by guardrails, none promoted | — | [D10 §12.3](../../design/ab-test-engine-design.md#124–what-the-field-test-validates-about-the-ab-test-engine) | 5/5 bad edits caught; 0 promoted | [#68](https://github.com/deghosal-2026/agent-self-edit/issues/68) · ⬜ |
| 19 | Analyzer quality test | Run analyzer on 10 batches of traces; measure: proposal validity rate, proposal uniqueness, hypothesis quality | — | [D10 §14.4](../../design/ab-test-engine-design.md#145–llm-tests-requires-api-key-ci-skipped) | > 80% validity rate; proposals are unique | [#68](https://github.com/deghosal-2026/agent-self-edit/issues/68) · ⬜ |
| 20 | Cost analysis | Track: cost per iteration, cost per improvement, cost per A/B test, cost per analysis; target: < $0.50 per full iteration | — | [D10 §6](../../design/ab-test-engine-design.md#7–cost-estimation) | cost documented; < $0.50 per iteration | [#68](https://github.com/deghosal-2026/agent-self-edit/issues/68) · ⬜ |

#### Docker Tests

| # | Task | Build (files) | Behavior + edge cases | Feature | Design Ref | Verify | Status |
|---|------|---------------|----------------------|---------|------------|--------|--------|
| 21 | Dockerfile + compose | `Dockerfile` (multi-stage), `docker-compose.yml` | Build stage: pip install; runtime stage: python -m; volume mounts for config, registry, traces | F-14 | [D10 §14.2](../../design/ab-test-engine-design.md#143–integration-tests-hermetic-ci-safe) | image builds; container runs | [#69](https://github.com/deghosal-2026/agent-self-edit/issues/69) · ✅ |
| 22 | Docker smoke test | `tests/test_docker.py` | `docker build . && docker run agent-self-edit --help`; verify image builds and runs; CLI commands work inside container | F-14 | [D10 §14.2](../../design/ab-test-engine-design.md#143–integration-tests-hermetic-ci-safe) | image builds; help works | [#69](https://github.com/deghosal-2026/agent-self-edit/issues/69) · ✅ |
| 23 | Docker integration test | `tests/test_docker.py` | Run full loop (with OMLX real LLM) in Docker container; verify: trace ingestion, analysis, A/B test, promotion gate, LLM I/O capture all work. A/B test bug fixed (#104) — now constructs full candidate prompt. Test asserts ≥2 distinct prompts. | F-14 | [D10 §14.2](../../design/ab-test-engine-design.md#143–integration-tests-hermetic-ci-safe) | 9/9 tests pass, LLM I/O captured to `field-test/v0.1.0/results/docker/omlx/qwen3.5-4b-4bit/` | [#69](https://github.com/deghosal-2026/agent-self-edit/issues/69) · ✅ [#98](https://github.com/deghosal-2026/agent-self-edit/issues/98) · ✅ [#103](https://github.com/deghosal-2026/agent-self-edit/issues/103) · ✅ |

#### A/B Test Fix (Blocker)

| # | Task | Build (files) | Behavior + edge cases | Feature | Design Ref | Verify | Status |
|---|------|---------------|----------------------|---------|------------|--------|--------|
| 23a | Fix A/B test candidate prompt construction | `src/agent_self_edit/cli/run.py` | `run.py:60` passes `proposal.new_text` (fragment) as `prompt_b`. Must construct full candidate prompt: `registry.current_prompt.replace(proposal.old_text, proposal.new_text)` | F-03 | [ab-test-engine-design.md §2.1](../../design/ab-test-engine-design.md#21-inputs) | A/B test produces non-zero deltas, bootstrap CI runs, real winner determined | [#104](https://github.com/deghosal-2026/agent-self-edit/issues/104) · ✅ |
| 23b | Verify A/B test with real distinct prompts | `tests/test_docker.py` | After #104 fix, re-run docker full loop. Verify LLM traffic shows two distinct prompts, non-zero deltas, real statistics | F-03 | [ab-test-engine-design.md §3](../../design/ab-test-engine-design.md#3-the-task-runner) | traffic log shows prompt A ≠ prompt B, deltas ≠ 0 | [#104](https://github.com/deghosal-2026/agent-self-edit/issues/104) · ✅ |

#### Analysis & Report

| # | Task | Deliverable | Acceptance |
|---|-------|-------------|------------|
| 24 | Field test report | `docs/field-test/v0.1.0/FIELD_TEST_REPORT.md` | All results documented: baseline, per-iteration, guardrail validation, rollback, Docker, cost, non-LLM vs LLM comparison, recommendations |
| 25 | Improvement trend analysis | Charts + tables: accuracy per iteration, guardrail outcomes, cost | Improvement visible; target: 10%+ over 10 iterations |
| 26 | Guardrail effectiveness analysis | False positive rate (good edits rejected), false negative rate (bad edits promoted) | FP < 1%, FN < 0.1% |
| 27 | Test matrix summary | Table: all tests run, pass/fail, date, environment (non-LLM/LLM/Docker) | All tests documented |

### M10 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Non-LLM tests | 100% pass in CI | CI run |
| LLM tests | all pass manually | manual run |
| Improvement | 10%+ over 10 iterations | improvement trend |
| Guardrail FP rate | < 1% (good edits rejected) | guardrail analysis |
| Guardrail FN rate | < 0.1% (bad edits promoted) | adversarial test |
| Docker tests | 100% pass | Docker CI test |
| Cost per iteration | < $0.50 | cost analysis |
| Coverage | > 92% | `--cov-fail-under=92` |

### M10 Out of Scope

- Fleet-wide testing (v0.4.0), production deployment guide (v1.0.0), real-agent integration testing (v0.3.0)

### M10 Exit Gate

- [ ] Field test plan reviewed and committed
- [ ] Synthetic task corpus created (50 tasks across 3 domains)
- [ ] Baseline measurement completed
- [ ] Non-LLM tests: all pass (trace generation, dry-run loop, gate validation, rollback, zero-LLM, concurrency, registry stress, guardrail stress)
- [ ] LLM tests: full loop integration, 10-iteration improvement, adversarial edits, analyzer quality, cost analysis (#100)
- [x] Docker tests: build, smoke, integration (full loop against OMLX — #98, #103, #104 closed)
- [x] A/B test fix (#104): construct full candidate prompt, verify 2 distinct prompts — closed
- [ ] LLM field tests (#100): 10-iteration improvement, adversarial, cost analysis
- [ ] Field test report written with all results (#101)
- [ ] Improvement measured (target: 10%+ over 10 iterations)
- [ ] Guardrails catch 100% of injected bad edits (real LLM — #107)
- [ ] Zero bad edits promoted in any test (real LLM — #107)
- [ ] Cost documented (target: < $0.50 per iteration) (#107)
- [ ] Ruff clean (#105), mypy strict clean (#106), all tests pass, coverage > 92%
- [ ] **Design docs authored:** D10 (field-test-plan) (#93)
- [ ] Cleanup: run_traces.py wrong tool (#95), scoring ignores trace.success (#96), duplicate task_id (#97), stale run_docker_field_test.py (#99)

**Dependency:** M9 (CLI). **Produces for M11+:** field test results, synthetic corpus, validation scripts, Docker setup.

### M10 Design Gaps Found (WBS vs Ticket Audit, 2026-08-30)

| # | Gap | WBS requirement | Current state | Ticket | Fix |
|---|-----|----------------|---------------|--------|-----|
| G-1 | D10 field test plan design doc | "Design docs authored: D10 (field-test-plan)" | File exists at `docs/field-test/v0.1.0/field-test-plan.md` | [#93](https://github.com/deghosal-2026/agent-self-edit/issues/93) · ⬜ | Review and confirm D10 |
| G-2 | Field test report deliverables | WBS §24–§27: report, improvement trend, FP/FN analysis, test matrix | Not written | [#94](https://github.com/deghosal-2026/agent-self-edit/issues/94), [#101](https://github.com/deghosal-2026/agent-self-edit/issues/101) · ⬜ | Write after LLM field tests complete |
| G-3 | LLM field tests not implemented | WBS rows 15-20: 10-iteration, adversarial, cost | No implementation | [#100](https://github.com/deghosal-2026/agent-self-edit/issues/100) · ⬜ | Create script to run N iterations against real LLM |
| G-4 | run_traces.py is wrong tool | Should run self-edit loop, not generic eval | Eval runner only | [#95](https://github.com/deghosal-2026/agent-self-edit/issues/95) · ⬜ | Replace or delete |
| G-5 | Scoring ignores trace.success | Real traces always "pass" | Label mode too lenient | [#96](https://github.com/deghosal-2026/agent-self-edit/issues/96) · ⬜ | Evaluate against trace.success |
| G-6 | Duplicate task_id in observatory traces | 336 traces all `s_BlipZorp_000000` | import_real_traces.py bug | [#97](https://github.com/deghosal-2026/agent-self-edit/issues/97) · ⬜ | Generate unique IDs |
| G-7 | run_docker_field_test.py stale | Duplicates test_docker.py | Old config, no env vars | [#99](https://github.com/deghosal-2026/agent-self-edit/issues/99) · ⬜ | Delete or rewrite |
| G-8 | Ruff lint errors | 13 errors in test_docker.py | Exit gate requires clean | [#105](https://github.com/deghosal-2026/agent-self-edit/issues/105) · ⬜ | ruff check --fix + manual |
| G-9 | Mypy type errors | 5 errors in propose.py, run.py | Exit gate requires clean | [#106](https://github.com/deghosal-2026/agent-self-edit/issues/106) · ⬜ | Add type annotations |
| G-10 | Guardrail FP/FN + cost not measured vs real LLM | Exit gate: 100% caught, <\$0.50/iter | Only mock-tested | [#107](https://github.com/deghosal-2026/agent-self-edit/issues/107) · ⬜ | Part of #100 LLM field tests |
| G-11 | Docker test: no per-trace latency/token assertions | Silent failures not caught | Only checks ≥2 distinct prompts | [#108](https://github.com/deghosal-2026/agent-self-edit/issues/108) · ⬜ | Add latency > 0 and tokens > 0 assertions |
| G-12 | Docker test: all 10 seeded traces identical | Non-tie A/B unlikely with same input | All use same task_input | [#109](https://github.com/deghosal-2026/agent-self-edit/issues/109) · ⬜ | Use varied inputs from classification task set |
| G-13 | Docker test: accepts tie without delta check | A/B tie silently accepted | No delta assertion | [#110](https://github.com/deghosal-2026/agent-self-edit/issues/110) · ⬜ | Assert non-zero deltas OR document tie as expected |