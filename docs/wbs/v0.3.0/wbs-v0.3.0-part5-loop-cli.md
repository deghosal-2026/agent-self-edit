# WBS — AgentSelfEdit v0.3.0 Part 5: Loop, CLI & Test Hardening

> **Milestones covered:** M9 (Loop Orchestration, Caching & Concurrency) · M10 (CLI, Diff & Test Hardening)
> **Source:** Loop per-proposal re-init + gate audit not atomic + swallowed exceptions + CLI diff/_run_once gaps (field-test: stale `current_prompt` disk reads per proposal)
> **Dependency:** M9 (depends on M5–M8 loop inputs) → M10 (depends on M9 loop hardening)
> **Issue Range:** #288, #240, #280, #216, #230, #229, #221, #210 (M9) + #218, #212, #247, #233, #232, #246, #208, #275 (M10) — [M9 milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/31) · [M10 milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/32)

---

## Milestone 9: Loop Orchestration, Caching & Concurrency (8 issues)

**Objective:** Fix per-proposal YAML re-read and client re-init, gate bypass that leaves audit not atomic, missing A/B cache, missing file lock, swallowed exceptions with no backoff, and underreported staged cost. Loop currently wastes I/O and can lose audit or cost provenance.

### M9 Design Documents

- **D9 — Loop orchestration design** (`docs/design/loop-orchestration-design.md`): per-loop task/LLM hoisting, gate atomicity, A/B caching, registry file lock, exception classification, cost accounting with multi-pass.

### M9 Task Checklist

| # | Issue | Build (files) | Behavior + edge cases | Issue | Verify | Status |
|---|-------|---------------|----------------------|-------|--------|--------|
| 1 | Hoist task set + LLM out of proposal loop | `src/agent_self_edit/cli/run.py`, `propose.py` — load `task_set` + build `LLM` once before `for proposal in proposals:`; reuse | Batch of 3 proposals = 1 YAML read + 1 client init, not 3 | [#288](https://github.com/deghosal-2026/agent-self-edit/issues/288), [#240](https://github.com/deghosal-2026/agent-self-edit/issues/240) | Loop before/after file reads & client inits measured; 1 per batch | ⬜ |
| 2 | Fix `PromotionGate.check()` bypass / atomic audit | `src/agent_self_edit/cli/run.py`, `propose.py`, `src/agent_self_edit/gate.py` — call `PromotionGate.check()` (not `check_all` directly) so audit log write is atomic with decision; do not bypass | Gate decision and audit log are same txn; previously `check_all` called and log not atomic | [#280](https://github.com/deghosal-2026/agent-self-edit/issues/280), [#216](https://github.com/deghosal-2026/agent-self-edit/issues/216) | `check()` path used; audit log present even when `check_all` raises | ⬜ |
| 3 | Add A/B result caching | `src/agent_self_edit/ab_test.py` — cache key `(task_id, prompt_hash)`; skip re-running identical pair; cache invalidation on prompt version bump | Same `(task, prompt)` not re-run; cache hit saves tokens | [#230](https://github.com/deghosal-2026/agent-self-edit/issues/230) | Identical pair reuses cached `ABResult` | ⬜ |
| 4 | Add file-based registry lock | `src/agent_self_edit/registry.py` — `flock` or lockfile during `create`/`rollback`; multi-process safe | Two concurrent `run.py` do not corrupt `v{N}.md` | [#229](https://github.com/deghosal-2026/agent-self-edit/issues/229) | Concurrent write test; lock held | ⬜ |
| 5 | Classify exceptions (fail-fast vs backoff) | `src/agent_self_edit/cli/run.py` — do not swallow all exceptions; classify: rate-limit→backoff, fatal→exit 1, transient→retry | Previously `except Exception: pass` hides fatal; now fatal exits non-zero, transient backoffs | [#221](https://github.com/deghosal-2026/agent-self-edit/issues/221) | Fatal error exits non-zero; transient backoff | ⬜ |
| 6 | Fix staged analyzer cost underreport | `src/agent_self_edit/analyzer.py` — sum tokens across 4 stages, not single-pass estimate | Reported cost reflects actual staged tokens | [#210](https://github.com/deghosal-2026/agent-self-edit/issues/210) | Staged cost = sum(stages), not 1x | ⬜ |

### M9 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Hoisted loop | 1 YAML + 1 LLM per batch | Per-proposal I/O test |
| Gate atomic | Audit log always written | `check()` atomic test |
| A/B caching | Hit on identical pair | Cache hit test |
| File lock | No concurrent corruption | Concurrent write test |
| Exception classification | Fatal exits 1, not swallowed | Exception path tests |
| Staged cost | Sum across stages | Token accounting test |
| Coverage | > 91% | `--cov-fail-under=91` |

### M9 Exit Gate

- [ ] Task+LLM hoisted out of loop (both #288/#240 fixed)
- [ ] Gate atomic via `PromotionGate.check()` (both #280/#216 fixed)
- [ ] A/B caching avoids identical re-runs (#230)
- [ ] File-based registry lock (#229)
- [ ] Exception classification with backoff/fatal (#221)
- [ ] Staged cost sums all stages (#210)
- [ ] Ruff clean: `ruff check .` → 0 errors
- [ ] Mypy strict clean: `mypy --strict src/agent_self_edit` → 0 errors
- [ ] All tests pass: `python3 -m pytest --ignore=tests/test_docker.py -x -q` → 0 failures
- [ ] Coverage > 91%: `pytest --cov=agent_self_edit --cov-fail-under=91`
- [ ] Documentation updated for the milestone's scope

**Dependency:** M5–M8. **Produces for M10+:** cheap loop, atomic gate+audit, safe concurrency, correct cost.

---

## Milestone 10: CLI, Diff & Test Hardening (8 issues)

**Objective:** Fix CLI visibility bugs that hide failures: `gate-check count` shown as lines changed, side-by-side diff identical on both sides, missing `_run_once` unit tests, behavioral asserts only on exit code, untested staged path, heatmap bucket by hypothesis not section, and `raw .replace()` no-ops.

### M10 Design Documents

- **D10 — CLI diff fix design** (`docs/design/cli-diff-fix-design.md`): edit summary formatting, side-by-side diff correctness, _run_once tests, behavioral CLI asserts, staged tests, heatmap bucket fix, safe `.replace()` guard.

### M10 Task Checklist

| # | Issue | Build (files) | Behavior + edge cases | Issue | Verify | Status |
|---|-------|---------------|----------------------|-------|--------|--------|
| 1 | Fix `format_edit_summary()` gate count as lines | `src/agent_self_edit/cli/status.py` or `diff.py` — show actual `diff lines_changed` not `len(gate_checks)` | Summary reads `+12% (p=0.03, n=40) — 5 lines` not `6 checks` | [#218](https://github.com/deghosal-2026/agent-self-edit/issues/218) | Summary shows diff lines, not check count | ⬜ |
| 2 | Fix side-by-side diff identical text | `src/agent_self_edit/diff.py` — side-by-side `removed` vs `added` distinct; previously both sides showed same text for modified lines | Modified line: left shows `-old`, right shows `+new` | [#212](https://github.com/deghosal-2026/agent-self-edit/issues/212) | Side-by-side not identical | ⬜ |
| 3 | Add `_run_once()` unit tests | `tests/test_run.py` or `test_loop.py` — core loop only tested via full CLI invocation; add unit tests mocking trace/batch/gate/registry | `_run_once` has direct unit coverage; no CLI subprocess required | [#247](https://github.com/deghosal-2026/agent-self-edit/issues/247) | `_run_once` tests exist and pass | ⬜ |
| 4 | Add behavioral asserts to CLI tests | `tests/test_cli.py` — currently `assert exit_code ==0` only; add output shape, diff content, lineage JSON, guardrail report assertions | CLI tests assert behavior, not just code | [#233](https://github.com/deghosal-2026/agent-self-edit/issues/233) | Behavioral asserts added | ⬜ |
| 5 | Add StagedAnalyzer unit tests | `tests/test_analyzer.py` — entire default path untested; cover staged 4-stage happy + failure | Staged path tested; coverage of default | [#232](https://github.com/deghosal-2026/agent-self-edit/issues/232) | Staged tests added | ⬜ |
| 6 | Fix edit density heatmap bucket | `src/agent_self_edit/diff.py` — bucket by `prompt section` (e.g. `role`, `steps`, `examples`) not `hypothesis` text | Heatmap shows per-section frequency | [#246](https://github.com/deghosal-2026/agent-self-edit/issues/246) | Heatmap buckets by section | ⬜ |
| 7 | Guard raw `.replace()` no-ops | `src/agent_self_edit/cli/run.py`, `propose.py` — `candidate = materialize_candidate_prompt(current_prompt, proposal.old_text, proposal.new_text)` and assert `candidate != current_prompt` or fail | Silent no-op when `old_text` missing becomes loud failure; previously raw `.replace()` silently unchanged | [#208](https://github.com/deghosal-2026/agent-self-edit/issues/208), [#275](https://github.com/deghosal-2026/agent-self-edit/issues/275) | Missing `old_text` does not silently no-op | ⬜ |

### M10 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Edit summary | Real lines changed | Summary test |
| Side-by-side diff | Distinct old/new | Diff test |
| _run_once tests | Direct unit coverage | Loop tests |
| Behavioral asserts | Output shape checked | CLI tests |
| Staged tests | Default path covered | Analyzer tests |
| Heatmap | Section buckets | Density test |
| Replace guard | Loud on missing old_text | .replace guard test |
| Coverage | > 91% | `--cov-fail-under=91` |

### M10 Exit Gate

- [ ] `format_edit_summary` shows diff lines (#218)
- [ ] Side-by-side diff distinct (#212)
- [ ] `_run_once` unit tests added (#247)
- [ ] CLI behavioral asserts (#233)
- [ ] StagedAnalyzer tests added (#232)
- [ ] Heatmap buckets by section (#246)
- [ ] `raw .replace` guarded (both #208/#275 fixed)
- [ ] Ruff clean: `ruff check .` → 0 errors
- [ ] Mypy strict clean: `mypy --strict src/agent_self_edit` → 0 errors
- [ ] All tests pass: `python3 -m pytest --ignore=tests/test_docker.py -x -q` → 0 failures
- [ ] Coverage > 91%: `pytest --cov=agent_self_edit --cov-fail-under=91`
- [ ] Documentation updated for the milestone's scope

**Dependency:** M9. **Produces for M11+:** visible diffs, tested loop, safe materialization.
