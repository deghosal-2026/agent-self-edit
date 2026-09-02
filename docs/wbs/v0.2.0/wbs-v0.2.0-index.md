# WBS — AgentSelfEdit v0.2.0 (Index)

> v0.2.0 issues are attached to the [**v0.2.0 release**](https://github.com/deghosal-2026/agent-self-edit/milestone/12) GitHub milestone. 9 milestones (M1–M9), each with its own GitHub milestone, labels, and exit gates.
>
> **Version split note:** the WBS below is the **active plan for v0.2.0**. Once v0.2.0 ships, this will be frozen history.

## 1. Milestone Overview

| M | Name | Core features | Issues | Part file | Status |
|---|------|---------------|--------|-----------|--------|
| M1 | Correctness Fixes | Gate edit-distance, drift, A/B alpha, promotion persistence | [#116–#119](https://github.com/deghosal-2026/agent-self-edit/issues/116) | [part1](wbs-v0.2.0-part1-correctness.md) | ✅ |
| M2 | Scorer Contract Cleanup | Runtime scorer selection, classification subsets, other semantics, label-set-aware scorers | [#120–#123](https://github.com/deghosal-2026/agent-self-edit/issues/120) | [part2](wbs-v0.2.0-part2-scorer-analyzer.md) | ✅ |
| M3 | Analyzer & Regression | Staged analyzer, multi-suite runner, extraction scorer, hermetic tests, regression sentinel | [#124–#128](https://github.com/deghosal-2026/agent-self-edit/issues/124) | [part2](wbs-v0.2.0-part2-scorer-analyzer.md) | ✅ |
| M4 | Local LLM & Accuracy | Model role separation, provider config, benchmark manifests, local-model comparison, optimizer metrics | [#129–#135](https://github.com/deghosal-2026/agent-self-edit/issues/129) | [part3](wbs-v0.2.0-part3-llm-benchmarks.md) | ✅ |
| M5 | Benchmark Expansion | Larger A/B sets, prompt style for small models, canonical examples, missing corpus types, task-set metadata, rejection-aware analyzer | [#136–#141](https://github.com/deghosal-2026/agent-self-edit/issues/136) | [part3](wbs-v0.2.0-part3-llm-benchmarks.md) | ✅ |
| M6 | Operational Reliability | Trace ack by row identity, retry-safe batch, runnable init state, duplicate-filename fix, benchmark validation | [#142–#147](https://github.com/deghosal-2026/agent-self-edit/issues/142) | [part4](wbs-v0.2.0-part4-reliability-packaging.md) | ✅ |
| M7 | Packaging & CLI | CI/CD, lockfile, conftest fixtures, Dockerfile fixes, CLI exit codes, diff/lineage bugs, config tightening | [#148–#171](https://github.com/deghosal-2026/agent-self-edit/issues/148) | [part4](wbs-v0.2.0-part4-reliability-packaging.md) | ✅ |
| M8 | Field Test | Multi-domain suites, adversarial edits, real-trace ingestion, LLM integration, hermetic CI suite, report | [#172–#179](https://github.com/deghosal-2026/agent-self-edit/issues/172) | [part5](wbs-v0.2.0-part5-field-test.md) | ✅ |
| M9 | Release | PyPI, Docker, documentation, coverage, security, GitHub release | [#180–#185](https://github.com/deghosal-2026/agent-self-edit/issues/180) | [part6](wbs-v0.2.0-part6-release.md) | ✅ |

## 2. Dependency Graph

```
M1 ──► M2 ──► M3 ──► M4 ──► M5 ──► M6 ──► M7 ──► M8 ──► M9
 │                      │               │
 └──────────────────────┘               │
        └───────────────────────────────┘
```

- **M1 (Correctness)** must ship first — gate, A/B, and promotion path bugs affect everything downstream
- **M2 (Scorer)** runs after M1 — scorer selection depends on working A/B and gate
- **M3 (Analyzer)** depends on M2 — staged analyzer needs runtime scorer selection
- **M4 (LLM roles)** depends on M3 — role separation needs analyzer to exist
- **M5 (Benchmarks)** depends on M4 — model comparison informs benchmark design
- **M6 (Reliability)** can run in parallel with M4/M5 — fixes ingestion and trace store
- **M7 (Packaging)** can run in parallel with M4/M5/M6 — CI, Docker, lockfile
- **M8 (Field Test)** depends on M2–M7 — needs all improvements before multi-domain validation
- **M9 (Release)** depends on M8 — needs field test results

## 3. Traceability — v0.1.0 Issues-Found → WBS

| Issue source | Implemented by |
|-------------|----------------|
| [issues-found.md Issue 1](../release/v0.1.0/issues-found.md) — promotion persistence | M1 (#116) |
| [issues-found.md Issue 2](../release/v0.1.0/issues-found.md) — gate edit-distance | M1 (#117) |
| [issues-found.md Issue 3](../release/v0.1.0/issues-found.md) — gate drift | M1 (#118) |
| [issues-found.md Issue 4](../release/v0.1.0/issues-found.md) — A/B alpha semantics | M1 (#119) |
| [issues-found.md Issue 5](../release/v0.1.0/issues-found.md) — runtime scorer selection | M2 (#120) |
| [issues-found.md Issue 6](../release/v0.1.0/issues-found.md) — hermetic bad-edit rejection | M3 (#124) |
| [issues-found.md Issue 7](../release/v0.1.0/issues-found.md) — per-suite runner modes | M3 (#125) |
| [issues-found.md Issue 8](../release/v0.1.0/issues-found.md) — held-out set size & statistical power | M5 (#136) |
| [issues-found.md Issue 9](../release/v0.1.0/issues-found.md) — rejection-aware analyzer | M5 (#141) |
| [issues-found.md Issue 10](../release/v0.1.0/issues-found.md) — prompt style for local models | M5 (#137) |
| [issues-found.md Issue 11](../release/v0.1.0/issues-found.md) — classification examples | M5 (#138) |
| [issues-found.md Issue 12](../release/v0.1.0/issues-found.md) — generation judge rubric | M4 (#129) |
| [issues-found.md Issue 13](../release/v0.1.0/issues-found.md) — missing corpus types | M5 (#139) |
| [issues-found.md Issue 14](../release/v0.1.0/issues-found.md) — classification subsets | M2 (#121) |
| [issues-found.md Issue 15](../release/v0.1.0/issues-found.md) — other semantics | M2 (#122) |
| [issues-found.md Issue 16](../release/v0.1.0/issues-found.md) — label-set-aware scorers | M2 (#123) |
| [issues-found.md Issue 17](../release/v0.1.0/issues-found.md) — extraction scorer | M3 (#126) |
| [issues-found.md Issue 18](../release/v0.1.0/issues-found.md) — staged analyzer | M3 (#127) |
| [issues-found.md Issue 19](../release/v0.1.0/issues-found.md) — regression sentinel | M3 (#128) |
| [issues-found.md Issue 20](../release/v0.1.0/issues-found.md) — model role separation | M4 (#130) |
| [issues-found.md Issue 21](../release/v0.1.0/issues-found.md) — provider configurability | M4 (#131) |
| [issues-found.md Issue 22](../release/v0.1.0/issues-found.md) — benchmark manifests | M4 (#132) |
| [issues-found.md Issue 23](../release/v0.1.0/issues-found.md) — local-model comparison | M4 (#133) |
| [issues-found.md Issue 24](../release/v0.1.0/issues-found.md) — optimizer-effectiveness metrics | M4 (#134) |
| [issues-found.md Issue 25](../release/v0.1.0/issues-found.md) — tighten claims | M4 (#135) |

## 4. Cross-Cutting Contracts

- **All exit gates apply to every milestone:** Ruff clean, mypy strict clean, all tests pass, coverage > 92%, docs updated
- **No paid LLM calls in CI:** Hermetic by default — mock providers used in all CI tests
- **Fail-closed on analyzer:** Analyzer still has no authority — all proposals through A/B + gate
- **Deterministic gate:** Gate remains deterministic code, not LLM-judged
- **Provenance-first:** Every prompt version carries full lineage
- **File-based persistence:** No external database dependency

## 5. Issue Naming Convention

- Title: `[v0.2.0-M1] Task description`
- Labels: `milestone-M1` through `milestone-M9`, `area-*`, `kind-*`
- Milestone: `v0.2.0-M1` through `v0.2.0-M9`

## 6. Exit Gate (Every Milestone)

- [ ] Ruff clean: `ruff check .` → 0 errors
- [ ] Mypy strict clean: `mypy --strict` → 0 errors
- [ ] All tests pass: `pytest` → 0 failures
- [ ] Coverage > 92%: `pytest --cov=agent_self_edit --cov-fail-under=92`
- [ ] Zero paid LLM calls in CI (hermetic by default — mock providers used)
- [ ] Documentation updated for the milestone's scope
- [ ] WBS index updated with milestone status

## 7. Design Documents to Author

| D# | Doc | Milestone | Path | Contents |
|----|-----|-----------|------|----------|
| D1 | Scorer selection design | M2 | `docs/design/scorer-selection-design.md` | Runtime scorer selection, classification subsets, label-set-aware scorers |
| D2 | Staged analyzer design | M3 | `docs/design/staged-analyzer-design.md` | Four-stage analyzer pipeline, failure summarization, edit synthesis |
| D3 | Model role separation design | M4 | `docs/design/model-role-design.md` | Executor/analyzer/judge roles, provider config per role |
| D4 | Benchmark manifest design | M4 | `docs/design/benchmark-manifest-design.md` | Benchmark-role manifests, disjointness validation, scorer compatibility |
| D5 | Rejection-aware analyzer design | M5 | `docs/design/rejection-aware-analyzer-design.md` | Structured feedback feeding, proposal memory, novelty constraints |
| D6 | Trace reliability design | M6 | `docs/design/trace-reliability-design.md` | Row-identity ack, retry-safe batching, init state guarantees |
| D7 | Field test plan v0.2.0 | M8 | `docs/field-test/v0.2.0/field-test-plan.md` | Multi-domain test objectives, corpus structure, success criteria |

## 8. Connected

- [PRD](../design/README.md) — Product requirements
- [Architecture](../design/prd/02-architecture.md) — System architecture
- [Features](../design/prd/05-features.md) — Feature set F-01 through F-14
- [CUJs](../design/prd/04-users-and-cujs.md) — Customer user journeys
- [Roadmap](../design/prd/09-roadmap.md) — Full roadmap v0.1.0 through v1.0.0
- [v0.1.0 WBS](../wbs/v0.1.0/wbs-v0.1.0-index.md) — Previous version WBS
- [Issues Found](../release/v0.1.0/issues-found.md) — Issues found during v0.1.0 field test