# AgentSelfEdit v0.3.0 Release Notes

**Date:** 2026-09-04

## What's New

AgentSelfEdit v0.3.0 hardens the self-improvement loop with a hermetic non-LLM CI suite, Oracle Drift Guard, real-trace gold corpus, multi-domain Docker validation, and 94.86% coverage.

```
Agent executes task → trace stored (SQLite) →
Feedback Analyzer (LLM) reviews → separated-role runner
(executor/analyzer/judge) → proposals with hypotheses →
A/B test candidate vs current prompt → Promotion Gate (7 deterministic checks) →
promote or reject → versioned Registry with Oracle Drift Guard
```

### Core Features

- **F-01 Execution trace ingestion** — SQLite-backed trace storage with validation, batching, and cleanup
- **F-02 Feedback analyzer** — LLM-powered analysis of failed traces with structured prompt-edit proposals; v0.3.0: separated-role runner supports executor/analyzer/judge as different models
- **F-03 A/B test engine** — Paired comparison of prompt variants with bootstrap CI, permutation test, effect size
- **F-04 Promotion gate** — 7 deterministic fail-fast checks: sample floor, effect size, confidence, frozen sections, edit distance, drift, Oracle Drift Guard
- **F-05 Prompt registry** — Versioned prompt storage with full lineage, diff, rollback, SHA-256 integrity
- **F-06 Frozen core sections** — User-annotated sections the analyzer cannot modify
- **F-07 Edit-distance limit** — Configurable max lines changed per edit
- **F-08 Oracle Drift Guard** — Detects shared wrong success definition across optimizer/scorer/golden
- **F-09 CLI** — 11 commands: init, run, status, diff, rollback, guardrails, lineage, propose, ingest, validate, materialize
- **F-10 Held-out task set management** — YAML-based task sets for A/B evaluation; label-set-aware, multi-domain
- **F-11 Near-miss logging** — Rejected edits logged with guardrail reasoning
- **F-12 Rollback** — One-command rollback to any previous prompt version
- **F-13 Config file** — YAML/TOML configuration for all thresholds and paths
- **F-14 Docker support** — Multi-stage Dockerfile, 16/16 tests pass across 5 domains
- **F-15 Materialize guard** — `materialize_candidate_prompt()` replaces raw `str.replace()`; loudly rejects missing `old_text`
- **F-16 Real-trace gold corpus** — 30 traces, 7 failure clusters, 7 ideal interventions for analyzer quality evaluation
- **F-17 Adversarial robustness** — 8/8 bad edits blocked, 0 false negatives
- **F-18 Hermetic test suite** — 807 tests, zero LLM calls, ruff + mypy strict

### Separated-Role Runner

Executor, analyzer, and judge can be different models with fallback. First run produced zero proposals (analyzer sensitivity to executor outputs); tuning in progress.

### Field Test Results

The v0.3.0 field test ran across 5 domains (classification, extraction, generation, mixed-domain, adversarial) with a hermetic non-LLM test suite and real-trace gold corpus.

| Metric | Result |
|--------|--------|
| Hermetic tests | 807 passing |
| Coverage | 94.86% |
| Ruff / mypy | 0 errors |
| FP rate (bad edits promoted) | 0% |
| Docker tests | 16/16 pass |
| Adversarial edits caught | 8/8 (0 FN) |
| Sentinel regression | detected |
| Strongest analyzer | mistralai/mistral-small-3.2-24b-instruct |
| Best effect size | 0.0625 (p=0.79, below confidence) |

**Key finding:** The promotion gate works correctly — 0% false positive rate across all versions. The strongest analyzer (Mistral Small 24B) produced a directional positive signal (+0.0625 effect size) but still below the promotion bar. The framework is sound; analyzer search quality and statistical power are the bottlenecks.

## Known Issues

- **Analyzer search quality** — No analyzer has yet produced a promotable edit locally; local 4B gives null edits, Mistral 24B gives weak positive signal only
- **Proposal diversity** — Analyzer stuck in narrow local search neighborhood (urgency rule rewrites)
- **Statistical power** — Once proposal quality improves, confidence/p-value becomes the next bottleneck
- **Separated-role runner** — First separated-role run produced zero proposals (analyzer sensitivity to executor outputs)
- **Generation regressions** — Overly strict format-adherence edits cause broader regressions in generation corpus

## Upgrade Guide

Upgrade from v0.2.0:

```bash
pip install --upgrade agent-self-edit==0.3.0
agent-self-edit init   # regenerates config with new defaults
agent-self-edit run --once
agent-self-edit status
```

### What changed in v0.3.0

- `materialize_candidate_prompt()` replaces raw `str.replace()` — edits must specify `old_text`
- Oracle Drift Guard enabled by default
- `--cov-fail-under=91` enforced in CI
- Separated-role runner configured via `executor`, `analyzer`, `judge` provider keys

### Backward compatibility

Prompt registry files from v0.2.0 are compatible. Oracle Drift Guard is additive and does not modify existing prompts.

See the [README](https://github.com/deghosal-2026/agent-self-edit#readme) for full documentation.

## Credits

Built by Debashish Ghosal. Powered by mistralai/mistral-small-3.2-24b-instruct via OpenRouter.
