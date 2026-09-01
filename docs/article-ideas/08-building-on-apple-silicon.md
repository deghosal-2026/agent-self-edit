# Building a Self-Improving Prompt System on Apple Silicon

## Hook

No cloud API. No GPU cluster. Just a MacBook, a 4B local model, and a loop that rewrites its own prompt. Here's what we learned.

## Summary

This article is the engineering story: how we built AgentSelfEdit, a sidecar that observes execution traces and rewrites its own system prompt through a closed loop (trace → analyze → A/B test → gate → promote). We ran the entire field test on a MacBook with a local 4B Qwen model via MLX. No cloud API keys, no GPU rentals, no per-token costs. 4,150 LLM calls in 37 minutes. The system works end-to-end. The gate correctly rejects underpowered improvements. The loop is mechanically sound.

## Key Points

- The architecture: TraceStore (SQLite) → FeedbackAnalyzer (LLM) → ABTestEngine (permutation test + bootstrap CI) → PromotionGate (6 deterministic checks) → Registry (versioned prompts)
- Why we chose local MLX (Apple Silicon): free, fast (540ms/call), no network dependency, no API keys
- The 4B model produces valid classification labels and valid analyzer proposals — it's smart enough
- The loop runs without Docker for local testing, and inside Docker for containerized validation
- LLM I/O capture via `AGENT_SELF_EDIT_LLM_LOG` — every request/response logged to JSONL
- Per-iteration artifacts: prompt-a.md, prompt-b.md, results-a.json, results-b.json, ab-comparison.json
- The gate's 6 checks: sample floor, effect size, confidence, frozen sections, edit distance, drift
- Why the gate rejecting is the success condition, not the failure condition

## Learnings

- You don't need cloud APIs to build and test a self-improving prompt system
- A 4B local model on Apple Silicon is fast enough for iterative A/B testing (26 tasks × 2 prompts in 30s)
- The system's value is in the gate, not the optimizer — the gate is what makes it safe
- LLM I/O capture is the single most important debugging tool — every bug was found via traffic inspection
- Fabricated test data is the #1 risk — if your failure traces don't match real model behavior, the loop optimizes against nothing

## Experience

- Built the full system: TraceStore, Analyzer, ABTestEngine, PromotionGate, Registry, CLI, Docker
- Ran 15 iterations against Qwen3.5-4B-4bit on local MLX
- 4,150 LLM calls, 716,580 tokens, 37 minutes, $0.00
- 9 Docker tests pass (build, connectivity, CLI, full loop, propose)
- 31 issues fixed across the session — each found via LLM traffic inspection

## What Went Well

- Local 4B made iterative debugging fast and free — no API rate limits, no cost anxiety
- The per-iteration artifacts made every A/B test inspectable
- The 6-check gate architecture made it clear which check blocked promotion
- Docker tests proved the system works in a containerized environment

## What Could Have Gone Better

- Started with fake test data — should have grounded traces in real model outputs from day one
- The confidence check was inverted — should have been caught in unit tests
- The analyzer has no rejection feedback — it proposes the same edit every iteration
- Non-LLM hermetic tests were not run in this session

## Data

- 4,150 LLM calls, 716,580 tokens, 37 minutes, $0.00
- 15 iterations, all rejected (p=0.23 >= 0.05)
- 9/9 Docker tests pass
- 31 issues fixed
- System: Python 3.14, Click CLI, SQLite trace store, file-based prompt registry

## Audience

AI engineers, indie hackers, anyone building LLM systems without cloud API budgets.
