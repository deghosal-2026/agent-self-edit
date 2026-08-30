# WBS — AgentSelfEdit v0.1.0 (Index)

> v0.1.0 issues are attached to the [**v0.1.0 release**](https://github.com/deghosal-2026/agent-self-edit/milestone/1) GitHub milestone. 11 milestones (M1–M11), each with its own GitHub milestone, labels, and exit gates.
>
> **Version split note:** the WBS below is the **active plan for v0.1.0**. Once v0.1.0 ships, this will be frozen history.

## 1. Milestone Overview

| M | File | Focus | Issue Range | Status |
|---|------|-------|-------------|--------|
| M1 | [part1-foundation.md](wbs-v0.1.0-part1-foundation.md) | Scaffold, config, CI, OSS files | #1–#7 | ⬜ Pending |
| M2 | [part1-foundation.md](wbs-v0.1.0-part1-foundation.md) | Execution trace ingestion | #8–#13 | ⬜ Pending |
| M3 | [part2-core-engine.md](wbs-v0.1.0-part2-core-engine.md) | A/B test engine | #14–#20 | ⬜ Pending |
| M4 | [part2-core-engine.md](wbs-v0.1.0-part2-core-engine.md) | Promotion gate | #21–#30 | ⬜ Pending |
| M5 | [part3-storage-guardrails.md](wbs-v0.1.0-part3-storage-guardrails.md) | Prompt registry | #31–#37 | ⬜ Pending |
| M6 | [part3-storage-guardrails.md](wbs-v0.1.0-part3-storage-guardrails.md) | Guardrail module | #38–#43 | ⬜ Pending |
| M7 | [part4-intelligence.md](wbs-v0.1.0-part4-intelligence.md) | Feedback analyzer | #44–#50 | ⬜ Pending |
| M8 | [part4-intelligence.md](wbs-v0.1.0-part4-intelligence.md) | Diff visualization | #51–#54 | ⬜ Pending |
| M9 | [part5-cli.md](wbs-v0.1.0-part5-cli.md) | CLI | #55–#62 | ⬜ Pending |
| M10 | [part6-field-test.md](wbs-v0.1.0-part6-field-test.md) | Field test | #63–#68 | ⬜ Pending |
| M11 | [part7-release.md](wbs-v0.1.0-part7-release.md) | Release | #69–#74 | ⬜ Pending |

## 2. Dependency Graph

```
M1 ──► M3 ──► M4 ──► M5 ──► M6 ──► M7 ──► M8 ──► M9 ──► M10 ──► M11
 │               │                           │
 └──► M2 ────────┘                           │
        └────────────────────────────────────┘
```

- M1 (Scaffold) must ship first — everything depends on config and package structure
- M3 (A/B Test) must ship before M4 (Promotion Gate) — gate needs the test engine
- M2 (Trace Ingestion) and M3 (A/B Test) are independent — can build in parallel
- M4 (Promotion Gate) depends on M3 (A/B Test results)
- M5 (Prompt Registry) depends on M4 (gate decisions to store)
- M6 (Guardrail Module) depends on M5 (needs registry to diff against)
- M7 (Analyzer) depends on M2 (traces) and M6 (guardrails for proposal constraints)
- M8 (Diff Viz) depends on M5 (needs registry to diff versions)
- M9 (CLI) depends on M7 and M8 — wraps all operations
- M10 (Field Test) depends on M9 — needs the CLI to run
- M11 (Release) depends on M10 — needs validation results

## 3. Build Order (Recommended)

1. **M1** — Scaffold + config (everything depends on this)
2. **M3** — A/B test engine (the core measurement capability)
3. **M2** — Execution trace ingestion (independent of M3, can parallelize)
4. **M4** — Promotion gate (depends on M3)
5. **M5** — Prompt registry (depends on M4)
6. **M6** — Guardrail module (depends on M5)
7. **M7** — Feedback analyzer (depends on M2 + M6)
8. **M8** — Diff visualization (depends on M5)
9. **M9** — CLI (depends on M7 + M8)
10. **M10** — Field test (depends on M9)
11. **M11** — Release (depends on M10)

## 4. Issue Naming Convention

- Title: `[v0.1.0-M1] Task description`
- Labels: `milestone-M1` through `milestone-M11`, `area-*`, `kind-*`
- Milestone: `v0.1.0-M1` through `v0.1.0-M11`

## 5. Exit Gate (Every Milestone)

- [ ] Design docs reviewed and committed (if applicable)
- [ ] Ruff clean: `ruff check .` → 0 errors
- [ ] Mypy strict clean: `mypy --strict` → 0 errors
- [ ] All tests pass: `pytest` → 0 failures
- [ ] Coverage > 92%: `pytest --cov=agent_self_edit --cov-fail-under=92`
- [ ] Zero paid LLM calls in CI (hermetic by default — mock providers used)
- [ ] Documentation updated for the milestone's scope
- [ ] WBS index updated with milestone status

## 6. Package Layout

```
src/agent_self_edit/
├── __init__.py
├── types.py                  # Trace, EditProposal, GateResult, PromptVersion
├── config.py                 # Config loader, validator
├── tasks.py                  # TaskSet, held-out task management
├── trace.py                  # Trace ingestion, store, batching
├── scorers.py                # Scorer interface (ExactMatch, Contains, LLMJudge)
├── ab_test.py                # A/B test engine, bootstrap, permutation
├── gate.py                   # Promotion gate, check implementations
├── registry.py               # Prompt registry, versioning, rollback
├── guardrails.py             # Frozen sections, edit distance, drift
├── analyzer.py               # Feedback analyzer, proposal generation
├── diff.py                   # Diff visualization, edit density
├── cli.py                    # CLI commands
├── llm/                      # LLM provider layer
│   ├── __init__.py
│   ├── base.py               # Abstract LLMProvider
│   ├── openai.py             # OpenAI-compatible transport
│   └── mock.py               # Mock provider for testing
└── adapters/                 # Trace adapters
    ├── __init__.py
    ├── base.py               # Abstract TraceAdapter
    ├── stdin.py              # StdinAdapter
    └── file.py               # FileAdapter

tests/
├── __init__.py
├── test_config.py
├── test_tasks.py
├── test_types.py
├── test_trace.py
├── test_adapters.py
├── test_ab_test.py
├── test_gate.py
├── test_registry.py
├── test_guardrails.py
├── test_analyzer.py
├── test_diff.py
├── test_cli.py
├── test_field_test.py
├── test_docker.py
├── test_release.py
└── conftest.py               # Shared fixtures, mock LLM provider, temp directories
```

## 7. Design Documents to Author

Authored inline with their milestone:

| D | Doc | Milestone | Description |
|---|-----|-----------|-------------|
| D1 | `docs/design/config-schema-design.md` | M1 | Config file format, validation, schema |
| D2 | `docs/design/trace-schema-design.md` | M2 | Trace format, store schema, adapter design |
| D3 | `docs/design/ab-test-engine-design.md` | M3 | Statistical methodology, scorer interface, bootstrap |
| D4 | `docs/design/promotion-gate-design.md` | M4 | Gate architecture, check order, near-miss classification |
| D5 | `docs/design/prompt-registry-design.md` | M5 | Registry format, versioning, rollback, integrity |
| D6 | `docs/design/guardrail-module-design.md` | M6 | Guardrail architecture, drift calculation, frozen sections |
| D7 | `docs/design/feedback-analyzer-design.md` | M7 | Analyzer prompt, proposal format, deduplication |
| D8 | `docs/design/prompt-diff-design.md` | M8 | Diff visualization, edit density, guardrail report |
| D9 | `docs/design/cli-surface-design.md` | M9 | CLI commands, flags, output formats |
| D10 | `docs/design/field-test-plan.md` | M10 | Synthetic task suite, validation methodology |

## 8. Documentation Map

| Doc | Milestone | Location |
|-----|-----------|----------|
| Config reference | M1 | `docs/reference/config.md` |
| Trace schema reference | M2 | `docs/reference/trace-schema.md` |
| Adapter guide | M2 | `docs/explanation/adapters.md` |
| Registry reference | M5 | `docs/reference/registry.md` |
| Guardrails reference | M6 | `docs/reference/guardrails.md` |
| Analyzer reference | M7 | `docs/reference/analyzer.md` |
| Integration guide | M7 | `docs/explanation/integration.md` |
| Diff reference | M8 | `docs/reference/diff.md` |
| CLI reference | M9 | `docs/reference/cli.md` |
| Quickstart guide | M9 | `docs/explanation/quickstart.md` |
| Field test report | M10 | `docs/field-test/v0.1.0/FIELD_TEST_REPORT.md` |
| Performance benchmark | M10 | `docs/explanation/performance.md` |
| Troubleshooting guide | M10 | `docs/explanation/troubleshooting.md` |
| Release notes | M11 | `docs/release/v0.1.0/release-notes.md` |

## 9. Connected

- [PRD](../design/README.md) — Product requirements
- [Architecture](../design/prd/02-architecture.md) — System architecture
- [Features](../design/prd/05-features.md) — Feature set F-01 through F-14
- [Roadmap](../design/prd/09-roadmap.md) — Full roadmap v0.1.0 through v1.0.0