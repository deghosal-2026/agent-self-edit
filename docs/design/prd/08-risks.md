# 08 — Risks

> Sub-document of the [Design overview](../README.md). Risks, open questions, and mitigations.

## 8.1 Risk Matrix

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-01 | A single fluke edit promoted on noise poisons the baseline | Medium | Critical | Statistical promotion gate with sample floor, confidence intervals, and effect-size threshold. Drift detection alerts on divergence |
| R-02 | The analyzer proposes the same bad edit repeatedly | Medium | Medium | Near-miss logging captures rejected edits. The analyzer learns from near-misses to avoid re-proposing |
| R-03 | The prompt drifts too far from original intent over many iterations | Low | High | Drift detection compares current prompt to original. Configurable threshold alerts operator. Rollback is one command |
| R-04 | The held-out task set doesn't represent real-world distribution | Medium | High | User provides the held-out set. Multiple sets can be rotated. Per-task performance tracking reveals gaps |
| R-05 | The A/B test engine overfits to the held-out set | Low | Medium | Held-out set is separate from training set. Multiple held-out sets can be used. Regular rotation |
| R-06 | Users don't trust the system to edit their prompts | High | High | Shadow mode (v0.2.0) lets users review edits without risk. Diff visualization shows exactly what changed. Guardrail report proves safety |
| R-07 | The LLM analyzer costs too much to run continuously | Medium | Medium | Batch mode (analyze after N tasks). Configurable trigger frequency. Cost tracking per edit cycle |
| R-08 | The guardrails are too strict and block good edits | Medium | Medium | Configurable thresholds. Near-miss logging shows blocked edits. Users can adjust thresholds |
| R-09 | The guardrails are too lenient and let bad edits through | Low | Critical | Multiple guardrails in sequence (defense in depth). Each guardrail is independent. Red-team testing before release |
| R-10 | The system requires too much manual setup | Medium | Medium | CLI init scaffolds config. Default guardrail thresholds work out of the box. Shadow mode for first run |

## 8.2 Open Questions

| # | Question | Decision needed | By when |
|---|---|---|---|
| Q-01 | Should the analyzer be the same model as the agent or a different one? | Same model is cheaper but shares blind spots. Different model is more expensive but more independent | v0.1.0 design review |
| Q-02 | What is the minimum sample floor for the A/B test engine? | Too low = noisy. Too high = slow to improve. Need to benchmark | v0.1.0 field test |
| Q-03 | Should the system auto-promote or require manual approval? | Auto-promote is the product vision. Manual approval is safer for early adopters | v0.1.0 design review |
| Q-04 | How do we handle multi-agent deployments where the same prompt is shared across agents? | Fleet-wide learning is deferred to v0.4.0. For v0.1.0, each agent has its own prompt and registry | v0.1.0 design review |
| Q-05 | What happens when the agent's task distribution changes significantly? | The held-out set may become stale. Need a mechanism to detect distribution shift | v0.2.0 |
| Q-06 | Should the system support editing tool definitions or just the system prompt? | Prompts only for v0.1.0. Tool definitions are deferred | v0.1.0 design review |

## 8.3 Hard Parts

1. **Evaluation safety** — proving an edit made the agent better, not just different. The statistical gate is the hardest part to get right.

2. **Drift prevention** — keeping a self-modifying system aligned with its original intent over hundreds of iterations.

3. **User trust** — convincing users that a self-editing agent is safe. The diff visualization and guardrail report are the primary trust mechanisms.

4. **Cost management** — the LLM analyzer and A/B test engine both consume tokens. Cost per improvement must be predictable and bounded.