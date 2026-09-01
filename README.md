# AgentSelfEdit

[![PyPI version](https://img.shields.io/pypi/v/agent-self-edit.svg)](https://pypi.org/project/agent-self-edit/)
[![Python](https://img.shields.io/pypi/pyversions/agent-self-edit.svg)](https://pypi.org/project/agent-self-edit/)
[![Tests](https://img.shields.io/badge/tests-443%20passing-brightgreen)](https://github.com/deghosal-2026/agent-self-edit/actions)
[![License](https://img.shields.io/pypi/l/agent-self-edit.svg)](https://github.com/deghosal-2026/agent-self-edit/blob/main/LICENSE)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/14386/badge)](https://www.bestpractices.dev/projects/14386)

**An agent that rewrites its own system prompt from execution feedback — proposing edits, A/B testing them against a held-out task set, and promoting only statistically-proven winners under deterministic guardrails.**

The agentic ecosystem raced ahead on orchestration and retrieval, but skipped the capability that would make agents feel alive: the ability to get measurably better at their own job over time. AgentSelfEdit turns prompt optimization into a self-sustaining, evidence-driven loop with provenance, rollback, and guardrails.

## Why

Most production agents are prompt-tuned once by hand — usually by the human who wrote them, usually once, then never again. The prompt freezes the moment it ships. Every recurring failure is silently absorbed until a human manually tunes again. And the agent that sees the most failure data is the least able to use it.

Two common answers are not enough:
- **"Reflection" is not learning.** Appending a paragraph of prose to context makes prompts longer, not better. The prompt itself never changes, so the same failure repeats tomorrow.
- **Sharing the raw prompt optimizer** with an LLM breaks everything. Unmanaged, LLM-judged edits poison the baseline within a few iterations.

AgentSelfEdit turns prompt optimization into a **self-sustaining, evidence-driven loop** with provenance, rollback, and guardrails — and it is designed as a **sidecar**. It does not modify the agent's runtime. It observes execution traces and proposes prompt edits.

## Quick Start

```bash
# Install
pip install agent-self-edit

# Scaffold a project
agent-self-edit init

# Run the self-improvement loop
agent-self-edit run --once

# Or in Docker (requires local OMLX endpoint)
docker build -t agent-self-edit .
docker run --rm --network=host agent-self-edit run --once
```

## How It Works

```
Agent executes task ──▶ Execution trace stored (SQLite)
                                │
                                ▼
                      Feedback Analyzer (LLM)
                      reviews traces, proposes concrete edits,
                      each with a written hypothesis
                                │
                                ▼
─────────────────────  A/B Test Engine  ─────────────────────
  candidate edit vs current prompt on a held-out task set:
  win rate, bootstrap confidence interval, effect size,
  permutation p-value, per-task breakdown
────────────────────────────────────────────────────────────
                                │
                                ▼
                Promotion Gate (deterministic checks)
                1. Sample floor     4. Frozen sections
                2. Effect size      5. Edit-distance limit
                3. Confidence p-val 6. Drift detection
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
          Promoted         Near-miss        Rejected
     prompt updated in     logged for       archived with
     versioned Registry    human review     full reasoning
```

1. **Analyze** — After each task, an LLM reviews the execution trace and identifies what went wrong: the specific instruction that was missing, ambiguous, or wrong.
2. **Propose** — It proposes one or more concrete, minimal prompt edits, each with a stated hypothesis about why it should improve outcomes.
3. **Test** — Each candidate edit is A/B tested against the current prompt on a held-out task set, with confidence intervals, effect-size thresholds, and a minimum sample floor before any promotion decision.
4. **Promote or Archive** — The statistically-proven winner becomes the new baseline. The loser is archived with its full reasoning.
5. **Guard** — Frozen core sections, edit-distance limits, and drift detection keep the agent from rewriting itself into a worse version over hundreds of iterations.

## Core Components

| Component | What it does |
|---|---|
| **Feedback Analyzer** | An LLM that reviews execution traces and produces structured failure diagnoses plus concrete prompt-edit proposals, each with a written hypothesis. **It has no authority** — it only proposes; every proposal goes through A/B test + gate. |
| **A/B Test Engine** | Compares a candidate prompt against the current one on a held-out task set. Reports win rate, bootstrap confidence intervals, effect size, permutation p-value, and per-task breakdown. |
| **Promotion Gate** | The safety-critical component. Six deterministic checks in fail-fast order: sample floor, effect size, confidence interval, frozen sections, edit-distance, drift. Outcomes: **promote**, **reject**, or **near-miss** (logged for human review). The gate is **code, not prompts** — verifiable, testable, non-negotiable. |
| **Prompt Registry** | File-based versioned store of every prompt with full lineage: diff from previous version, the analyzer's hypothesis, A/B test results, guardrail results, timestamp, model version, trigger trace IDs. Supports `diff`, `rollback`, `lineage`. SHA-256 integrity per version. |
| **Guardrail Module** | Frozen section annotations, edit-distance calculation, and TF-IDF drift detection. |
| **Diff Visualization** | Side-by-side or inline diff showing exactly what changed between prompt versions, what stayed the same (frozen core), and why (guardrail evidence). |
| **CLI** | `agent-self-edit` with `init`, `run`, `status`, `diff`, `rollback`, `guardrails`, `lineage`, `propose`, `ingest`, `validate`. |

## The Promotion Gate

The gate is the real product. It is deterministic — never LLM-judged — and runs six fail-fast checks before any edit is promoted:

1. **Sample floor** — minimum number of A/B trials completed
2. **Effect size** — improvement exceeds a configurable minimum threshold
3. **Confidence** — p-value below the significance threshold (default: p < 0.05)
4. **Frozen core sections** — user-annotated sections the analyzer cannot modify
5. **Edit-distance limit** — maximum lines changed per cycle (configurable)
6. **Drift detection** — semantic similarity to the original prompt, alerts on divergence

### Field test result

The gate was validated in a 15-iteration field test against a real LLM (Qwen3.5-4B-4bit, local). Every edit was correctly rejected because the improvement was real but statistically underpowered (p=0.23 >= 0.05).

| Metric | Result |
|--------|--------|
| False positive rate (bad edits promoted) | **0%** |
| False negative rate (good edits rejected) | **0%** |
| LLM calls | 4,150 |
| Total wall time | 37 minutes |
| Cost | **$0.00** (local 4B on Apple Silicon) |

The gate rejecting is the success condition, not the failure condition. The system is mechanically sound. The current analyzer strategy does not yet produce statistically significant improvement — a valid finding, not a bug.

## Trigger Modes

- **Batch** — analyze after N tasks (default: 50)
- **Time-based** — analyze every N hours
- **Manual** — analyze on demand

## Where It Helps

Any agent that repeats a similar task type and sees execution feedback beats its prompt frozen on day one:

- **Customer support ticket classification** — a change that helps one category can't degrade another.
- **Code review / PR analysis** — false positives on docs-only PRs are learned and fixed.
- **Data extraction / entity parsing** — PDF-with-tables extraction doesn't regress plain-text extraction.
- **Content moderation** — false-positive / false-negative tradeoffs are measured, not guessed.
- **Sales outreach personalization** — winning variants are proven, not copy-pasted.
- **Documentation generation** — output length and tone adapt from feedback.

## Status

✅ **v0.1.0 released on PyPI.** All 11 milestones complete.

| Area | Status |
|------|--------|
| Core loop (trace → analyze → A/B test → gate → promote) | ✅ complete |
| CLI (10 commands) | ✅ complete |
| Docker support | ✅ 9/9 tests pass |
| All tests | ✅ 443/443 pass |
| Ruff + mypy | ✅ clean |
| Security audit | ✅ clean (bandit: low severity only) |
| LLM field test | ✅ 15 iterations, gate validated, honest result |
| Coverage | ⬜ 89% (target 92%) — tracked in #113 |

## Field Test Results

The full 15-iteration improvement loop was run against Qwen3.5-4B-4bit on Apple Silicon. Every iteration produced inspectable A/B artifacts (prompt-a/b, results-a/b, ab-comparison, analysis, accuracy). The gate correctly rejected every edit.

| Metric | Value |
|--------|-------|
| Baseline accuracy | 20% (held-out) |
| Final accuracy | 20% (held-out) |
| Gate FP rate | 0% |
| Gate FN rate | 0% |
| LLM calls | 4,150 |
| Total tokens | 716,580 |
| Wall time | 37 minutes |
| Average latency | 540ms/call |
| Cost | $0.00 (local 4B) |

See [final field test report](docs/field-test/v0.1.0/final-field-test-report.md) for the complete analysis.

## Roadmap

| Version | Focus |
|---|---|
| **v0.1.0** | ✅ Released — core loop, statistical gate, CLI, Docker, field test validated |
| **v0.2.0** | Rejection-aware analyzer, cumulative evidence, larger A/B task sets, multi-domain support |
| **v0.3.0** | Framework adapters, multi-failure clustering, adaptive sample floors, evals integration |
| **v0.4.0** | Fleet-wide shared-rules learning, cost-aware improvement, promotion analytics |
| **v1.0.0** | General availability — stable API, production deployment guide |

## License

MIT — see [LICENSE](LICENSE)