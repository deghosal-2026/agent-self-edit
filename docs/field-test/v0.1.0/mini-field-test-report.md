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

## What Was Not Expected

### Docker tests were running with `--dry-run` — skipping A/B test and gate

The original `test_docker.py` integration tests ran `agent-self-edit run --once --dry-run`. The `--dry-run` flag causes `run.py:46` to skip the A/B test and gate entirely. The "integration test" only tested ingest + analyze, not the full loop. It was marked ✅ in the WBS despite acceptance criteria never being met.

### `run_traces.py` was the wrong tool entirely

A script was built that sends each trace's `task_input` to the LLM as a standalone chat completion. This is a generic eval runner — it has nothing to do with the self-edit loop. It was being used as the field test runner, which was fundamentally wrong.

### Scoring marked everything as "passed"

`run_traces.py` scoring used `scoring_mode: label` which only checked `bool(llm_output.strip())`. Every trace — including failure traces — was marked as "passed" because the LLM produced a non-empty response. 100% pass rate was meaningless.

### Duplicate `task_id` across 336 traces

All 336 traces in `agent-observatory-traces.jsonl` had `task_id = "s_BlipZorp_000000"`. The import script hardcoded the same ID for every row. This breaks TraceStore ingestion.

### The `propose` command didn't exist

`src/agent_self_edit/cli/propose.py` only contained `_build_llm()` — no Click command. `__init__.py` tried to `from .propose import propose`, crashing the entire CLI inside Docker.

### `run.py` bypassed the configured LLM provider

`run.py:37` hardcoded `MockProvider(responses="[]")` instead of using `_build_llm(config)`. Even with `provider: openai` in config, `run` never made a real LLM call.

### `base_url` was missing from `LLMConfig`

The `LLMConfig` dataclass didn't have a `base_url` field. The config YAML's `base_url` was silently ignored — the OMLX endpoint never reached the OpenAI client.

### A/B test with 30 tasks took 12+ minutes

The A/B test runs each task twice (prompt A + B). With 30 tasks at ~12s per call on 9B, that's 60 calls × 12s = 12 minutes. Original test timed out at 300s.

---

## Silly Mistakes

### WBS row 23 marked ✅ without meeting acceptance criteria

Marked done despite acceptance criteria ("A/B test, promotion gate") never being tested. A/B test and gate were skipped via `--dry-run`. False completion claim.

### Hardcoded model name in `RESULTS_DIR`

Hardcoded to `qwen3.5-9b-mlx-4bit` even after switching to `Qwen3.5-4B-4bit`. Results written to non-existent directory. Fixed by deriving from `OMLX_MODEL`.

### Broken YAML trimming with string slicing

Extracted task IDs but not their associated `input` and `expected_output` fields. Resulting YAML was malformed. Fixed by using `yaml.safe_load()` + `yaml.dump()`.

### `run_docker_field_test.py` duplicated `test_docker.py` with worse code

Standalone script with hardcoded OMLX constants, no env var support, old config, no LLM I/O capture. Should have been deleted.

### `run_traces.py` scoring ignored `trace.success`

A trace with `success: false` was marked "passed" because the LLM wrote a paragraph. Scoring must evaluate against the trace's success/failure status.

### System prompt was `"You are a helpful assistant."` for everything

Every trace file ran with the same generic prompt. No domain context. Fixed by auto-detecting domain and selecting appropriate prompts.

### LLM didn't catch that the A/B test wasn't actually A/B testing

The LLM built the tests, ran them, reported "9/9 passed," and claimed the A/B test ran. Never inspected traffic to verify prompt B was different from prompt A. The human had to insist on inspecting before the bug was discovered.

### LLM wasted time on `--dry-run` and system prompt tweaks instead of fixing the core loop

Spent cycles fixing dry-run, system prompts, scoring, README — never investigated the fundamental issue: A/B test comparing a prompt against itself. Optimizing surface-level details while the core test was invalid.

### The fast completion time was a red flag the LLM missed

54s with a perfect tie — `all(d == 0.0)` shortcut skipped statistics entirely. Suspicious speed + perfect tie = something is wrong. LLM reported it as a clean pass.

### Domain detection used filename only — synthetic traces got wrong prompt

`/tmp/synth.jsonl` matched no domain pattern, fell through to `mixed`, used generic prompt → 0% ExactMatch. Fixed with content-based fallback.

### Same env var for both LLM arms causes key collision

`OPENROUTER_API_KEY=omlx-test` for OMLX runs carried over to cloud runs → 401. Same env var serves both arms with different values.

---

## What Got Fixed

| # | Problem | Fix | Issue |
|---|---------|-----|-------|
| 1 | `propose` command missing | Added `@click.command() propose` with full loop | — |
| 2 | `run.py` hardcoded MockProvider | Replaced with `_build_llm(config)` | — |
| 3 | `base_url` missing from LLMConfig | Added `base_url: str = ""` to dataclass | — |
| 4 | `openai` not in Docker image | Added `pip install 'openai>=1.0'` to Dockerfile | — |
| 5 | No LLM traffic capture | Added `AGENT_SELF_EDIT_LLM_LOG` env var to OpenAIProvider | — |
| 6 | Qwen3.5 thinking blocks | Added `extra_body={"chat_template_kwargs":{"enable_thinking":False}}` | — |
| 7 | Docker tests used `--dry-run` | Replaced with full loop, config includes `task_set_path` | #98 |
| 8 | A/B test timed out with 30 tasks | Trimmed to 5 tasks, switched to Qwen3.5-4B-4bit | #98 |
| 9 | `RESULTS_DIR` hardcoded model name | Derive from `OMLX_MODEL` | — |
| 10 | Broken YAML trimming | Use `yaml.safe_load()` + `yaml.dump()` | — |
| 11 | OpenRouter model 404 | Changed to `openai/gpt-4o-mini` | — |
| 12 | Results lost on abort | Write every 10 traces with `partial: true` | — |
| 13 | WBS row 23 falsely marked done | Reverted to ⬜, linked to #98 | #102 |
| 14 | A/B test passes fragment not full prompt | Construct `candidate_prompt = current_prompt.replace(old, new)` | #104 |
| 15 | Domain detection filename-only | Added content-based fallback (check `expected_output` + `metadata.scorer`) | — |

---

## Lessons Learned

### The field test must exercise the actual product loop, not a proxy

Building a generic LLM eval runner instead of running the actual `agent-self-edit run` loop was the biggest mistake. The field test for a self-improving prompt optimizer must test: trace → analyze → A/B test → gate → promote.

### `--dry-run` is not an integration test

`--dry-run` skips the most important stages (A/B test, gate). A test that only runs `--dry-run` is a smoke test. The WBS should distinguish "loop completes" (smoke) from "all stages produce valid output" (integration).

### Marking a WBS row done requires meeting all acceptance criteria

A row marked ✅ must satisfy every condition. "A/B test, promotion gate" was listed but never tested. False completion claims propagated through project tracking.

### Local MLX Qwen models CAN produce labels — but need explicit format instructions

Initial testing showed models producing conversational responses instead of labels → 0% ExactMatch → A/B always tied. Root cause was the system prompt, not the model. With `Output ONLY the category name. Nothing else.` both 4B and 9B produce labels. **Before declaring a model "not suitable," fix the prompt.**

### LLM I/O capture is non-negotiable for debuggability

Without full request/response capture, it's impossible to debug why the A/B test returned a tie. `AGENT_SELF_EDIT_LLM_LOG` JSONL capture should be on by default.

### Container networking requires `host.docker.internal`

`localhost` inside Docker refers to the container, not the host. OMLX must be reached via `host.docker.internal:8000`.

### Results must be written incrementally

LLM field tests are slow. If results are only written at the end, an abort loses everything. Write every N traces with `partial: true`.

### The gate rejecting a proposal is valid — but only if the A/B test was real

The gate correctly rejected (tie, p=1.0), but the tie was caused by a bug (comparing prompt against itself). A rejection from an invalid A/B test is not a valid outcome. The A/B test must use two distinct prompts.

### The LLM agent repeatedly declared success without verifying

The LLM declared tests passing without inspecting traffic. It optimized surface-level details while the core mechanism was broken. **The LLM should verify the core mechanism works before declaring success.** Suspicious speed + perfect tie = red flag.

### PRD compliance status (after #104 fix)

| PRD Feature | Status |
|-------------|--------|
| F-01 Trace ingestion | ✅ works |
| F-02 Feedback analyzer | ✅ works |
| F-03 A/B test engine | ✅ works (2 distinct prompts verified) |
| F-04 Promotion gate | ✅ works (correctly rejects on tie) |
| F-05 Prompt registry | ✅ works |
| F-10 Held-out task set | ✅ configured |
| F-14 Docker support | ✅ works (9/9 tests pass) |
| M10 Field test | ❌ not implemented (#100) |

---

## Open Items

| Issue | Description | Status |
|-------|-------------|--------|
| #93 | D10 field test plan design doc | open |
| #94 | Field test report deliverables | open |
| #95 | `run_traces.py` is wrong tool | open |
| #96 | Scoring ignores `trace.success` | open |
| #97 | Duplicate `task_id` in observatory traces | open |
| #99 | `run_docker_field_test.py` is stale | open |
| #100 | LLM field tests (rows 15-20) not implemented | open |
| #101 | `FIELD_TEST_REPORT.md` missing | open |
| #105 | Ruff: 13 lint errors | open |
| #106 | Mypy: 5 type errors | open |
| #107 | Guardrail FP/FN + cost vs real LLM | open |
| #108 | Docker: no latency/token assertions | open |
| #109 | Docker: identical seeded traces | open |
| #110 | Docker: accepts tie without delta check | open |
| #98 | Docker integration only `--dry-run` | closed |
| #102 | WBS row 23 falsely marked done | closed |
| #103 | A/B test engine not exercised | closed |
| #104 | A/B test fragment bug | closed |

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
