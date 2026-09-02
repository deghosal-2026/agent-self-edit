# Field Test Plan — AgentSelfEdit v0.2.0

> Comprehensive field test plan covering v0.1.0 baseline tests, new v0.2.0 multi-domain suites, model-role separation, staged analyzer, and Docker integration. This document is the single source of truth for all v0.2.0 field test activities.

## 1. What This Project Does

AgentSelfEdit is a sidecar that observes execution traces and rewrites its own system prompt through a closed loop:

```
Agent executes task ──▶ Execution trace stored (SQLite)
                                │
                                ▼
                      Feedback Analyzer (LLM)
                      reviews traces, proposes concrete edits,
                      each with a written hypothesis
                                │
                                ▼
       ─────────────────────  A/B Test Engine  ─────────────────────
         candidate edit vs current prompt on a held-out task set:
         win rate, bootstrap confidence interval, effect size,
         permutation p-value, per-task breakdown
       ────────────────────────────────────────────────────────────
                                │
                                ▼
                Promotion Gate (deterministic checks)
                1. Sample floor     4. Frozen sections
                2. Effect size      5. Edit-distance limit
                3. Confidence p-val 6. Drift detection
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
          Promoted         Near-miss        Rejected
     prompt updated in     logged for       archived with
     versioned Registry    human review     full reasoning
```

The field test must prove this loop works end-to-end against a real LLM, across multiple domains and model roles.

## 2. What Changed in v0.2.0

| Change | Impact on field test |
|--------|----------------------|
| **Model role separation** (executor/analyzer/judge) | Field test must verify each role uses its own provider/model config |
| **Multi-domain corpora** (extraction, generation, mixed) | Full loop must be tested on non-classification benchmarks |
| **Staged analyzer** (4-stage pipeline) | Field test must run with staged mode and verify structured proposals |
| **Structured extraction scorer** | Extraction benchmark auto-selects the correct scorer |
| **LLMJudgeScorer with rubrics** | Generation benchmark uses judge role for scoring |
| **Scorer consistency enforcement** | Manifest-based scorer selection validated during field test |
| **Row-safe trace ack** (in-flight reservation) | Reliability under concurrent processing |
| **Promotion-seeking corpus** | Larger A/B set (40 tasks) enables statistical significance |
| **Sentinel benchmark** | Regression detection on previously-correct tasks |
| **Rejection-aware analyzer** | Structured feedback from prior A/B and gate outcomes |
| **Statistical ceiling analysis** | Task set sizing is deliberate, not accidental |
| **Oracle drift guard** | Acceptance cases isolated from the self-editing boundary |

## 3. Test Objectives

1. **Loop closure** — can the full loop (trace → analyze → A/B test → gate → promote) run end-to-end with mock providers (hermetic) and real LLM (OMLX)?
2. **Multi-domain execution** — does the loop work on classification, extraction, and generation corpora independently?
3. **Model role separation** — do executor, analyzer, and judge each use their own provider/config when configured?
4. **Staged analyzer** — does the 4-stage pipeline produce structured proposals?
5. **Improvement** — does the loop measurably improve accuracy over 10 iterations on the promotion-seeking corpus? Target: detectable improvement.
6. **Guardrail effectiveness** — do guardrails catch 100% of injected bad edits? (FN < 0.1%, FP < 1%)
7. **Regression sentinel** — does the sentinel benchmark catch edits that break previously-correct tasks?
8. **Rollback** — does rollback revert the prompt and preserve lineage?
9. **Cost** — is cost per iteration < $0.50?
10. **Docker** — does the image build and run the full loop against OMLX inside a container for all domains?
11. **LLM I/O capture** — are all LLM requests and responses written to disk for debuggability?
12. **Rejection awareness** — does the analyzer produce different proposals after receiving structured rejection feedback?

## 4. LLM Arms

All LLM-based tests support two arms, configurable via environment variables:

| Arm | Provider | Endpoint | Model | Key env var |
|-----|----------|----------|-------|-------------|
| Local | `openai` | `http://localhost:8000/v1` | `Qwen3.5-4B-4bit` | `OMLX_KEY` |
| Local (analyzer) | `openai` | `http://localhost:8000/v1` | `Qwen3.5-9B-MLX-4bit` | `OMLX_KEY` |

For model role separation tests, `executor_role`, `analyzer_role`, and `judge_role` can be configured independently.

## 5. Corpus Structure

### 5.1 Synthetic Corpus (180+ tasks)

All synthetic corpora live under `field-test/corpus/synthetic/`.

| File | Tasks | Scorer | Benchmark role | Description |
|------|-------|--------|----------------|-------------|
| `classification-single-label.yaml` | 20 | `SingleLabelScorer` | `promotion_ab` | Strict single-label classification |
| `classification-multi-label.yaml` | 5 | `ExactSetScorer` | `promotion_ab` | Multi-label (unordered set) |
| `classification-ambiguous.yaml` | 5 | `SingleLabelScorer` | `promotion_ab` | Ambiguous → "other" |
| `classification-boundary.yaml` | 20 | mixed | `promotion_ab` | Boundary-heavy, urgent/security/technical ambiguity |
| `classification-promotion.yaml` | 40 | `SingleLabelScorer` | `promotion_ab` | Tasks designed to reach significance with small edits |
| `classification-held-out.yaml` | 25 | mixed | `held_out` | Held-out generalization set |
| `sentinel.yaml` | 20 | `SingleLabelScorer` | `regression_sentinel` | Previously-correct tasks, catch regressions |
| `extraction.yaml` | 25 | `StructuredExtractionScorer` | `promotion_ab` | Structured field extraction |
| `generation.yaml` | 15 | `LLMJudgeScorer` | `promotion_ab` | Rubric-backed generation with judge role |
| `mixed-domain.yaml` | 10 | mixed | `promotion_ab` | Cross-domain tasks (to be expanded to 30+) |

Additional:
- **Seeded failure prompts**: `seeded-prompts/seeded-prompts.yaml` — 15 prompts with known failure modes
- **Adversarial edits**: `adversarial-edits/adversarial-edits.yaml` — 8 intentionally bad edits

### 5.2 Real-Life Corpus (770+ traces)

All real traces live under `field-test/corpus/real-traces/`.

| Source | Traces | Description |
|--------|--------|-------------|
| AgentObservatory | 336 | Real LLM telemetry from Qwen 4B/9B models |
| EvalForge | 34 | Real agent scenario failures across 12 frameworks |
| HuggingFace (open-agent-traces) | 150 | 10-domain multi-agent traces |
| HuggingFace (customer-support) | 50 | Customer support agent traces |
| HuggingFace (pi coding agent) | 200 | Real human-AI coding agent sessions |

### 5.3 Directory Layout

```
field-test/
├── corpus/
│   ├── synthetic/
│   │   ├── classification-single-label.yaml
│   │   ├── classification-multi-label.yaml
│   │   ├── classification-ambiguous.yaml
│   │   ├── classification-boundary.yaml
│   │   ├── classification-promotion.yaml
│   │   ├── classification-held-out.yaml
│   │   ├── sentinel.yaml
│   │   ├── extraction.yaml
│   │   ├── generation.yaml
│   │   ├── mixed-domain.yaml
│   │   ├── seeded-prompts/
│   │   │   └── seeded-prompts.yaml
│   │   └── adversarial-edits/
│   │       └── adversarial-edits.yaml
│   └── real-traces/
│       ├── agent-observatory-traces.jsonl  (336)
│       ├── evalforge-failures.jsonl         (34)
│       ├── hf-open-agent-traces.jsonl       (150)
│       ├── hf-customer-support-traces.jsonl  (50)
│       ├── hf-pi-coding-agent-traces.jsonl  (200)
│       └── README.md
├── scripts/
│   ├── run_improvement_loop.py
│   ├── generate_traces.py
│   ├── import_real_traces.py
│   ├── download_hf_traces.py
│   ├── download_pi_traces.py
│   ├── run_docker_tests.py
│   └── README.md
├── v0.1.0/
│   └── results/          ← historical results (preserved)
└── v0.2.0/
    └── results/          ← v0.2.0 field test results
```

## 6. Baseline Measurement

1. Pick a baseline prompt (e.g. "You are a helpful classification assistant.").
2. Run `run_ab_test(baseline, baseline, task_set, llm, scorer)` → n_trials.
3. Record: accuracy, per-task scores, cost.
4. Target: > 70% baseline accuracy on classification, extraction, and generation corpora independently.

## 7. Multi-Domain Improvement Measurement

### 7.1 Classification

1. Run 10 self-improvement iterations via `agent-self-edit run --once` on classification corpus.
2. Use the promotion-seeking corpus (40 tasks) for A/B to maximize statistical power.
3. Use the held-out set (25 tasks) for generalization measurement.
4. Run sentinel benchmark (20 tasks) after each iteration to detect regressions.
5. Record: accuracy, guardrail decisions, cost, A/B test results, LLM I/O, sentinel regressions.

### 7.2 Extraction

1. Same loop on extraction corpus (25 tasks).
2. Verify `StructuredExtractionScorer` is auto-selected.
3. Same metrics as classification.

### 7.3 Generation

1. Same loop on generation corpus (15 tasks).
2. Configure `judge_role` with same or different model.
3. Verify `LLMJudgeScorer` is auto-selected with rubric metadata.
4. Same metrics as classification.

### 7.4 Mixed-Domain

1. Loop on mixed-domain corpus (after expansion to 30+ tasks).
2. Verify correct scorer selection per task type.
3. Same metrics as classification.

## 8. Model Role Separation Tests

### 8.1 Same role config

All three roles use the same model (Qwen3.5-4B-4bit). Verify the loop works identically to single-provider mode.

### 8.2 Separated role config

Configure:
- `executor_role`: Qwen3.5-4B-4bit (fast task execution)
- `analyzer_role`: Qwen3.5-9B-MLX-4bit (stronger model for analysis)
- `judge_role`: Qwen3.5-4B-4bit (same as executor)

Verify:
- Analyzer calls go to the 9B model
- Task execution calls go to the 4B model
- Judge calls go to the 4B model
- Proposal quality is measurably different from same-role mode

## 9. Staged Analyzer Tests

1. Run the full loop with `analyze_batch(..., staged=True)` (default in v0.2.0).
2. Verify the staged analyzer produces structured failure patterns.
3. Verify proposals are more minimal than single-pass mode.
4. Verify rejection context is populated and fed into subsequent iterations.

## 10. Guardrail Validation

- **False positive test:** Inject 5 good edits. Verify < 1% rejected (FP < 1%).
- **False negative test:** Inject 5 intentionally bad edits (adversarial). Verify 100% caught (FN < 0.1%).
- **Failure-mode-specific tests:** Verify each check (frozen sections, missing old_text, excessive edit distance, insufficient statistics, empty replacement) produces the correct failure.
- **Stress test:** Run 100 random edits through gate. Verify 0 crashes, all decisions valid.

## 11. Regression Sentinel Validation

1. Run sentinel benchmark (20 tasks) after each proposed edit.
2. Verify sentinel regressions are reported explicitly.
3. Verify edits that fix hard tasks but break easy ones are caught.

## 12. Rollback Validation

1. Promote an edit.
2. Roll back via `agent-self-edit rollback <version> --reason "test"`.
3. Verify prompt reverts.
4. Verify lineage shows both promote and rollback events.

## 13. Rejection-Aware Analyzer

1. Run the full loop for multiple iterations.
2. Verify that after a gate rejection, the next iteration produces a different proposal.
3. Verify rejection context includes which tasks were fixed, which regressed, and which gate check failed.
4. Verify the analyzer stops proposing the same edit after repeated rejection.

## 14. LLM I/O Capture

Every LLM call (analyzer + A/B test + judge) is captured to disk for debuggability:

- **Traffic log:** `AGENT_SELF_EDIT_LLM_LOG` env var → JSONL append-mode file
- **Each entry:** `{model, base_url, messages, temperature, response, usage, latency_ms}`
- **Results JSON:** structured per-test report with meta + per-trace LLM I/O and scoring

Results are stored under `field-test/v0.2.0/results/<provider>/<model>/`.

## 15. Test Matrix

### 15.1 Hermetic (CI-safe, mock LLM)

| Test | CI | LLM | Pass condition | Status |
|------|----|-----|----------------|--------|
| Baseline measurement | ✅ | mock | > 70% accuracy | ✅ |
| Dry-run loop | ✅ | mock | loop completes, all stages | ✅ |
| Gate validation (5/5 rejection) | ✅ | mock | 5/5 bad edits rejected with correct failure modes | ✅ |
| Failure-mode-specific: frozen section | ✅ | mock | Rejected by frozen_sections check | ✅ |
| Failure-mode-specific: missing old_text | ✅ | mock | Rejected by frozen_sections/validation | ✅ |
| Failure-mode-specific: excessive edit distance | ✅ | mock | Rejected by edit_distance check | ✅ |
| Rollback test | ✅ | mock | prompt reverts, lineage shows | ✅ |
| Zero-LLM full loop | ✅ | mock | no real LLM calls, loop completes | ✅ |
| Concurrency | ✅ | mock | 100 traces, no data loss | ✅ |
| Registry integrity | ✅ | mock | 20 versions, 0 corruption | ✅ |
| Guardrail stress | ✅ | mock | 100 random edits, 0 crashes | ✅ |
| Real trace replay | ✅ | mock | 50 real traces validate + ingest | ✅ |
| Sentinel corpus load | ✅ | mock | 20 tasks load and validate | ✅ |
| Scorer consistency | ✅ | mock | Mixed scorer sets fail fast | ✅ |
| Staged analyzer (mock) | ✅ | mock | Staged analyzer produces proposals | ✅ |

### 15.2 LLM-based (OMLX, CI-skipped)

| Test | LLM | Pass condition | Status | Issue |
|------|-----|----------------|--------|-------|
| Classification full loop | OMLX 4B | All stages produce valid output, LLM I/O captured | ⬜ | #173 |
| Extraction full loop | OMLX 4B | StructuredExtractionScorer used, all stages produce output | ⬜ | #173 |
| Generation full loop | OMLX 4B | LLMJudgeScorer used, judge role wired, all stages produce output | ⬜ | #173 |
| Mixed-domain full loop | OMLX 4B | Correct scorer per task type, all stages produce output | ⬜ | #173 |
| Same role config | OMLX 4B | Loop works identically to single-provider mode | ⬜ | #177 |
| Separated role config | OMLX 4B+9B | Each role uses its own model | ⬜ | #177 |
| Staged analyzer full loop | OMLX 4B | Staged analyzer produces structured proposals | ⬜ | #203 |
| Rejection-aware iterations | OMLX 4B | Different proposals after rejection feedback | ⬜ | #173 |
| 10-iteration improvement | OMLX 4B | Detectable improvement on promotion-seeking corpus | ⬜ | #173 |
| Adversarial edit test | OMLX 4B | 5/5 bad edits caught | ⬜ | #174 |
| Sentinel regression test | OMLX 4B | Regressions detected and reported | ⬜ | #173 |
| Real-trace ingestion | OMLX 4B | Analyzer produces valid proposals on real traces | ⬜ | #175 |
| Real-trace gold corpus | OMLX 4B | Gold corpus with human-labeled failures operationalized | ⬜ | #200 |

### 15.3 Docker (requires Docker daemon + OMLX)

| Test | LLM | Pass condition | Status | Issue |
|------|-----|----------------|--------|-------|
| Docker build | none | image builds, openai installed via [llm] extra | ✅ | — |
| OMLX is up | none | non-empty model list | ✅ | — |
| OMLX model available | none | configured model found | ✅ | — |
| OMLX reachable from container | none | model visible from container | ✅ | — |
| Docker help | none | all 10 commands listed | ✅ | — |
| Docker validate | none | exit 0 or 2 | ✅ | — |
| Docker status | none | exit 0, 1, or 2 | ✅ | — |
| Docker classification full loop | OMLX | ingest → analyze → A/B → gate → promote, LLM I/O captured, distinct prompts, tokens>0 | ⬜ | #204 |
| Docker extraction full loop | OMLX | StructuredExtractionScorer selected, all stages produce output | ⬜ | #201 |
| Docker generation full loop | OMLX | LLMJudgeScorer selected, judge role wired, all stages produce output | ⬜ | #202 |
| Docker staged analyzer | OMLX | Staged analyzer produces proposals, rejection context populated | ⬜ | #203 |
| Docker propose full | OMLX | analyze → propose → A/B → gate, LLM I/O captured | ⬜ | #204 |

## 16. Success Criteria

| Metric | Target | Verification |
|--------|--------|-------------|
| Classification loop | All stages complete, LLM I/O captured | Field test run |
| Extraction loop | All stages complete, StructuredExtractionScorer used | Field test run |
| Generation loop | All stages complete, LLMJudgeScorer + judge role used | Field test run |
| Model role separation | Each role uses its own provider/model config | Traffic log inspection |
| Staged analyzer | Structured failure patterns in output | Analyzer output inspection |
| Adversarial rejection | 5/5 bad edits caught; 0 FN | Adversarial test |
| Sentinel detection | Regressions reported explicitly | Sentinel test run |
| Hermetic CI tests | All pass in CI; zero LLM calls | CI run |
| Docker tests | All suites run in Docker; traffic captured | Docker test run |
| Coverage | > 92% | `--cov-fail-under=92` |

## 17. Deliverables

- `docs/field-test/v0.2.0/field-test-plan.md` — this document
- `docs/field-test/v0.2.0/docker-test-plan.md` — Docker-specific test plan
- `docs/field-test/v0.2.0/docker-field-test-summary.md` — Docker test results summary
- `docs/field-test/v0.2.0/FIELD_TEST_REPORT.md` — comprehensive field test report
- `field-test/v0.2.0/results/` — per-suite result artifacts (JSON, LLM traffic, accuracy reports)
- Per-iteration accuracy tables + trend data
- Guardrail FP/FN analysis per domain
- Cost-per-iteration breakdown
- Test matrix pass/fail summary
- v0.1.0 vs v0.2.0 comparison

## 18. Exit Gate

- [ ] Field test plan v0.2.0 authored and reviewed
- [ ] Classification, extraction, generation, mixed-domain suites executed
- [ ] Model role separation tested (same role + separated role configs)
- [ ] Staged analyzer tested (structured proposals, rejection context)
- [ ] Adversarial edits: 5/5 rejected; FP/FN analysis complete
- [ ] Sentinel benchmark: regressions detected and reported
- [ ] Real-trace ingestion validated with analyzer quality report
- [ ] Docker field test covers classification, extraction, generation, staged analyzer
- [ ] LLM integration tests across model role combinations
- [ ] Hermetic CI test suite runs in CI; zero LLM calls
- [ ] Comprehensive field test report written
- [ ] Ruff clean, mypy strict clean, all tests pass, coverage > 92%

## 19. Open Issues

| Issue | Problem | Status |
|-------|---------|--------|
| #173 | Multi-domain field test | Open |
| #174 | Adversarial edit field test | Open |
| #175 | Real-trace ingestion and analyzer quality | Open |
| #176 | Docker field test with multi-domain support | Open |
| #177 | LLM integration tests across all supported models | Open |
| #178 | Non-LLM hermetic test suite for CI | Open |
| #179 | Field test report and deliverables | Open |
| #198 | Add scoring rubrics to generation corpus | Open |
| #199 | Expand mixed-domain corpus to 30+ tasks | Open |
| #200 | Create real-trace gold corpus | Open |
| #201 | Extraction domain Docker test | Open |
| #202 | Generation domain Docker test with judge role | Open |
| #203 | Staged analyzer Docker test | Open |
| #204 | Update existing Docker tests for v0.2.0 paths | Open |