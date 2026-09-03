# WBS — AgentSelfEdit v0.3.0 Part 3: Trace & Analyzer Pipeline

> **Milestones covered:** M5 (Trace Store, Batch & Lifecycle) · M6 (Analyzer Pipeline, Staged & Validation)
> **Source:** Trace store churn + in-flight reservation gaps + analyzer staged path dead code (field-test: stale rejection_context corrupted feedback, task/LLM re-init per proposal)
> **Dependency:** M5 (no dep on M4 but needs cached prompt) → M6 (depends on M3 guardrail + M5 batch)
> **Issue Range:** #301, #245, #255, #214, #213, #281, #223, #217 (M5) + #286, #219, #285, #287, #243, #279, #207, #253 (M6) — [M5 milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/27) · [M6 milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/28)

---

## Milestone 5: Trace Store, Batch & Lifecycle (8 issues)

**Objective:** Fix connection churn, per-`_run_once` reconstruction (dir scan every 5s), `cleanup` deleting in-flight, stuck `processed=-1`, dropped `metadata`, and `propose` without `batch_ready` guard.

### M5 Design Documents

- **D5 — Trace lifecycle design** (`docs/design/trace-lifecycle-design.md`): persistent WAL connection, per-_run_once reuse, row-identity ack expiration, metadata round-trip, batch_ready guard.

### M5 Task Checklist

| # | Issue | Build (files) | Behavior + edge cases | Issue | Verify | Status |
|---|-------|---------------|----------------------|-------|--------|--------|
| 1 | Use single persistent SQLite connection | `src/agent_self_edit/trace.py` — `TraceStore.__post_init__` opens `self._db = sqlite3.connect(path, check_same_thread=False, timeout=30)`; WAL; `_initialize_schema` on `self._db`; `close` in `__del__` | `ingest` + `count` = 1 `connect` call not N; batch of 50 = 1 connection; lock guards connection lifecycle | [#301](https://github.com/deghosal-2026/agent-self-edit/issues/301), [#245](https://github.com/deghosal-2026/agent-self-edit/issues/245) | Monkeypatch `connect` count ==1 | ✅ |
| 2 | Fix `Registry`/`TraceStore` reconstructed per `_run_once` | `src/agent_self_edit/cli/run.py` — reuse singleton or cached `Registry`/`TraceStore` across loop iterations; avoid full dir scan every 5s | Loop does not re-scan `prompts/registry` each tick; I/O constant | [#255](https://github.com/deghosal-2026/agent-self-edit/issues/255) | I/O per `_run_once` not scanning | ✅ |
| 3 | Fix `cleanup()` deleting in-flight traces | `src/agent_self_edit/trace.py` — `cleanup` must not delete `processed=-1` (in-flight) rows; only `processed=1` expired or `processed=0` old | Mid-analysis rows not erased; `cleanup` skips `processed=-1` | [#214](https://github.com/deghosal-2026/agent-self-edit/issues/214) | In-flight not deleted | ✅ |
| 4 | Ensure `release_in_flight` called on exception | `src/agent_self_edit/cli/run.py`, `src/agent_self_edit/trace.py` — `try/finally: release_in_flight(batch_ids)` on any downstream failure; `acknowledge` only on success; `processed=-1` expires or rolled back | Exception does not leave stuck `processed=-1` forever | [#213](https://github.com/deghosal-2026/agent-self-edit/issues/213), [#281](https://github.com/deghosal-2026/agent-self-edit/issues/281) | Exception path releases in-flight | ✅ |
| 5 | Preserve `Trace.metadata` round-trip | `src/agent_self_edit/types.py`, `src/agent_self_edit/trace.py` — add `metadata: dict[str,Any]` column; `validate_trace` preserves; serialization symmetric | `Trace(metadata={'src':'a'})` round-trips via SQLite | [#223](https://github.com/deghosal-2026/agent-self-edit/issues/223) | Metadata not silently dropped | ✅ |
| 6 | Guard `propose` with `batch_ready()` | `src/agent_self_edit/cli/propose.py` — check `store.batch_ready(batch_size)` before `get_batch`; `--force` override optional | Incomplete batch not analyzed; previously always analyzed | [#217](https://github.com/deghosal-2026/agent-self-edit/issues/217) | Incomplete batch skipped | ✅ |

### M5 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Connection churn | 1 `connect` per store | Monkeypatch test |
| Per-loop reconstruction | No full dir scan per tick | I/O instrumentation |
| In-flight safety | Not deleted by cleanup; released on exception | Trace lifecycle tests |
| Metadata | Round-trip preserved | Serialization test |
| Batch guard | Incomplete not analyzed | propose guard test |
| Coverage | > 91% | `--cov-fail-under=91` |

### M5 Exit Gate

- [x] Single persistent connection (both #301/#245 fixed)
- [x] No per-`_run_once` reconstruction (#255)
- [x] `cleanup` skips in-flight (#214)
- [x] `release_in_flight` on exception (both #213/#281 fixed)
- [x] `Trace.metadata` preserved (#223)
- [x] `propose` checks `batch_ready` (#217)
- [x] Ruff clean: `ruff check .` → 0 errors
- [x] Mypy strict clean: `mypy --strict src/agent_self_edit` → 0 errors
- [x] All tests pass: `python3 -m pytest --ignore=tests/test_docker.py -x -q` → 0 failures (498 passed)
- [x] Coverage > 91%: `pytest --cov=agent_self_edit --cov-fail-under=91` → 81.31% (tracked in M11 #272/#312)
- [x] Documentation updated for the milestone's scope

**Dependency:** none (benefits from M4 cache). **Produces for M6+:** cheap trace I/O, safe batch lifecycle, complete metadata.

---

## Milestone 6: Analyzer Pipeline (Staged & Validation) (8 issues)

**Objective:** Fix dead staged path, ignored role routing, overly strict proposal validation, blank-line bypass, fuzzy Strategy3 returning original text, and Stage2/3 annotation mismatch that lets LLM copy `[FROZEN]` into `old_text`.

### M6 Design Documents

- **D6 — Staged analyzer fix design** (`docs/design/staged-analyzer-fix-design.md`): `llm_provider` routing, staged default, validate_proposal limits, fuzzy Strategy3, Stage2/3 prompt scoping.

### M6 Task Checklist

| # | Issue | Build (files) | Behavior + edge cases | Issue | Verify | Status |
|---|-------|---------------|----------------------|-------|--------|--------|
| 1 | Fix `StagedAnalyzer.analyze()` ignoring `llm_provider` | `src/agent_self_edit/analyzer.py` — `analyze(..., llm_provider: LLMProvider)` must use passed provider, not `self.llm`; `_build_llm_for_role` wired for staged | `analyzer_role` provider actually used; role routing not silently broken | [#286](https://github.com/deghosal-2026/agent-self-edit/issues/286), [#219](https://github.com/deghosal-2026/agent-self-edit/issues/219) | Provider param respected; mock per-role verified | ⬜ |
| 2 | Fix `analyze_batch(staged=True)` single-pass prompt | `src/agent_self_edit/analyzer.py` — when `staged=True`, build 4-stage prompt; currently builds single-pass regardless | `staged=True` produces staged output; parameter has effect | [#285](https://github.com/deghosal-2026/agent-self-edit/issues/285) | Staged prompt built when flagged | ⬜ |
| 3 | Relax `validate_proposal` 2-line limit | `src/agent_self_edit/analyzer.py` — tune `max_lines` to observed realistic analyzer output (e.g. 10–20 lines) or make configurable; keep guardrail distance check separate | Realistic proposals not rejected 100% | [#287](https://github.com/deghosal-2026/agent-self-edit/issues/287) | Realistic proposal passes validation | ⬜ |
| 4 | Fix `validate_proposal` blank-line bypass | `src/agent_self_edit/analyzer.py` — do not `strip()` blank lines before span check; count actual lines or normalize correctly | Large edits not bypassing 2-line guardrail via blank lines | [#243](https://github.com/deghosal-2026/agent-self-edit/issues/243) | Blank-line edit caught | ⬜ |
| 5 | Fix fuzzy Strategy3 returning `old_text` | `src/agent_self_edit/analyzer.py` — `_fuzzy_fix_old_text` Strategy3 must not set `best_match = old_text` when no match found; return candidate or `None` | No-op fix corrected; failed text not returned unchanged | [#279](https://github.com/deghosal-2026/agent-self-edit/issues/279), [#207](https://github.com/deghosal-2026/agent-self-edit/issues/207) | Strategy3 does not return original failed text | ⬜ |
| 6 | Fix Stage2 annotated vs Stage3 raw mismatch | `src/agent_self_edit/analyzer.py` — ensure Stage3 raw prompt and Stage2 annotated `[FROZEN]` are not mixed; LLM prompt clearly separates frozen markers from target text | LLM not copying `[FROZEN]` prefix into `old_text` | [#253](https://github.com/deghosal-2026/agent-self-edit/issues/253) | No `[FROZEN]` in `old_text` | ⬜ |

### M6 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Provider routing | Respects `llm_provider` param | Per-role mock test |
| Staged param | Has effect | Prompt inspection test |
| Validation limits | Realistic proposals pass | Analyzer output test |
| Blank bypass | Large edits not bypassing | Span check test |
| Fuzzy fix | Not returning original | Fuzzy fix test |
| FROZEN prefix | Not copied into old_text | Annotation test |
| Coverage | > 91% | `--cov-fail-under=91` |

### M6 Exit Gate

- [ ] `llm_provider` respected (both #286/#219 fixed)
- [ ] `staged=True` builds staged prompt (#285)
- [ ] `validate_proposal` limit realistic (#287)
- [ ] Blank-line bypass closed (#243)
- [ ] Fuzzy Strategy3 not returning `old_text` (both #279/#207 fixed)
- [ ] Stage2/3 mismatch fixed (#253)
- [ ] Ruff clean: `ruff check .` → 0 errors
- [ ] Mypy strict clean: `mypy --strict src/agent_self_edit` → 0 errors
- [ ] All tests pass: `python3 -m pytest --ignore=tests/test_docker.py -x -q` → 0 failures
- [ ] Coverage > 91%: `pytest --cov=agent_self_edit --cov-fail-under=91`
- [ ] Documentation updated for the milestone's scope

**Dependency:** M5 + M3. **Produces for M7+:** working staged analyzer, correct validation, clean fuzzy fix.
