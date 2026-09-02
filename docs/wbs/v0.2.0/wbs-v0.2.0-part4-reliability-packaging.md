# WBS — AgentSelfEdit v0.2.0 Part 4: Operational Reliability & Packaging

> **Milestones covered:** M6 (Operational Reliability) · M7 (Packaging, CI, CLI Reliability)
> **Source:** v0.1.0 engineering backlog and field test findings
> **Dependency:** M6 and M7 are independent of each other; both can run in parallel with M4/M5
> **Issue Range:** #142–#171

---

## Milestone 6: Operational Reliability (#142, #143, #144, #146, #147)

**Objective:** Fix trace processing reliability bugs — acknowledge traces by row identity not task_id, make batch processing retry-safe, verify benchmark compatibility on validate, make init produce truly runnable state, and fix file adapter duplicate-filename skipping.

### M6 Design Documents

- **D6 — Trace reliability design** (`docs/design/trace-reliability-design.md`): row-identity ack semantics, retry-safe batching protocol, init state contract, benchmark validation contract.

### M6 Task Checklist

| # | Issue | Build (files) | Behavior + edge cases | Issue | Verify |
|---|-------|---------------|----------------------|-------|--------|
| 1 | Fix file adapter duplicate-filename skipping | `src/agent_self_edit/adapters/file.py`, adapter tests | Remove in-memory `_processed` filename cache; rely on rename-to-`.done` behavior alone; new file with same basename ingested correctly; malformed files do not permanently blacklist filename | [#142](https://github.com/deghosal-2026/agent-self-edit/issues/142) | Repeated filenames ingested correctly; malformed does not poison |
| 2 | Make init produce runnable initial state | `src/agent_self_edit/cli/init.py` | `init` must create initial prompt version when `--prompt` is provided; fail with clear error if required state is missing; no half-configured states | [#143](https://github.com/deghosal-2026/agent-self-edit/issues/143) | `init` always produces runnable state; clear error on incomplete config |
| 3 | Extend validate for benchmark compatibility | `src/agent_self_edit/cli/validate.py`, task-set schema | Validate that configured runtime can execute declared benchmark end-to-end: scorer compatibility, model role wiring, benchmark contract assumptions | [#144](https://github.com/deghosal-2026/agent-self-edit/issues/144) | Pass validates runnability; fail catches misconfiguration |
| 4 | Make batch processing retry-safe | `src/agent_self_edit/trace.py`, `src/agent_self_edit/cli/run.py`, `src/agent_self_edit/cli/propose.py` | Do not acknowledge traces after downstream processing failures; acknowledgement is a durable state transition tied to successful completion; failed batches retryable; transient failures do not erase traces | [#146](https://github.com/deghosal-2026/agent-self-edit/issues/146) | Failed processing does not ack; retries work correctly |
| 5 | Acknowledge traces by row identity | `src/agent_self_edit/trace.py` | Use SQLite row `id` (immutable row identity) for acknowledgement, not `task_id`; ensure one-row acknowledgment semantics; duplicate `task_id` values do not cause silent data loss | [#147](https://github.com/deghosal-2026/agent-self-edit/issues/147) | Ack targets single row; duplicate task_ids handled safely |

### M6 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| File adapter reliability | Repeated filenames ingested correctly over long-running processes | Adapter test suite |
| Init state | `init` always produces runnable state; clear errors on incomplete config | Init test suite |
| Validate completeness | Validates benchmark runnability, not just file parseability | Validate test suite |
| Retry safety | Failed processing never acks; retries work | Trace + integration tests |
| Row-identity ack | Ack by `id` not `task_id`; no silent data loss | Trace test suite |
| Coverage | > 92% | `--cov-fail-under=92` |

### M6 Exit Gate

- [ ] File adapter does not use in-memory filename cache; `.done` rename is sole dedup mechanism
- [ ] `init` produces truly runnable initial state
- [ ] `validate` checks benchmark compatibility end-to-end
- [ ] Batch processing is retry-safe — no ack after downstream failure
- [ ] Traces acknowledged by row identity, not `task_id`
- [ ] Ruff clean, mypy strict clean, all tests pass, coverage > 92%
- [ ] **Design docs authored:** D6 (trace-reliability-design)

**Dependency:** none (can run in parallel with M4/M5). **Produces for M8+:** reliable trace processing, safe retries, runnable init.

---

## Milestone 7: Packaging, CI & CLI Reliability (#148–#171)

**Objective:** Fix all packaging, CI, CLI reliability, and operational issues found in v0.1.0 engineering audit. Add CI/CD pipeline, lockfile, shared test fixtures, Dockerfile fixes, CLI exit-code standardization, diff/lineage/config bugs, and remaining test coverage gaps.

### M7 Task Checklist

| # | Issue | Build (files) | Behavior + edge cases | Issue | Verify |
|---|-------|---------------|----------------------|-------|--------|
| 1 | Fix `diff --config` ignoring flag | `src/agent_self_edit/cli/diff.py` | Replace hardcoded config path with `config_path` from `--config` flag | [#148](https://github.com/deghosal-2026/agent-self-edit/issues/148) | `diff --config` uses requested config path |
| 2 | Harden MockProvider against empty-list config | `src/agent_self_edit/llm/mock.py` | Reject empty list `responses` at construction with clear error, not `ZeroDivisionError` | [#149](https://github.com/deghosal-2026/agent-self-edit/issues/149) | Empty response list → explicit error |
| 3 | Standardize CLI fatal error handling | `src/agent_self_edit/cli/status.py`, `rollback.py`, `diff.py`, all CLI commands | Use `click.ClickException` or explicit non-zero exits for fatal failures; bad config path, invalid rollback target, invalid diff version, broken registry path all exit non-zero | [#150](https://github.com/deghosal-2026/agent-self-edit/issues/150) | All fatal errors exit non-zero |
| 4 | Separate fake-seeded Docker tests from real | `tests/test_docker.py` | Clearly separate hermetic/mechanical Docker smoke tests from realistic end-to-end behavioral tests | [#151](https://github.com/deghosal-2026/agent-self-edit/issues/151) | Test types clearly distinguished; artifact naming reflects mode |
| 5 | Stabilize lineage JSON output | `src/agent_self_edit/cli/lineage.py`, `src/agent_self_edit/registry.py` | Add stable serializer or `to_dict()` for `Meta`; JSON output schema is stable and versioned; changes to dataclass internals do not silently change output | [#152](https://github.com/deghosal-2026/agent-self-edit/issues/152) | JSON output shape is stable; output-shape tests |
| 6 | Update adapter tests for correct semantics | `tests/test_adapters.py` | Rewrite adapter tests to reflect desired retry and same-filename semantics; malformed file is retried after correction; does not permanently blacklist | [#153](https://github.com/deghosal-2026/agent-self-edit/issues/153) | Tests reflect desired semantics; bug-fixing not resisted |
| 7 | Remove or make git auto-commit hook bypass configurable | `src/agent_self_edit/registry.py` | Remove `--no-verify` by default, or make hook bypass opt-in via config | [#154](https://github.com/deghosal-2026/agent-self-edit/issues/154) | Repo hooks not silently bypassed |
| 8 | Persist real promotion cost metadata | `src/agent_self_edit/cli/status.py`, promotion paths, registry metadata | Define accounting model; persist cost metadata when prompt version created from proposal evaluation; status reads same accounting model | [#155](https://github.com/deghosal-2026/agent-self-edit/issues/155) | Promoted version persists cost; status reflects real cost |
| 9 | Tighten config validation for confidence_level | `src/agent_self_edit/config.py` | Raise minimum accepted confidence level (e.g., 0.9 or 0.95); require explicit unsafe/dev mode for weaker thresholds | [#156](https://github.com/deghosal-2026/agent-self-edit/issues/156) | `confidence_level=0.5` rejected; lower-bound tests |
| 10 | Make git-backed registry opt-in or repo-scoped | `src/agent_self_edit/registry.py` | Require explicit opt-in for git-backed mode in config; verify registry path belongs to intended project repo root | [#157](https://github.com/deghosal-2026/agent-self-edit/issues/157) | Auto-commits do not pollute unintended parent repos |
| 11 | Expand CLI integration coverage | `tests/test_cli.py` | Add integration tests for: `diff --config`, `lineage --format json` output shape, `guardrails --json`, non-zero exit behavior | [#158](https://github.com/deghosal-2026/agent-self-edit/issues/158) | Direct integration tests for config path, exit codes, output shape |
| 12 | Fix real-trace import schema incompatibility | `src/agent_self_edit/types.py`, `trace.py`, import scripts | Extend Trace schema to include `metadata: dict[str, Any]` or remove top-level `metadata` emission from corpus scripts | [#159](https://github.com/deghosal-2026/agent-self-edit/issues/159) | Trace round-trip preserves metadata or script output tests assert no unsupported fields |
| 13 | Fix non-deterministic task-id generation | `field-test/scripts/import_real_traces.py` | Derive deterministic ids from stable source keys; same input corpus produces identical output ids | [#160](https://github.com/deghosal-2026/agent-self-edit/issues/160) | Same input run twice → identical ids |
| 14 | Fix synthetic trace generation dead parameters | `field-test/scripts/generate_traces.py` | Either make `prompt`/`batch_size` meaningfully affect output or remove them | [#161](https://github.com/deghosal-2026/agent-self-edit/issues/161) | Parameters either affect output or are removed |
| 15 | Fix scaffold package test coverage | `tests/test_scaffold.py`, `src/agent_self_edit/__init__.py` | Decide whether `__version__` is part of package contract; test it properly or remove fake assertion | [#162](https://github.com/deghosal-2026/agent-self-edit/issues/162) | Package version properly tested or removed |
| 16 | Declare openai as optional dependency | `pyproject.toml`, `src/agent_self_edit/llm/openai.py` | Add `[project.optional-dependencies] llm = ["openai>=1.0"]`; update error message to reference correct install command | [#164](https://github.com/deghosal-2026/agent-self-edit/issues/164) | `pip install "agent-self-edit[llm]"` installs openai |
| 17 | Remove pytest-cov from default addopts | `pyproject.toml` | Remove `--cov` flags from `addopts`; use separate `pytest --cov` for coverage CI | [#165](https://github.com/deghosal-2026/agent-self-edit/issues/165) | `pytest` works without pytest-cov; coverage still available explicitly |
| 18 | Add CI/CD pipeline | `.github/workflows/ci.yml` | Add minimal CI: pytest on push/PR without LLM/Docker, ruff lint, mypy type check, coverage threshold enforcement, Docker build on tagged releases | [#166](https://github.com/deghosal-2026/agent-self-edit/issues/166) | Tests run automatically on push and PR |
| 19 | Remove unnecessary COPY from Dockerfile | `Dockerfile` | Remove `COPY docs/` and `COPY field-test/` lines; only include runtime-needed files | [#167](https://github.com/deghosal-2026/agent-self-edit/issues/167) | Docker image size reduced; no extraneous directories |
| 20 | Add .dockerignore | `.dockerignore` | Exclude `.git/`, `__pycache__/`, `*.pyc`, `.coverage`, `htmlcov/`, `venv/`, `.venv/`, `.env`, `field-test/results/` | [#168](https://github.com/deghosal-2026/agent-self-edit/issues/168) | Faster Docker builds; no dev artifacts in context |
| 21 | Move common test fixtures to conftest.py | `tests/conftest.py` | Identify and move common fixtures: `TraceStore`, `Registry`, `Config`, `MockProvider`, `ExactMatchScorer`, `TaskSet` | [#169](https://github.com/deghosal-2026/agent-self-edit/issues/169) | Test modules use shared fixtures; less boilerplate |
| 22 | Add lockfile for reproducible deps | `requirements.txt` or lockfile | Generate and commit pinned transitive dependencies | [#170](https://github.com/deghosal-2026/agent-self-edit/issues/170) | Reproducible dependency resolution guaranteed |
| 23 | Add CLI entry point smoke test | `tests/test_cli.py` | Add smoke test that calls CLI entry point as subprocess and verifies exit code 0 | [#171](https://github.com/deghosal-2026/agent-self-edit/issues/171) | `python -m agent_self_edit --help` returns 0 |

### M7 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Bug fixes | 23 issues resolved across packaging, CLI, config, Docker, tests | Issue-by-issue verification |
| CI/CD | Pipeline runs on push/PR; lint, type, test, coverage all pass | CI run |
| CLI reliability | All fatal errors exit non-zero; `--config` flag respected | CLI test suite |
| Coverage | > 92% | `--cov-fail-under=92` |

### M7 Exit Gate

- [ ] All 23 issues resolved with passing tests
- [ ] CI/CD pipeline operational on push/PR
- [ ] All fatal CLI errors exit non-zero
- [ ] `diff --config` works correctly
- [ ] openai declared as optional dependency
- [ ] pytest-cov removed from default addopts
- [ ] Dockerfile fixed (.dockerignore, no extra COPY)
- [ ] Common test fixtures in conftest.py
- [ ] Lockfile or pinned requirements committed
- [ ] Ruff clean, mypy strict clean, all tests pass, coverage > 92%

**Dependency:** none (can run in parallel with M4/M5/M6). **Produces for M8+:** CI/CD, fixed Docker, correct CLI, shared test fixtures.