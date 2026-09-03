# WBS — AgentSelfEdit v0.3.0 Part 2: Guardrail & Registry Integrity

> **Milestones covered:** M3 (Drift, Frozen & Guardrail Safety) · M4 (Prompt Registry & Integrity)
> **Source:** Guardrail parser + drift metric audit (TF-IDF missing log, _MALFORMED_RE, _FROZEN_RE) + registry integrity audit (Meta serialization, git, disk cache)
> **Dependency:** M3 (depends on M2 gate ordering) → M4 (independent but registry must be correct before M5 traces read prompt)
> **Issue Range:** #283, #250, #276, #206, #284, #209, #256, #252 (M3) + #292, #241, #291, #215, #222, #237, #254, #290 (M4) — [M3 milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/25) · [M4 milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/26)

---

## Milestone 3: Drift, Frozen & Guardrail Safety (8 issues)

**Objective:** Fix miscalibrated drift metric, always-passing drift gate, and guardrail parser crashes on any HTML comment. Guardrails currently either mis-score or crash, making promotion unsafe.

### M3 Design Documents

- **D3 — Guardrail safety design** (`docs/design/guardrail-safety-design.md`): TF-IDF log fix, drift baseline vs original, frozen section parsing, HTML comment handling.

### M3 Task Checklist

| # | Issue | Build (files) | Behavior + edge cases | Issue | Verify | Status |
|---|-------|---------------|----------------------|-------|--------|--------|
| 1 | Fix TF-IDF IDF missing `math.log` | `src/agent_self_edit/guardrails.py` — `idf = math.log(N / df)` not `N/df`; drift = `1 - cosine(TFIDF)` in [0,1] | Tiny edit drift ~0.05; rewrite drift ~0.7; previously miscalibrated low | [#283](https://github.com/deghosal-2026/agent-self-edit/issues/283), [#250](https://github.com/deghosal-2026/agent-self-edit/issues/250) | Drift scores calibrated; `log` present | ⬜ |
| 2 | Fix drift gate self-baseline | `src/agent_self_edit/cli/run.py`, `propose.py`, `src/agent_self_edit/gate.py`, `src/agent_self_edit/registry.py` — pass `original_prompt` (first version) not `current_prompt`; persist baseline or derive from lineage | Drift measured cumulative from baseline, not self; threshold 0.30 triggers | [#276](https://github.com/deghosal-2026/agent-self-edit/issues/276), [#206](https://github.com/deghosal-2026/agent-self-edit/issues/206) | Drift not always 0; exceeds threshold on divergence | ⬜ |
| 3 | Fix `_MALFORMED_RE` matching all HTML comments | `src/agent_self_edit/guardrails.py` — narrow `_MALFORMED_RE` to only flag malformed frozen annotations, not any `<!--.*?-->`; test `<!-- comment -->` passes, `<!-- frozen -->` without closure fails | Any HTML comment no longer raises `GuardrailError` | [#284](https://github.com/deghosal-2026/agent-self-edit/issues/284), [#209](https://github.com/deghosal-2026/agent-self-edit/issues/209) | `<!-- note -->` does not crash parser | ⬜ |
| 4 | Fix `_FROZEN_RE` `re.DOTALL` | `src/agent_self_edit/guardrails.py` — remove `re.DOTALL` from `_FROZEN_RE` or scope `parse_frozen_sections` to line-level; whole-prompt string does not greedy-match | `parse_frozen_sections` on full prompt not unsafe; frozen line ranges correct | [#256](https://github.com/deghosal-2026/agent-self-edit/issues/256) | FROZEN regex not DOTALL-sensitive | ⬜ |
| 5 | Pass `frozen_sections` config to `check_all` | `src/agent_self_edit/gate.py` — `check_all(..., frozen_sections=config.guardrails.frozen_sections)` → `check_frozen_sections` | Configured frozen sections enforced, not ignored | [#252](https://github.com/deghosal-2026/agent-self-edit/issues/252) | Configured frozen edit rejected | ⬜ |

### M3 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Drift calibration | `log` IDF, correct range | Unit drift tests |
| Drift baseline | Original vs self | Gate drift tests |
| HTML comment | No crash on `<!-- x -->` | Guardrail parser tests |
| Frozen handling | No DOTALL greedy, config passed | Guardrail tests |
| Coverage | > 91% | `--cov-fail-under=91` |

### M3 Exit Gate

- [ ] TF-IDF uses `math.log(N/df)` (both #283/#250 fixed)
- [ ] Drift measured from `original_prompt` not `current_prompt` (both #276/#206 fixed)
- [ ] `_MALFORMED_RE` narrowed (both #284/#209 fixed)
- [ ] `_FROZEN_RE` not `DOTALL`
- [ ] `frozen_sections` config passed to `check_all`
- [ ] Ruff clean: `ruff check .` → 0 errors
- [ ] Mypy strict clean: `mypy --strict src/agent_self_edit` → 0 errors
- [ ] All tests pass: `python3 -m pytest --ignore=tests/test_docker.py -x -q` → 0 failures
- [ ] Coverage > 91%: `pytest --cov=agent_self_edit --cov-fail-under=91`
- [ ] Documentation updated for the milestone's scope

**Dependency:** M2. **Produces for M4+:** calibrated drift, safe frozen checks, correct parser.

---

## Milestone 4: Prompt Registry & Integrity (8 issues)

**Objective:** Fix incomplete `Meta.to_dict()`, forward-compat crash on future fields, two-phase write corruption window, silent git failures, and `current_prompt` disk churn (12+ reads per proposal loop).

### M4 Design Documents

- **D4 — Registry integrity design** (`docs/design/registry-integrity-design.md`): `Meta.to_dict` completeness via `dataclasses.fields`, forward-compat filter, atomic write + git, prompt caching, two-phase safety.

### M4 Task Checklist

| # | Issue | Build (files) | Behavior + edge cases | Issue | Verify | Status |
|---|-------|---------------|----------------------|-------|--------|--------|
| 1 | Fix `Meta.to_dict()` omits audit fields | `src/agent_self_edit/registry.py` — `def to_dict(self): return {f.name: getattr(self,f.name) for f in dataclasses.fields(self)}` | `trigger_trace_ids`, `model_version`, `diff_from_previous`, `rollback_*` included | [#292](https://github.com/deghosal-2026/agent-self-edit/issues/292), [#241](https://github.com/deghosal-2026/agent-self-edit/issues/241) | `to_dict` includes all fields; API/CLI not silently omitting | ⬜ |
| 2 | Add forward-compat filter for `Meta(**meta_data)` | `src/agent_self_edit/registry.py` — filter `meta_data` to known fields before constructing `Meta`; ignore unknown future fields | Newer registry readable by older code; no `TypeError: unexpected keyword` | [#291](https://github.com/deghosal-2026/agent-self-edit/issues/291), [#215](https://github.com/deghosal-2026/agent-self-edit/issues/215) | Unknown field tolerated | ⬜ |
| 3 | Fix `registry.create()` two-phase corruption window | `src/agent_self_edit/registry.py` — atomic write: temp file + rename; git SHA written after temp sync; crash leaves no partial `.md`/`.meta.json` | Kill mid-write → no corrupt version; SHA not lost | [#222](https://github.com/deghosal-2026/agent-self-edit/issues/222) | Atomic write test; corruption window closed | ⬜ |
| 4 | Fix `_git_commit()` swallowing failures | `src/agent_self_edit/registry.py` — surface git errors; log or raise; do not silently claim git-backed when commits lost | Git failure visible; registry not claimed git-backed when not | [#237](https://github.com/deghosal-2026/agent-self-edit/issues/237) | Git failure not swallowed | ⬜ |
| 5 | Cache `current_prompt` (fix 12+ reads) | `src/agent_self_edit/registry.py` — cache `current_prompt` with invalidation on `create`/`rollback`; avoid per-proposal disk reads | `get_batch` → `acknowledge` → proposal loop: 1 read not 12+; full dir scan avoided | [#254](https://github.com/deghosal-2026/agent-self-edit/issues/254), [#290](https://github.com/deghosal-2026/agent-self-edit/issues/290) | `current_prompt` cached; file reads measured | ⬜ |

### M4 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| `Meta.to_dict` | All fields via `dataclasses.fields` | Dict completeness test |
| Forward-compat | Unknown fields ignored | Future-field test |
| Atomic write | Temp + rename, no corruption | Kill test |
| Git errors | Not swallowed | Error visibility test |
| Prompt cache | 1 read per loop, not 12+ | I/O count test |
| Coverage | > 91% | `--cov-fail-under=91` |

### M4 Exit Gate

- [ ] `Meta.to_dict()` uses `dataclasses.fields` (both #292/#241 fixed)
- [ ] Forward-compat filter tolerates future fields (both #291/#215 fixed)
- [ ] `create()` atomic (temp+rename), SHA not lost on kill
- [ ] `_git_commit` surfaces failures
- [ ] `current_prompt` cached (both #254/#290 fixed)
- [ ] Ruff clean: `ruff check .` → 0 errors
- [ ] Mypy strict clean: `mypy --strict src/agent_self_edit` → 0 errors
- [ ] All tests pass: `python3 -m pytest --ignore=tests/test_docker.py -x -q` → 0 failures
- [ ] Coverage > 91%: `pytest --cov=agent_self_edit --cov-fail-under=91`
- [ ] Documentation updated for the milestone's scope

**Dependency:** M3. **Produces for M5+:** correct lineage, atomic registry, cached prompt reads.
