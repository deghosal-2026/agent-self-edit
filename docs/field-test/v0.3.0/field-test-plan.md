# Field Test Plan — AgentSelfEdit v0.3.0

> D11 — Authored per M11/M12 scope. Covers hermetic foundations (M11) and full corpora + reporting (M12).
> Builds on the v0.2.0 field test plan, incorporating all M1–M10 correctness fixes.

## 1. What Changed in v0.3.0 (M1–M10 Affecting Field Test)

| Change | M | Impact on field test |
|--------|---|----------------------|
| **Two-tailed permutation** | M1 | A/B winner='a' path now live; one-tailed results are superseded |
| **Tie detection epsilon** | M1 | Near-identical scores → `tie` not `inconclusive`; affects tie count |
| **`run_task` system role** | M1 | A/B test message format changed; mock provider validates two-message format |
| **Exponential backoff** | M1 | Rate-limit retries no longer cause A/B failures |
| **Persistent A/B cache** | M1 | Identical `(task, prompt)` pairs skip re-run; cache key includes config hash |
| **`near_miss_threshold` >0** | M2 | `0.0` rejected at validation; `near_miss` only when ratio >0 |
| **Near-miss ratio denominator** | M2 | Uses `checks_run` not `total`; reason names failing check |
| **Near-miss dedup loaded** | M2 | Analyzer receives rejection history; dedup filters similar proposals |
| **Drift baseline = original** | M3 | Drift measured from v1, not current; drift gate now fires on divergence |
| **TF-IDF `math.log`** | M3 | Drift scores calibrated (was miscalibrated low); threshold behavior changed |
| **HTML comment handling** | M3 | `<!-- note -->` no longer crashes guardrail parser |
| **`frozen_sections` config** | M3 | Configured frozen sections enforced; gate rejects edits to them |
| **`Meta.to_dict` complete** | M4 | Lineage JSON includes all fields (`trigger_trace_ids`, `model_version`, etc.) |
| **Forward-compat filter** | M4 | Older code reads newer registry without crash |
| **Atomic registry write** | M4 | Temp+rename; no partial `.md`/`.meta.json` on crash |
| **Prompt caching** | M4 | 1 disk read per loop, not 12+ |
| **Persistent SQLite connection** | M5 | Single `connect` per store, not N-per-op |
| **In-flight trace safety** | M5 | `cleanup` skips `processed=-1`; `release_in_flight` on exception |
| **`Trace.metadata` round-trip** | M5 | Metadata preserved through SQLite |
| **`batch_ready` guard** | M5 | `propose` checks incomplete batch before analysis |
| **`llm_provider` parameter** | M6 | Role routing now works; `analyzer_role` provider actually used |
| **`staged=True` prompt** | M6 | Staged param has effect; builds 4-stage prompt |
| **`max_edit_lines` configurable** | M6 | `AnalyzerConfig.max_edit_lines` replaces hardcoded 2-line limit |
| **Fuzzy Strategy3 fix** | M6 | No-op fix no longer returns unchanged `old_text` |
| **Stage2 vs Stage3 mismatch** | M6 | No `[FROZEN]` copied into `old_text` |
| **`ContainsScorer` denom** | M7 | Blank lines excluded from denominator; trailing newline no longer deflates |
| **Extraction double-count** | M7 | `matched_act_keys` prevents same key scored twice |
| **LLMJudge verbose parse** | M7 | Regex extracts first float; verbose responses no longer score 0.0 |
| **`resolve_scorer` deterministic** | M7 | Sorted selection; conflicting hints no longer non-deterministic |
| **Empty task set rejection** | M7 | `load_task_set` raises on `[]` |
| **Fence-preserving JSON** | M7 | Inner backtick fences in code blocks preserved |
| **Partial `${VAR}` interpolation** | M8 | `Bearer ${KEY}` expanded; all occurrences, not just first |
| **Per-role provider validation** | M8 | Typo in `analyzer_role.provider` caught at validation |
| **`task_timeout_seconds` + others** | M8 | Config schema expanded |
| **Exponential backoff** | M8 | 429 retries with backoff in `run_task` |
| **Failure reason surface** | M8 | LLM error text propagated, not `"unknown"` |
| **Trigger modes honored** | M8 | `trigger: time` and `trigger: manual` work |
| **`llm_b` model-vs-model** | M8 | A/B can compare two different models |
| **Task+LLM hoisted** | M9 | 1 YAML read + 1 client init per batch, not per-proposal |
| **Gate atomic with audit** | M9 | `PromotionGate.check()` writes audit in same call |
| **A/B caching** | M9 | `_ABResultCache` persistent SQLite |
| **File lock** | M9 | `fcntl.flock` on registry for multi-process safety |
| **Exception classification** | M9 | Rate-limit → backoff, fatal → exit 1, transient → retry |
| **Staged cost sum** | M9 | Cost = sum of 4 stages, not single-pass estimate |
| **`format_edit_summary` lines** | M10 | Shows real `diff_lines_changed`, not `len(gate_checks)` |
| **Side-by-side diff distinct** | M10 | Modified lines show `-old` / `+new` |
| **`materialize_candidate_prompt`** | M10 | Raw `.replace()` replaced; missing `old_text` raises loudly |
| **Heatmap by section** | M10 | `changed_section` field; buckets by section not hypothesis |
| **`_run_once` tests** | M10 | Core loop has direct unit coverage |
| **Behavioral CLI asserts** | M10 | Version/pending/audit checks in CLI tests |
| **StagedAnalyzer tests** | M10 | Per-stage + pipeline + fuzzy-fix + failure isolation |

## 2. Test Objectives

1. **Hermetic baseline** — ruff/mypy clean, coverage >= 91%, all tests pass, zero LLM calls
2. **Loop closure** — full loop (trace → analyze → A/B → gate → promote) with mock providers
3. **Multi-domain** — classification, extraction, generation, mixed-domain (30+ tasks)
4. **Model role separation** — executor/analyzer/judge each use own provider
5. **Staged analyzer** — 4-stage pipeline produces structured proposals
6. **Improvement** — directional improvement over 5-10 iterations (target: detectable)
7. **Guardrail effectiveness** — adversarial edits 5/5 blocked; oracle drift detected
8. **Sentinel regression** — sentinel benchmark catches regressions
9. **Rollback** — real promoted version reverts, lineage preserved
10. **Cost** — per-iteration cost documented
11. **Seeded-prompts** — 15 prompts with known failure modes run
12. **Real-trace gold corpus** — analyzer quality scored against human-labeled clusters
13. **Misleading metrics corrected** — 20% vs 46% baseline clarified

## 3. LLM Arms

| Arm | Provider | Endpoint | Model | Key env var |
|-----|----------|----------|-------|-------------|
| Local | `openai` | `http://localhost:8000/v1` | `Qwen3.5-4B-4bit` | `OMLX_KEY` |
| Local (analyzer) | `openai` | `http://localhost:8000/v1` | `Qwen3.5-9B-MLX-4bit` | `OMLX_KEY` |
| Local (judge) | `openai` | `http://localhost:8000/v1` | `Qwen3.5-4B-4bit` | `OMLX_KEY` |

Config allows per-role override via `executor_role`, `analyzer_role`, `judge_role`.

## 4. Corpus Structure

### 4.1 Synthetic Corpus

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
| `mixed-domain.yaml` | 30+ | mixed | `promotion_ab` | Cross-domain tasks (expanded from 10) |

Seeded failure prompts: `seeded-prompts/` (15 prompts with known failure modes)
Adversarial edits: `adversarial-edits/` (8 intentionally bad edits)

### 4.2 Real-Trace Gold Corpus

`field-test/corpus/real-traces/gold/` — human-labeled failure clusters with expected edit intents, used for analyzer-quality evaluation (not direct loop input per v0.2.0 finding).

### 4.3 Directory Layout

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
│       ├── gold/              ← human-labeled gold corpus
│       ├── usable/            ← real traces with vague expected outputs
│       └── telemetry/         ← placeholder outputs
├── scripts/
│   ├── run_improvement_loop.py
│   ├── generate_traces.py
│   ├── import_real_traces.py
│   ├── download_hf_traces.py
│   ├── download_pi_traces.py
│   ├── run_docker_tests.py
│   └── README.md
├── v0.2.0/
│   └── results/              ← historical results (preserved)
└── v0.3.0/
    └── results/
        ├── hermetic/         ← M11: zero-LLM full loop, gate validation, registry integrity
        ├── sentinel/         ← M11: sentinel report
        ├── adversarial/      ← M11: 5+ bad edits FP/FN
        ├── rollback/         ← M11: real promoted version rollback
        ├── mixed-domain/     ← M11: 30+ run
        ├── real-traces/      ← M12: A/B with correct corpus + analyzer gold scoring
        ├── rejection-aware/  ← M12: novelty/FT/FB before-vs-after
        ├── roles/            ← M12: executor/analyzer matrix
        └── seeded-prompts/   ← M12: 15-prompt run
```

## 5. Baseline Measurement

1. Pick a baseline prompt (e.g. "You are a helpful classification assistant.").
2. Run `run_ab_test(baseline, baseline, task_set, llm, scorer)` → n_trials.
3. Record: accuracy, per-task scores, cost.
4. Confirm A/B cache is empty on first run, populated on second (identical) run.
5. Target: > 70% baseline accuracy on classification, extraction, and generation independently.

## 6. Multi-Domain Improvement Measurement

### 6.1 Classification

1. Run 5-10 self-improvement iterations via `agent-self-edit run --once` on classification corpus.
2. Use promotion-seeking corpus (40 tasks) for A/B.
3. Use held-out set (25 tasks) for generalization.
4. Run sentinel benchmark (20 tasks) after each iteration.
5. Record: accuracy, guardrail decisions, cost, A/B cache hits, sentinel regressions.

### 6.2 Extraction

1. Same loop on extraction corpus (25 tasks).
2. Verify `StructuredExtractionScorer` is auto-selected.
3. Same metrics as classification.

### 6.3 Generation

1. Same loop on generation corpus (15 tasks).
2. Configure `judge_role` with same or different model.
3. Verify `LLMJudgeScorer` is auto-selected with rubric metadata.
4. Same metrics as classification.

### 6.4 Mixed-Domain (30+)

1. Loop on mixed-domain corpus (30+ tasks).
2. Verify correct scorer selection per task type.
3. Same metrics as classification.

## 7. Model Role Separation Tests

### 7.1 Same role config

All three roles use the same model. Verify loop works identically to single-provider mode.

### 7.2 Separated role config

- `executor_role`: Qwen3.5-4B-4bit
- `analyzer_role`: Qwen3.5-9B-MLX-4bit
- `judge_role`: Qwen3.5-4B-4bit

Verify:
- Analyzer calls go to the 9B model
- Task execution calls go to the 4B model
- Judge calls go to the 4B model
- Proposal quality is measurably different from same-role mode (#265)

### 7.3 Model-vs-model A/B (#227)

- `llm_b` configured with a different model
- Verify A/B compares two different models on the same prompt

## 8. Staged Analyzer Tests

1. Full loop with `analyze_batch(..., staged=True)` (default).
2. Verify staged analyzer produces structured failure patterns.
3. Verify `llm_provider` parameter routes to the correct role-specific provider.
4. Verify proposals are more minimal than single-pass mode.
5. Verify rejection context is populated and fed into subsequent iterations.
6. Verify cost accounting sums across 4 stages, not single-pass estimate.

## 9. Guardrail Validation

- **False positive test:** Inject 5 good edits. Verify < 1% rejected.
- **False negative test:** Inject 5 intentionally bad edits (adversarial). Verify 100% blocked.
- **Frozen section test:** Inject edits to frozen sections → verify rejected by `frozen_sections` check.
- **Missing `old_text` test:** Inject proposal where `old_text` not in prompt → verify `materialize_candidate_prompt` raises `ValueError`, proposal skipped.
- **Drift baseline test:** After several diverging edits, verify drift measured from original v1, not current.
- **Oracle Drift Guard test:** Verify shared wrong success definition is flagged (#226).
- **Stress test:** Run 100 random edits. Verify 0 crashes, all decisions valid.

## 10. Regression Sentinel Validation

1. Run sentinel benchmark (20 tasks) after each proposed edit.
2. Verify sentinel regressions reported explicitly.
3. Verify edits that fix hard tasks but break easy ones are caught.

## 11. Rollback Validation

1. Promote an edit.
2. Roll back via `agent-self-edit rollback <version> --reason "test"`.
3. Verify prompt reverts.
4. Verify lineage shows both promote and rollback events with `rollback_reason` and `rollback_target`.
5. Verify `changed_section` is populated in the rollback version's Meta.

## 12. Rejection-Aware Analyzer

1. Run full loop for multiple iterations.
2. Verify after gate rejection, the next iteration produces a different proposal.
3. Verify rejection context lists which gate check failed.
4. Verify near-miss dedup prevents re-proposing the same edit.

## 13. Real-Trace Gold Corpus Evaluation

1. Load gold corpus `field-test/corpus/real-traces/gold/`.
2. Run analyzer on each failure cluster.
3. Score proposals against expected edit intents.
4. Report: proposal relevance rate, proposal novelty rate, `old_text` match rate.

## 14. LLM I/O Capture

Every LLM call captured to `AGENT_SELF_EDIT_LLM_LOG` (JSONL). Each entry: `{model, base_url, messages, temperature, response, usage, latency_ms}`.

Results stored under `field-test/v0.3.0/results/<provider>/<model>/`.

## 15. Test Matrix

### 15.1 Hermetic (CI-safe, mock LLM)

| Test | CI | LLM | Pass condition | Status |
|------|----|-----|----------------|--------|
| Baseline measurement | ✅ | mock | > 70% accuracy | ⬜ |
| Dry-run loop | ✅ | mock | loop completes, all stages | ⬜ |
| Gate validation (5/5 rejection) | ✅ | mock | 5/5 bad edits rejected with correct failure modes | ⬜ |
| Failure-mode: frozen section | ✅ | mock | Rejected by `frozen_sections` check | ⬜ |
| Failure-mode: missing `old_text` | ✅ | mock | `materialize_candidate_prompt` raises `ValueError` | ⬜ |
| Failure-mode: excessive edit distance | ✅ | mock | Rejected by `edit_distance` check | ⬜ |
| Rollback test | ✅ | mock | prompt reverts, lineage shows rollback reason | ⬜ |
| Zero-LLM full loop | ✅ | mock | no real LLM calls, loop completes | ⬜ |
| Concurrency | ✅ | mock | 100 traces, no data loss, file lock held | ⬜ |
| Registry integrity | ✅ | mock | 20 versions, 0 corruption, hash verification | ⬜ |
| Guardrail stress | ✅ | mock | 100 random edits, 0 crashes | ⬜ |
| Real trace replay | ✅ | mock | 50 real traces validate + ingest | ⬜ |
| Sentinel corpus load | ✅ | mock | 20 tasks load and validate | ⬜ |
| Scorer consistency | ✅ | mock | Mixed scorer sets fail fast | ⬜ |
| Staged analyzer (mock) | ✅ | mock | Staged analyzer produces proposals | ⬜ |
| A/B cache hit/miss | ✅ | mock | Cache hit skips LLM, cache miss re-runs | ⬜ |
| Exception classification | ✅ | mock | Rate-limit → backoff, fatal → exit 1 | ⬜ |
| Oracle drift guard | ✅ | mock | Shared wrong oracle flagged | ⬜ |

### 15.2 LLM-based (OMLX, CI-skipped)

| Test | LLM | Pass condition | Status | Issue |
|------|-----|----------------|--------|-------|
| Classification full loop | OMLX 4B | All stages produce valid output, LLM I/O captured | ⬜ | M11 |
| Extraction full loop | OMLX 4B | `StructuredExtractionScorer` used | ⬜ | M11 |
| Generation full loop | OMLX 4B | `LLMJudgeScorer` + judge role wired | ⬜ | M11 |
| Mixed-domain full loop (30+) | OMLX 4B | Correct scorer per task type | ⬜ | M11 |
| Same role config | OMLX 4B | Loop works identically to single-provider mode | ⬜ | M12 |
| Separated role config | OMLX 4B+9B | Each role uses its own model | ⬜ | #265 |
| Model-vs-model A/B | OMLX 4B+9B | `llm_b` compares models | ⬜ | #227 |
| Staged analyzer full loop | OMLX 4B | Staged analyzer produces structured proposals | ⬜ | M11 |
| Rejection-aware iterations | OMLX 4B | Different proposals after rejection feedback | ⬜ | M12 |
| 5-iteration improvement | OMLX 4B | Directional improvement on promotion corpus | ⬜ | M12 |
| Adversarial edit test | OMLX 4B | 5/5 bad edits caught | ⬜ | M11 |
| Sentinel regression test | OMLX 4B | Regressions detected and reported | ⬜ | M11 |
| Real-trace gold corpus | OMLX 4B | Analyzer scored against gold | ⬜ | M12 |
| Seeded-prompts 15 | OMLX 4B | 15 prompts with known failure modes run | ⬜ | M12 |
| Oracle drift guard | OMLX 4B | Shared wrong oracle flagged | ⬜ | M11 |

### 15.3 Docker (requires Docker daemon + OMLX)

| Test | LLM | Pass condition | Status | Issue |
|------|-----|----------------|--------|-------|
| Docker build | none | image builds, `[llm]` extra installed | ✅ | — |
| OMLX is up | none | non-empty model list | ✅ | — |
| OMLX model available | none | configured model found | ✅ | — |
| OMLX reachable from container | none | model visible from container | ✅ | — |
| Docker help | none | all 10 commands listed | ✅ | — |
| Docker validate | none | exit 0 or 2 | ✅ | — |
| Docker status | none | exit 0, 1, or 2 | ✅ | — |
| Docker classification full loop | OMLX | ingest → analyze → A/B → gate → promote/reject | ⬜ | #303 |
| Docker extraction full loop | OMLX | `StructuredExtractionScorer` selected | ⬜ | #303 |
| Docker generation full loop | OMLX | `LLMJudgeScorer` + judge role wired | ⬜ | #303 |
| Docker staged analyzer | OMLX | Staged analyzer produces proposals | ⬜ | #303 |
| Docker mixed-domain | OMLX | 30+ tasks, correct scorer per task | ⬜ | #303 |
| Docker adversarial | OMLX | 5/5 bad edits blocked | ⬜ | #303 |
| Docker propose full | OMLX | analyze → propose → A/B → gate | ⬜ | #303 |
| Docker A/B cache | OMLX | Cache hit on identical re-run | ⬜ | #303 |
| Docker materialize guard | OMLX | Missing `old_text` → proposal skipped | ⬜ | #303 |

## 16. Success Criteria

| Metric | Target | Verification |
|--------|--------|-------------|
| Coverage | >= 91% | `pytest --cov-fail-under=91` |
| Ruff | 0 errors | `ruff check .` |
| Mypy | 0 errors | `mypy --strict src/agent_self_edit` |
| Hermetic CI | All pass, zero LLM | CI run |
| Oracle drift guard | Flags shared wrong oracle | Guard test |
| Adversarial | 5/5 blocked, FP/FN measured | Adversarial report |
| Sentinel | Regressions reported | Sentinel result |
| Rollback | Real promoted version reverted | Rollback report |
| Mixed-domain | 30+ tasks execute | Corpus count |
| Gold corpus | Human-labeled clusters operationalized | Analyzer quality report |
| Cost breakdown | Per-iteration $, tokens, wall-clock | Cost table |
| Seeded-prompts | 15 prompts run | Result file |
| Role separation | Measurably different per-role outcomes | Role matrix CSV |
| Metrics correction | 20% vs 46% clarified | Report section |

## 17. Deliverables

- `docs/field-test/v0.3.0/field-test-plan.md` — this document
- `docs/field-test/v0.3.0/docker-test-plan.md` — Docker-specific test plan
- `docs/field-test/v0.3.0/docker-field-test-summary.md` — Docker test results summary
- `docs/field-test/v0.3.0/FIELD_TEST_REPORT.md` — comprehensive field test report
- `field-test/v0.3.0/results/` — per-suite result artifacts
- Per-iteration accuracy tables + trend data
- Guardrail FP/FN analysis per domain
- Cost-per-iteration breakdown
- Test matrix pass/fail summary
- v0.2.0 vs v0.3.0 comparison

## 18. Exit Gate

- [ ] Ruff clean: `ruff check .` → 0 errors
- [ ] Mypy strict clean: `mypy --strict src/agent_self_edit` → 0 errors
- [ ] All tests pass: `python3 -m pytest --ignore=tests/test_docker.py -x -q` → 0 failures
- [ ] Coverage >= 91%: `pytest --cov=agent_self_edit --cov-fail-under=91`
- [ ] Hermetic CI suite run in CI with recorded results (#263)
- [ ] Sentinel validated end-to-end (#261)
- [ ] Adversarial injection run (#260)
- [ ] Rollback with real promoted version tested (#262)
- [ ] Mixed-domain expanded to 30+ tasks (#259)
- [ ] Oracle Drift Guard implemented (#226)
- [ ] Real-trace gold corpus operationalized for analyzer quality (#268)
- [ ] Rejection-aware behavioral diff measured (#270)
- [ ] Cost-per-iteration documented (#269)
- [ ] Seeded-prompts 15 used (#271)
- [ ] Role separation measurably different (#265)
- [ ] Real-trace ingestion corpus fixed (#264)
- [ ] 20% vs 46% misleading metrics corrected (#266)
- [ ] Docker tests authored and executed (#302–#304)
- [ ] Zero paid LLM calls in CI

## 19. References

- [WBS Part 6](../wbs/v0.3.0/wbs-v0.3.0-part6-field-test.md)
- [WBS Index](../wbs/v0.3.0/wbs-v0.3.0-index.md)
- [v0.2.0 Field Test Plan](../v0.2.0/field-test-plan.md)
- [v0.2.0 FIELD_TEST_REPORT.md](../v0.2.0/FIELD_TEST_REPORT.md)