# 07 — Success Metrics

> Sub-document of the [Design overview](../README.md). Success criteria, reliability targets, and measurement framework.

## 7.1 Product Success Criteria

### v0.1.0 Must-Have

| Criterion | Target | How measured |
|---|---|---|
| Self-improvement loop runs end-to-end | Agent fails a task → analyzer proposes edit → A/B test → gate decides → prompt updated | Integration test with synthetic task suite |
| Sentinels catch bad edits | Guardrails block edits that degrade performance on held-out tasks | Guardrail pass/fail rate in CI |
| Prompt lineage is inspectable | Full history of every prompt version with diff, evidence, and rollback | CLI query returns complete lineage |
| Rollback works | One command restores any previous prompt version | Rollback test in CI |
| Improvement is measurable | Measured win-rate improvement over N self-improvement iterations | Per-iteration performance tracking |

### v0.2.0 Must-Have

| Criterion | Target | How measured |
|---|---|---|
| Drift detection alerts | Alerts when drift exceeds configurable threshold | Integration test with drift scenario |
| Web dashboard usable | Operator can view timeline, diffs, and guardrail reports without CLI | Manual QA |
| Near-miss feedback reduces bad proposals | Rejection rate decreases over time | Near-miss trend tracking |

## 7.2 Reliability Targets

| Metric | Target | How measured |
|---|---|---|
| Guardrail false positive rate | < 1% (good edits rejected) | A/B test history audit |
| Guardrail false negative rate | < 0.1% (bad edits promoted) | Red-team testing with intentionally bad edits |
| Rollback success rate | 100% | Automated rollback test |
| Prompt registry integrity | 0 corruption events | Checksum on every write |
| Analyzer uptime | 99.9% (loop runs as scheduled) | Heartbeat monitoring |

## 7.3 Article-Worthiness Metrics

| Metric | Target | Why |
|---|---|---|
| Measured improvement | 10%+ accuracy improvement over 100 iterations | Article: "I Let My Agent Rewrite Its Own Brain" |
| Guardrail saves | 5+ bad edits caught by guardrails per 100 iterations | Article: "The Statistics of Letting an AI Edit Its Own Prompt Safely" |
| Near-miss learning | 20%+ reduction in rejection rate over time | Article: "Why Most Self-Improving Agents Are Just Context Bloat" |
| Rollback events | < 1% of promoted edits need rollback | Article: "Guardrails for Agents That Rewrite Themselves" |

## 7.4 External Interest Metrics

| Metric | Target | Timeline |
|---|---|---|
| GitHub stars | 50+ | 3 months post-launch |
| Community forks | 10+ | 3 months post-launch |
| OSS contributors | 3+ external PRs | 6 months post-launch |
| dev.to article engagement | 50+ reactions, 20+ comments per article | Per article |

## 7.5 Measurement Framework

All metrics are collected via:

1. **CLI telemetry** — opt-in, anonymous usage stats (loop runs, edits proposed, promoted, rejected)
2. **Guardrail audit log** — every guardrail check recorded with pass/fail and evidence
3. **Prompt registry** — full version history with timestamps and metadata
4. **CI test suite** — automated tests for all reliability targets