# WBS — AgentSelfEdit v0.1.0 (Index)

> v0.1.0 issues are attached to the [**v0.1.0 release**](https://github.com/deghosal-2026/agent-self-edit/milestone/1) GitHub milestone. 11 milestones (M1–M11), each with its own GitHub milestone, labels, and exit gates.
>
> **Version split note:** the WBS below is the **active plan for v0.1.0**. Once v0.1.0 ships, this will be frozen history.

## 1. Milestone Overview

| M | Name | Core features | CUJs | Issues | Part file | Status |
|---|------|---------------|------|--------|-----------|--------|
| M1 | Scaffold + Config | F-13, F-10, F-01 (partial) | CUJ 5 | [#1–#8](https://github.com/deghosal-2026/agent-self-edit/issues/1) | [part1](wbs-v0.1.0-part1-foundation.md) | ✅ Done |
| M2 | Trace Ingestion | F-01, F-13 | CUJ 1 | [#9–#14](https://github.com/deghosal-2026/agent-self-edit/issues/8) | [part1](wbs-v0.1.0-part1-foundation.md) | ✅ Done |
| M3 | A/B Test Engine | F-03 | CUJ 1 | [#15–#21](https://github.com/deghosal-2026/agent-self-edit/issues/14) | [part2](wbs-v0.1.0-part2-core-engine.md) | ✅ Done |
| M4 | Promotion Gate | F-04, F-11 | CUJ 2 | [#22–#31](https://github.com/deghosal-2026/agent-self-edit/issues/21) | [part2](wbs-v0.1.0-part2-core-engine.md) | ⬜ Pending |
| M5 | Prompt Registry | F-05, F-12 | CUJ 3, CUJ 4 | [#32–#38](https://github.com/deghosal-2026/agent-self-edit/issues/31) | [part3](wbs-v0.1.0-part3-storage-guardrails.md) | ⬜ Pending |
| M6 | Guardrail Module | F-06, F-07 | CUJ 9 | [#39–#44](https://github.com/deghosal-2026/agent-self-edit/issues/38) | [part3](wbs-v0.1.0-part3-storage-guardrails.md) | ⬜ Pending |
| M7 | Feedback Analyzer | F-02 | CUJ 1, CUJ 2 | [#45–#51](https://github.com/deghosal-2026/agent-self-edit/issues/44) | [part4](wbs-v0.1.0-part4-intelligence.md) | ⬜ Pending |
| M8 | Diff Visualization | F-08 | CUJ 1, CUJ 3 | [#52–#55](https://github.com/deghosal-2026/agent-self-edit/issues/51) | [part4](wbs-v0.1.0-part4-intelligence.md) | ⬜ Pending |
| M9 | CLI | F-09 | CUJ 5, CUJ 4 | [#56–#63](https://github.com/deghosal-2026/agent-self-edit/issues/55) | [part5](wbs-v0.1.0-part5-cli.md) | ⬜ Pending |
| M10 | Field Test | F-14 | CUJ 1, CUJ 2, CUJ 4 | [#64–#69](https://github.com/deghosal-2026/agent-self-edit/issues/63) | [part6](wbs-v0.1.0-part6-field-test.md) | ⬜ Pending |
| M11 | Release | — | all P0 | [#70–#75](https://github.com/deghosal-2026/agent-self-edit/issues/69) | [part7](wbs-v0.1.0-part7-release.md) | ⬜ Pending |

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

## 3. Traceability — PRD → WBS

| PRD source | Implemented by |
|-----------|----------------|
| [05-features F-01](../../design/prd/05-features.md) | M2 (trace ingestion) |
| [05-features F-02](../../design/prd/05-features.md) | M7 (feedback analyzer) |
| [05-features F-03](../../design/prd/05-features.md) | M3 (A/B test engine) |
| [05-features F-04](../../design/prd/05-features.md) | M4 (promotion gate) |
| [05-features F-05](../../design/prd/05-features.md) | M5 (prompt registry) |
| [05-features F-06](../../design/prd/05-features.md) | M6 (frozen core sections) |
| [05-features F-07](../../design/prd/05-features.md) | M6 (edit-distance limit) |
| [05-features F-08](../../design/prd/05-features.md) | M8 (diff visualization) |
| [05-features F-09](../../design/prd/05-features.md) | M9 (CLI) |
| [05-features F-10](../../design/prd/05-features.md) | M1 (task set management) |
| [05-features F-11](../../design/prd/05-features.md) | M4 (near-miss logging) |
| [05-features F-12](../../design/prd/05-features.md) | M5 (rollback) |
| [05-features F-13](../../design/prd/05-features.md) | M1 (config file) |
| [05-features F-14](../../design/prd/05-features.md) | M10/M11 (Docker) |
| [02-architecture §2.2](../../design/prd/02-architecture.md) | M3 (A/B test), M4 (gate checks), M5 (registry), M6 (guardrails), M7 (analyzer) |
| [04-users-and-cujs §4.3](../../design/prd/04-users-and-cujs.md) | CUJ-1 deploys loop (M9), CUJ-2 bad edit (M4), CUJ-3 lineage (M5), CUJ-4 rollback (M5), CUJ-5 first-time setup (M9), CUJ-9 guardrails (M6) |

## 4. Cross-Cutting Contracts

- **Package:** import `agent_self_edit` — PyPI `agent-self-edit` — CLI `agent-self-edit`.
- **Hermetic by default:** CI never calls a paid LLM. Mock providers used in all tests. Real LLM tests are manual/CI-skipped.
- **Mock-first:** Every milestone that depends on an LLM provider must also implement a mock provider usable in CI.
- **Fail-closed on analyzer:** The analyzer proposes edits but has no authority. All proposals go through A/B test + promotion gate. No edit is promoted on the analyzer's authority alone.
- **Deterministic gate:** The promotion gate is deterministic code, not LLM-judged. Every guardrail check is verifiable, testable, and non-negotiable.
- **Cheap by default:** Default config uses cheap models (gpt-4o-mini). Cost ceiling enforced per cycle. Analyzer runs in batch mode, not per-task.
- **File-based persistence:** Prompt registry is file-based (`.md` + `.json`), not dependent on an external database. SQLite for traces only.
- **Provenance-first:** Every prompt version carries full lineage — what changed, why, what evidence justified it, and how to roll back. Tamper-evident via hash chain.

## 5. Issue Naming Convention

- Title: `[v0.1.0-M1] Task description`
- Labels: `milestone-M1` through `milestone-M11`, `area-*`, `kind-*`
- Milestone: `v0.1.0-M1` through `v0.1.0-M11`

## 6. Exit Gate (Every Milestone)

- [ ] Ruff clean: `ruff check .` → 0 errors
- [ ] Mypy strict clean: `mypy --strict` → 0 errors
- [ ] All tests pass: `pytest` → 0 failures
- [ ] Coverage > 92%: `pytest --cov=agent_self_edit --cov-fail-under=92`
- [ ] Zero paid LLM calls in CI (hermetic by default — mock providers used)
- [ ] Documentation updated for the milestone's scope
- [ ] WBS index updated with milestone status

## 7. Package Layout

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
├── conftest.py               # Shared fixtures, mock LLM provider, temp directories
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
```

## 8. Design Documents to Author

| D# | Doc | Milestone | Path | Contents |
|----|-----|-----------|------|----------|
| D1 | Config schema design | M1 | `docs/design/config-schema-design.md` | Config file format, all fields, validation rules, schema versioning |
| D2 | Trace schema design | M2 | `docs/design/trace-schema-design.md` | Trace JSON schema, SQLite store schema, adapter interface design |
| D3 | A/B test engine design | M3 | `docs/design/ab-test-engine-design.md` | Statistical methodology, scorer interface, bootstrap, permutation test |
| D4 | Promotion gate design | M4 | `docs/design/promotion-gate-design.md` | Gate architecture, 6-check fail-fast order, near-miss classification |
| D5 | Prompt registry design | M5 | `docs/design/prompt-registry-design.md` | Registry format, versioning, rollback, integrity checks |
| D6 | Guardrail module design | M6 | `docs/design/guardrail-module-design.md` | Guardrail architecture, drift calculation, frozen sections |
| D7 | Feedback analyzer design | M7 | `docs/design/feedback-analyzer-design.md` | Analyzer prompt, proposal format, deduplication, cost tracking |
| D8 | Diff visualization design | M8 | `docs/design/prompt-diff-design.md` | Diff output formats, edit density, guardrail report formatting |
| D9 | CLI surface design | M9 | `docs/design/cli-surface-design.md` | CLI commands, flags, output formats, exit codes |
| D10 | Field test plan | M10 | `docs/design/field-test-plan.md` | Synthetic task suite, validation methodology, test matrix |

## 9. Documentation Map

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

## 10. Connected

- [PRD](../design/README.md) — Product requirements
- [Architecture](../design/prd/02-architecture.md) — System architecture
- [Features](../design/prd/05-features.md) — Feature set F-01 through F-14
- [CUJs](../design/prd/04-users-and-cujs.md) — Customer user journeys
- [Roadmap](../design/prd/09-roadmap.md) — Full roadmap v0.1.0 through v1.0.0