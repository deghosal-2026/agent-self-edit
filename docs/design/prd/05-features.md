# 05 — Features

> Sub-document of the [Design overview](../README.md). Complete feature set for v0.1.0 through v0.4.0.

## 5.1 Feature Naming

Features are numbered F-01 through F-N. Each row includes: ID, title, description, priority, and version.

## 5.2 v0.1.0 Features (Must-Have)

| ID | Title | Description | Priority |
|---|---|---|---|
| F-01 | Execution trace ingestion | Agent feeds execution traces (task, steps, output, success/failure) into the analyzer. Traces are stored in a local SQLite database | P0 |
| F-02 | Feedback analyzer | An LLM reviews execution traces and produces structured failure diagnoses plus concrete prompt-edit proposals, each with a written hypothesis | P0 |
| F-03 | A/B test engine | Compares candidate edits against the current prompt on a held-out task set. Reports win rate, confidence interval, effect size | P0 |
| F-04 | Promotion gate | Enforces statistical and safety criteria before any edit is promoted. Checks: sample floor, effect size, confidence interval, frozen sections, edit distance, drift | P0 |
| F-05 | Prompt registry | Versioned store of every prompt with full lineage. Supports diff, rollback, and history queries | P0 |
| F-06 | Frozen core sections | User annotates sections of the prompt that the analyzer cannot modify. The guardrail module enforces this | P0 |
| F-07 | Edit-distance limit | Maximum number of lines the analyzer can change per edit cycle. Configurable by the user | P0 |
| F-08 | Prompt diff visualization | Side-by-side or inline diff showing exactly what changed between any two prompt versions | P0 |
| F-09 | CLI | `agent-self-edit` CLI with commands for init, run, diff, rollback, guardrails, and status | P0 |
| F-10 | Held-out task set management | User provides a held-out task set for A/B evaluation. Tasks can be added or removed without restarting the loop | P0 |
| F-11 | Near-miss logging | Rejected edits are logged with the guardrail that blocked them and the reasoning. The analyzer learns from near-misses | P1 |
| F-12 | Rollback | One-command rollback to any previous prompt version. The rollback is logged in the registry | P0 |
| F-13 | Config file | YAML/TOML configuration for guardrail thresholds, sample floors, trigger modes, and held-out task set path | P0 |
| F-14 | Docker support | Dockerfile and docker-compose for running the loop as a sidecar | P1 |

## 5.3 v0.2.0 Features

| ID | Title | Description | Priority |
|---|---|---|---|
| F-20 | Drift detection | Semantic similarity comparison between current prompt and original. Alerts when drift exceeds configurable threshold | P1 |
| F-21 | Divergence alerts | When drift exceeds threshold, operator is notified and prompted to review | P1 |
| F-22 | Edit density visualization | Per-section heatmap showing which parts of the prompt change most over time | P1 |
| F-23 | Near-miss feedback loop | The analyzer adapts its proposal generation based on which edits were rejected and why | P1 |
| F-24 | Web dashboard | React-based dashboard showing timeline, diffs, guardrail reports, and rollback controls | P1 |
| F-25 | REST API | FastAPI-based REST API for programmatic access to diff, rollback, and registry queries | P1 |

## 5.4 v0.3.0 Features

| ID | Title | Description | Priority |
|---|---|---|---|
| F-30 | Multi-failure clustering | Analyzer identifies skill gaps across multiple traces, not just one-off mistakes | P2 |
| F-31 | Adaptive sample-floor sizing | Sample floor adjusts based on observed variance in the held-out task set | P2 |
| F-32 | Evals integration | Integration with EvalForge for held-out task evaluation and scoring | P2 |
| F-33 | Framework adapters | Adapters for common agent frameworks (LangGraph, PydanticAI, CrewAI) | P2 |
| F-34 | Guardrail history dashboard | Timeline of guardrail pass/fail rates, near-miss trends, and drift scores | P2 |

## 5.5 v0.4.0 Features

| ID | Title | Description | Priority |
|---|---|---|---|
| F-40 | Fleet-wide shared-rules learning | Aggregate near-miss patterns across multiple agents to identify shared prompt improvements | P3 |
| F-41 | Cost-aware self-improvement | Improve quality without inflating token spend. Track cost per edit and per improvement | P3 |
| F-42 | Promotion analytics | Regression reports, per-segment performance tracking, and A/B test archive | P3 |
| F-43 | Shadow mode | Run the full loop without modifying the prompt. Review proposed edits before enabling promotion | P2 |

## 5.6 Feature Priority Matrix

| Priority | Meaning | Count |
|---|---|---|
| P0 | Ship-blocking for v0.1.0 | 12 |
| P1 | Important but deferrable to v0.2.0 | 6 |
| P2 | Valuable but not urgent (v0.3.0) | 4 |
| P3 | Long-term vision (v0.4.0+) | 4 |