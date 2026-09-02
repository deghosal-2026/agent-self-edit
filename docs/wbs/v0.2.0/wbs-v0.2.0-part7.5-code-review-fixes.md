# WBS — AgentSelfEdit v0.2.0 Part 7.5: Code Review Fixes

> **Milestone covered:** M7.5 (Code Review Fixes)
> **Source:** Code review audit of all M1–M7 implementations
> **Dependency:** M7.5 depends on M1–M7 and is a pre-flight gate before M8 (Field Test) and M9 (Release)
> **Issue Range:** TBD — create via GitHub issues under milestone `v0.2.0-M7.5`

---

## Milestone 7.5: Code Review Fixes

**Objective:** Fix the highest-priority issues found during the pre-M8 code audit. These are correctness, reliability, and evaluation-accuracy gaps that were only partially addressed by M1–M7. Shipping M8 and M9 without fixing these would weaken the evidence and risk claims.

---

### M7.5 Task Checklist

#### Trace Reliability

| # | Issue | Build (files) | Behavior + edge cases | Acceptance |
|---|-------|---------------|----------------------|------------|
| 1 | Migrate runtime trace acknowledgement to row-safe + retry-safe processing | `src/agent_self_edit/trace.py`, `src/agent_self_edit/cli/run.py`, `src/agent_self_edit/cli/propose.py`, `field-test/scripts/run_improvement_loop.py` | `acknowledge_batch()` used everywhere; no ack after downstream failure; in-flight reservation prevents concurrent duplicate fetch; duplicate `task_id`s in pending queue do not cause silent data loss | All runtime paths acknowledge by immutable row identity; processing failure does not advance backlog; concurrent workers cannot fetch same rows |
| 2 | Add in-flight reservation state for trace processing | `src/agent_self_edit/trace.py` | `get_batch()` atomically reserves rows with `processed = -1` (in-flight); stuck reservations expire after timeout; `acknowledge` sets `processed = 1`; rollback sets `processed = 0` | Concurrent workers cannot fetch same pending rows; stuck reservations are recoverable |

#### Gate & Drift Correctness

| # | Issue | Build (files) | Behavior + edge cases | Acceptance |
|---|-------|---------------|----------------------|------------|
| 3 | Eliminate duplicate gate execution | `src/agent_self_edit/cli/run.py`, `src/agent_self_edit/cli/propose.py`, `src/agent_self_edit/gate.py` | `PromotionGate.check()` accepts an existing `GateResult` for logging; `check_all()` called exactly once per proposal; logged result always matches displayed result | `check_all()` called once per proposal; no duplicate computation |
| 4 | Fix drift baseline to use original prompt, not current prompt | `src/agent_self_edit/cli/run.py`, `src/agent_self_edit/cli/propose.py`, `field-test/scripts/run_improvement_loop.py` | Drift is measured against the first prompt version or a configured baseline, not the current prompt; `original_prompt` is persisted or derived from registry lineage | Drift values reflect cumulative divergence from a stable baseline |

#### Model Role Wiring

| # | Issue | Build (files) | Behavior + edge cases | Acceptance |
|---|-------|---------------|----------------------|------------|
| 5 | Route analyzer calls through `analyzer_role` config | `src/agent_self_edit/cli/run.py`, `src/agent_self_edit/cli/propose.py` | `_build_llm_for_role(config, config.analyzer_role)` used for analyzer calls; separate from executor provider | Analyzer uses its own model/provider when configured |
| 6 | Route task execution through `executor_role` config | `src/agent_self_edit/cli/run.py`, `src/agent_self_edit/cli/propose.py` | Task execution (A/B test) uses `executor_role`; separate from analyzer provider | Executor uses its own model/provider when configured |
| 7 | Route LLM judging through `judge_role` config | `src/agent_self_edit/scorers.py`, `src/agent_self_edit/cli/run.py`, `src/agent_self_edit/cli/propose.py` | `resolve_scorer()` uses `judge_role` for `LLMJudgeScorer`; fallback to analyzer or default provider | Judge uses its own model/provider when configured |
| 8 | Add `extra_body` to `ModelRoleConfig` | `src/agent_self_edit/config.py` | Per-role `extra_body` field; defaults to `None`; merged with `LLMConfig.extra_body` at provider construction | Each role can have distinct backend-specific request extensions |

#### Scorer & Evaluation Accuracy

| # | Issue | Build (files) | Behavior + edge cases | Acceptance |
|---|-------|---------------|----------------------|------------|
| 9 | Enforce scorer consistency across task sets | `src/agent_self_edit/scorers.py` | `resolve_scorer()` prefers manifest-level scorer; validates all per-task scorer hints match; fails fast on mixed scorer sets unless explicitly supported | Mixed scorer sets fail fast; manifest-level scorer takes precedence |
| 10 | Wire corpus manifests into field-test runner | `field-test/scripts/run_improvement_loop.py` | Suite selection driven by manifest/benchmark-role; no hardcoded A/B task IDs; held-out set loaded from corpus file | Runner loads suites from manifests; no hardcoded task IDs |
| 11 | Wire `LLMJudgeScorer` rubrics/anchors/dimensions from corpus manifests | `src/agent_self_edit/scorers.py`, corpus loading paths | `judge_rubric`, anchors, dimensions loaded from manifest metadata; verified in field-test artifact output | Generation benchmarks have populated rubrics at runtime |
| 12 | Deepen `StructuredExtractionScorer` for nested fields, nulls, precedence | `src/agent_self_edit/scorers.py` | Support nested structures, null handling, conflicting-source precedence, stronger equivalence normalization; normalization profiles per benchmark | Extraction benchmarks handle full range of claimed capabilities |

#### Staged Analyzer & Rejection Context

| # | Issue | Build (files) | Behavior + edge cases | Acceptance |
|---|-------|---------------|----------------------|------------|
| 13 | Make staged analyzer the default and wire rejection context | `src/agent_self_edit/analyzer.py`, `src/agent_self_edit/cli/run.py`, `src/agent_self_edit/cli/propose.py` | `analyze_batch(..., staged=True)` default; `rejection_context` built from A/B + gate results and fed into subsequent calls; structured error artifacts on failure | Staged analyzer active by default; rejection summaries prevent repeated proposals |
| 14 | Preserve explicit failure signal in analyzer results | `src/agent_self_edit/analyzer.py` | `AnalysisResult` includes `failure_reason` field; staged analyzer failures produce structured error state instead of silent empty list | Analyzer failures are distinguishable from 'no proposals found' |

#### CLI & Validation Hardening

| # | Issue | Build (files) | Behavior + edge cases | Acceptance |
|---|-------|---------------|----------------------|------------|
| 15 | Make `init` write a real runnable config file | `src/agent_self_edit/cli/init.py` | Write a starter config to disk when none exists; fail non-zero if required bootstrap inputs are missing | `init` always produces a persisted runnable config |
| 16 | Extend `validate` for benchmark compatibility | `src/agent_self_edit/cli/validate.py` | Check judge provider present for judge benchmarks; structured scorer selected for structured extraction sets; role-specific runtime dependencies configured | Validation proves end-to-end runnability, not just file parseability |
| 17 | Tighten CLI exit code tests | `tests/test_cli.py` | Replace permissive `(0, 1, 2)` assertions with exact exit semantics; assert non-zero for fatal errors; assert specific error messages | All fatal CLI errors produce deterministic non-zero exit codes |
| 18 | Define and persist clear status metrics | `src/agent_self_edit/cli/status.py`, `src/agent_self_edit/registry.py` | `total_edits` excludes seed and rollback copies; `edit_id` is a proper identifier; guardrail pass rate has clear semantics; cost provenance is consistent | Status metrics have explicit contracts; source data is persisted |

#### Data Model Fixes

| # | Issue | Build (files) | Behavior + edge cases | Acceptance |
|---|-------|---------------|----------------------|------------|
| 19 | Complete `Trace.metadata` support | `src/agent_self_edit/types.py`, `src/agent_self_edit/trace.py` | `validate_trace()` parses and preserves `metadata`; persisted through SQLite; serialization and deserialization are symmetric | Trace round-trip preserves metadata |
| 20 | Fix `Trace.get(task_id)` ambiguity | `src/agent_self_edit/trace.py` | Document semantics or replace with row-id based retrieval; or return all matching rows | `get()` either returns all matches or raises on ambiguity |

#### Packaging & Release Integrity

| # | Issue | Build (files) | Behavior + edge cases | Acceptance |
|---|-------|---------------|----------------------|------------|
| 21 | Generate real pinned lockfile | `requirements.txt` or `pyproject.toml` + lock tool | Use `pip-tools`, `uv`, or `poetry` to generate pinned transitive dependencies | Reproducible dependency resolution is guaranteed |
| 22 | Align CI coverage threshold with release bar | `.github/workflows/ci.yml` | Change `--cov-fail-under=85` to `--cov-fail-under=92` | CI policy matches documented milestone exit gate |
| 23 | Extend CI lint scope to whole repo | `.github/workflows/ci.yml` | Run `ruff check .` instead of `ruff check src/` | Lint cleanliness enforced consistently across all source and test files |
| 24 | Fix Docker install path to use package extra | `Dockerfile` | Install openai via `agent-self-edit[llm]` instead of `'openai>=1.0'` directly | Docker dependency policy stays synchronized with pyproject.toml |

#### Test Quality

| # | Issue | Build (files) | Behavior + edge cases | Acceptance |
|---|-------|---------------|----------------------|------------|
| 25 | Strengthen field-test failure-mode assertions | `tests/test_field_test.py` | Assert exact failing checks and decision types; do not force early rejection for unrelated reasons; prove the right check blocks the right edit | Field-test tests prove the intended safety property, not just non-promotion |
| 26 | Migrate CLI tests off global `os.chdir()` | `tests/test_cli.py` | Use `click.testing.CliRunner` with `chdir` or `tmp_path` per-invocation; no global CWD side effects | No order-dependent test behavior from CWD |
| 27 | Complete fixture deduplication | `tests/conftest.py`, all test modules | Move remaining common fixtures to `conftest.py`; remove local duplicate helpers | Adding new tests requires minimal boilerplate |

#### Versioning & Evidence Integrity

| # | Issue | Build (files) | Behavior + edge cases | Acceptance |
|---|-------|---------------|----------------------|------------|
| 28 | Migrate v0.2.0 field-test assets to `field-test/v0.2.0/` | `field-test/` | Create `field-test/v0.2.0/` paths; copy or migrate v0.2.0 corpora, scripts, and results; leave v0.1.0 assets untouched | v0.2.0 field-test evidence lives under versioned paths; v0.1.0 is preserved unchanged |

---

### M7.5 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Trace reliability | All runtime paths use row-safe ack; in-flight reservation active | Integration tests with duplicate task_ids |
| Gate correctness | `check_all()` called once per proposal; drift measured from baseline | Manual + test verification |
| Model role wiring | Executor, analyzer, and judge each use separate provider when configured | Integration tests |
| Scorer consistency | Mixed scorer sets fail fast; manifest-level scorer respected | Scorer selection tests |
| Staged analyzer | Staged mode is default; rejection context populated; failure signal preserved | Analyzer output tests |
| CLI hardening | `init` writes config; `validate` checks runnability; exit codes are deterministic | CLI test suite |
| Field-test assertions | Tests prove exact safety properties, not just non-promotion | Field-test test suite |
| CI alignment | Coverage threshold at 92%; lint covers whole repo | CI run |
| Evidence integrity | v0.2.0 assets under `v0.2.0/` paths; v0.1.0 preserved | Manual review |
| Coverage | > 92% | `--cov-fail-under=92` |

### M7.5 Exit Gate

- [ ] All 28 tasks pass with documented acceptance criteria
- [ ] Ruff clean, mypy strict clean, all tests pass, coverage > 92%
- [ ] CI coverage threshold at 92%
- [ ] CI lint covers whole repo
- [ ] v0.2.0 field-test assets under `v0.2.0/` paths
- [ ] WBS index updated with M7.5 status

**Dependency:** M1–M7. **Produces for M8+:** reliable trace processing, correct gate behavior, wired model roles, strengthened evaluation, hardened CLI, clean evidence paths.