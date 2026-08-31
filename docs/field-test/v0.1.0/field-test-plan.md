# Field Test Plan — AgentSelfEdit v0.1.0

> Test objectives, corpus structure, baseline/improvement measurement, guardrail validation, rollback validation, cost analysis, and hermetic vs LLM testing strategy.

## 1. Test Objectives

1. **Loop closure** — can the full loop (trace → analyze → A/B test → gate → promote) run end-to-end with mock providers?
2. **Improvement** — does the loop measurably improve accuracy over 10 iterations?
3. **Guardrail effectiveness** — do guardrails catch 100% of injected bad edits? (FN < 0.1%, FP < 1%)
4. **Rollback** — does rollback revert the prompt and preserve lineage?
5. **Cost** — is cost per iteration < $0.50?
6. **Docker** — does the image build and run the loop?

## 2. Corpus Structure

### 2.1 Synthetic Corpus (90 tasks)

| Domain | Tasks | Scorer | Edge cases |
|--------|-------|--------|------------|
| Classification | 30 | ExactMatch | ambiguous boundary, multi-label, missing category, truly ambiguous |
| Extraction | 25 | Contains | missing fields, wrong format, extra fields, nested, multi-entity, conflicting info |
| Generation | 25 | LLMJudge | off-topic, wrong tone, missing constraints, non-ops, tone variation, constraint conflict |
| Mixed-domain | 10 | Contains | cross-domain (classification+extraction, extraction+generation, etc.) |

Additional:
- **Seeded failure prompts**: 15 prompts with known failure modes (including `<!-- frozen -->` annotations)
- **Adversarial edits**: 8 intentionally bad edits (each improves one task type but degrades another)

### 2.2 Real-Life Corpus (770 traces)

| Source | Traces | Description |
|--------|--------|-------------|
| agent-exec-trace (AgentObservatory) | 336 | Real LLM telemetry from Qwen 4B/9B models — detector results, latency, tokens, cache hits |
| agent-eval-forge (EvalForge) | 34 | Real agent scenario failures across 12 frameworks (LangGraph, CrewAI, PydanticAI, etc.) |
| HuggingFace (open-agent-traces) | 150 | 10-domain multi-agent traces (customer support, code review, incident response, etc.) |
| HuggingFace (customer-support) | 50 | Customer support agent traces with tool calls, reasoning steps, deviations |
| HuggingFace (pi coding agent) | 200 | Real human-AI coding agent sessions (TypeScript, Java, Python) — real prompts, real tool calls, real errors |

All real traces are validated against the Trace schema (`validate_trace()`). Each has `steps` populated with per-step metadata (latency, tokens, model, tool calls).

### 2.3 Directory Layout

```
field-test/v0.1.0/
├── corpus/
│   ├── synthetic/
│   │   ├── classification.yaml          (30 tasks)
│   │   ├── extraction.yaml              (25 tasks)
│   │   ├── generation.yaml              (25 tasks)
│   │   ├── mixed-domain.yaml            (10 tasks)
│   │   ├── seeded-prompts/
│   │   │   └── seeded-prompts.yaml      (15 prompts)
│   │   └── adversarial-edits/
│   │       └── adversarial-edits.yaml   (8 edits)
│   └── real-life/
│       └── real-traces/
│           ├── agent-observatory-traces.jsonl  (336)
│           ├── evalforge-failures.jsonl         (34)
│           ├── hf-open-agent-traces.jsonl       (~150, optional)
│           └── hf-customer-support-traces.jsonl (~100, optional)
├── scripts/
│   ├── generate_traces.py          (synthetic trace generator)
│   ├── import_real_traces.py       (portfolio trace importer)
│   ├── download_hf_traces.py       (HuggingFace dataset downloader)
│   └── README.md                    (script usage guide)
├── results/
│   └── (field test results go here — FIELD_TEST_REPORT.md, charts, etc.)
└── field-test-plan.md              (this file)
```

## 3. Baseline Measurement

1. Pick a baseline prompt (e.g. "You are a classifier.").
2. Run `run_ab_test(baseline, baseline, holdout_set, llm, scorer)` → n_trials.
3. Record: accuracy, per-task scores, cost.
4. Target: > 70% baseline accuracy (synthetic tasks are designed to be achievable).

## 4. Improvement Measurement

1. Run 10 self-improvement iterations via `agent-self-edit run --once`.
2. Each iteration: analyze failed traces → propose edits → A/B test → gate → promote.
3. Record per iteration: accuracy on held-out set, guardrail pass/fail, cost, A/B test results.
4. Target: 10%+ improvement over baseline after 10 iterations.

## 5. Guardrail Validation

- **False positive test:** Inject 5 good edits. Verify < 1% rejected (FP < 1%).
- **False negative test:** Inject 5 intentionally bad edits (adversarial). Verify 100% caught (FN < 0.1%).
- **Stress test:** Run 100 random edits through gate. Verify 0 crashes, all decisions valid.

## 6. Rollback Validation

1. Promote an edit.
2. Roll back via `agent-self-edit rollback <version> --reason "test"`.
3. Verify prompt reverts.
4. Verify lineage shows both promote and rollback events.

## 7. Test Matrix

| Test | Env | CI | LLM | Pass condition |
|------|-----|----|-----|----------------|
| Baseline measurement | Hermetic | ✅ | mock | > 70% accuracy |
| Dry-run loop | Hermetic | ✅ | mock | loop completes, all stages |
| Gate validation | Hermetic | ✅ | mock | 5/5 bad edits rejected |
| Rollback test | Hermetic | ✅ | mock | prompt reverts, lineage shows |
| Zero-LLM full loop | Hermetic | ✅ | mock | no real LLM calls, loop completes |
| Concurrency | Hermetic | ✅ | mock | 100 traces, no data loss |
| Registry integrity | Hermetic | ✅ | mock | 20 versions, 0 corruption |
| Guardrail stress | Hermetic | ✅ | mock | 100 random edits, 0 crashes |
| Real trace replay | Hermetic | ✅ | mock | 50 real traces validate + ingest |
| Full loop integration | LLM | ❌ | real | all stages produce valid output |
| 10-iteration improvement | LLM | ❌ | real | 10%+ improvement |
| Multi-domain | LLM | ❌ | real | improvement in all 3 domains |
| Adversarial edit | LLM | ❌ | real | 5/5 bad edits caught |
| Analyzer quality | LLM | ❌ | real | > 80% validity rate |
| Cost analysis | LLM | ❌ | real | < $0.50 per iteration |
| Docker build | Docker | ❌ | mock | image builds, help works |
| Docker integration | Docker | ❌ | mock | loop completes in container |

## 8. Deliverables

- `field-test/v0.1.0/results/FIELD_TEST_REPORT.md`
- Per-iteration accuracy table + trend chart
- Guardrail FP/FN analysis
- Cost-per-iteration breakdown
- Test matrix pass/fail summary