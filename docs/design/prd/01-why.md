# 01 — Why (Business Requirements)

> Sub-document of the [Design overview](../README.md). Covers the market context, the pain we remove, and why this matters for the OSS portfolio.

## 1.1 The market context

The agent ecosystem has raced ahead on orchestration and retrieval, but has completely skipped the single capability that would make agents feel *alive*: the ability to get measurably better at their own job over time.

- **Prompts freeze on day one.** Every production agent gets prompt-tuned by hand, usually by the human who wrote it, usually once, and then never again. The prompt freezes the moment it ships. Every subsequent failure is a bug the human has to fix manually.
- **Feedback dies at the point of execution.** The agent that actually executes the tasks sees, task after task, exactly where its own instructions fail — the edge cases, the ambiguous inputs, the tool-selection mistakes. Yet the feedback dies on the spot. Nothing captures it, and nothing acts on it.
- **"Reflection" is not learning.** Most frameworks gesture at this with a `reflect` step that appends a paragraph of prose to context and calls it learning. That is not learning; that is context bloat. The prompt itself never changes, so the same failure repeats tomorrow.
- **Self-improvement is the most talked-about and least-built capability in agentic AI.** The narrative writes itself — a system that measurably gets better on its own — but almost nobody ships a real, safe version of it.

## 1.2 The pain we remove

| Status quo | Pain |
|---|---|
| Hand-tuned prompts, tuned once, frozen forever | Every recurring failure silently absorbed until a human manually tunes again |
| "Reflection" step appends prose to context | Context bloat, not learning; same failure repeats |
| Self-editing is terrifying | No guardrails, no statistical validation, no rollback — a single bad edit poisons the baseline |
| No prompt lineage | When a prompt does change, no recorded history of what changed, why, or how to revert |
| Manual A/B testing of prompts | Humans run informal side-by-side comparisons, no statistical rigor, no sample-size discipline |

## 1.3 Why it matters for the OSS portfolio

- **For agent builders:** a safe, evidence-driven self-improvement loop that turns execution feedback into better prompts — without a human hand-tuning every iteration.
- **For platform teams:** a versioned, auditable history of why a prompt is the way it is, with one-click rollback and full lineage.
- **For the solo-build OSS portfolio:** a Tier-1, high-engagement problem — self-improvement is the most captivating story in agentic AI, with a sharp article series and strong family compatibility:
  - **EvalForge** provides held-out task evaluation and scoring
  - **ToolTrust** provides guardrail and trust primitives
  - **Braintrust** provides eval and tracing infrastructure
  - **PromptForge** provides prompt version control and deployment discipline

## 1.4 Grounded in (sources)

- Industry pattern: most production agents are prompt-tuned once by the human who wrote them, then never again
- Self-correction blind spot (arXiv 2507.02778) — 64.5% average across 14 LLMs for same-model review
- Voyager ablation (arXiv 2305.16291) — self-verification accumulates correct skills
- OWASP Top 10 for Agentic Applications 2026 — ASI08 (Cascading Failures), ASI09 (Misaligned Behavior)