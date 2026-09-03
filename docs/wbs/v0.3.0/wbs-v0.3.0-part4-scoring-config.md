# WBS — AgentSelfEdit v0.3.0 Part 4: Scoring & Config

> **Milestones covered:** M7 (Scoring & Task Correctness) · M8 (Config, Providers & Resilience)
> **Source:** Scorer denominator/double-count/verbose-parse audit + config interpolation/allowlist/resilience gaps (field-test: extraction and generation benchmarks mis-scored, model role providers unchecked)
> **Dependency:** M7 (depends on M6 analyzer) → M8 (can run parallel with M6/M7, needs scoring per task)
> **Issue Range:** #296, #225, #297, #295, #220, #242, #236, #224 (M7) + #293, #299, #239, #235, #231, #238, #228, #227 (M8) — [M7 milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/29) · [M8 milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/30)

---

## Milestone 7: Scoring & Task Correctness (8 issues)

**Objective:** Fix mis-scored benchmarks: ContainsScorer deflation, StructuredExtraction double-count, LLMJudge verbose failure, dimensions `0.0` silent, nondet scorer selection, empty task set acceptance, and fence-stripping corrupting JSON.

### M7 Design Documents

- **D7 — Scoring correctness design** (`docs/design/scoring-correctness-design.md`): denoms via `non_empty`, matched-key tracking, verbose float extraction, scorer determinism, empty-set guard, fence-preserving JSON extraction.

### M7 Task Checklist

| # | Issue | Build (files) | Behavior + edge cases | Issue | Verify | Status |
|---|-------|---------------|----------------------|-------|--------|--------|
| 1 | Fix `ContainsScorer` denom (blank lines) | `src/agent_self_edit/scorers.py` — `score = found / len(non_empty)` not `len(expected_lines)` | `foo\nbar\n` with trailing newline scores 1.0 not 0.67; blank lines not counted | [#296](https://github.com/deghosal-2026/agent-self-edit/issues/296), [#225](https://github.com/deghosal-2026/agent-self-edit/issues/225) | Trailing newline not deflating | ⬜ |
| 2 | Fix `StructuredExtractionScorer` double-count | `src/agent_self_edit/scorers.py` — track `matched_act_keys: set[str]`; same `act_key` not matched twice | `expected {city: London, location: London}` + `actual {city: London}` → score <1.0 not 1.0 | [#297](https://github.com/deghosal-2026/agent-self-edit/issues/297) | No double-count; 1.0 only if full | ⬜ |
| 3 | Fix `LLMJudgeScorer._parse_score` verbose | `src/agent_self_edit/scorers.py` — regex extract first float `\b(\d+\.\d+|\d+)\b`; handle `Score: 0.9`, `I would rate 0.8` | `0.8` extracted not `ValueError→0.0`; correct answer not scored 0 | [#295](https://github.com/deghosal-2026/agent-self-edit/issues/295) | Verbose response parses to 0.8/0.9 | ⬜ |
| 4 | Fix `LLMJudgeScorer` dimensions `OVERALL:` parse | `src/agent_self_edit/scorers.py` — on malformed `OVERALL:` line return `0.0` is silent; must raise or log; parse `OVERALL: 0.9` robustly | Malformed line not silently 0.0; dimension scoring visible | [#220](https://github.com/deghosal-2026/agent-self-edit/issues/220) | Malformed OVERALL not silent | ⬜ |
| 5 | Fix `resolve_scorer` nondet set pick | `src/agent_self_edit/scorers.py` — deterministic priority: manifest `scorer` > per-task hints must match; if conflict, fail fast or define precedence (`exact` > `contains` > `llmjudge`) | Multiple hints conflicting → deterministic, not `set` random | [#242](https://github.com/deghosal-2026/agent-self-edit/issues/242) | Deterministic scorer selection | ⬜ |
| 6 | Reject empty task list at `load_task_set` | `src/agent_self_edit/tasks.py` — `load_task_set` raises if `tasks==[]` | Empty YAML not accepted; error at load time | [#236](https://github.com/deghosal-2026/agent-self-edit/issues/236) | Empty list raises | ⬜ |
| 7 | Fix `_extract_json` fence stripping | `src/agent_self_edit/analyzer.py` — preserve backtick-fenced JSON containing code blocks; strip only outer fences, not inner lines starting with `` ``` `` | JSON with code block proposal not corrupted | [#224](https://github.com/deghosal-2026/agent-self-edit/issues/224) | Fence-contained JSON preserved | ⬜ |

### M7 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| ContainsScorer | `non_empty` denom | Blank-line fixtures |
| Extraction double-count | Track matched keys | Double-count fixtures |
| LLMJudge parse | Regex float extraction | Verbose response tests |
| Dimensions | Not silent 0.0 | Malformed OVERALL test |
| Scorer determinism | Manifest priority | Conflict test |
| Empty guard | Raises on empty | Empty task set test |
| Fence preserving | JSON with code not corrupted | Fence test |
| Coverage | > 91% | `--cov-fail-under=91` |

### M7 Exit Gate

- [ ] `ContainsScorer` uses `len(non_empty)` (both #296/#225 fixed)
- [ ] Extraction tracks `matched_act_keys` (#297)
- [ ] `_parse_score` regex extracts first float (#295)
- [ ] Dimensions `OVERALL:` not silent (#220)
- [ ] `resolve_scorer` deterministic (#242)
- [ ] Empty task list rejected (#236)
- [ ] `_extract_json` preserves fences (#224)
- [ ] Ruff clean: `ruff check .` → 0 errors
- [ ] Mypy strict clean: `mypy --strict src/agent_self_edit` → 0 errors
- [ ] All tests pass: `python3 -m pytest --ignore=tests/test_docker.py -x -q` → 0 failures
- [ ] Coverage > 91%: `pytest --cov=agent_self_edit --cov-fail-under=91`
- [ ] Documentation updated for the milestone's scope

**Dependency:** M6. **Produces for M8+:** correct scoring, deterministic scorer, safe JSON extraction.

---

## Milestone 8: Config, Providers & Resilience (8 issues)

**Objective:** Fix partial env interpolation, role provider allowlist gap, hardcoded roadmap block, missing config schema knobs, swallowed LLM errors, ignored trigger modes, and enable model-vs-model A/B with resilient retries.

### M8 Design Documents

- **D8 — Config & provider design** (`docs/design/config-provider-design.md`): partial `${VAR}` via `re.sub`, per-role provider validation, `task_timeout_seconds` etc, `extra_body`, backoff, trigger modes, `llm_b`.

### M8 Task Checklist

| # | Issue | Build (files) | Behavior + edge cases | Issue | Verify | Status |
|---|-------|---------------|----------------------|-------|--------|--------|
| 1 | Fix `_interpolate_env` partial | `src/agent_self_edit/config.py` — use `re.sub(r"\$\{(\w+)\}", replacer, value)` expanding all occurrences; raise if env var missing | `Bearer ${MY_KEY}` → `Bearer abc123`; `http://${HOST}:8000/v1` expanded | [#293](https://github.com/deghosal-2026/agent-self-edit/issues/293) | Partial interpolation expanded | ⬜ |
| 2 | Validate model role providers | `src/agent_self_edit/config.py` — loop `executor_role, analyzer_role, judge_role` per-role `provider in ('openai','mock')`; report `which role` in error | Typo `opneai` in `analyzer_role` fails validation not runtime `ProviderError` | [#299](https://github.com/deghosal-2026/agent-self-edit/issues/299) | Bad role provider caught at validation | ⬜ |
| 3 | Remove hardcoded allowlist block on roadmap extensions | `src/agent_self_edit/config.py` — allow provider extensions (e.g. `anthropic`, `azure`) if supported or via `extra_body`; not hard error | Roadmap provider not blocked | [#239](https://github.com/deghosal-2026/agent-self-edit/issues/239) | Roadmap provider accepted | ⬜ |
| 4 | Add `task_timeout_seconds`, `trigger_interval_hours`, `cache_enabled` | `src/agent_self_edit/config.py`, `pyproject.toml`, docs | Config schema includes all three; defaults documented; validation | [#235](https://github.com/deghosal-2026/agent-self-edit/issues/235) | Schema accepts new knobs | ⬜ |
| 5 | Add exponential backoff for rate-limit in `run_task` | `src/agent_self_edit/ab_test.py` — retry on 429 with `backoff_factor * 2**attempt`; jitter; max retries | Rate-limit does not fail A/B suite; retries with backoff | [#231](https://github.com/deghosal-2026/agent-self-edit/issues/231) | Rate-limit retry with backoff | ⬜ |
| 6 | Surface staged analyzer failure reason | `src/agent_self_edit/analyzer.py` — propagate LLM error text, not vague generic string | `failure_reason` contains provider error, not `unknown` | [#238](https://github.com/deghosal-2026/agent-self-edit/issues/238) | LLM error visible to caller | ⬜ |
| 7 | Implement trigger modes (time/manual ignored) | `src/agent_self_edit/config.py`, `src/agent_self_edit/cli/run.py` — honor `trigger: batch|time|manual`; time interval and manual flag | `trigger: time` runs every N hours; manual requires flag | [#228](https://github.com/deghosal-2026/agent-self-edit/issues/228) | Time/manual triggers handled | ⬜ |
| 8 | Support model-vs-model A/B (`llm_b`) | `src/agent_self_edit/ab_test.py` — `run_ab_test(..., llm_b: LLMProvider \| None)` compare two models on same prompt | Model comparison enabled, not just prompt-vs-prompt | [#227](https://github.com/deghosal-2026/agent-self-edit/issues/227) | `llm_b` param compares models | ⬜ |

### M8 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Partial interpolation | `Bearer ${V}` expanded | Env interpolation tests |
| Role validation | Per-role error at validation | Bad role provider test |
| Roadmap not blocked | Extension not hard error | Provider extension test |
| New knobs | Schema accepts 3 new | Config schema test |
| Backoff | 429 retried with backoff | Rate-limit test |
| Failure surface | LLM error visible | Analyzer error test |
| Triggers | batch/time/manual honored | Trigger mode tests |
| Model-vs-model | `llm_b` works | A/B `llm_b` test |
| Coverage | > 91% | `--cov-fail-under=91` |

### M8 Exit Gate

- [ ] Partial `${VAR}` via `re.sub` (#293)
- [ ] Per-role provider validation (#299)
- [ ] Allowlist not blocking roadmap (#239)
- [ ] `task_timeout_seconds`, `trigger_interval_hours`, `cache_enabled` added (#235)
- [ ] Exponential backoff in `run_task` (#231)
- [ ] Failure reason surfaces LLM error (#238)
- [ ] Trigger modes implemented (#228)
- [ ] `llm_b` model-vs-model A/B (#227)
- [ ] Ruff clean: `ruff check .` → 0 errors
- [ ] Mypy strict clean: `mypy --strict src/agent_self_edit` → 0 errors
- [ ] All tests pass: `python3 -m pytest --ignore=tests/test_docker.py -x -q` → 0 failures
- [ ] Coverage > 91%: `pytest --cov=agent_self_edit --cov-fail-under=91`
- [ ] Documentation updated for the milestone's scope

**Dependency:** M6/M7 parallel. **Produces for M9+:** correct config, resilient runners, model-vs-model capability.
