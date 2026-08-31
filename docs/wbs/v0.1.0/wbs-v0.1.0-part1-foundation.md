# WBS — AgentSelfEdit v0.1.0 Part 1: Foundation

> **Milestones covered:** M1 (Scaffold + Config) · M2 (Execution Trace Ingestion)
> **PRD coverage:** [F-13](../../design/prd/05-features.md) (config), [F-10](../../design/prd/05-features.md) (task set), [F-01](../../design/prd/05-features.md) (trace ingestion)
> **CUJs covered:** CUJ 5 (first-time setup — init), CUJ 1 (deploy, observe, improve — trace ingestion)
> **Dependency:** M1 (none) → M2 (depends on M1)
> **Issue Range:** #1–#14

---

## Milestone 1: Scaffold + Config (#1–#8)

**Objective:** Repo structure, package, CI, config system, held-out task set management. Everything downstream imports from here.

### M1 Design Documents

- **D1 — Config schema design** (`docs/design/config-schema-design.md`): config file format, all fields, validation rules, schema versioning, migration strategy.
- **D13 — Design decisions** (append to `docs/design/design-decisions.md`): DD-01 (package/CLI naming), DD-02 (config format YAML), DD-03 (task set format).

### M1 Task Checklist

| # | Task | Build (files) | Behavior + edge cases | Feature | Design Ref | Verify | Status |
|---|------|---------------|----------------------|---------|------------|--------|--------|
| 1 | Package scaffold | `pyproject.toml`, `src/agent_self_edit/__init__.py`, `tests/__init__.py`, `tests/conftest.py` | `pip install -e .` succeeds; `python -c "import agent_self_edit"` succeeds; pytest discovers tests | F-13 (partial) | D1 | clean venv install + import | [#1](https://github.com/deghosal-2026/agent-self-edit/issues/1) · ✅ |
| 2 | Config file format | `src/agent_self_edit/config.py`: `Config` dataclass, `load_config(path)`, `validate_config(config)`, `ConfigError` | Valid config loads without errors; invalid config returns list of errors; config round-trips through YAML; missing file raises `FileNotFoundError` | F-13 | D1 | valid/invalid fixture YAMLs; round-trip test | [#3](https://github.com/deghosal-3036/agent-self-edit/issues/3) · ✅ |
| 3 | Config validation | Validation rules in `config.py`: `max_edit_distance > 0`, `drift_threshold in [0,1]`, `confidence_level in [0.5, 0.999]`, `sample_floor >= 10`, `trigger in {batch, time, manual}` | Each rule produces a clear error message; multiple violations all reported; boundary values tested | F-13 | D1 | each rule independently tested with pass/fail fixtures | [#4](https://github.com/deghosal-2026/agent-self-edit/issues/4) · ✅ |
| 4 | Held-out task set loader | `src/agent_self_edit/tasks.py`: `TaskSet` class, `load_task_set(path)`, `validate_task_set(task_set)` | YAML and JSON formats supported; missing required fields return validation errors; duplicate task IDs rejected; empty task set accepted | F-10 | D1 | YAML + JSON fixtures; duplicate IDs; empty set | [#5](https://github.com/deghosal-2026/agent-self-edit/issues/5) · ✅ |
| 5 | Task set management API | `TaskSet.add_task()`, `remove_task()`, `list_tasks()`, `validate_set()` | Thread-safe with read-write lock; add persists; remove removes; list returns all; validate returns pass/fail per task; concurrent modifications don't corrupt | F-10 | D1 | concurrent add/remove; validate after mutation | [#6](https://github.com/deghosal-2026/agent-self-edit/issues/6) · ✅ |
| 6 | CI pipeline | `.github/workflows/ci.yml`, `.github/dependabot.yml`, `.github/PULL_REQUEST_TEMPLATE.md` | CI runs on push and PR; ruff passes; mypy strict passes; coverage reports generated; dependabot creates PRs | F-13 (partial) | — | push triggers CI; lint + coverage + test pass | [#7](https://github.com/deghosal-2027/agent-self-edit/issues/7) · ✅ |
| 7 | OSS community files | `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `SUPPORT.md`, `.github/ISSUE_TEMPLATE/bug_report.md`, `.github/ISSUE_TEMPLATE/feature_request.md` | CONTRIBUTING covers: how to report bugs, coding standards, PR process; SECURITY covers vulnerability reporting; templates have correct YAML frontmatter | — | — | all files exist, contain meaningful content | [#8](https://github.com/deghosal-2026/agent-self-edit/issues/8) · ✅ |

### M1 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Config loading | 100% valid configs load, 100% invalid configs rejected | config test suite |
| Task set loading | both YAML and JSON formats round-trip | task set test suite |
| CI pipeline | 0 lint errors, 0 type errors, tests green, coverage > 92% | CI run on push |
| Community files | 6 files exist with meaningful content | manual review |
| Coverage | > 92% on `agent_self_edit` | `--cov-fail-under=92` |

### M1 Out of Scope

- Trace ingestion (M2), A/B test engine (M3), any LLM provider code
- Real LLM calls — hermetic only

### M1 Exit Gate

- [x] `pip install -e .` succeeds
- [x] Config loads and validates correctly
- [x] Task set loads and validates correctly
- [x] All 6 community files exist
- [x] Ruff clean, mypy strict clean, all tests pass, coverage > 92%
- [x] CI pipeline is green on push
- [x] **Design docs authored:** D1 (config-schema), D13 (DD-01/02/03)

**Dependency:** none. **Produces for M2+:** `Config` dataclass, `TaskSet`, `load_config()`, `validate_config()`, CI pipeline, community files.

---

## Milestone 2: Execution Trace Ingestion (#9–#14)

**Objective:** Accept execution traces from the agent, store them, batch them for analysis. Fully testable with synthetic traces — no LLM needed.

### M2 Design Documents

- **D2 — Trace schema design** (`docs/design/trace-schema-design.md`): trace JSON schema, all fields, validation rules, SQLite store schema, indexes, adapter interface design, cleanup strategy.
- **D13 — Design decisions:** DD-04 (trace store SQLite), DD-05 (adapter pattern).

### M2 Task Checklist

| # | Task | Build (files) | Behavior + edge cases | Feature | Design Ref | Verify | Status |
|---|------|---------------|----------------------|---------|------------|--------|--------|
| 1 | Trace schema | `src/agent_self_edit/types.py`: `Trace` dataclass, `validate_trace(trace: dict) -> Trace` | Valid trace deserializes; missing required fields raise error; extra fields ignored; timestamps parsed as ISO 8601; `failure_reason` optional; `steps` optional | F-01 | [D2](../../design/trace-schema-design.md) | valid/invalid JSON fixtures; field-by-field edge cases | [#9](https://github.com/deghosal-2026/agent-self-edit/issues/9) · ✅ |
| 2 | Trace store | `src/agent_self_edit/trace.py`: `TraceStore.__init__(path)`, `store(trace)`, `get(task_id)`, `list(success=None, prompt_version=None, limit=100)`, `count(success=None)`, `delete_before(timestamp)` | SQLite DB created on init; indexes on task_id, prompt_version, success; schema migration on version change; `list` returns correct filtered results; 0 traces → empty list | F-01 | [D2](../../design/trace-schema-design.md) | CRUD on temp DB; filtered queries; schema migration | [#10](https://github.com/deghosal-2026/agent-self-edit/issues/10) · ✅ |
| 3 | Trace ingestion API | `TraceStore.ingest(trace) -> str` | Validates via `validate_trace()`; stores via `store()`; returns `task_id`; batch counter increments; invalid traces raise `ValueError` without incrementing | F-01 | [D2](../../design/trace-schema-design.md) | valid + invalid traces; batch counter accuracy | [#11](https://github.com/deghosal-2026/agent-self-edit/issues/11) · ✅ |
| 4 | Trace batching | `TraceStore.batch_ready()`, `get_batch(size)`, `acknowledge(task_ids)` | `batch_ready()` returns True when pending >= batch_size; `get_batch()` returns oldest N unprocessed; `acknowledge()` marks processed; partial acknowledgement works | F-01 | [D2](../../design/trace-schema-design.md) | batch size boundary; partial ack; no pending traces | [#12](https://github.com/deghosal-2026/agent-self-edit/issues/12) · ✅ |
| 5 | Trace adapter interface | `src/agent_self_edit/adapters/`: `base.py` (ABC), `stdin.py` (StdinAdapter), `file.py` (FileAdapter) | `StdinAdapter` reads JSON lines from stdin; `FileAdapter` watches directory for new `.json` files; both call `ingest()` for each trace | F-01 | [D2](../../design/trace-schema-design.md) | stdin pipe test; file watch + add; malformed input | [#13](https://github.com/deghosal-2026/agent-self-edit/issues/13) · ✅ |
| 6 | Trace cleanup | `TraceStore.cleanup(retention_days=90)` | Deletes traces older than retention; preserves traces within window; called on startup and every 24h; cleanup logged; retention_days=0 deletes everything | F-01 | [D2](../../design/trace-schema-design.md) | old traces deleted; recent preserved; 0 retention edge case | [#14](https://github.com/deghosal-2026/agent-self-edit/issues/14) · ✅ |

### M2 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Trace validation | 100% valid traces accepted, 100% invalid rejected | validation test suite |
| Store CRUD | 100% operations correct on temp DB | store test suite |
| Batching | batch triggers at correct threshold; ordering preserved | batch test suite |
| Adapters | both adapters produce valid ingested traces | adapter test suite |
| Cleanup | old traces deleted, recent preserved | cleanup test suite |
| Coverage | > 92% | `--cov-fail-under=92` |

### M2 Out of Scope

- A/B test engine (M3), any LLM provider code, prompt registry (M5), guardrails (M6)

### M2 Exit Gate

- [x] Trace schema validates correctly
- [x] SQLite store is created and queryable
- [x] `ingest()` validates, stores, returns task_id
- [x] Batching triggers correctly
- [x] Both adapters work (stdin + file)
- [x] Cleanup deletes old traces
- [x] Ruff clean, mypy strict clean, all tests pass, coverage > 92%
- [x] **Design docs authored:** D2 (trace-schema), D13 (DD-04/05)

**Dependency:** M1. **Produces for M7+:** `Trace` dataclass, `TraceStore`, `TraceAdapter` interface, `StdinAdapter`, `FileAdapter`.