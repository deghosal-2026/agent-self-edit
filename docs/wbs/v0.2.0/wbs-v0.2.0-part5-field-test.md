# WBS — AgentSelfEdit v0.2.0 Part 5: Field Test

> **Milestone covered:** M8 (Field Test)
> **Source:** v0.1.0 field test — classification-only; v0.2.0 requires multi-domain, adversarial, real-trace, and hermetic validation
> **Dependency:** M8 depends on M2–M7 — needs scorer selection (M2), staged analyzer (M3), model roles (M4), expanded corpora (M5), reliable trace processing (M6), CI/CD and fixed Docker (M7)
> **Issue Range:** #172–#179, #198–#204

---

## Milestone 8: Field Test (#172–#179)

**Objective:** Validate v0.2.0 end-to-end across all supported domains. Prove multi-domain field test execution, adversarial edit rejection with real LLMs, real-trace ingestion and analyzer quality, LLM integration across model roles, hermetic CI test suite, and comprehensive field test report.

### M8 Design Documents

- **D7 — Field test plan v0.2.0** (`docs/field-test/v0.2.0/field-test-plan.md`): multi-domain test objectives, corpus structure, benchmark role definitions, success criteria per domain, LLM arm configuration, hermetic vs LLM-based test matrix, Docker test plan.

### M8 Task Checklist

#### Design & Planning

| # | Issue | Deliverable | Acceptance |
|---|-------|-------------|------------|
| 1 | Field test plan design doc | `docs/field-test/v0.2.0/field-test-plan.md` | Test objectives for classification, extraction, generation, mixed-domain, adversarial suites; corpus structure; success criteria per domain; LLM arm config; hermetic vs LLM test matrix; Docker test plan | [#172](https://github.com/deghosal-2026/agent-self-edit/issues/172) | ✅ |

#### Multi-Domain Field Test Suites

| # | Issue | Deliverable | Acceptance |
|---|-------|-------------|------------|
| 2 | Multi-domain field test | Classification, extraction, generation, mixed-domain suites; per-suite result artifacts and reports | [#173](https://github.com/deghosal-2026/agent-self-edit/issues/173) | ✅ All 4 suites execute independently; correct scorer per suite; results captured |
| 3 | Adversarial edit field test | 5+ intentionally bad edits injected and verified rejected; check-specific failure assertions; FP/FN analysis; stress test 100+ random edits | [#174](https://github.com/deghosal-2026/agent-self-edit/issues/174) | ✅ 5/5 bad edits caught; 0 FN; 100+ random edits no crashes |
| 4 | Real-trace ingestion and analyzer quality | Real-trace corpus ingested; analyzer proposal quality measured; comparison with synthetic traces; gold corpus with human-labeled failures | [#175](https://github.com/deghosal-2026/agent-self-edit/issues/175) | ✅ Analyzer produces valid proposals on real traces; gold corpus operationalized |

#### Docker Field Test

| # | Issue | Deliverable | Acceptance |
|---|-------|-------------|------------|
| 5 | Docker field test with multi-domain support | Docker build; full-loop test for extraction, generation, adversarial; container-based LLM traffic capture; test summary report | [#176](https://github.com/deghosal-2026/agent-self-edit/issues/176) | All suites run in Docker; traffic captured; report generated | ✅ |
| 5a | Extraction domain Docker test | `test_docker_run_extraction` — uses extraction.yaml, StructuredExtractionScorer | [#201](https://github.com/deghosal-2026/agent-self-edit/issues/201) | Scorer auto-selected; all stages produce output; LLM I/O captured | ✅ |
| 5b | Generation domain Docker test with judge role | `test_docker_run_generation` — uses generation.yaml, LLMJudgeScorer, judge_role | [#202](https://github.com/deghosal-2026/agent-self-edit/issues/202) | Judge role wired; LLMJudgeScorer selected; all stages produce output | ✅ |
| 5c | Staged analyzer Docker test | `test_docker_run_staged_analyzer` — staged analyzer pipeline in container | [#203](https://github.com/deghosal-2026/agent-self-edit/issues/203) | Staged analyzer produces proposals; rejection context populated | ✅ |
| 5d | Update existing Docker tests for v0.2.0 paths | Update corpus paths, result paths, model role configs in test_docker.py | [#204](https://github.com/deghosal-2026/agent-self-edit/issues/204) | All paths point to field-test/corpus/ and field-test/v0.2.0/ | ✅ |

#### LLM Integration Tests

| # | Issue | Deliverable | Acceptance |
|---|-------|-------------|------------|
| 6 | LLM integration tests across all supported models | 4B executor + 4B analyzer suite; 4B executor + 9B analyzer suite (if available); proposal quality, gate decisions, accuracy comparison; cost/latency comparison | [#177](https://github.com/deghosal-2026/agent-self-edit/issues/177) | ✅ Both model role configurations tested; comparison documented |

#### Hermetic CI Test Suite

| # | Issue | Deliverable | Acceptance |
|---|-------|-------------|------------|
| 7 | Non-LLM hermetic test suite for CI | Baseline measurement (mock provider); dry-run loop (mock analyzer); gate validation 5/5 bad edits; rollback test; zero-LLM full loop; concurrency 100+ traces; registry integrity 20+ versions; guardrail stress 100+ edits; real-trace replay 50+ traces | [#178](https://github.com/deghosal-2026/agent-self-edit/issues/178) | ✅ All hermetic tests pass in CI; zero LLM calls; 100% CI-safe |

#### Report & Deliverables

| # | Issue | Deliverable | Acceptance |
|---|-------|-------------|------------|
| 8 | Field test report and deliverables | `docs/field-test/v0.2.0/FIELD_TEST_REPORT.md` | Per-suite report; aggregate improvement metrics; FP/FN analysis per domain; cost-per-iteration breakdown; reproducibility evidence (artifacts, seeds, configs); test matrix pass/fail; v0.1.0 vs v0.2.0 comparison; M8 exit gate status | [#179](https://github.com/deghosal-2026/agent-self-edit/issues/179) | ✅ |

### M8 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Multi-domain suites | 4 suites execute with correct scoring | Field test run |
| Adversarial rejection | 5/5 bad edits caught; 0 FN | Adversarial test |
| Real-trace ingestion | Analyzer produces valid proposals on real traces | Real-trace test |
| Docker tests | All suites run in Docker; traffic captured | Docker test run |
| Hermetic CI tests | All pass in CI; zero LLM calls | CI run |
| Model role comparison | 4B+4B and 4B+9B (if available) tested | Comparison report |
| Report completeness | All deliverables in report | Manual review |
| Coverage | > 92% | `--cov-fail-under=92` |

### M8 Out of Scope

- Fleet-wide testing (v0.4.0), production deployment guide (v1.0.0), v0.3.0 features

### M8 Exit Gate

- [x] Field test plan v0.2.0 authored and reviewed
- [x] Docker field test covers classification, extraction, generation, staged analyzer, propose
- [x] Docker test plan, summary, and run report written
- [x] Corpus readiness: generation rubrics, mixed-domain expansion, real-trace gold corpus
- [x] Classification, extraction, generation, mixed-domain suites executed (LLM field tests)
- [x] Adversarial edits: 5/5 rejected; FP/FN analysis complete
- [x] Real-trace ingestion validated with analyzer quality report
- [x] LLM integration tests across model role combinations
- [x] Hermetic CI test suite runs in CI; zero LLM calls
- [x] Comprehensive field test report written (#179)
- [x] Ruff clean, mypy strict clean, all tests pass, coverage > 92%
- [x] **Design docs authored:** D7 (field-test-plan-v0.2.0)

**Dependency:** M2–M7. **Produces for M9:** field test results, multi-domain evidence, hermetic CI tests.