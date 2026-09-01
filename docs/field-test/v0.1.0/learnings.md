# Field Test Learnings — v0.1.0

**Date:** 2026-08-31

---

## Part 1: Improvement Loop Learnings (Aug 31, post-fix)

### Problem

The 10-iteration improvement loop produced 0% improvement across all 3 models:

| Model | Baseline | Final | Improvement |
|-------|----------|-------|-------------|
| Qwen3.5-4B-4bit | 20% | 20% | 0% |
| Qwen3.5-9B-MLX-4bit | 40% | 40% | 0% |
| openai/gpt-4o-mini | 60% | 60% | 0% |

Every A/B test was a tie (p=1.0, delta=0.0). The gate rejected every iteration.

### Root Cause

#### 1. Fake failure traces — the analyzer was optimizing against fabricated data

`_seed_trace_store()` hardcoded `final_output: "other"` for every failed trace:

```python
"final_output": "other",  # WRONG — not what the model actually produces
"expected_output": task["expected_output"],
"success": False,
```

The analyzer saw failures like:
- input: "billing page shows wrong amount"
- model output: `other` (fabricated)
- expected: `technical`

But the model actually outputs `billing`, not `other`. The analyzer was learning from a failure pattern that didn't match reality. It proposed edits aimed at the wrong problem.

#### 2. A/B test used easy tasks where both prompts already succeed

The A/B task set used the first 5 easy classification tasks (classify-001 through 005). The baseline prompt already scores 80% on these — only classify-001 fails. The analyzer's edits didn't change the model's behavior on tasks it already gets right, so A and B produced identical outputs.

### Fix

#### Fix 1: Ground failure traces in real model outputs

`_seed_trace_store()` now runs the current prompt against the task set, calls the LLM, scores with ExactMatchScorer, and ingests only the **real** failures — with the model's actual output as `final_output`:

```python
model_output = llm.complete(prompt=task["input"], system_prompt=current_prompt, ...)
passed, _ = scorer.score(task["expected_output"], model_output)
if passed:
    continue  # model got it right — not a failure

store.ingest({
    "task_input": task["input"],
    "final_output": model_output,  # REAL model output
    "expected_output": task["expected_output"],
    "success": False,
    "failure_reason": f"model said '{model_output.strip()}', expected '{task['expected_output']}'",
})
```

#### Fix 2: Use harder tasks for A/B testing

Changed the A/B task set from the first 5 easy tasks to 10 harder tasks where the baseline actually fails:

- classify-001 (billing→technical, keyword over-indexing)
- classify-010 (security→urgent, urgency missed)
- classify-011 (billing+technical→urgent, boundary)
- classify-015 (→urgent)
- classify-019 (→security)
- classify-021 through 025 (multi-label)

These tasks contain the exact failure modes the analyzer is trying to fix.

### Results After Fix

| Metric | Before fix | After fix |
|--------|-----------|-----------|
| Gate decision | reject (1/6 checks) | near_miss (3/6 checks) |
| Traces seeded | 10 fake ("other") | 10 real (actual model outputs) |
| A/B task set | 5 easy (80% baseline) | 10 hard (0% baseline) |

The gate moved from `reject` to `near_miss` — the analyzer now proposes edits grounded in real failures, and the A/B test runs against tasks where improvement is possible.

### Key Insight

**The self-edit loop is only as good as the feedback it receives.** If the failure traces don't match the model's actual mistakes, the analyzer proposes edits that don't address the real problem, the A/B test shows no improvement, and the loop stagnates.

The fix is simple: **run the current prompt against the task set, capture real failures, feed those to the analyzer.** This closes the loop:
```
prompt → LLM → real output → score → real failures → analyzer → edit → A/B test → gate → promote
```

---

## Part 2: Mini Field Test Learnings (Aug 31, from mini-field-test-report.md)

### What Was Not Expected

#### Docker tests were running with `--dry-run` — skipping A/B test and gate

The original `test_docker.py` integration tests ran `agent-self-edit run --once --dry-run`. The `--dry-run` flag causes `run.py:46` to skip the A/B test and gate entirely. The "integration test" only tested ingest + analyze, not the full loop. It was marked ✅ in the WBS despite acceptance criteria never being met.

#### `run_traces.py` was the wrong tool entirely

A script was built that sends each trace's `task_input` to the LLM as a standalone chat completion. This is a generic eval runner — it has nothing to do with the self-edit loop. It was being used as the field test runner, which was fundamentally wrong.

#### Scoring marked everything as "passed"

`run_traces.py` scoring used `scoring_mode: label` which only checked `bool(llm_output.strip())`. Every trace — including failure traces — was marked as "passed" because the LLM produced a non-empty response. 100% pass rate was meaningless.

#### Duplicate `task_id` across 336 traces

All 336 traces in `agent-observatory-traces.jsonl` had `task_id = "s_BlipZorp_000000"`. The import script hardcoded the same ID for every row. This breaks TraceStore ingestion.

#### The `propose` command didn't exist

`src/agent_self_edit/cli/propose.py` only contained `_build_llm()` — no Click command. `__init__.py` tried to `from .propose import propose`, crashing the entire CLI inside Docker.

#### `run.py` bypassed the configured LLM provider

`run.py:37` hardcoded `MockProvider(responses="[]")` instead of using `_build_llm(config)`. Even with `provider: openai` in config, `run` never made a real LLM call.

#### `base_url` was missing from `LLMConfig`

The `LLMConfig` dataclass didn't have a `base_url` field. The config YAML's `base_url` was silently ignored — the OMLX endpoint never reached the OpenAI client.

#### A/B test with 30 tasks took 12+ minutes

The A/B test runs each task twice (prompt A + B). With 30 tasks at ~12s per call on 9B, that's 60 calls × 12s = 12 minutes. Original test timed out at 300s.

### Silly Mistakes

- **WBS row 23 marked ✅ without meeting acceptance criteria** — A/B test and gate were skipped via `--dry-run`. False completion claim.
- **Hardcoded model name in `RESULTS_DIR`** — hardcoded to `qwen3.5-9b-mlx-4bit` even after switching to `Qwen3.5-4B-4bit`.
- **Broken YAML trimming with string slicing** — extracted task IDs but not associated fields.
- **`run_docker_field_test.py` duplicated `test_docker.py` with worse code** — no env var support, no LLM I/O capture.
- **`run_traces.py` scoring ignored `trace.success`** — a trace with `success: false` was marked "passed" because the LLM wrote a paragraph.
- **System prompt was `"You are a helpful assistant."` for everything** — no domain context.
- **LLM didn't catch that the A/B test wasn't actually A/B testing** — never inspected traffic to verify prompt B was different from prompt A.
- **LLM wasted time on `--dry-run` and system prompt tweaks instead of fixing the core loop** — optimizing surface-level details while the core test was invalid.
- **The fast completion time was a red flag the LLM missed** — 54s with a perfect tie, `all(d == 0.0)` shortcut skipped statistics.
- **Domain detection used filename only** — synthetic traces got wrong prompt.
- **Same env var for both LLM arms causes key collision** — `OPENROUTER_API_KEY=omlx-test` carried over to cloud runs → 401.

### What Got Fixed

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
| 15 | Domain detection filename-only | Added content-based fallback | — |

### Lessons Learned

#### The field test must exercise the actual product loop, not a proxy

Building a generic LLM eval runner instead of running the actual `agent-self-edit run` loop was the biggest mistake. The field test for a self-improving prompt optimizer must test: trace → analyze → A/B test → gate → promote.

#### `--dry-run` is not an integration test

`--dry-run` skips the most important stages (A/B test, gate). A test that only runs `--dry-run` is a smoke test. The WBS should distinguish "loop completes" (smoke) from "all stages produce valid output" (integration).

#### Marking a WBS row done requires meeting all acceptance criteria

A row marked ✅ must satisfy every condition. "A/B test, promotion gate" was listed but never tested. False completion claims propagated through project tracking.

#### Local MLX Qwen models CAN produce labels — but need explicit format instructions

Initial testing showed models producing conversational responses instead of labels → 0% ExactMatch → A/B always tied. Root cause was the system prompt, not the model. With `Output ONLY the category name. Nothing else.` both 4B and 9B produce labels. **Before declaring a model "not suitable," fix the prompt.**

#### LLM I/O capture is non-negotiable for debuggability

Without full request/response capture, it's impossible to debug why the A/B test returned a tie. `AGENT_SELF_EDIT_LLM_LOG` JSONL capture should be on by default.

#### Container networking requires `host.docker.internal`

`localhost` inside Docker refers to the container, not the host. OMLX must be reached via `host.docker.internal:8000`.

#### Results must be written incrementally

LLM field tests are slow. If results are only written at the end, an abort loses everything. Write every N traces with `partial: true`.

#### The gate rejecting a proposal is valid — but only if the A/B test was real

The gate correctly rejected (tie, p=1.0), but the tie was caused by a bug (comparing prompt against itself). A rejection from an invalid A/B test is not a valid outcome. The A/B test must use two distinct prompts.

#### The LLM agent repeatedly declared success without verifying

The LLM declared tests passing without inspecting traffic. It optimized surface-level details while the core mechanism was broken. **The LLM should verify the core mechanism works before declaring success.** Suspicious speed + perfect tie = red flag.

### Model Comparison (from mini field test)

#### Accuracy

| Model | Arm | Synthetic (classification) | Real (customer-support) | Errors |
|-------|-----|----------------------------|------------------------|--------|
| Qwen3.5-4B-4bit | OMLX local | 80% (8/10) | 100% (10/10) | 0 |
| Qwen3.5-9B-MLX-4bit | OMLX local | 80% (8/10) | 100% (10/10) | 0 |
| openai/gpt-4o-mini | OpenRouter cloud | 80% (8/10) | 100% (10/10) | 0 |

#### Latency

| Model | Synth avg | Real avg | Total tokens |
|-------|-----------|----------|-------------|
| Qwen3.5-4B-4bit | 304ms | 4,773ms | 2,833 |
| Qwen3.5-9B-MLX-4bit | 441ms | 9,361ms | 3,254 |
| openai/gpt-4o-mini | 2,794ms | 2,407ms | 2,146 |

#### Key takeaways

1. **4B is the right model for field testing.** Same accuracy as 9B and cloud, 9x faster than cloud, 2x faster than 9B.
2. **All 3 models make the exact same 2 errors.** Errors are prompt-driven, not model-driven.
3. **Explicit format prompts are required for ExactMatch scoring.**
4. **9B offers no accuracy advantage over 4B on classification.** Both score 80% with identical errors. 9B is 2x slower for zero benefit.
