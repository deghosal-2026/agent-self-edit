# 09 — Roadmap

> Sub-document of the [Design overview](../README.md). Milestone roadmap from v0.1.0 through v0.4.0.

## 9.1 Release Cadence

| Version | Target | Focus | Scope |
|---|---|---|---|
| v0.1.0 | Sep 2026 | Core loop | Analyzer, A/B test engine, promotion gate, prompt registry, CLI, guardrails, diff visualization |
| v0.2.0 | Oct 2026 | Dashboard + drift | Web dashboard, drift detection, edit density, near-miss feedback, REST API |
| v0.3.0 | Nov 2026 | Scale + adapters | Multi-failure clustering, adaptive sample floors, evals integration, framework adapters |
| v0.4.0 | Dec 2026 | Fleet | Fleet-wide shared-rules learning, cost-aware improvement, promotion analytics, shadow mode |

## 9.2 v0.1.0 Milestones

| M | Focus | Issues | Features |
|---|---|---|---|
| M1 | Scaffold + config | F-13 | Repo, CI, config file, held-out task set management |
| M2 | Feedback analyzer | F-01, F-02 | Trace ingestion, analyzer LLM, edit proposal format |
| M3 | A/B test engine | F-03 | Held-out task evaluation, win rate, confidence intervals, effect size |
| M4 | Promotion gate | F-04, F-11 | Sample floor, effect size, CI, frozen sections, edit distance, drift, near-miss logging |
| M5 | Prompt registry | F-05, F-12 | Versioned store, diff, rollback, lineage |
| M6 | Guardrail module | F-06, F-07 | Frozen core sections, edit-distance limit, drift detection |
| M7 | Diff visualization | F-08, F-22 | Side-by-side/inline diff, edit density, guardrail report |
| M8 | CLI | F-09 | init, run, diff, rollback, guardrails, status commands |
| M9 | Field test | — | Synthetic task suite, improvement measurement, guardrail validation |
| M10 | Release | F-14 | Docker, docs, packaging, PyPI, GitHub release, public repo |

## 9.3 v0.2.0 Milestones

| M | Focus | Issues | Features |
|---|---|---|---|
| M1 | Drift detection | F-20, F-21 | Semantic drift, divergence alerts, drift dashboard |
| M2 | Web dashboard | F-24, F-25 | React-based timeline, diff view, guardrail reports, rollback controls |
| M3 | REST API | F-25 | FastAPI endpoints for diff, rollback, registry queries |
| M4 | Near-miss feedback | F-23 | Analyzer learns from rejected edits, reduced proposal frequency |
| M5 | Edit density | F-22 | Per-section heatmap, configurable time windows |

## 9.4 v0.3.0 Milestones

| M | Focus | Features |
|---|---|---|
| M1 | Multi-failure clustering | F-30 |
| M2 | Adaptive sample floors | F-31 |
| M3 | Evals integration | F-32 |
| M4 | Framework adapters | F-33 |
| M5 | Guardrail history dashboard | F-34 |

## 9.5 v0.4.0 Milestones

| M | Focus | Features |
|---|---|---|
| M1 | Fleet-wide learning | F-40 |
| M2 | Cost-aware improvement | F-41 |
| M3 | Promotion analytics | F-42 |
| M4 | Shadow mode | F-43 |

## 9.6 Build Sequence

The v0.1.0 build sequence is engine-first: the promotion gate and A/B test engine are built first, because everything else is downstream of the one question that matters: can you prove one prompt is better than another, safely?

**Build order:**
1. Config scaffold + held-out task set management (M1)
2. A/B test engine (M3) — the core measurement capability
3. Promotion gate (M4) — the safety-critical component
4. Prompt registry (M5) — versioned storage
5. Guardrail module (M6) — constraint enforcement
6. Feedback analyzer (M2) — edit proposal generation
7. Diff visualization (M7) — user-facing output
8. CLI (M8) — user-facing interface
9. Field test (M9) — validation
10. Release (M10) — ship