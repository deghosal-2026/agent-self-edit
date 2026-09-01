# AgentSelfEdit v0.1.0 Release Notes

**Date:** 2026-09-01

## What's New

AgentSelfEdit is a sidecar that observes execution traces and rewrites its own system prompt through a closed loop:

```
Agent executes task → trace stored → Feedback Analyzer (LLM) reviews →
A/B test candidate vs current prompt → Promotion Gate (6 deterministic checks) →
promote or reject → versioned Registry
```

### Core Features

- **F-01 Execution trace ingestion** — SQLite-backed trace storage with validation, batching, and cleanup
- **F-02 Feedback analyzer** — LLM-powered analysis of failed traces with structured prompt-edit proposals
- **F-03 A/B test engine** — Paired comparison of prompt variants with bootstrap CI, permutation test, effect size
- **F-04 Promotion gate** — 6 deterministic fail-fast checks: sample floor, effect size, confidence, frozen sections, edit distance, drift
- **F-05 Prompt registry** — Versioned prompt storage with full lineage, diff, rollback
- **F-06 Frozen core sections** — User-annotated sections the analyzer cannot modify
- **F-07 Edit-distance limit** — Configurable max lines changed per edit
- **F-08 Prompt diff visualization** — Side-by-side and inline diff between prompt versions
- **F-09 CLI** — 10 commands: init, run, status, diff, rollback, guardrails, lineage, propose, ingest, validate
- **F-10 Held-out task set management** — YAML-based task sets for A/B evaluation
- **F-11 Near-miss logging** — Rejected edits logged with guardrail reasoning
- **F-12 Rollback** — One-command rollback to any previous prompt version
- **F-13 Config file** — YAML/TOML configuration for all thresholds and paths
- **F-14 Docker support** — Multi-stage Dockerfile and docker-compose

## Field Test Results

The v0.1.0 field test ran 15 iterations of the self-edit loop against a local Qwen3.5-4B-4bit model on Apple Silicon.

| Metric | Result |
|--------|--------|
| LLM calls | 4,150 |
| Total tokens | 716,580 |
| Wall time | 37 minutes |
| Cost | $0.00 (local 4B) |
| Gate false positive rate | 0% |
| Gate false negative rate | 0% |
| Docker tests | 9/9 pass |
| All tests | 443/443 pass |

**Key finding:** The promotion gate works correctly. It rejects edits that produce real but statistically underpowered improvement (p=0.23 >= 0.05). Zero false positives, zero false negatives over 15 iterations.

## Known Issues

- **Coverage**: 89% (target 92%) — CLI modules tested via Docker not unit tests
- **Improvement**: 0% over 15 iterations — analyzer proposes same edit every time, needs rejection feedback
- **Non-LLM hermetic tests**: CI-safe tests not yet run in CI

## Upgrade Guide

v0.1.0 is the first release. No upgrade path from previous versions.

### Installing

```bash
pip install agent-self-edit
```

### Quickstart

```bash
agent-self-edit init
agent-self-edit run --once
agent-self-edit status
```

See the [README](https://github.com/deghosal-2026/agent-self-edit#readme) for full documentation.

## Credits

Built by Debashish Ghosal. Powered by Qwen3.5-4B-4bit via MLX on Apple Silicon.