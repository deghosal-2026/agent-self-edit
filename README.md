# AgentSelfEdit

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

# Or in Docker (requires local OMLX or OpenRouter key)
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
| **Guardrail Module** | Frozen section annotations, edit-distance calculation, and TF-IDF drift (embedding drift in v0.2.0). |
| **Diff Visualization** | Side-by-side or inline diff showing exactly what changed between prompt versions, what stayed the same (frozen core), and why (guardrail evidence). |
| **CLI** | `agent-self-edit` with `init`, `run`, `status`, `diff`, `rollback`, `guardrails`, `lineage`, `propose`, `ingest`, `validate`. Shortest path from `pip install` to a working loop is under 5 minutes. |

## Guardrails

The promotion gate is deterministic — never LLM-judged — and runs six checks before any edit is promoted:

1. **Sample floor** — minimum number of A/B trials completed
2. **Effect size** — improvement exceeds a configurable minimum threshold
3. **Confidence interval** — p-value below the confidence threshold
4. **Frozen core sections** — user-annotated sections the analyzer cannot modify
5. **Edit-distance limit** — maximum lines changed per cycle (configurable)
6. **Drift detection** — semantic similarity to the original prompt, alerts on divergence

Design target: < 1% of good edits rejected (false positives), < 0.1% of bad edits promoted (false negatives), 100% rollback success.

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

## Roadmap

| Version | Focus |
|---|---|
| **v0.1.0** | Prove the loop — core loop, statistical gate, CLI, guardrails, Docker, field test (in progress — M10) |
| **v0.2.0** | Trust + visibility — web dashboard, drift detection, near-miss feedback, REST API, shadow mode |
| **v0.3.0** | Scale + adapters — framework adapters, multi-failure clustering, adaptive sample floors, evals integration |
| **v0.4.0** | Fleet — fleet-wide shared-rules learning, cost-aware improvement, promotion analytics |
| **v1.0.0** | General availability — stable API, production deployment guide |

## Status

🚧 **Pre-release v0.1.0.** Core loop complete: trace ingestion, feedback analyzer, A/B test engine, promotion gate, prompt registry, CLI (10 commands), Docker support, diff visualization, rollback, guardrails. **434 hermetic tests + 9 Docker tests pass.** Docker full-loop integration test runs against OMLX real LLM (9/9 tests pass in 112s). Field test in progress (M10): 3-model comparison (4B/9B/cloud) completed, 10-iteration improvement run pending.

## Field Test Status

| Component | Status |
|-----------|--------|
| F-01 Trace ingestion | ✅ works |
| F-02 Feedback analyzer | ✅ works (proposes edits against OMLX) |
| F-03 A/B test engine | ✅ works (2 distinct prompts, real statistics) |
| F-04 Promotion gate | ✅ works (6 checks, deterministic) |
| F-05 Prompt registry | ✅ works (versioned, lineage, rollback) |
| F-09 CLI | ✅ works (10 commands) |
| F-14 Docker support | ✅ works (9/9 tests, full loop against OMLX) |
| M10 Field test | ⬜ 10-iteration improvement run pending (#100) |

See [mini field test report](docs/field-test/v0.1.0/mini-field-test-report.md) for 3-model (4B, 9B, cloud) comparison results.

## License

MIT — see [LICENSE](LICENSE)