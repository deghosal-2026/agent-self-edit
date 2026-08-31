# Mini Field Test Report — 10 Traces × 3 Models

> **BLUF:** All 3 models (4B local, 9B local, gpt-4o-mini cloud) completed 10/10 traces with zero errors. Classification accuracy is 80% across all models — they make the same 2 errors. The self-edit loop has real work to do. The 4B model is the best choice for iterative testing (304ms per classification, same accuracy as 9B and cloud). Domain auto-detection and format-constrained prompts now work correctly.

**Date:** 2026-08-31  
**Sample size:** 10 traces per arm per trace type  
**Trace types:** Synthetic classification (ExactMatch), Real customer-support (label mode)

---

## Observations

### Accuracy

| Model | Arm | Synthetic (classification) | Real (customer-support) | Errors |
|-------|-----|----------------------------|------------------------|--------|
| Qwen3.5-4B-4bit | OMLX local | 80% (8/10) | 100% (10/10) | 0 |
| Qwen3.5-9B-MLX-4bit | OMLX local | 80% (8/10) | 100% (10/10) | 0 |
| openai/gpt-4o-mini | OpenRouter cloud | 80% (8/10) | 100% (10/10) | 0 |

### Latency

| Model | Synth avg | Real avg | Total tokens |
|-------|-----------|----------|-------------|
| Qwen3.5-4B-4bit | 304ms | 4,773ms | 2,833 |
| Qwen3.5-9B-MLX-4bit | 441ms | 9,361ms | 3,254 |
| openai/gpt-4o-mini | 2,794ms | 2,407ms | 2,146 |

### Classification errors (same across all 3 models)

| task_id | input | expected | all 3 models output | error type |
|---------|-------|----------|---------------------|------------|
| classify-001 | "My billing page shows the wrong amount for my subscription." | technical | billing | Keyword over-indexing — model sees "billing" and picks billing, ignores "wrong amount" (system bug) |
| classify-010 | "I think my account was compromised — someone logged in from an unknown IP." | urgent | security | Domain correct, urgency missed — account compromise = urgent, not just security |

---

## Expectations

1. **Models would produce labels with explicit format prompts** — ✅ confirmed. The prompt `Output ONLY the category name. Nothing else.` works for all 3 models.
2. **4B would be faster than 9B** — ✅ confirmed. 304ms vs 441ms on classification, 4,773ms vs 9,361ms on real traces.
3. **Cloud would be slower due to network overhead** — ✅ confirmed. 2,794ms for a single label vs 304ms local.
4. **All models would make similar errors on ambiguous cases** — ✅ confirmed. All 3 made identical errors on classify-001 and classify-010.
5. **Domain auto-detection would work after the fix** — ✅ confirmed. `/tmp/synth.jsonl` correctly detected as `classification` via content-based fallback.
6. **Real trace scoring would not be meaningful** — ✅ confirmed. Label mode passes any non-empty response. 100% on real traces is not a real accuracy measure.

---

## Surprises

1. **9B offers no accuracy advantage over 4B on classification.** Both score 80% with identical errors. The 9B is 2x slower for zero benefit. Expected the larger model to classify better.

2. **4B classification is extremely fast — 304ms.** Faster than cloud (2,794ms) by 9x. For iterative A/B testing where you run 5 tasks × 2 prompts = 10 calls per loop, 4B local completes in ~3 seconds vs ~28 seconds for cloud.

3. **All 3 models make the exact same 2 errors.** This suggests the errors are inherent to the prompt/task design, not model capability. A prompt edit that addresses keyword over-indexing should fix all 3 models simultaneously.

4. **Domain detection was broken for temp files.** `/tmp/synth.jsonl` was detected as `mixed` (generic prompt) instead of `classification`. The fix — content-based fallback checking `expected_output` against known labels — works but was only added after the first runs showed 0%.

5. **Same env var for both LLM arms caused a 401.** `OPENROUTER_API_KEY=omlx-test` exported for OMLX runs carried over to cloud runs. OpenRouter rejected the OMLX key. Not a code bug — a usability trap in the README.

6. **9B uses more tokens than 4B** (3,254 vs 2,833). The 9B model is more verbose on real traces, producing longer responses without better quality.

---

## Key Takeaways

1. **4B is the right model for field testing.** Same accuracy as 9B and cloud, 9x faster than cloud, 2x faster than 9B. No reason to use 9B for iterative runs.

2. **The self-edit loop has real work to do.** 80% baseline accuracy with 2 identifiable classification errors. The analyzer should detect keyword over-indexing and propose a prompt edit. If the edit improves accuracy to 90%+, the gate promotes it. This is the core value proposition.

3. **Explicit format prompts are required for ExactMatch scoring.** Without `Output ONLY the category name. Nothing else.`, all models produce full sentences → 0% accuracy. The prompt is the lever.

4. **Real trace scoring needs improvement.** Label mode (pass = non-empty response) is meaningless. Needs LLM-as-judge or relevance scoring. Tracked in #96.

5. **Domain detection must be content-based, not filename-based.** Temp files, renamed files, and files without domain in the name all break filename-based detection. Content fallback is required.

6. **LLM I/O capture works correctly.** All 60 calls (3 models × 10 traces × 2 trace types) captured with messages, responses, tokens, and latency. Debuggability is solid.

---

## Next Steps — Fixes Before Full Run

| # | Fix | Issue | Why it blocks the full run |
|---|-----|-------|---------------------------|
| 1 | **Implement 10-iteration improvement run** | #100 | The full field test requires running the self-edit loop for 10 iterations and measuring accuracy improvement. Currently no script runs this. Must create a script that runs `agent-self-edit run --once` × 10 iterations with LLM traffic capture. |
| 2 | **Fix real trace scoring** | #96 | Real traces score 100% because label mode passes any non-empty response. Need LLM-as-judge or Contains scorer so real trace results are meaningful. |
| 3 | **Fix duplicate task_ids in observatory traces** | #97 | 336 traces all have `task_id = "s_BlipZorp_000000"`. TraceStore keys on task_id — duplicates break ingestion. Must generate unique IDs in `import_real_traces.py`. |
| 4 | **Delete or rewrite `run_docker_field_test.py`** | #99 | Stale script duplicates `test_docker.py` with worse code. Confusing to have two entry points doing the same thing. |
| 5 | **Replace `run_traces.py` with self-edit loop runner** | #95 | `run_traces.py` is a generic eval runner, not the self-edit loop. The full run needs `agent-self-edit run` with trace ingestion, not standalone LLM calls. |
| 6 | **Fix ruff lint errors** | #105 | 13 errors in `test_docker.py`. WBS exit gate requires ruff clean. |
| 7 | **Fix mypy type errors** | #106 | 5 errors in `propose.py` and `run.py`. WBS exit gate requires mypy strict clean. |
| 8 | **Write FIELD_TEST_REPORT.md** | #101 | Final deliverable: per-iteration accuracy, guardrail FP/FN, cost analysis, test matrix. Must be written after the 10-iteration run completes. |
| 9 | **Measure guardrail FP/FN and cost against real LLM** | #107 | Adversarial edit test and cost-per-iteration measurement not implemented. Only mock-tested so far. |
| 10 | **Separate env vars for OMLX vs cloud keys** | — | `OPENROUTER_API_KEY` collision causes 401 when switching arms. Use `OMLX_KEY` for local and `OPENROUTER_API_KEY` for cloud, or document the re-export requirement prominently. |
| 11 | **Add per-trace latency and token tracking to docker test assertions** | — | Docker test only checks ≥2 distinct prompts. Should also verify per-trace latency and token counts are non-zero to catch silent failures. |
| 12 | **Vary seeded traces in docker test** | — | All 10 seeded traces use the same `task_input` ("classify this ticket: 'My billing page shows wrong amount'"). Identical tasks make non-tie A/B results unlikely. Use varied inputs from the classification task set. |
| 13 | **Add A/B test delta assertion to docker test** | — | Docker test accepts a tie as valid. Should assert that if the A/B test runs, at least some deltas are non-zero OR document that a tie is an expected valid outcome. |

---

## Appendix A: Per-Trace Latency and Token Breakdown

### Synthetic (classification) — 10 traces

| Model | Latency range | Token range | Avg response length |
|-------|--------------|-------------|---------------------|
| 4B | 251–538ms | 63–71 | 8 chars (single label) |
| 9B | 354–684ms | 63–71 | 8 chars (single label) |
| Cloud | 522–6,098ms | 57–64 | 8 chars (single label) |

### Real (customer-support) — 10 traces

| Model | Latency range | Token range | Avg response length |
|-------|--------------|-------------|---------------------|
| 4B | 2,609–6,539ms | 134–293 | 751 chars |
| 9B | 6,121–13,363ms | 191–381 | 944 chars |
| Cloud | 980–8,130ms | 83–332 | 562 chars |

Key observations:
- **4B has the tightest latency range on real traces** (2.6–6.5s), 9B is widest (6.1–13.4s)
- **Cloud has the widest variance on classification** (522ms–6.1s) — network jitter
- **9B produces longer real responses** (944 chars avg) vs 4B (751) and cloud (562) — more verbose without better quality
- **Classification responses are identical length** across all models (8 chars = one label) — format constraint works perfectly

---

## Appendix B: Cost Estimate (gpt-4o-mini pricing)

Based on OpenRouter pricing for `openai/gpt-4o-mini`: $0.150/1M input tokens, $0.600/1M output tokens.

### Per 10-trace run

| Trace type | Model | Input tokens | Output tokens | Est. cost |
|------------|-------|-------------|---------------|-----------|
| Synthetic | 4B | 650 | 10 | $0.000103 |
| Synthetic | 9B | 650 | 10 | $0.000103 |
| Synthetic | Cloud | 587 | 11 | $0.000095 |
| Real | 4B | 453 | 1,720 | $0.001100 |
| Real | 9B | 453 | 2,141 | $0.001353 |
| Real | Cloud | 378 | 1,170 | $0.000759 |

### Projected 10-iteration full loop cost

A 10-iteration self-edit loop runs:
- 10 analyzer calls (1 per iteration)
- 10 A/B tests × 5 tasks × 2 prompts = 100 A/B calls
- Total: 110 LLM calls

Using cloud pricing (gpt-4o-mini) as the upper bound:

| Component | Calls | Est. tokens/call | Total tokens | Est. cost |
|-----------|-------|-----------------|-------------|-----------|
| Analyzer | 10 | ~700 | 7,000 | $0.001 |
| A/B test (classification) | 100 | ~65 | 6,500 | $0.001 |
| **Total per 10-iteration loop** | **110** | — | **~13,500** | **~$0.002** |

This is well under the $0.50/iteration target ($0.002 total for 10 iterations = $0.0002/iteration). The cost ceiling is not a concern for v0.1.0 field testing.

Note: OMLX is local and free — cost only applies to the cloud arm.

---

## Appendix C: Identical Outputs Across All 3 Models

All 3 models produced **identical** classification outputs on all 10 traces:

| task_id | 4B | 9B | Cloud | Identical? |
|---------|----|----|-------|-----------|
| classify-001 | billing | billing | billing | ✅ |
| classify-002 | billing | billing | billing | ✅ |
| classify-003 | feature | feature | feature | ✅ |
| classify-004 | technical | technical | technical | ✅ |
| classify-005 | feature | feature | feature | ✅ |
| classify-006 | security | security | security | ✅ |
| classify-007 | technical | technical | technical | ✅ |
| classify-008 | billing | billing | billing | ✅ |
| classify-009 | technical | technical | technical | ✅ |
| classify-010 | security | security | security | ✅ |

**10/10 identical outputs.** The 4B, 9B, and cloud models all classify the same way. This means:
1. The classification errors are **prompt-driven, not model-driven** — a prompt edit should fix all 3 models
2. The A/B test will produce the **same result** regardless of which model is used
3. The 4B model is sufficient — no benefit from larger models on this task

---

## Appendix D: Results File Locations

```
field-test/v0.1.0/results/
├── omlx/
│   ├── qwen3.5-4b-4bit/
│   │   ├── synth-results.json
│   │   ├── llm-traffic-synth.jsonl
│   │   ├── hf-customer-support-traces-results.json
│   │   └── llm-traffic-hf-customer-support-traces.jsonl
│   └── qwen3.5-9b-mlx-4bit/
│       ├── synth-results.json
│       ├── llm-traffic-synth.jsonl
│       ├── hf-customer-support-traces-results.json
│       └── llm-traffic-hf-customer-support-traces.jsonl
├── openai/
│   └── openai-gpt-4o-mini/
│       ├── synth-results.json
│       ├── llm-traffic-synth.jsonl
│       ├── hf-customer-support-traces-results.json
│       └── llm-traffic-hf-customer-support-traces.jsonl
└── docker/
    └── omlx/
        └── qwen3.5-4b-4bit/
            ├── docker-run-full-loop-omlx.json
            ├── docker-propose-full-omlx.json
            ├── llm-traffic-run.jsonl
            └── llm-traffic-propose.jsonl
```

Each `*-results.json` contains: meta (provider, model, domain, accuracy, tokens, latency, n_done, partial) + per-trace results (task_id, task_input, llm_call with messages/response/usage/latency, scoring with passed/expected/actual).

Each `llm-traffic-*.jsonl` is append-only raw LLM request/response pairs for stream debugging.
