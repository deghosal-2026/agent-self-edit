# AgentSelfEdit

[![PyPI version](https://img.shields.io/pypi/v/agent-self-edit.svg)](https://pypi.org/project/agent-self-edit/)
[![Tests](https://img.shields.io/badge/tests-807%20passing-brightgreen)](https://github.com/deghosal-2026/agent-self-edit/actions)
[![Coverage](https://img.shields.io/badge/coverage-94.86%25-brightgreen)](https://github.com/deghosal-2026/agent-self-edit/actions)
[![Python](https://img.shields.io/pypi/pyversions/agent-self-edit.svg)](https://pypi.org/project/agent-self-edit/)
[![License](https://img.shields.io/pypi/l/agent-self-edit.svg)](https://github.com/deghosal-2026/agent-self-edit/blob/main/LICENSE)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/14386/badge)](https://www.bestpractices.dev/projects/14386)

**A self-improving agent prompt optimizer.** Proposes edits to its own system prompt from execution feedback, A/B tests them against a held-out task set, and promotes only statistically-proven winners under deterministic guardrails.

[Changelog](CHANGELOG.md) · [v0.3.0 Release Notes](https://github.com/deghosal-2026/agent-self-edit/releases/tag/v0.3.0) · [v0.2.0 Release Notes](https://github.com/deghosal-2026/agent-self-edit/releases/tag/v0.2.0) · [v0.1.0 Field Test Report](docs/field-test/v0.1.0/final-field-test-report.md) · [v0.2.0 Field Test Report](docs/field-test/v0.2.0/FIELD_TEST_REPORT.md) · [v0.3.0 Field Test Report](docs/field-test/v0.3.0/FIELD_TEST_REPORT.md)

## Why

Most production agents are prompt-tuned once by hand, then frozen at ship time. Every recurring failure is silently absorbed. Two common approaches fall short:

- **Reflection** appends prose to context but never changes the prompt itself. The same failure repeats.
- **Unconstrained LLM-judged edits** poison the baseline within a few iterations.

AgentSelfEdit is a sidecar that observes execution traces and proposes prompt edits through a deterministic, evidence-driven loop.

## Quick Start

```bash
pip install agent-self-edit
agent-self-edit init
agent-self-edit run --once
```

## How It Works

```
Agent executes task → Execution trace stored (SQLite)
                           ↓
                 Feedback Analyzer (LLM)
                 reviews traces, proposes concrete edits,
                 each with a written hypothesis
                           ↓
            ──── A/B Test Engine ────
             candidate vs current prompt
             held-out task set, bootstrap CI,
             effect size, permutation p-value
            ───────────────────────────
                           ↓
               Promotion Gate (deterministic)
                1. Sample floor     4. Frozen sections
                2. Effect size      5. Edit-distance limit
                3. Confidence p-val 6. Drift detection
                7. Oracle Drift Guard
                           ↓
                 ┌──────────┼──────────┐
                 ▼          ▼          ▼
             Promoted   Near-miss   Rejected
```

1. **Analyze** — An LLM reviews execution traces and identifies failures.
2. **Propose** — Concrete, minimal prompt edits with stated hypotheses.
3. **Test** — Each candidate is A/B tested with confidence intervals and effect-size thresholds.
4. **Promote or Archive** — Winners become the new baseline; losers are archived with reasoning.
5. **Guard** — Frozen sections, edit-distance limits, drift detection, Oracle Drift Guard prevent degradation.

## Core Components

| Component | What it does |
|-----------|-------------|
| Feedback Analyzer | LLM that reviews traces and produces edit proposals. v0.2.0: staged 4-pipeline (summarize → select → synthesize → score) with rejection-context feedback. v0.3.0: separated-role runner supports executor/analyzer/judge as different models. |
| A/B Test Engine | Compares candidate vs current prompt on held-out tasks. v0.2.0: 40-task promotion corpus. |
| Promotion Gate | Seven deterministic checks: sample floor, effect size, confidence, frozen sections, edit-distance, drift, Oracle Drift Guard. Code, not LLM-judged. |
| Prompt Registry | File-based versioned store with full lineage, diff, rollback, SHA-256 integrity. |
| Scorers | Runtime-selectable: ExactMatch, StructuredExtraction, LLMJudge. Label-set-aware, multi-domain. |
| CLI | `init`, `run`, `status`, `diff`, `rollback`, `guardrails`, `lineage`, `propose`, `ingest`, `validate`. |

## The Promotion Gate

Seven fail-fast checks before any edit is promoted:

1. **Sample floor** — minimum A/B trials completed
2. **Effect size** — minimum improvement threshold
3. **Confidence** — p < 0.05 (default)
4. **Frozen core sections** — user-annotated protected regions
5. **Edit-distance limit** — max lines changed per cycle
6. **Drift detection** — semantic similarity to original prompt
7. **Oracle Drift Guard** — detects shared wrong success definition across optimizer/scorer/golden

## v0.3.0 Release Notes

The v0.3.0 release hardens the self-improvement loop with a hermetic non-LLM CI suite, Oracle Drift Guard, real-trace gold corpus, multi-domain Docker validation, and 94.86% coverage.

### What shipped
- **807 hermetic tests**, zero LLM calls — full regression suite
- **Oracle Drift Guard** — detects shared wrong success definition across optimizer/scorer/golden
- **Real-trace gold corpus** — 30 traces, 7 failure clusters, 7 ideal interventions
- **5-domain validation** — classification, extraction, generation, mixed-domain, adversarial
- **16/16 Docker tests** — multi-domain coverage in containerized runtime
- **94.86% coverage** with `--cov-fail-under=91` enforced in CI
- **Separated-role runner** — executor/analyzer/judge can be different models
- **Materialize guard** — `materialize_candidate_prompt()` replaces raw `str.replace()`
- **Adversarial robustness** — 8/8 bad edits blocked, 0 false negatives
- **Ruff + mypy strict** — 0 errors

### What we learned
The framework is sound — 0% false positive rate across all versions, and the strongest analyzer (Mistral Small 24B) produced a directional positive signal (+0.0625 effect size). The bottleneck is now analyzer search quality and statistical power, not gate correctness. Next steps: improve proposal diversity and reduce confidence thresholds.

### Known issues
- No analyzer has yet produced a promotable edit locally
- Statistical power limited by small A/B sample sizes
- Separated-role runner produced zero proposals in first run

## Field Test Results

### v0.3.0
Validation across 5 domains, adversarial edits, real-trace gold corpus, Docker, hermetic suite. Strongest analyzer: Mistral Small 24B (OpenRouter). Weak positive signal (+0.0625 effect size) but still below promotion bar — framework is sound, analyzer search quality and statistical power are the bottlenecks. 807 tests, 94.86% coverage, 0 errors ruff/mypy.

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

[Full v0.3.0 field test report](docs/field-test/v0.3.0/FIELD_TEST_REPORT.md)

### v0.2.0
Validation across 4 domains, adversarial edits, real-trace ingestion, Docker. Strongest analyzer: Mistral Small 24B (OpenRouter). Directional gains but no promotable edit — framework is sound, analyzer quality is the bottleneck.

| Metric | Result |
|--------|--------|
| FP rate | 0% |
| FN rate | not observed |
| Multi-domain suites | 4/4 |
| Adversarial edits caught | 5/5 (0 FN) |
| Strongest analyzer | mistralai/mistral-small-3.2-24b-instruct |
| Coverage | 81% → 94.86% (v0.3.0) |

[Full v0.2.0 field test report](docs/field-test/v0.2.0/FIELD_TEST_REPORT.md)

### v0.1.0
15-iteration loop against Qwen3.5-4B-4bit (local). Gate correctly rejected every edit.

## Trigger Modes

- **Batch** — analyze after N tasks (default: 50)
- **Time-based** — analyze every N hours
- **Manual** — analyze on demand

## Where It Helps

Agents that repeat a task type and see execution feedback: classification, code review, data extraction, content moderation, sales outreach, documentation generation.

## Status

| Area | Status |
|------|--------|
| Core loop | ✅ |
| Model role separation | ✅ |
| Staged analyzer | ✅ |
| Multi-domain support | ✅ |
| Runtime scorer selection | ✅ |
| Adversarial rejection (5/5) | ✅ |
| Real-trace ingestion | ✅ |
| Tests (807/807 pass) | ✅ |
| Ruff + mypy strict | ✅ |
| Security (bandit, gitleaks, trufflehog) | ✅ clean |
| Coverage | ✅ 94.86% |

## Roadmap

| Version | Focus |
|---------|-------|
| **v0.1.0** | ✅ Released — core loop, gate, CLI, Docker |
| **v0.2.0** | ✅ Released — staged analyzer, model roles, multi-domain, field test |
| **v0.3.0** | ✅ Released — hermetic suite, Oracle guard, gold corpus, Docker 16/16, 94.86% coverage |
| **v0.4.0** | Fleet-wide learning, cost-aware improvement |
| **v1.0.0** | Stable API, production deployment guide |

## License

MIT — see [LICENSE](LICENSE)