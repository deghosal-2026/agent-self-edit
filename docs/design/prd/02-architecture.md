# 02 — Architecture

> Sub-document of the [Design overview](../README.md). Covers the core components, loop design, guardrails, and non-goals.

## 2.1 Architecture Overview

AgentSelfEdit is a self-improvement loop wrapped around an existing agent. It does not modify the agent's runtime — it sits alongside it, observing execution traces and proposing prompt edits.

```
┌─────────────────────────────────────────────────────────────────┐
│                     AgentSelfEdit Loop                           │
│                                                                 │
│   ┌──────────┐    ┌──────────────┐    ┌──────────────────┐      │
│   │  Agent    │───▶│  Execution   │───▶│  Feedback        │      │
│   │  executes │    │  Trace       │    │  Analyzer (LLM)  │      │
│   │  task     │    │  (stored)    │    │                  │      │
│   └──────────┘    └──────────────┘    └────────┬─────────┘      │
│                                                │                 │
│                                                ▼                 │
│   ┌──────────┐    ┌──────────────┐    ┌──────────────────┐      │
│   │  Prompt  │◀───│  Promotion   │◀───│  A/B Test        │      │
│   │  Registry│    │  Gate        │    │  Engine           │      │
│   │  (v1..vN)│    │  (statistical│    │  (held-out tasks) │      │
│   │          │    │   + safety)  │    │                  │      │
│   └──────────┘    └──────────────┘    └──────────────────┘      │
│                        │                                        │
│                        ▼                                        │
│               ┌──────────────────┐                              │
│               │  Diff Viz +      │                              │
│               │  Dashboard       │                              │
│               └──────────────────┘                              │
└─────────────────────────────────────────────────────────────────┘
```

## 2.2 Core Components

### 2.2.1 Feedback Analyzer

An LLM that reviews execution traces and produces structured failure diagnoses plus concrete prompt-edit proposals.

**Input:** Execution trace (task, steps, output, success/failure), current prompt with frozen-section annotations.
**Output:** One or more edit proposals, each with: the exact instruction change, the section of the prompt to modify, the hypothesis for why this change should improve outcomes, and the evidence from the trace that supports it.

**Non-goals:** The analyzer does not edit the prompt directly. It only proposes. All edits go through the A/B test engine and promotion gate.

### 2.2.2 A/B Test Engine

Compares candidate edits against the current prompt on a held-out task set.

**Input:** Current prompt, candidate prompt, held-out task set.
**Output:** Win rate, confidence interval, effect size, per-task performance breakdown.

**Design constraints:**
- Held-out task set is configurable and domain-specific
- Minimum sample floor enforced before any promotion decision
- Confidence intervals computed via bootstrap resampling
- Effect-size threshold configurable per deployment

### 2.2.3 Promotion Gate

The safety-critical component. Enforces statistical and safety criteria before any edit is promoted.

**Checks (in order):**
1. Sample floor — minimum number of A/B trials completed
2. Effect size — improvement exceeds minimum threshold
3. Confidence interval — p-value below threshold
4. Frozen core sections — no changes to protected sections
5. Edit-distance limit — total changes within bounds
6. Drift detection — divergence from original intent below threshold

**Outcomes:**
- **Promoted** — all checks pass, edit becomes new baseline
- **Rejected** — any check fails, edit archived with full reasoning
- **Near-miss** — rejected but close to passing, logged for human review

### 2.2.4 Prompt Registry

Versioned store of every prompt with full lineage.

**Data per version:**
- Full prompt text
- Diff from previous version
- Analyzer's hypothesis (if promoted)
- A/B test results (if promoted)
- Guardrail check results
- Timestamp, model version, trigger trace IDs

**Operations:**
- `get(version)` — retrieve prompt by version
- `diff(v1, v2)` — diff between any two versions
- `rollback(version)` — promote a previous version to current
- `lineage()` — full history with metadata

### 2.2.5 Guardrail Module

Enforces constraints on prompt evolution.

**Guardrails:**
- **Frozen core sections** — annotated paragraphs the analyzer cannot modify
- **Edit-distance limit** — maximum number of lines changed per cycle
- **Drift detection** — semantic similarity to original prompt, alerts on divergence
- **Near-miss logging** — captures rejected edits so the analyzer learns not to re-propose

### 2.2.6 Diff Visualization + Dashboard

See [prompt-diff-design.md](../prompt-diff-design.md) for full design.

## 2.3 The Self-Improvement Loop

```
1. Agent executes task → execution trace stored
2. Trace accumulates until batch threshold or time trigger
3. Feedback Analyzer reviews traces → produces edit proposals
4. A/B Test Engine runs each candidate against held-out tasks
5. Promotion Gate checks all criteria
6. If promoted: prompt updated in Registry, agent picks up new prompt
7. If rejected: edit archived, analyzer notified of rejection reason
8. Dashboard updated with diff, evidence, guardrail results
```

**Trigger modes:**
- **Batch** — analyze after N tasks (default: 50)
- **Time-based** — analyze every N hours (default: 24)
- **Manual** — user triggers analysis on demand

## 2.4 Non-Goals

- Replace human review entirely — near-misses flagged for human inspection
- Become a general prompt-optimization benchmark suite
- Mutate code, tool schemas, or anything beyond the system prompt
- Guarantee convergence — the goal is safe improvement, not a provable optimum
- Multi-agent coordinated self-improvement (fleet-wide shared rules) — deferred to v0.4.0
- Self-improvement of tool definitions or runtime configs — prompts only for v0.1.0

## 2.5 Key Design Decisions

| Decision | Rationale |
|---|---|
| Analyzer is an LLM, not a rule engine | Execution traces are unstructured; only an LLM can interpret failure modes and propose nuanced edits |
| Promotion gate is deterministic | The gate must be verifiable, testable, and non-negotiable. Statistical checks are code, not prompts |
| Held-out task set is user-provided | The system cannot evaluate itself on its own tasks without overfitting. The user provides the ground truth |
| Prompt registry is versioned in git | Git provides free diff, rollback, branching, and merge. The registry is a thin layer on top |
| Frozen sections are annotation-based | The user marks sections that must not change. The analyzer reads the annotations and respects them |