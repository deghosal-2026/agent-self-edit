# Mini Field Test Report — 10 Traces × 3 Models

> Quick field test: 10 synthetic classification traces + 10 real customer-support traces run through 3 LLM arms. Validates that traces produce labels (synthetic) and responses (real) with correct domain detection and scoring.

**Date:** 2026-08-31  
**Sample size:** 10 traces per arm per trace type  
**Trace types:** Synthetic classification (ExactMatch), Real customer-support (label mode)

---

## 1. Summary

All three models completed 10/10 traces with zero errors. Synthetic classification accuracy is identical across all three models: 80% (8/10 correct). Real customer-support traces scored 100% (label mode — non-empty response). All three models made the same two classification errors.

| Model | Arm | Synthetic accuracy | Real accuracy | Errors | Avg latency (synth) |
|-------|-----|-------------------|---------------|--------|---------------------|
| Qwen3.5-4B-4bit | OMLX local | 80% | 100% | 0 | 304ms |
| Qwen3.5-9B-MLX-4bit | OMLX local | 80% | 100% | 0 | 441ms |
| openai/gpt-4o-mini | OpenRouter cloud | 80% | 100% | 0 | 2,794ms |

---

## 2. Synthetic Classification Results

**System prompt (auto-detected as `classification`):**
```
Classify the input into exactly one of: urgent, billing, technical, feature, security, other.
Output ONLY the category name. Nothing else. No explanation. No reasoning.
```

### Qwen3.5-4B-4bit (OMLX local)

| task_id | expected | LLM output | passed |
|---------|----------|------------|--------|
| classify-001 | technical | billing | ❌ |
| classify-002 | billing | billing | ✅ |
| classify-003 | feature | feature | ✅ |
| classify-004 | technical | technical | ✅ |
| classify-005 | feature | feature | ✅ |
| classify-006 | security | security | ✅ |
| classify-007 | technical | technical | ✅ |
| classify-008 | billing | billing | ✅ |
| classify-009 | technical | technical | ✅ |
| classify-010 | urgent | security | ❌ |

**Accuracy: 8/10 (80%)**

### Qwen3.5-9B-MLX-4bit (OMLX local)

| task_id | expected | LLM output | passed |
|---------|----------|------------|--------|
| classify-001 | technical | billing | ❌ |
| classify-002 | billing | billing | ✅ |
| classify-003 | feature | feature | ✅ |
| classify-004 | technical | technical | ✅ |
| classify-005 | feature | feature | ✅ |
| classify-006 | security | security | ✅ |
| classify-007 | technical | technical | ✅ |
| classify-008 | billing | billing | ✅ |
| classify-009 | technical | technical | ✅ |
| classify-010 | urgent | security | ❌ |

**Accuracy: 8/10 (80%)**

### openai/gpt-4o-mini (OpenRouter cloud)

| task_id | expected | LLM output | passed |
|---------|----------|------------|--------|
| classify-001 | technical | billing | ❌ |
| classify-002 | billing | billing | ✅ |
| classify-003 | feature | feature | ✅ |
| classify-004 | technical | technical | ✅ |
| classify-005 | feature | feature | ✅ |
| classify-006 | security | security | ✅ |
| classify-007 | technical | technical | ✅ |
| classify-008 | billing | billing | ✅ |
| classify-009 | technical | technical | ✅ |
| classify-010 | urgent | security | ❌ |

**Accuracy: 8/10 (80%)**

---

## 3. Real Customer-Support Results

**System prompt (auto-detected as `customer-support`):**
```
You are a customer support agent. Respond helpfully and professionally to the customer's issue.
```

All three models produced helpful, professional responses to all 10 real customer support traces. Scoring is label mode (pass = non-empty, non-error response).

| Model | Accuracy | Tokens | Avg latency |
|-------|----------|--------|-------------|
| Qwen3.5-4B-4bit | 100% | 2,173 | 4,773ms |
| Qwen3.5-9B-MLX-4bit | 100% | 2,594 | 9,361ms |
| openai/gpt-4o-mini | 100% | 1,548 | 2,407ms |

---

## 4. Latency Comparison

| Model | Synth avg latency | Real avg latency | Total tokens (synth + real) |
|-------|-------------------|------------------|----------------------------|
| Qwen3.5-4B-4bit | 304ms | 4,773ms | 2,833 |
| Qwen3.5-9B-MLX-4bit | 441ms | 9,361ms | 3,254 |
| openai/gpt-4o-mini | 2,794ms | 2,407ms | 2,146 |

Key observations:
- **4B is fastest on classification** (304ms — single label output, small model)
- **9B is 2x slower than 4B** on real traces (9,361ms vs 4,773ms)
- **Cloud has network overhead** — 2,794ms for a single label includes round-trip to OpenRouter
- **9B uses more tokens** — 3,254 vs 2,833 for 4B, suggesting more verbose responses

---

## 5. Classification Errors Analysis

All three models made the **same two errors**:

| task_id | input | expected | all 3 models output | error type |
|---------|-------|----------|---------------------|------------|
| classify-001 | "My billing page shows the wrong amount for my subscription." | technical | billing | Keyword over-indexing — model sees "billing" and picks billing, ignores "wrong amount" (a system bug) |
| classify-010 | "I think my account was compromised — someone logged in from an unknown IP." | urgent | security | Misclassification — model picks security (correct domain) but misses urgency (account compromise = urgent) |

These are exactly the kind of classification errors the self-edit loop is designed to fix — the analyzer should identify that the model over-indexes on keywords and propose a prompt edit that instructs it to consider the root cause, not the surface keyword.

---

## 6. Key Findings

1. **All three models produce labels with the right prompt.** The explicit format instruction (`Output ONLY the category name. Nothing else.`) works for 4B, 9B, and cloud models alike. The earlier 0% accuracy was a prompt problem, not a model capability problem.

2. **All three models make identical classification errors.** This suggests the errors are inherent to the task/prompt combination, not model-specific. The self-edit loop should be able to address these.

3. **4B is the best choice for iterative field testing.** Fastest on classification (304ms), comparable accuracy (80%), and completes 10 traces in seconds. The 9B offers no accuracy advantage on this task.

4. **Cloud is not faster for classification.** Despite being a larger model, gpt-4o-mini takes 2,794ms per classification call due to network round-trip. The 4B local model at 304ms is 9x faster.

5. **Real trace scoring (100%) is not meaningful.** Label mode passes any non-empty response. The customer-support traces need a better scoring mechanism — perhaps LLM-as-judge or relevance scoring.

6. **Domain auto-detection works after the fix.** `/tmp/synth.jsonl` correctly detected as `classification` via content-based fallback (checking `expected_output` against known labels).

---

## 7. What This Means for the Self-Edit Loop

The 80% baseline accuracy on classification is the starting point. The self-edit loop should:

1. Feed the 2 failed classification traces to the analyzer
2. Analyzer identifies the keyword over-indexing pattern ("billing" → billing, ignoring "wrong amount")
3. Proposes a prompt edit: "When the user mentions a billing page but describes a system error (wrong amount, page not loading), classify as technical, not billing."
4. A/B test the edited prompt against the current prompt on the held-out task set
5. If the edit improves accuracy (e.g. from 80% to 90%), the gate promotes it
6. Loop repeats

This is the core value proposition of AgentSelfEdit — and the field test shows the loop has real work to do (2/10 classification errors to fix).
