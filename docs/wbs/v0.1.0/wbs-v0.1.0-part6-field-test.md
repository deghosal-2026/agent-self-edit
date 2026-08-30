# WBS — AgentSelfEdit v0.1.0 Part 6: Field Test

> Part of the v0.1.0 release. See [index](wbs-v0.1.0-index.md) for milestone overview.
>
> **Milestone:** M10 (Field Test)
> **Dependency:** M10 depends on M9 (CLI) — needs the CLI to run the loop
> **Issue Range:** #63–#68

## M10 — Field Test (#63–#68)

**Goal:** Validate the loop end-to-end on a synthetic task suite. Prove improvement is measurable and guardrails work. Test with and without LLM calls.

### Design

| Task | Description | Deliverable |
|---|---|---|
| D10.1 | Field test plan | `docs/field-test/v0.1.0/field-test-plan.md` — test objectives, synthetic task suite design, baseline measurement methodology, improvement measurement methodology, guardrail validation methodology, rollback validation, cost analysis, non-LLM vs LLM testing strategy |
| D10.2 | Field test corpus | `docs/field-test/v0.1.0/corpus/` — task sets, expected outputs, scorer configurations |
| D10.3 | Test results template | `docs/field-test/v0.1.0/FIELD_TEST_REPORT.md` — template for the final report |

### Build — Field Test Corpus

| Task | Description | Deliverable |
|---|---|---|
| M10.1 | Domain 1 task set: classification | 20 tasks. Input: text string. Expected output: category label. Scorer: ExactMatch. Failures: ambiguous boundary cases, missing categories, multi-label inputs. |
| M10.2 | Domain 2 task set: extraction | 15 tasks. Input: text string. Expected output: structured fields. Scorer: Contains (key fields present). Failures: missing fields, wrong format, extra fields. |
| M10.3 | Domain 3 task set: generation | 15 tasks. Input: topic + constraints. Expected output: generated text. Scorer: LLMJudge (quality, relevance, tone). Failures: off-topic, wrong tone, missing constraints. |
| M10.4 | Held-out task set | 30 tasks (10 from each domain). Used for A/B testing. Seeded with specific failure modes. |
| M10.5 | Training task set | 20 tasks (remaining from each domain). Used for generating traces. |
| M10.6 | Seeded failure prompts | 10 prompts with known failure modes. Each prompt fails on 3-5 specific tasks. Used to verify the loop detects and fixes failures. |
| M10.7 | Adversarial test cases | 5 intentionally bad edits. Each edit: improves one task type but degrades another. Used to verify guardrails catch tradeoff failures. |

### Build — Non-LLM Tests (Hermetic, CI-safe)

| Task | Description | Deliverable |
|---|---|---|
| M10.8 | Trace generation script | `scripts/generate_traces.py` — generates synthetic traces from a task set and prompt. Runs offline (no LLM). Produces: success traces, failure traces, mixed batches. |
| M10.9 | Baseline measurement | Run baseline prompt against held-out set. Measure: accuracy, per-task scores, cost. Target: > 70% baseline accuracy. |
| M10.10 | Dry-run loop test | Run `agent-self-edit run --dry-run --once` with mock analyzer. Verify: loop doesn't crash, proposals are generated, A/B test runs, gate decisions are produced. |
| M10.11 | Gate validation test | Feed 5 intentionally bad edits through the gate. Verify all 5 are rejected. Verify each rejection includes the correct guardrail failure reason. |
| M10.12 | Rollback test | Promote an edit, verify it's promoted. Roll back. Verify prompt reverts. Verify lineage shows both events. |
| M10.13 | Zero-LLM test | Run the full loop with mock analyzer, mock LLM provider, mock scorer. Verify: no real LLM calls, all decisions are correct, loop completes. |
| M10.14 | Concurrency test | Send 100 traces in rapid succession. Verify: trace store handles load, batching triggers correctly, loop processes correctly. |
| M10.15 | Registry integrity test | Create 20 prompt versions. Verify: all versions are stored, all hashes are correct, no corruption. |
| M10.16 | Guardrail stress test | Generate 100 random edits. Run through gate. Verify: no crashes, all decisions are valid, near-miss rate is rational. |

### Build — LLM Tests (Requires API Key, CI-skipped)

| Task | Description | Deliverable |
|---|---|---|
| M10.17 | Full loop integration test | Run `agent-self-edit run --once` with real LLM provider. Verify: analyzer produces valid proposals, A/B test produces results, gate makes a decision. |
| M10.18 | 10-iteration improvement test | Run 10 self-improvement iterations. Measure: accuracy improvement per iteration, guardrail pass rate, rejection rate, near-miss rate, cost per iteration. |
| M10.19 | Multi-domain improvement test | Run the loop on each domain independently. Measure: per-domain improvement, per-domain guardrail behavior, per-domain cost. |
| M10.20 | Adversarial edit test | Inject 5 intentionally bad edits via the prompt file. Verify: all 5 are caught by guardrails, none are promoted. |
| M10.21 | Analyzer quality test | Run analyzer on 10 batches of traces. Measure: proposal validity rate, proposal uniqueness, hypothesis quality (LLM-judged). |
| M10.22 | Cost analysis | Track: cost per iteration, cost per improvement, cost per A/B test, cost per analysis. Target: < $0.50 per full iteration. |

### Build — Docker Tests

| Task | Description | Deliverable |
|---|---|---|
| M10.23 | Dockerfile | Multi-stage Dockerfile. Build stage: pip install. Runtime stage: python -m agent_self_edit. |
| M10.24 | Docker compose | `docker-compose.yml` — agent-self-edit service, volume mounts for config, registry, traces. |
| M10.25 | Docker smoke test | `docker build . && docker run` — verify image builds and runs. CLI commands work inside container. |
| M10.26 | Docker integration test | Run full loop in Docker container. Verify: trace ingestion, analysis, A/B test, promotion gate all work. |
| M10.27 | Docker CI test | `tests/test_docker.py` — build image, run container, run CLI commands, verify output. Runs in CI. |

### Analysis

| Task | Description | Deliverable |
|---|---|---|
| M10.28 | Field test report | `docs/field-test/v0.1.0/FIELD_TEST_REPORT.md` — baseline, per-iteration results, guardrail validation, rollback validation, Docker test results, cost analysis, non-LLM vs LLM comparison, recommendations |
| M10.29 | Improvement trend analysis | Chart: accuracy per iteration. Table: per-iteration improvement, guardrail outcomes, cost. |
| M10.30 | Guardrail effectiveness analysis | Table: all guardrail check results across all tests. False positive rate (good edits rejected). False negative rate (bad edits promoted). |
| M10.31 | Cost analysis | Table: cost per iteration, cost per improvement, total cost. Chart: cumulative cost vs cumulative improvement. |
| M10.32 | Test matrix summary | Table: all tests run, pass/fail, date, environment (non-LLM/LLM/Docker). |

### Tests

| Task | Description | Files |
|---|---|---|
| T10.1 | Test trace generation script | `tests/test_field_test.py` — generates traces, traces are valid, traces include failures, traces include successes |
| T10.2 | Test baseline measurement | `tests/test_field_test.py` — baseline runs without errors, scores are recorded, per-task scores are accurate |
| T10.3 | Test dry-run loop | `tests/test_field_test.py` — loop completes, proposals generated, A/B test runs, gate produces decisions |
| T10.4 | Test Docker integration | `tests/test_docker.py` — image builds, container runs, CLI commands work, full loop runs in container |
| T10.5 | Test zero-LLM mode | `tests/test_field_test.py` — no real LLM calls made, all decisions correct, loop completes |
| T10.6 | Test concurrency | `tests/test_field_test.py` — 100 traces in rapid succession, no data loss, batching works |
| T10.7 | Test registry stress | `tests/test_field_test.py` — 20 versions, all correct hashes, no corruption |
| T10.8 | Test guardrail stress | `tests/test_field_test.py` — 100 random edits, no crashes, valid decisions, rational near-miss rate |

### Documentation

| Task | Description | Deliverable |
|---|---|---|
| M10.DOC1 | Field test report | Write `docs/field-test/v0.1.0/FIELD_TEST_REPORT.md` with all results |
| M10.DOC2 | Performance benchmark | Create `docs/explanation/performance.md` — latency, throughput, cost benchmarks from field test |
| M10.DOC3 | Troubleshooting guide | Create `docs/explanation/troubleshooting.md` — common issues, solutions, debugging tips learned from field test |
| M10.DOC4 | Update WBS index | Update `docs/wbs/v0.1.0/wbs-v0.1.0-index.md` with M10 status, issue links, exit gate results |

### M10 Exit Gate

- [ ] Field test plan reviewed and committed
- [ ] Synthetic task corpus created (50 tasks across 3 domains)
- [ ] Baseline measurement completed
- [ ] Non-LLM tests: all pass (trace generation, dry-run loop, gate validation, rollback, zero-LLM, concurrency, registry stress, guardrail stress)
- [ ] LLM tests: full loop integration, 10-iteration improvement, adversarial edits, analyzer quality, cost analysis
- [ ] Docker tests: build, smoke, integration, CI
- [ ] Field test report written with all results
- [ ] Improvement measured (target: 10%+ over 10 iterations)
- [ ] Guardrails catch 100% of injected bad edits
- [ ] Zero bad edits promoted in any test
- [ ] Cost documented (target: < $0.50 per iteration)
- [ ] Ruff clean, mypy strict clean
- [ ] All tests pass: `pytest` → 0 failures
- [ ] Coverage > 92%: `pytest --cov=agent_self_edit --cov-fail-under=92`