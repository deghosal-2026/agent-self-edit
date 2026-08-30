# Design — AgentSelfEdit

> This README is the overview and index for the product requirements (the `prd/` sub-docs). Start here.

**Version:** 0.1 (Draft)
**Date:** 2026-08-30
**Owner:** Debashish Ghosal
**Repo:** `deghosal-2026/agent-self-edit`

---

## Executive Summary

AgentSelfEdit is an open-source framework that lets AI agents improve their own system prompts through a guarded self-improvement loop. After each task, the agent analyzes what went wrong, proposes concrete prompt edits, A/B tests them against the current prompt, and promotes only the statistically-proven winner — with guardrails that prevent a bad edit from spiraling.

The insight that justifies the project: **every production agent gets prompt-tuned once by hand, then never again.** The agent that sees the most failure data is the least able to use it. Most frameworks gesture at this with a `reflect` step that appends prose to context and calls it learning — that is context bloat, not improvement. A real self-improvement loop requires three things almost nobody ships: a mechanism that *proposes* concrete prompt edits, an A/B test that *proves* an edit is better rather than merely different, and a promotion gate that *prevents* a bad edit from poisoning the baseline.

**Core architectural principle:** The promotion gate is the product. Everything else — the analyzer, the A/B engine, the registry — is downstream of the one question that matters: can you *prove* one prompt is better than another, safely? If the gate is sound, the loop is straightforward. If it isn't, no amount of clever editing matters.

---

## PRD Document Map

| # | Sub-document | Covers |
|---|---|---|
| 01 | [prd/01-why.md](prd/01-why.md) | Why — market context, the pain, OSS goals |
| 02 | [prd/02-architecture.md](prd/02-architecture.md) | What — core components, loop, guardrails, non-goals |
| 03 | [prd/03-landscape.md](prd/03-landscape.md) | Landscape & identity — competitive table, the gap |
| 04 | [prd/04-users-and-cujs.md](prd/04-users-and-cujs.md) | Target users + CUJs |
| 05 | [prd/05-features.md](prd/05-features.md) | Feature set (F-01…F-N) |
| 06 | [prd/06-security-baseline.md](prd/06-security-baseline.md) | OpenSSF / security baselines |
| 07 | [prd/07-success-metrics.md](prd/07-success-metrics.md) | Success criteria & reliability |
| 08 | [prd/08-risks.md](prd/08-risks.md) | Risks & open questions |
| 09 | [prd/09-roadmap.md](prd/09-roadmap.md) | Milestone roadmap (v0.1.0 → v0.4.0) |

---

## Connected

- **Vault:** [[projects/High/149-AgentSelfEdit.md]]
- **Siblings:** EvalForge (held-out task evaluation) · ToolTrust (guardrail primitives) · Braintrust (eval tracing) · PromptForge (prompt version control) · LessonExtractor (consumes failed-edit patterns)