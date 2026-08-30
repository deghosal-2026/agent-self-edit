# 06 — Security Baseline

> Sub-document of the [Design overview](../README.md). OpenSSF, OWASP, and security posture for AgentSelfEdit.

## 6.1 OpenSSF Best Practices

Target: **OpenSSF Best Practices Passing badge** for v0.1.0.

### Requirements

| Requirement | Status | How met |
|---|---|---|
| Basic project documentation | ✅ README, LICENSE, CONTRIBUTING | README exists, MIT license, CONTRIBUTING to write |
| Build system | ✅ Python package | pyproject.toml, pip installable |
| Test suite | ✅ pytest | Unit tests for all core components |
| CI/CD | ✅ GitHub Actions | CI runs on every push, runs tests + lint |
| Security policy | ✅ SECURITY.md | Vulnerability reporting process |
| Static analysis | ✅ ruff + mypy | ruff lint, mypy strict type checking |
| Dependency scanning | ✅ Dependabot | Auto-dependency updates |
| Signed releases | ✅ GitHub releases | Signed tags for all releases |

### OpenSSF Badge Checklist

- [ ] Basic project website (README serves as front page)
- [ ] FLOSS license (MIT — done)
- [ ] Documentation (docs/ — done)
- [ ] Build system (pyproject.toml — to do)
- [ ] Test suite (pytest — to do)
- [ ] CI/CD (GitHub Actions — to do)
- [ ] Contribution guidelines (CONTRIBUTING.md — to do)
- [ ] Security policy (SECURITY.md — to do)
- [ ] Static analysis (ruff — to do)
- [ ] Dependency scanning (Dependabot — to do)

## 6.2 OWASP Agentic Top 10

| ID | Risk | Mitigation | Status |
|---|---|---|---|
| ASI01 | Prompt injection | The agent's prompt is the only attack surface. The guardrail module limits edit distance and frozen sections, preventing an attacker from rewriting the prompt through a compromised trace | To assess |
| ASI08 | Cascading failures | The promotion gate prevents a bad edit from propagating. If a promoted edit degrades behavior, the drift detector alerts and rollback is one command | To assess |
| ASI09 | Misaligned behavior | The drift detector tracks semantic similarity to the original prompt. If the prompt drifts too far, the operator is alerted | To assess |

## 6.3 AgentSelfEdit Security Posture

| Layer | Risk | Mitigation |
|---|---|---|
| Prompt registry | Unauthorized rollback | CLI authentication, audit logging |
| Promotion gate | Bypassing guardrails | Gate is deterministic code, not configurable by the analyzer |
| A/B test engine | Held-out task contamination | Tasks are read-only during evaluation, hashed for integrity |
| Feedback analyzer | Hallucinated edit proposals | All proposals go through A/B test before promotion. No edit is promoted on the analyzer's authority alone |
| Trace storage | Sensitive data in traces | User is responsible for trace sanitization. AgentSelfEdit does not inspect trace content beyond success/failure and failure reason |

## 6.4 Security Non-Goals

- Full prompt injection defense for the agent (that's the agent owner's responsibility)
- Trace data sanitization or PII redaction (user provides traces, user sanitizes)
- Authentication and authorization for the web dashboard (deferred to v0.2.0)