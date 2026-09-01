# 4,150 Calls, 37 Minutes, $0.00

## Hook

We ran 15 iterations of a self-edit loop against a local 4B model. 4,150 LLM calls. 716,580 tokens. 37 minutes. $0.00. Same accuracy as a 9B model and cloud gpt-4o-mini.

## Summary

We ran 15 iterations of a self-edit loop against a local 4B model. 4,150 LLM calls. 716,580 tokens. 37 minutes total. $0.00 cost. The same run on cloud (gpt-4o-mini) would have taken 3+ hours and cost money. All 3 models we tested (4B, 9B, cloud) produced identical classification outputs and identical errors. The errors were prompt-driven, not model-driven. The 4B local model was not just sufficient — it was optimal.

## Key Points

- Cost comparison: 4,150 calls, 716K tokens, $0.00 (local) vs ~$0.11 (cloud equivalent)
- Speed: 540ms avg/call on 4B vs 2,794ms on cloud (9x slower)
- Accuracy: all 3 models score 80% with identical errors — errors are prompt-driven
- When cloud matters (generation, extraction, multi-step reasoning) vs when it doesn't
- Local MLX (Apple Silicon) as a viable inference backend for iterative testing
- The "fix the prompt before blaming the model" lesson

## Learnings

- For classification (ExactMatch, single-label), the smallest sufficient model wins
- Cloud adds latency, jitter, and cost for zero accuracy benefit when errors are prompt-driven
- Local MLX on Apple Silicon is a viable inference backend for iterative testing
- The entire 15-iteration field test cost nothing — cost ceiling is irrelevant with local inference
- A bigger model doesn't fix a bad prompt

## Experience

- Ran 10 traces × 3 models as a baseline mini field test
- All 60 LLM calls captured with full request/response, tokens, latency
- 4B classified in 304ms — fast enough for iterative A/B testing (26 tasks × 2 prompts in ~30s)
- Switched entirely to 4B for the 15-iteration improvement loop
- 4,150 calls completed in 37 minutes with zero cost

## What Went Well

- The mini field test made the model comparison data-driven, not vibes-based
- 4B's speed made 15-iteration loops feasible (each iteration ~42s with 50 traces)
- Dropping cloud and 9B simplified the setup and removed cost/jitter

## What Could Have Gone Better

- Should have started with 4B only instead of testing all 3 models
- The cloud run had env var collisions (same key for OMLX and OpenRouter) causing 401s
- 9B was 2x slower for zero benefit — wasted time on it initially

## Data

- 4,150 calls, 716,580 tokens, 2,239s wall time, 540ms avg latency
- gpt-4o-mini equivalent cost: $0.11
- Actual cost: $0.00
- 4B: 540ms/call, 9B: 441ms easy / 9,361ms real, cloud: 2,794ms

## Audience

AI engineers choosing between local and cloud LLMs, cost-conscious teams.
