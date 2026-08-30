# WBS — AgentSelfEdit v0.1.0 Part 1: Foundation

> Part of the v0.1.0 release. See [index](wbs-v0.1.0-index.md) for milestone overview.
>
> **Milestones:** M1 (Scaffold + Config) · M2 (Execution Trace Ingestion)
> **Dependency:** M1 → M2
> **Issue Range:** #1–#13

## M1 — Scaffold + Config (#1–#7)

**Goal:** Repo structure, package, CI, config system, held-out task set management.

### Design

| Task | Description | Deliverable |
|---|---|---|
| D1 | Design config schema | `docs/design/config-schema-design.md` — config file format, all fields, validation rules, schema versioning, migration strategy |
| D1.1 | Design held-out task set format | Documented in the same config-schema doc — task set YAML/JSON schema, scorer reference format, validation rules |

### Build

| Task | Description | Deliverable |
|---|---|---|
| M1.1 | Package scaffold | `pyproject.toml` with dependencies (Click, PyYAML, SQLite3, numpy, scipy, sentence-transformers, pytest, pytest-cov, ruff, mypy). `src/agent_self_edit/__init__.py`, `tests/__init__.py` |
| M1.2 | Config file format | `src/agent_self_edit/config.py` — `Config` dataclass, `load_config(path) -> Config`, `validate_config(config) -> list[str]` |
| M1.3 | Config validation | Field-level validation rules: max_edit_distance > 0, drift_threshold in [0,1], confidence_level in [0.5, 0.999], sample_floor >= 10, trigger in {batch, time, manual}. Custom `ConfigError` exception. |
| M1.4 | Held-out task set loader | `src/agent_self_edit/tasks.py` — `TaskSet` class, `load_task_set(path) -> TaskSet`, `validate_task_set(task_set) -> list[str]` |
| M1.5 | Task set management API | Methods on `TaskSet`: `add_task()`, `remove_task()`, `list_tasks()`, `validate_set()`. Thread-safe with read-write lock. |
| M1.6 | CI pipeline | `.github/workflows/ci.yml` (ruff, mypy strict, pytest, coverage >92%), `.github/dependabot.yml`, `.github/PULL_REQUEST_TEMPLATE.md` |
| M1.7 | OSS community files | CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md, SUPPORT.md, issue templates (bug report, feature request) |

### Tests

| Task | Description | Files |
|---|---|---|
| T1.1 | Test config loading | `tests/test_config.py` — valid config, invalid config, missing fields, wrong types, boundary values for all numeric fields |
| T1.2 | Test config validation | `tests/test_config.py` — each validation rule tested independently, error messages verified |
| T1.3 | Test task set loading | `tests/test_tasks.py` — valid task set, invalid tasks, duplicate IDs, missing fields, YAML and JSON formats |
| T1.4 | Test task set management | `tests/test_tasks.py` — add, remove, list, validate, concurrent access, thread safety |
| T1.5 | Test CI pipeline runs | Manual verification — CI passes on push, lint clean, coverage > 92% |

### Documentation

| Task | Description | Deliverable |
|---|---|---|
| M1.DOC1 | Update design README | Update `docs/design/README.md` with M1 scope, config schema link, task set format link |
| M1.DOC2 | Update WBS index | Update `docs/wbs/v0.1.0/wbs-v0.1.0-index.md` with M1 status, issue links, exit gate results |
| M1.DOC3 | Config reference | Create `docs/reference/config.md` — full config file reference with all fields, defaults, examples for each field |

### M1 Exit Gate

- [ ] Design docs reviewed and committed
- [ ] `pip install -e .` succeeds
- [ ] Config loads and validates correctly
- [ ] Task set loads and validates correctly
- [ ] All 6 community files exist
- [ ] Ruff clean: `ruff check .` → 0 errors
- [ ] Mypy strict clean: `mypy --strict` → 0 errors
- [ ] All tests pass: `pytest` → 0 failures
- [ ] Coverage > 92%: `pytest --cov=agent_self_edit --cov-fail-under=92`
- [ ] CI pipeline is green on push

---

## M2 — Execution Trace Ingestion (#8–#13)

**Goal:** Accept execution traces from the agent, store them, batch them for analysis.

### Design

| Task | Description | Deliverable |
|---|---|---|
| D2 | Design trace schema | `docs/design/trace-schema-design.md` — trace JSON schema, all fields, validation rules, SQLite store schema, indexes, adapter interface design, cleanup strategy |

### Build

| Task | Description | Deliverable |
|---|---|---|
| M2.1 | Trace schema | `src/agent_self_edit/types.py` — `Trace` dataclass, `TraceSchema` validator, `validate_trace(trace: dict) -> Trace` |
| M2.2 | Trace store | `src/agent_self_edit/trace.py` — `TraceStore` class. SQLite table with columns: task_id, task_input, steps, final_output, success, failure_reason, timestamp, prompt_version. Indexes on task_id, prompt_version, success. |
| M2.3 | Trace ingestion API | `TraceStore.ingest(trace)` — validates, stores, returns task_id. Batch counter increments. |
| M2.4 | Trace batching | `TraceStore.batch_ready()`, `get_batch(size)`, `acknowledge(task_ids)`. Triggers when pending count >= batch_size. |
| M2.5 | Trace adapter interface | `src/agent_self_edit/adapters/` — `TraceAdapter` ABC, `StdinAdapter`, `FileAdapter` (watch directory for .json files) |
| M2.6 | Trace cleanup | `TraceStore.cleanup(retention_days=90)` — deletes old traces. Runs on startup and every 24h. |

### Tests

| Task | Description | Files |
|---|---|---|
| T2.1 | Test trace schema validation | `tests/test_types.py` — valid trace, missing fields, extra fields, invalid timestamps, None values |
| T2.2 | Test trace store CRUD | `tests/test_trace.py` — store, get, list, count, delete, schema migration |
| T2.3 | Test trace ingestion | `tests/test_trace.py` — `ingest()` validates, stores, returns task_id. Invalid traces raise error without incrementing counter. |
| T2.4 | Test trace batching | `tests/test_trace.py` — batch_ready, get_batch returns oldest, acknowledge marks processed, counter accuracy |
| T2.5 | Test adapter implementations | `tests/test_adapters.py` — StdinAdapter reads JSON lines, FileAdapter watches directory, both call ingest |
| T2.6 | Test trace cleanup | `tests/test_trace.py` — old traces deleted, recent traces preserved, cleanup runs on startup, cleanup is logged |

### Documentation

| Task | Description | Deliverable |
|---|---|---|
| M2.DOC1 | Trace schema reference | Create `docs/reference/trace-schema.md` — trace JSON schema, all fields, examples, validation rules |
| M2.DOC2 | Adapter guide | Create `docs/explanation/adapters.md` — how to write a custom trace adapter, built-in adapters, configuration |
| M2.DOC3 | Update design docs | Update `docs/design/trace-schema-design.md` with final schema, store decisions, adapter design |
| M2.DOC4 | Update WBS index | Update `docs/wbs/v0.1.0/wbs-v0.1.0-index.md` with M2 status, issue links, exit gate results |

### M2 Exit Gate

- [ ] Design docs reviewed and committed
- [ ] Trace schema validates correctly
- [ ] SQLite store is created and queryable
- [ ] `ingest()` validates, stores, and returns task_id
- [ ] Batching triggers correctly
- [ ] Both adapters work (stdin + file)
- [ ] Cleanup deletes old traces
- [ ] Ruff clean, mypy strict clean
- [ ] All tests pass: `pytest` → 0 failures
- [ ] Coverage > 92%: `pytest --cov=agent_self_edit --cov-fail-under=92`