# WBS — AgentSelfEdit v0.2.0 Part 1: Correctness Fixes

> **Milestone covered:** M1 (Correctness Fixes)
> **Source:** v0.1.0 field test issues-found.md Issues 1–4
> **Dependency:** none (runs on v0.1.0 foundation)
> **Issue Range:** #116–#119

---

## Milestone 1: Correctness Fixes (#116–#119)

**Objective:** Fix four correctness bugs in the core product path — promotion persistence, gate edit-distance, gate drift calculation, and A/B significance semantics. These bugs mean the system may evaluate, gate, and store different prompts than it should. All were discovered during v0.1.0 field test.

### M1 Task Checklist

| # | Issue | Build (files) | Behavior + edge cases | Issue | Verify | Status |
|---|-------|---------------|----------------------|-------|--------|--------|
| 1 | Fix promoted prompt persistence | `src/agent_self_edit/cli/run.py`, `src/agent_self_edit/cli/propose.py` | Materialize full candidate prompt once; use same candidate for A/B test input and promotion persistence; do not store `proposal.new_text` alone; `materialize_candidate_prompt()` shared helper | [#116](https://github.com/deghosal-2026/agent-self-edit/issues/116) | Promoted prompt equals full candidate used in A/B; no path stores fragment only | ✅ |
| 2 | Fix gate edit-distance | `src/agent_self_edit/gate.py` | Compute edit distance between `current_prompt` and fully materialized candidate prompt; use shared materialization helper from #116; one-line replacement → small edit-distance; multi-line insertion → proportionate value | [#117](https://github.com/deghosal-2026/agent-self-edit/issues/117) | Edit-distance computed against full candidate, not fragment | ✅ |
| 3 | Fix gate drift calculation | `src/agent_self_edit/gate.py` | Compute drift between `original_prompt` and fully materialized candidate prompt; tiny in-place edits → low drift; full rewrites → high drift | [#118](https://github.com/deghosal-2026/agent-self-edit/issues/118) | Drift computed against full candidate, not fragment | ✅ |
| 4 | Fix A/B significance semantics | `src/agent_self_edit/ab_test.py` | Compute `alpha = 1.0 - confidence_level`; use `p_value < alpha` not `p_value < confidence_level`; align A/B and gate significance semantics; `p=0.23` at 95% confidence → inconclusive; `p=0.01` → significant | [#119](https://github.com/deghosal-2026/agent-self-edit/issues/119) | A/B and gate significance semantics match; synthetic stats verify correct thresholds | ✅ |

### M1 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Promotion persistence | Full candidate prompt persisted, not fragment | Integration test for run + propose paths |
| Edit-distance accuracy | Distance computed against full candidate | Gate test suite |
| Drift accuracy | Drift computed against full candidate | Gate test suite |
| A/B alpha semantics | `p < alpha` used consistently; A/B aligns with gate | A/B + gate test suites |
| Coverage | > 92% | `--cov-fail-under=92` |

### M1 Out of Scope

- Scorer selection (M2), staged analyzer (M3), model role separation (M4), benchmarks (M5)

### M1 Exit Gate

- [x] Promotion persists full candidate prompt, no path stores fragment only
- [x] Edit-distance measures full candidate prompt vs current
- [x] Drift measures full candidate prompt vs original
- [x] A/B uses `alpha = 1 - confidence_level`; `p < alpha` semantics match gate
- [x] Ruff clean, mypy strict clean, all tests pass, coverage > 92%
- [x] Shared `materialize_candidate_prompt()` helper extracted and tested
- [x] Integration tests prove persistence, edit-distance, drift, and A/B correctness

**Dependency:** none. **Produces for M2+:** correct promotion path, correct gate checks, correct A/B semantics.