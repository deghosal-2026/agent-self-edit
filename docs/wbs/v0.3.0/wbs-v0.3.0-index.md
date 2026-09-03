# WBS — AgentSelfEdit v0.3.0 (Index)

> v0.3.0 issues are attached to the **13 GitHub milestones** `0.3.0-M1` through `0.3.0-M13` (milestones [#23–#35](https://github.com/deghosal-2026/agent-self-edit/milestones)). 109 open issues (#206–#314; #206–#301 original 96 + 7 new M12 field-test/Docker + 6 new M13 release), 8 per milestone for M1–M11, 15 for M12, 6 for M13, organized by similar asks. All issues retitled with `[0.3.0-MX]` prefix.
>
> **Version split note:** the WBS below is the **active plan for v0.3.0**. Once v0.3.0 ships, this will be frozen history. Builds on v0.2.0 field test audit (field-test: 0% improvement root cause, hermetic suite gaps, corpus gaps) and bug backlog 206–301.

## 1. Milestone Overview

| M | Name | Core features | Issues | Part file | Status |
|---|------|---------------|--------|-----------|--------|
| M1 | A/B Statistical Engine | bootstrap CI seed, permutation one-tailed (x2), tie detection, CI calibration, winner='a' path, run_task format (x2) | [#294](https://github.com/deghosal-2026/agent-self-edit/issues/294), [#278](https://github.com/deghosal-2026/agent-self-edit/issues/278), [#257](https://github.com/deghosal-2026/agent-self-edit/issues/257), [#244](https://github.com/deghosal-2026/agent-self-edit/issues/244), [#234](https://github.com/deghosal-2026/agent-self-edit/issues/234), [#248](https://github.com/deghosal-2026/agent-self-edit/issues/248), [#277](https://github.com/deghosal-2026/agent-self-edit/issues/277), [#267](https://github.com/deghosal-2026/agent-self-edit/issues/267) — [milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/23) | [part1](wbs-v0.3.0-part1-statistical-gate.md) | ✅ Done |
| M2 | Promotion Gate & Near-Miss Logic | near_miss_threshold=0, ratio denom, unchecked gates, audit near_misses, dead loading, stale context (x2) | [#300](https://github.com/deghosal-2026/agent-self-edit/issues/300), [#298](https://github.com/deghosal-2026/agent-self-edit/issues/298), [#211](https://github.com/deghosal-2026/agent-self-edit/issues/211), [#258](https://github.com/deghosal-2026/agent-self-edit/issues/258), [#249](https://github.com/deghosal-2026/agent-self-edit/issues/249), [#282](https://github.com/deghosal-2026/agent-self-edit/issues/282), [#251](https://github.com/deghosal-2026/agent-self-edit/issues/251), [#289](https://github.com/deghosal-2026/agent-self-edit/issues/289) — [milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/24) | [part1](wbs-v0.3.0-part1-statistical-gate.md) | ✅ Done |
| M3 | Drift, Frozen & Guardrail Safety | TF-IDF log (x2), drift self-baseline (x2), _MALFORMED_RE (x2), _FROZEN_RE DOTALL, frozen_sections arg | [#283](https://github.com/deghosal-2026/agent-self-edit/issues/283), [#250](https://github.com/deghosal-2026/agent-self-edit/issues/250), [#276](https://github.com/deghosal-2026/agent-self-edit/issues/276), [#206](https://github.com/deghosal-2026/agent-self-edit/issues/206), [#284](https://github.com/deghosal-2026/agent-self-edit/issues/284), [#209](https://github.com/deghosal-2026/agent-self-edit/issues/209), [#256](https://github.com/deghosal-2026/agent-self-edit/issues/256), [#252](https://github.com/deghosal-2026/agent-self-edit/issues/252) — [milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/25) | [part2](wbs-v0.3.0-part2-guardrail-registry.md) | ✅ Done |
| M4 | Prompt Registry & Integrity | Meta.to_dict omits (x2), forward-compat (x2), create corruption, git swallow, current_prompt cache (x2) | [#292](https://github.com/deghosal-2026/agent-self-edit/issues/292), [#241](https://github.com/deghosal-2026/agent-self-edit/issues/241), [#291](https://github.com/deghosal-2026/agent-self-edit/issues/291), [#215](https://github.com/deghosal-2026/agent-self-edit/issues/215), [#222](https://github.com/deghosal-2026/agent-self-edit/issues/222), [#237](https://github.com/deghosal-2026/agent-self-edit/issues/237), [#254](https://github.com/deghosal-2026/agent-self-edit/issues/254), [#290](https://github.com/deghosal-2026/agent-self-edit/issues/290) — [milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/26) | [part2](wbs-v0.3.0-part2-guardrail-registry.md) | ✅ Done |
| M5 | Trace Store, Batch & Lifecycle | churn per-op (x2), per-_run_once reconstruction, cleanup deletes in-flight, stuck release (x2), metadata dropped, batch_ready | [#301](https://github.com/deghosal-2026/agent-self-edit/issues/301), [#245](https://github.com/deghosal-2026/agent-self-edit/issues/245), [#255](https://github.com/deghosal-2026/agent-self-edit/issues/255), [#214](https://github.com/deghosal-2026/agent-self-edit/issues/214), [#213](https://github.com/deghosal-2026/agent-self-edit/issues/213), [#281](https://github.com/deghosal-2026/agent-self-edit/issues/281), [#223](https://github.com/deghosal-2026/agent-self-edit/issues/223), [#217](https://github.com/deghosal-2026/agent-self-edit/issues/217) — [milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/27) | [part3](wbs-v0.3.0-part3-trace-analyzer.md) | ⬜ TODO |
| M6 | Analyzer Pipeline (Staged & Validation) | ignores llm_provider (x2), staged no-effect, validate_proposal limits (x2), fuzzy Strategy3 (x2), Stage2 vs Stage3 mismatch | [#286](https://github.com/deghosal-2026/agent-self-edit/issues/286), [#219](https://github.com/deghosal-2026/agent-self-edit/issues/219), [#285](https://github.com/deghosal-2026/agent-self-edit/issues/285), [#287](https://github.com/deghosal-2026/agent-self-edit/issues/287), [#243](https://github.com/deghosal-2026/agent-self-edit/issues/243), [#279](https://github.com/deghosal-2026/agent-self-edit/issues/279), [#207](https://github.com/deghosal-2026/agent-self-edit/issues/207), [#253](https://github.com/deghosal-2026/agent-self-edit/issues/253) — [milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/28) | [part3](wbs-v0.3.0-part3-trace-analyzer.md) | ⬜ TODO |
| M7 | Scoring & Task Correctness | ContainsScorer denom (x2), double-count extraction, LLMJudge verbose + dimensions, resolve_scorer nondet, empty task list, fence stripping | [#296](https://github.com/deghosal-2026/agent-self-edit/issues/296), [#225](https://github.com/deghosal-2026/agent-self-edit/issues/225), [#297](https://github.com/deghosal-2026/agent-self-edit/issues/297), [#295](https://github.com/deghosal-2026/agent-self-edit/issues/295), [#220](https://github.com/deghosal-2026/agent-self-edit/issues/220), [#242](https://github.com/deghosal-2026/agent-self-edit/issues/242), [#236](https://github.com/deghosal-2026/agent-self-edit/issues/236), [#224](https://github.com/deghosal-2026/agent-self-edit/issues/224) — [milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/29) | [part4](wbs-v0.3.0-part4-scoring-config.md) | ⬜ TODO |
| M8 | Config, Providers & Resilience | interpolate partial, allowlist (x2), timeout/trigger/cache, backoff, vague failure, trigger ignored, model-vs-model | [#293](https://github.com/deghosal-2026/agent-self-edit/issues/293), [#299](https://github.com/deghosal-2026/agent-self-edit/issues/299), [#239](https://github.com/deghosal-2026/agent-self-edit/issues/239), [#235](https://github.com/deghosal-2026/agent-self-edit/issues/235), [#231](https://github.com/deghosal-2026/agent-self-edit/issues/231), [#238](https://github.com/deghosal-2026/agent-self-edit/issues/238), [#228](https://github.com/deghosal-2026/agent-self-edit/issues/228), [#227](https://github.com/deghosal-2026/agent-self-edit/issues/227) — [milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/30) | [part4](wbs-v0.3.0-part4-scoring-config.md) | ⬜ TODO |
| M9 | Loop Orchestration, Caching & Concurrency | rebuilt per proposal (x2), gate bypass + atomic (x2), A/B caching, file lock, swallowed exceptions, cost underreport | [#288](https://github.com/deghosal-2026/agent-self-edit/issues/288), [#240](https://github.com/deghosal-2026/agent-self-edit/issues/240), [#280](https://github.com/deghosal-2026/agent-self-edit/issues/280), [#216](https://github.com/deghosal-2026/agent-self-edit/issues/216), [#230](https://github.com/deghosal-2026/agent-self-edit/issues/230), [#229](https://github.com/deghosal-2026/agent-self-edit/issues/229), [#221](https://github.com/deghosal-2026/agent-self-edit/issues/221), [#210](https://github.com/deghosal-2026/agent-self-edit/issues/210) — [milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/31) | [part5](wbs-v0.3.0-part5-loop-cli.md) | ⬜ TODO |
| M10 | CLI, Diff & Test Hardening | format_edit_summary, side-by-side identical, _run_once tests, behavioral asserts, Staged tests, heatmap bucket, raw replace (x2) | [#218](https://github.com/deghosal-2026/agent-self-edit/issues/218), [#212](https://github.com/deghosal-2026/agent-self-edit/issues/212), [#247](https://github.com/deghosal-2026/agent-self-edit/issues/247), [#233](https://github.com/deghosal-2026/agent-self-edit/issues/233), [#232](https://github.com/deghosal-2026/agent-self-edit/issues/232), [#246](https://github.com/deghosal-2026/agent-self-edit/issues/246), [#208](https://github.com/deghosal-2026/agent-self-edit/issues/208), [#275](https://github.com/deghosal-2026/agent-self-edit/issues/275) — [milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/32) | [part5](wbs-v0.3.0-part5-loop-cli.md) | ⬜ TODO |
| M11 | Field-Test Foundations & Hermetic Suite | Oracle Drift Guard, mixed-domain 30+, sentinel, adversarial, rollback, hermetic suite, coverage 91%, ruff/mypy | [#272](https://github.com/deghosal-2026/agent-self-edit/issues/272), [#273](https://github.com/deghosal-2026/agent-self-edit/issues/273), [#263](https://github.com/deghosal-2026/agent-self-edit/issues/263), [#261](https://github.com/deghosal-2026/agent-self-edit/issues/261), [#260](https://github.com/deghosal-2026/agent-self-edit/issues/260), [#262](https://github.com/deghosal-2026/agent-self-edit/issues/262), [#259](https://github.com/deghosal-2026/agent-self-edit/issues/259), [#226](https://github.com/deghosal-2026/agent-self-edit/issues/226) — [milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/33) | [part6](wbs-v0.3.0-part6-field-test.md) | ⬜ TODO |
| M12 | Field-Test Corpora, Oracle & Reporting | 0% root cause, gold corpus, rejection-aware qualitative, cost breakdown, seeded-prompts 15, role separation, real-trace ingestion, 20% vs 46% + Docker/field-test plan/exec (7 new) | [#274](https://github.com/deghosal-2026/agent-self-edit/issues/274), [#268](https://github.com/deghosal-2026/agent-self-edit/issues/268), [#270](https://github.com/deghosal-2026/agent-self-edit/issues/270), [#269](https://github.com/deghosal-2026/agent-self-edit/issues/269), [#271](https://github.com/deghosal-2026/agent-self-edit/issues/271), [#265](https://github.com/deghosal-2026/agent-self-edit/issues/265), [#264](https://github.com/deghosal-2026/agent-self-edit/issues/264), [#266](https://github.com/deghosal-2026/agent-self-edit/issues/266), [#302](https://github.com/deghosal-2026/agent-self-edit/issues/302), [#303](https://github.com/deghosal-2026/agent-self-edit/issues/303), [#304](https://github.com/deghosal-2026/agent-self-edit/issues/304), [#305](https://github.com/deghosal-2026/agent-self-edit/issues/305), [#306](https://github.com/deghosal-2026/agent-self-edit/issues/306), [#307](https://github.com/deghosal-2026/agent-self-edit/issues/307), [#308](https://github.com/deghosal-2026/agent-self-edit/issues/308) — [milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/34) — 15 issues | [part6](wbs-v0.3.0-part6-field-test.md) | ⬜ TODO |
| M13 | Release Readiness | PyPI, Docker, docs, coverage 91%, security audit, GitHub release — mirrors v0.2.0-M9 | [#309](https://github.com/deghosal-2026/agent-self-edit/issues/309), [#310](https://github.com/deghosal-2026/agent-self-edit/issues/310), [#311](https://github.com/deghosal-2026/agent-self-edit/issues/311), [#312](https://github.com/deghosal-2026/agent-self-edit/issues/312), [#313](https://github.com/deghosal-2026/agent-self-edit/issues/313), [#314](https://github.com/deghosal-2026/agent-self-edit/issues/314) — [milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/35) — 6 issues | [part7](wbs-v0.3.0-part7-release.md) | ⬜ TODO |

## 2. Dependency Graph

```
M1 ──► M2 ──► M3 ──► M4 ──► M6 ──► M7 ──► M9 ──► M10 ──► M11 ──► M12 ──► M13
            │              │         │         │
            └──► M5 ───────┘         └──► M8 ──┘
```

- **M1 (Statistical Engine)** must ship first — `bootstrap_ci`/`permutation_test` seed and `run_task` format affect every A/B decision downstream
- **M2 (Gate & Near-Miss)** depends on M1 — near-miss ratio uses M1's corrected statistical outputs
- **M3 (Guardrail)** depends on M2 — drift/frozen checks are ordered after statistical checks in gate
- **M4 (Registry)** independent but linked — must be correct before M5/M6 read `current_prompt`/`Meta` during proposal loops
- **M5 (Trace)** can run in parallel with M3/M4 — batch lifecycle fixes unblock loop (M9)
- **M6 (Analyzer)** depends on M3/M4/M5 — staged pipeline reads prompt, guardrail annotations, and batch context
- **M7 (Scoring)** depends on M6 — scorers feed analyzer validation and A/B results
- **M8 (Config)** can run in parallel with M6/M7 — provider wiring needed before M9 loop execution
- **M9 (Loop)** depends on M5–M8 — orchestration, caching, file lock, and cost accounting need all prior correctness
- **M10 (CLI)** depends on M9 — diff/propose/_run_once visibility wraps loop fixes
- **M11 (Foundations)** depends on M1–M10 — hermetic suite measures true coverage/ruff/mypy after all correctness fixes
- **M12 (Corpora & Oracle)** depends on M11 — reporting, gold corpus, Docker/field-test planning+execution need foundations measured
- **M13 (Release Readiness)** depends on M12 — PyPI/Docker/docs/coverage/security/GitHub release need field-test evidence (mirrors v0.2.0-M9 #180–#185)

## 3. Traceability — v0.2.0 Issues-Found → WBS 0.3.0

| Issue source | Implemented by |
|--------------|----------------|
| Open bug backlog #206–#245, #248–#301 (duplicate pairs #283/#250, #276/#206, #248/#277, #292/#241, #291/#215, #301/#245, #286/#219, #296/#225, #248/#277, #288/#240, #254/#290) — correctness audit | M1–M10 |
| [v0.2.0 FIELD_TEST_REPORT.md still 0% improvement](../field-test/v0.2.0/FIELD_TEST_REPORT.md) — broken edit path not identified | M5 (#288 raw replace), M9 (#280 gate bypass), M12 (#274 root cause) |
| Field-test gaps: ruff/mypy never confirmed, coverage > 91% never measured | M11 (#273, #272) |
| [v0.2.0 sentinel/adversarial/rollback never validated](../field-test/v0.2.0/) | M11 (#261, #260, #262) |
| Mixed-domain 30+ tasks planned but never expanded | M11 (#259) |
| Seeded-prompts corpus (15 prompts) never used | M12 (#271) |
| Real-trace gold corpus never operationalized | M12 (#268) |
| Rejection-aware analyzer only qualitative | M12 (#270) |
| No cost-per-iteration breakdown for OpenRouter runs | M12 (#269) |
| Model role separation never tested measurably different | M12 (#265) |
| Real-trace ingestion loop conceptually invalid — wrong A/B corpus | M12 (#264) |
| Winner='a' path never tested — one-tailed permutation | M1 (#267, #278/#257) |
| v0.2.0 reported 20% baseline but A/B set was 46% — misleading | M12 (#266) |
| Hermetic suite not run in either version | M11 (#263) |
| Oracle Drift Guard — shared wrong oracle | M11 (#226) — design: detect optimizer/scorer/golden sharing incorrect success definition |
| Statistical ceiling: 5 movable tasks cannot clear p<0.05 | M11/M12 — covered by M1 calibration (#234) + M12 reporting |
| A/B task set / held-out expansion deferred from v0.2.0 M5 | M11 (#259) + M12 corpora |
| v0.2.0 field-test plan gaps (#172, #176) — Docker/hermetic | M12 (#302 Docker plan, #303 authoring, #304 execution, #305 planning) + M13 release mirrors #180–#185 |
| Docker authoring/execution (#201–#204) | M12 (#303, #304) |
| Release readiness (#180–#185) | M13 (#309–#314) |

## 4. Cross-Cutting Contracts

- **All exit gates apply to every milestone:** Ruff clean (`ruff check .` → 0), mypy strict clean (`mypy --strict src/agent_self_edit` → 0), all tests pass (`pytest` → 0 failures), coverage > 91% (`--cov-fail-under=91`), docs updated for scope
- **No paid LLM calls in CI:** Hermetic by default — mock providers used in all CI tests; real LLM tests in field-test only
- **Fail-closed on analyzer:** Analyzer still has no authority — all proposals through A/B + gate; staged analyzer default but still gated
- **Deterministic gate:** Gate remains deterministic code, not LLM-judged; `check_all` called once per proposal, atomic with audit log
- **Provenance-first:** Every prompt version carries full lineage via `Meta.to_dict()` including `trigger_trace_ids`, `model_version`, `diff_from_previous`; forward-compat filter tolerates future fields
- **File-based persistence:** Registry file-based (`.md` + `.meta.json`) with file lock; traces SQLite WAL with single persistent connection and row-identity ack

## 5. Issue Naming Convention

- Title: `[0.3.0-M1] Task description` — 13 milestones M1–M13, 109 total (#206–#314; M1–M11 8 each, M12 15, M13 6)
- Milestone: `0.3.0-M1` through `0.3.0-M13` — GitHub milestones 23–35, state `open`
- Link: `https://github.com/deghosal-2026/agent-self-edit/issues/<num>` and `https://github.com/deghosal-2026/agent-self-edit/milestone/<id>`

## 6. Exit Gate (Every Milestone)

- [ ] Ruff clean: `ruff check .` → 0 errors
- [ ] Mypy strict clean: `mypy --strict src/agent_self_edit` → 0 errors
- [ ] All tests pass: `python3 -m pytest --ignore=tests/test_docker.py -x -q` → 0 failures
- [ ] Coverage > 91%: `pytest --cov=agent_self_edit --cov-fail-under=91` (v0.2.0 accepted 81% at [#183](https://github.com/deghosal-2026/agent-self-edit/issues/183) — v0.3.0 must restore 91%)
- [ ] Zero paid LLM calls in CI (hermetic by default — mock providers used)
- [ ] Documentation updated for the milestone's scope
- [ ] WBS index updated with milestone status

## 7. Design Documents to Author

| D# | Doc | Milestone | Path | Contents |
|----|-----|-----------|------|----------|
| D1 | A/B statistical correction design | M1 | `docs/design/ab-test-statistical-fix-design.md` | Seeded CI calibration, permutation two-tailed, tie epsilon, `run_task` message format |
| D2 | Gate near-miss design | M2 | `docs/design/gate-near-miss-design.md` | Threshold validation, ratio denominator, audit `near_misses()` reconstruction |
| D3 | Guardrail safety design | M3 | `docs/design/guardrail-safety-design.md` | TF-IDF log correction, drift baseline vs original, frozen section parsing, HTML comment handling |
| D4 | Registry integrity design | M4 | `docs/design/registry-integrity-design.md` | `Meta.to_dict` completeness, forward-compat filter, two-phase write atomicity, git commit handling, prompt caching |
| D5 | Trace lifecycle design | M5 | `docs/design/trace-lifecycle-design.md` | Persistent WAL connection, per-_run_once reconstruction, in-flight reservation, metadata round-trip, batch_ready guard |
| D6 | Analyzer pipeline design | M6 | `docs/design/staged-analyzer-fix-design.md` | llm_provider routing, staged default, validate_proposal limits, fuzzy fix Strategy3, Stage2/3 annotation mismatch |
| D7 | Scoring correctness design | M7 | `docs/design/scoring-correctness-design.md` | ContainsScorer denom, extraction double-count fix, LLMJudge verbose parsing, scorer nondet, empty task set guard |
| D8 | Config & provider design | M8 | `docs/design/config-provider-design.md` | Partial ${VAR} interpolation, provider allowlist, timeout/trigger/cache, backoff, model-vs-model A/B |
| D9 | Loop orchestration design | M9 | `docs/design/loop-orchestration-design.md` | Per-proposal rebuild fix, gate atomicity, A/B caching, file lock, exception classification, cost accounting |
| D10 | CLI diff design | M10 | `docs/design/cli-diff-fix-design.md` | format_edit_summary, side-by-side diff, _run_once tests, behavioral asserts, heatmap bucket, raw replace guard |
| D11 | Field-test plan v0.3.0 | M11/M12 | `docs/field-test/v0.3.0/field-test-plan.md` | Hermetic suite, sentinel/adversarial/rollback, 30+ mixed-domain, seeded-prompts, real-trace gold, Oracle Drift Guard — plus Docker test plan (§302) |
| D12 | Release readiness design | M13 | `docs/release/v0.3.0/release-checklist.md` | PyPI, Docker, docs, coverage 91%, security audit, OpenSSF badge, GitHub release — mirrors v0.2.0-M9 |

## 8. Connected

- [PRD](../design/README.md) — Product requirements (v0.3.0 = Scale + Adapters per [roadmap](../design/prd/09-roadmap.md#93-v030--scale--adapters))
- [Architecture](../design/prd/02-architecture.md) — System architecture
- [Features](../design/prd/05-features.md) — Feature set F-01 through F-43
- [CUJs](../design/prd/04-users-and-cujs.md) — Customer user journeys
- [Roadmap](../design/prd/09-roadmap.md) — Full roadmap v0.1.0 through v1.0.0
- [v0.2.0 WBS](../wbs/v0.2.0/wbs-v0.2.0-index.md) — Previous version WBS (frozen)
- [v0.1.0 WBS](../wbs/v0.1.0/wbs-v0.1.0-index.md) — v0.1.0 WBS
- [Milestones](https://github.com/deghosal-2026/agent-self-edit/milestones) — All GitHub milestones (13 for v0.3.0: 23–35)
