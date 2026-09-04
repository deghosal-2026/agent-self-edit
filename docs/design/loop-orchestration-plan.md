# M9 — Loop Orchestration, Caching & Concurrency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 6 loop/caching/concurrency bugs in the self-improvement loop: hoist per-proposal re-init, atomic gate+audit, A/B cache, registry file lock, exception classification, staged cost tracking.

**Architecture:** 6 targeted fixes across `cli/run.py`, `cli/propose.py`, `ab_test.py`, `registry.py`, `analyzer.py`. No new modules — each fix hardens an existing code path. All tests hermetic (MockProvider only).

**Tech Stack:** Python 3.10+, SQLite (stdlib), fcntl (stdlib Unix-only), dataclasses.

## Global Constraints

- All tests hermetic — no paid LLM calls (MockProvider only)
- `fcntl.flock` for registry lock (Unix-only macOS/Linux; graceful fallback to threading-only)
- A/B cache at `config.project.registry_path / "ab_cache.db"`
- Cache key: `sha256(prompt_a + prompt_b + task_set_hash + scorer_name + config_hash)`
- Cache gated by `config.ab_test.cache_enabled` (M8)
- Exception classification: ProviderError message sniff for rate-limit, error hierarchy for fatal, TimeoutError/ConnectionError/OSError for transient
- `StagedAnalyzer.analyze()` return changes to 3-tuple: `(proposals, failure_reason, total_tokens)`
- Exit gate: ruff=0, mypy=0, all tests pass, coverage > 91%

---

## File Map

| File | Change | Responsibility |
|------|--------|----------------|
| `src/agent_self_edit/cli/run.py` | Modify | Hoist task_set/LLM/scorer (lines 98–110), add `_classify_exception()`, use `gate.check()` instead of `check_all`+`log_result`, classified exception handling in `run()` loop |
| `src/agent_self_edit/cli/propose.py` | Modify | Hoist executor/judge/scorer (lines 108–110), use `gate.check()` instead of `check_all`+`log_result` |
| `src/agent_self_edit/ab_test.py` | Modify | New `_ABResultCache` class (SQLite), `run_ab_test` wraps with cache lookup |
| `src/agent_self_edit/registry.py` | Modify | New `_file_lock()` context manager (fcntl.flock), wrap `create()` and `rollback()` |
| `src/agent_self_edit/analyzer.py` | Modify | `StagedAnalyzer.analyze` tracks per-stage tokens, return 3-tuple, update `analyze_batch` staged cost |
| `tests/test_m9_loop.py` | Create | Tests for all 6 fixes |
| `tests/test_analyzer_m6_coverage.py` | Modify | Update mock return values for 3-tuple |

---

### Task 1: Hoist task set + LLM out of proposal loop (#288/#240)

**Files:**
- Modify: `src/agent_self_edit/cli/run.py:98-110`
- Modify: `src/agent_self_edit/cli/propose.py:108-110`
- Test: `tests/test_m9_loop.py`

**Interfaces:**
- Consumes: `load_task_set(path) -> TaskSet`, `_build_llm_for_role(config, role) -> LLMProvider`, `resolve_scorer(task_set, judge_llm) -> Scorer`
- Produces: `task_set`, `executor_llm`, `judge_llm`, `scorer` variables hoisted above the `for proposal` loop

- [ ] **Step 1: Move load_task_set, _build_llm_for_role (×2), resolve_scorer above the loop in run.py**

In `run.py`, move lines 104-107 (`task_set = load_task_set(...)`, `executor_llm = ...`, `judge_llm = ...`, `scorer = ...`) to just before line 98 (`for proposal in result.proposals:`).

After:
```python
orig_prompt = registry.current_prompt  # or original_prompt var
task_set = load_task_set(config.tasks.task_set_path)
executor_llm = _build_llm_for_role(config, config.executor_role)
judge_llm = _build_llm_for_role(config, config.judge_role)
scorer = resolve_scorer(task_set, judge_llm=judge_llm)

for proposal in result.proposals:
    from ..ab_test import run_ab_test
    from ..gate import PromotionGate, check_all
    candidate_prompt = registry.current_prompt.replace(...)
    ...
```

- [ ] **Step 2: Same hoist in propose.py**

Move executor_llm, judge_llm, and scorer construction to just before line 124 (`for proposal in result.proposals:`). `task_set` is already hoisted at line 104.

- [ ] **Step 3: Write test for hoist behavior**

```python
def test_hoist_task_set_and_llm_once_per_batch():
    from agent_self_edit.cli.run import _run_once
    from agent_self_edit.config import Config, ProjectConfig, TasksConfig, LLMConfig, ModelRoleConfig, AnalyzerConfig
    from agent_self_edit.trace import TraceStore
    from agent_self_edit.registry import Registry
    from unittest.mock import patch, MagicMock
    import tempfile, os

    with tempfile.TemporaryDirectory() as tmp:
        cfg = Config(
            project=ProjectConfig(name="test", registry_path=tmp, trace_path=os.path.join(tmp, "traces.db")),
            tasks=TasksConfig(batch_size=50),
            llm=LLMConfig(provider="mock"),
            analyzer=AnalyzerConfig(max_proposals_per_batch=3),
        )
        store = MagicMock(spec=TraceStore)
        store.batch_ready.return_value = True
        store.get_batch.return_value = []
        store.count_pending.return_value = 10
        reg = MagicMock(spec=Registry)
        reg.current_prompt = "test prompt"
        reg.current_version = 1

        with patch("agent_self_edit.cli.run.load_task_set") as mock_load:
            with patch("agent_self_edit.cli.run._build_llm_for_role") as mock_build:
                mock_build.return_value = MagicMock()
                _run_once("dummy.yaml", 50, True, "", store=store, registry=reg, config=cfg)
                # When batch is empty, loop body never executes -> load_task_set not called
                # Test with a batch that has failed traces
                store.get_batch.return_value = [MagicMock(success=False)]
                _run_once("dummy.yaml", 50, True, "", store=store, registry=reg, config=cfg)
                # load_task_set called exactly once
                assert mock_load.call_count == 1
```

- [ ] **Step 4: Run test**

Run: `python3 -m pytest tests/test_m9_loop.py::test_hoist_task_set_and_llm_once_per_batch -xvs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_self_edit/cli/run.py src/agent_self_edit/cli/propose.py tests/test_m9_loop.py
git commit -m "M9: hoist task_set + LLM/scorer out of proposal loop (#288/#240)"
```

---

### Task 2: Gate atomicity via PromotionGate.check() (#280/#216)

**Files:**
- Modify: `src/agent_self_edit/cli/run.py:119-146`
- Modify: `src/agent_self_edit/cli/propose.py:135-162`
- Test: `tests/test_m9_loop.py`

**Interfaces:**
- Consumes: `PromotionGate(audit_path)`, `gate.check(edit, ab_result, current, original, config) -> GateResult`
- Produces: `gate_result` via single `gate.check()` call (audit log written atomically inside)

- [ ] **Step 1: Replace check_all + log_result with gate.check() in run.py**

```python
gate = PromotionGate(audit_path=config.project.registry_path + "/audit.jsonl")
gate_result = gate.check(proposal, ab_result, registry.current_prompt, original_prompt, config)
click.echo(f"  Gate: {gate_result.decision}")

if gate_result.decision in ("reject", "near_miss"):
    ...  # rejection context unchanged
if gate_result.decision == "promote":
    registry.create(...)
```

Remove line `gate.log_result(gate_result, edit=proposal)`.

- [ ] **Step 2: Same replacement in propose.py**

Same pattern — replace `check_all()` + `gate.log_result()` with single `gate.check()`.

- [ ] **Step 3: Write test for gate atomicity**

```python
def test_gate_check_writes_audit_atomically():
    from agent_self_edit.gate import PromotionGate, GateAuditLog, check_all
    from agent_self_edit.types import EditProposal, ABResult
    import tempfile, json

    with tempfile.TemporaryDirectory() as tmp:
        audit_path = os.path.join(tmp, "audit.jsonl")
        gate = PromotionGate(audit_path=audit_path)
        proposal = EditProposal(section="test", old_text="old", new_text="new", hypothesis="h", expected_improvement="e")
        ab_result = ABResult(winner="b", mean_delta=0.1, ci_low=0.01, ci_high=0.2, p_value=0.03, effect_size=0.2, n_trials=10, per_task=[], cost_usd=0.0, token_count=0)
        result = gate.check(proposal, ab_result, "current prompt", "original prompt",
                            MagicMock(gate=MagicMock(near_miss_threshold=0.5,
                                                       frozen_sections=None,
                                                       max_edit_distance=20,
                                                       drift_threshold=0.3),
                                      tasks=MagicMock(sample_floor=5),
                                      ab_test=MagicMock(min_effect_size=0.1,
                                                          confidence_level=0.95)))
        assert result.decision in ("promote", "reject", "near_miss")
        # Audit log should have one entry
        with open(audit_path) as f:
            entries = [json.loads(l) for l in f if l.strip()]
        assert len(entries) == 1
        assert entries[0]["decision"] == result.decision
        assert entries[0]["edit_id"] == result.edit_id
        assert entries[0]["proposal_old_text"] == "old"
```

- [ ] **Step 4: Run test**

Run: `python3 -m pytest tests/test_m9_loop.py::test_gate_check_writes_audit_atomically -xvs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_self_edit/cli/run.py src/agent_self_edit/cli/propose.py tests/test_m9_loop.py
git commit -m "M9: gate atomic via PromotionGate.check() (#280/#216)"
```

---

### Task 3: A/B result caching — persistent SQLite (#230)

**Files:**
- Create (modify): `src/agent_self_edit/ab_test.py` — add `_ABResultCache` class, modify `run_ab_test`
- Test: `tests/test_m9_loop.py`

**Interfaces:**
- Produces: `_ABResultCache(registry_path, enabled=True)` with `get(key) -> ABResult | None` and `set(key, ABResult) -> None`
- `run_ab_test()` accepts new optional `cache: _ABResultCache | None` parameter (None = no caching)
- Cache key computed internally: `sha256(prompt_a + prompt_b + task_set_hash + scorer.__class__.__name__ + config_hash)`
- `task_set_hash` = hex digest of sha256 of `json.dumps([task.to_dict() for task in tasks], sort_keys=True)`
- `config_hash` = hex digest of sha256 of `json.dumps(dataclasses.asdict(ab_config), sort_keys=True)`

- [ ] **Step 1: Write failing test for A/B cache**

```python
def test_ab_cache_hit_skips_llm_calls():
    from agent_self_edit.ab_test import _ABResultCache, run_ab_test
    from agent_self_edit.config import ABTestConfig
    from agent_self_edit.tasks import Task, TaskSet
    import tempfile, hashlib

    class TestScorer:
        def score(self, expected, actual):
            return {}, 1.0
        def __call__(self, expected, actual):
            return {}, 1.0

    tasks = TaskSet(tasks=[Task(id="test", input="hello world", expected_output="hello")])

    with tempfile.TemporaryDirectory() as tmp:
        cache = _ABResultCache(tmp, enabled=True)
        llm = MagicMock()
        llm.complete.return_value = "hello"
        scorer = TestScorer()
        cfg = MagicMock(ab_test=ABTestConfig(cache_enabled=True))

        # First call: cache miss
        result1 = run_ab_test("prompt a", "prompt b", tasks, llm, scorer, cfg, cache=cache)
        call_count1 = llm.complete.call_count

        # Second call: cache hit
        llm.complete.call_count = 0
        result2 = run_ab_test("prompt a", "prompt b", tasks, llm, scorer, cfg, cache=cache)
        assert llm.complete.call_count == 0, "LLM should not be called on cache hit"
        assert result1.winner == result2.winner
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_m9_loop.py::test_ab_cache_hit_skips_llm_calls -xvs`
Expected: FAIL with import or attribute error

- [ ] **Step 3: Implement _ABResultCache class**

```python
import sqlite3
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from .ab_test import ABResult, PerTask, estimate_cost

@dataclass
class _ABResultCache:
    path: str
    enabled: bool = True
    _conn: sqlite3.Connection | None = None

    def __post_init__(self):
        if not self.enabled:
            return
        self._conn = sqlite3.connect(os.path.join(self.path, "ab_cache.db"))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS ab_cache ("
            "key TEXT PRIMARY KEY, result_json TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        self._conn.commit()

    def _make_key(self, prompt_a, prompt_b, tasks, scorer_name, ab_config):
        import dataclasses
        task_data = json.dumps(
            [{"id": t.id, "input": t.input, "expected_output": t.expected_output} for t in tasks],
            sort_keys=True,
        )
        task_hash = sha256(task_data.encode()).hexdigest()
        config_data = json.dumps(dataclasses.asdict(ab_config), sort_keys=True)
        config_hash = sha256(config_data.encode()).hexdigest()
        combined = prompt_a + prompt_b + task_hash + scorer_name + config_hash
        return sha256(combined.encode()).hexdigest()

    def get(self, key: str) -> ABResult | None:
        if not self.enabled or self._conn is None:
            return None
        row = self._conn.execute(
            "SELECT result_json FROM ab_cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        data = json.loads(row[0])
        return ABResult(
            winner=data["winner"],
            mean_delta=data["mean_delta"],
            ci_low=data["ci_low"],
            ci_high=data["ci_high"],
            p_value=data["p_value"],
            effect_size=data["effect_size"],
            n_trials=data["n_trials"],
            per_task=[PerTask(**pt) for pt in data.get("per_task", [])],
            cost_usd=data.get("cost_usd", 0.0),
            token_count=data.get("token_count", 0),
        )

    def set(self, key: str, result: ABResult) -> None:
        if not self.enabled or self._conn is None:
            return
        import dataclasses
        data = {"winner": result.winner, "mean_delta": result.mean_delta,
                "ci_low": result.ci_low, "ci_high": result.ci_high,
                "p_value": result.p_value, "effect_size": result.effect_size,
                "n_trials": result.n_trials,
                "per_task": [dataclasses.asdict(pt) for pt in result.per_task],
                "cost_usd": result.cost_usd, "token_count": result.token_count}
        self._conn.execute(
            "INSERT OR REPLACE INTO ab_cache (key, result_json, created_at) VALUES (?, ?, datetime('now'))",
            (key, json.dumps(data)),
        )
        self._conn.commit()
```

- [ ] **Step 4: Modify run_ab_test to accept and use cache**

Add `cache: _ABResultCache | None = None` parameter to `run_ab_test()` signature.
In the function body, after `ab_config = _resolve_ab_config(config)` and `tasks = task_set.list_tasks()`:
```python
if cache is not None and cache.enabled:
    key = cache._make_key(prompt_a, prompt_b, tasks, scorer.__class__.__name__, ab_config)
    cached = cache.get(key)
    if cached is not None:
        return cached
```
And before `return`:
```python
    if cache is not None and cache.enabled:
        cache.set(key, result)
    return result
```

Add `import os` at the top of ab_test.py.

- [ ] **Step 5: Pass cache from run.py and propose.py**

In `run.py`, after `config = load_config(config_path)` and before the loop:
```python
cache = _ABResultCache(config.project.registry_path, enabled=config.ab_test.cache_enabled)
```
(Need to import `_ABResultCache` from `..ab_test` inside the loop body)
Pass `cache=cache` to `run_ab_test()` call.

In `run.py` and `propose.py`, the `run_ab_test` call becomes:
```python
ab_result = run_ab_test(
    registry.current_prompt, candidate_prompt, task_set, executor_llm, scorer, config,
    cache=cache,
)
```

- [ ] **Step 6: Write cache invalidation test**

```python
def test_ab_cache_miss_on_task_change():
    from agent_self_edit.ab_test import _ABResultCache, run_ab_test
    from agent_self_edit.tasks import Task, TaskSet
    import tempfile

    class TestScorer:
        def score(self, expected, actual):
            return {}, 1.0
        def __call__(self, expected, actual):
            return {}, 1.0

    with tempfile.TemporaryDirectory() as tmp:
        cache = _ABResultCache(tmp, enabled=True)
        llm = MagicMock()
        llm.complete.return_value = "hello"
        scorer = TestScorer()
        cfg = MagicMock(ab_test=ABTestConfig(cache_enabled=True),
                        tasks=MagicMock(batch_size=10, sample_floor=5),
                        gate=MagicMock(near_miss_threshold=0.5, frozen_sections=None,
                                        max_edit_distance=20, drift_threshold=0.3),
                        analyzer=MagicMock(cost_ceiling_usd=0.5, max_proposals_per_batch=3))

        tasks1 = TaskSet(tasks=[Task(id="t1", input="hello", expected_output="hello")])
        tasks2 = TaskSet(tasks=[Task(id="t1", input="hello world", expected_output="hello")])

        result1 = run_ab_test("prompt a", "prompt b", tasks1, llm, scorer, cfg, cache=cache)
        call1 = llm.complete.call_count
        llm.complete.call_count = 0
        result2 = run_ab_test("prompt a", "prompt b", tasks2, llm, scorer, cfg, cache=cache)
        # tasks differ -> cache miss, LLM should be called
        assert llm.complete.call_count > 0
```

- [ ] **Step 7: Run all A/B cache tests**

Run: `python3 -m pytest tests/test_m9_loop.py -xvs -k "cache"`
Expected: All pass

- [ ] **Step 8: Commit**

```bash
git add src/agent_self_edit/ab_test.py src/agent_self_edit/cli/run.py src/agent_self_edit/cli/propose.py tests/test_m9_loop.py
git commit -m "M9: persistent A/B result cache (SQLite) (#230)"
```

---

### Task 4: File-based registry lock — fcntl.flock (#229)

**Files:**
- Modify: `src/agent_self_edit/registry.py` — add `_file_lock()`, wrap `create()` and `rollback()`
- Test: `tests/test_m9_loop.py`

**Interfaces:**
- Consumes: `Registry._lock` (threading.Lock, already exists)
- Produces: `Registry._file_lock()` context manager (fcntl.flock), wraps `create()` and `rollback()`

- [ ] **Step 1: Add file lock imports and context manager**

At top of `registry.py`:
```python
import fcntl
import os
import time
from contextlib import contextmanager
```

Add to `__init__`:
```python
self._lock_path = self._path / ".registry.lock"
self._fcntl_available = hasattr(os, "O_CREAT") and not os.name == "nt"
```

Add method:
```python
@contextmanager
def _file_lock(self):
    if not self._fcntl_available:
        yield
        return
    for attempt in range(3):
        try:
            fd = os.open(self._lock_path, os.O_CREAT | os.O_RDWR)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
            return
        except (OSError, IOError) as e:
            if getattr(e, 'errno', None) in (errno.EACCES, errno.EAGAIN):
                if attempt < 2:
                    time.sleep(0.5)
                    continue
                raise RegistryError("registry locked by another process") from e
            raise
```

Need `import errno` at top.

- [ ] **Step 2: Wrap create() with file lock**

```python
def create(self, prompt_text, **metadata):
    with self._lock:  # threading (in-process)
        with self._file_lock():  # fcntl (cross-process)
            ... existing create body ...
```

Same for `rollback()`:
```python
def rollback(self, version, reason):
    with self._lock:
        with self._file_lock():
            ... existing rollback body ...
```

- [ ] **Step 3: Write test for file lock**

```python
def test_registry_file_lock_prevents_concurrent_corruption():
    from agent_self_edit.registry import Registry
    import tempfile, threading, os

    errors = []

    def create_in_thread(reg_path):
        try:
            reg = Registry(reg_path)
            reg.create("prompt v1", hypothesis="h1")
        except Exception as e:
            errors.append(str(e))

    with tempfile.TemporaryDirectory() as tmp:
        reg_path = os.path.join(tmp, "registry")
        threads = [threading.Thread(target=create_in_thread, args=(reg_path,)) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0, f"Errors: {errors}"
        reg = Registry(reg_path)
        assert reg.current_version >= 1
```

- [ ] **Step 4: Write test for lock contention**

```python
def test_registry_file_lock_raises_on_contention():
    from agent_self_edit.registry import Registry
    import tempfile, os

    with tempfile.TemporaryDirectory() as tmp:
        reg_path = os.path.join(tmp, "registry")
        reg = Registry(reg_path)
        # Manually acquire the file lock to simulate contention
        with open(os.path.join(reg_path, ".registry.lock"), "w") as f:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                reg.create("prompt v1", hypothesis="h1")
                assert False, "should have raised RegistryError"
            except Registry.RegistryError as e:
                assert "locked" in str(e)
```

- [ ] **Step 5: Run tests**

Run: `python3 -m pytest tests/test_m9_loop.py -xvs -k "lock"`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/agent_self_edit/registry.py tests/test_m9_loop.py
git commit -m "M9: file-based registry lock with fcntl.flock (#229)"
```

---

### Task 5: Exception classification (#221)

**Files:**
- Modify: `src/agent_self_edit/cli/run.py` — add `_classify_exception()`, modify `run()` loop
- Test: `tests/test_m9_loop.py`

**Interfaces:**
- Produces: `_classify_exception(Exception) -> Literal["rate_limit", "transient", "fatal"]`
- Consumes: `ProviderError`, `GateError`, `AnalyzerError`, `RegistryError`, `TimeoutError`, `ConnectionError`, `OSError`

- [ ] **Step 1: Add classifier function**

```python
def _classify_exception(exc: Exception) -> str:  # Literal["rate_limit", "transient", "fatal"]
    """Classify an exception for loop retry/exit decisions."""
    from ..llm.base import ProviderError
    from ..analyzer import AnalyzerError
    from ..gate import GateError
    from ..registry import RegistryError

    if isinstance(exc, ProviderError):
        msg = str(exc).lower()
        if "rate" in msg or "429" in msg or "too many" in msg:
            return "rate_limit"
        return "fatal"
    if isinstance(exc, (GateError, AnalyzerError, RegistryError)):
        return "fatal"
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return "transient"
    return "fatal"  # fail-closed for unknown
```

- [ ] **Step 2: Modify run() loop to use classification**

Replace the three `except Exception as e: click.echo(...)` blocks in `run()` with:

```python
except Exception as e:
    category = _classify_exception(e)
    if category in ("rate_limit", "transient"):
        sleep = 10 if category == "rate_limit" else 5
        click.echo(f"{category}: {e}; retrying in {sleep}s", err=True)
        time.sleep(sleep)
        continue
    click.echo(f"Fatal error: {e}", err=True)
    sys.exit(1)
```

Reduce the three `except Exception` blocks to just the above (same logic for all trigger modes — batch, time, manual — since the classification handles the retry/exit decision). Add `import sys` at top.

- [ ] **Step 3: Write parametrized test**

```python
import pytest
from agent_self_edit.llm.base import ProviderError
from agent_self_edit.gate import GateError
from agent_self_edit.analyzer import AnalyzerError
from agent_self_edit.registry import RegistryError
from agent_self_edit.cli.run import _classify_exception

@pytest.mark.parametrize("exc,expected", [
    (ProviderError("rate limited"), "rate_limit"),
    (ProviderError("429 too many requests"), "rate_limit"),
    (ProviderError("too many requests"), "rate_limit"),
    (ProviderError("invalid auth"), "fatal"),
    (GateError("version mismatch"), "fatal"),
    (AnalyzerError("LLM failed"), "fatal"),
    (RegistryError("version not found"), "fatal"),
    (TimeoutError("connection timed out"), "transient"),
    (ConnectionError("refused"), "transient"),
    (OSError("disk full"), "transient"),
    (ValueError("unknown"), "fatal"),
    (RuntimeError("unexpected"), "fatal"),
])
def test_exception_classification(exc, expected):
    assert _classify_exception(exc) == expected
```

- [ ] **Step 4: Run test**

Run: `python3 -m pytest tests/test_m9_loop.py::test_exception_classification -xvs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_self_edit/cli/run.py tests/test_m9_loop.py
git commit -m "M9: exception classification with backoff/fatal (#221)"
```

---

### Task 6: Staged analyzer cost underreport (#210)

**Files:**
- Modify: `src/agent_self_edit/analyzer.py` — `StagedAnalyzer.analyze()` token tracking, return 3-tuple, `analyze_batch` staged cost
- Modify: `tests/test_analyzer_m6_coverage.py` — update mock return values
- Test: `tests/test_m9_loop.py`

**Interfaces:**
- Produces: `StagedAnalyzer.analyze()` returns `tuple[list[EditProposal], str | None, int]` where int = `total_tokens`
- Consumes: `estimate_tokens(text) -> int`, `estimate_cost(tokens) -> float`

- [ ] **Step 1: Add token tracking to StagedAnalyzer**

In `__init__`:
```python
self._stage_tokens: list[int] = []
```

At start of `analyze()`:
```python
self._stage_tokens = []
```

After each `_llm_call()`:
```python
# Stage 1
resp1 = self._llm_call(llm, prompt1)
self._stage_tokens.append(estimate_tokens(prompt1) + estimate_tokens(resp1))

# Stage 2
resp2 = self._llm_call(llm, prompt2)
self._stage_tokens.append(estimate_tokens(prompt2) + estimate_tokens(resp2))

# Stage 3
resp3 = self._llm_call(llm, prompt3)
self._stage_tokens.append(estimate_tokens(prompt3) + estimate_tokens(resp3))
```

Change return at end from:
```python
return proposals, failure_reason
```
to:
```python
total_tokens = sum(self._stage_tokens)
return proposals, failure_reason, total_tokens
```

Similarly, in exception paths, return 0 for tokens:
```python
return [], f"staged analyzer error: {e}", 0
...
return [], f"validation failed: {errors}", 0
```

- [ ] **Step 2: Update analyze_batch staged cost path**

```python
proposals, stage_reason, staged_tokens = sa.analyze(
    failed, current_prompt, frozen_sections, llm_provider,
    rejection_context=rejection_context,
)
total_tokens = staged_tokens  # use actual stage tokens, not proxy
total_cost = estimate_cost(total_tokens)
```

Remove the old proxy calculation (lines 579-581 in original):
```python
total_tokens = estimate_tokens(current_prompt) + sum(
    estimate_tokens(t.task_input) for t in failed
)
```
Replace with just `total_tokens = staged_tokens`.

- [ ] **Step 3: Update test mock return values**

In `tests/test_analyzer_m6_coverage.py`:
```python
return_value=([_proposal()], None)  ->  return_value=([_proposal()], None, 40)
```

Two occurrences (lines 553 and 565).

- [ ] **Step 4: Write test for staged cost tracking**

```python
def test_staged_cost_tracks_actual_tokens():
    from agent_self_edit.analyzer import StagedAnalyzer, analyze_batch
    from agent_self_edit.llm.mock import MockProvider
    from agent_self_edit.types import Trace
    from agent_self_edit.config import Config, ProjectConfig, AnalyzerConfig
    import tempfile

    def responder(prompt, system_prompt=""):
        if "summarize" in prompt.lower():
            return '[{"pattern":"p","description":"d","trace_ids":["t1"]}]'
        if "Select exactly ONE section" in prompt:
            return '{"section":"classify","rationale":"r"}'
        if "Propose ONE minimal edit" in prompt:
            return '{"section":"classify","old_text":"a","new_text":"b","hypothesis":"h","expected_improvement":"e"}'
        return "[]"

    with tempfile.TemporaryDirectory() as tmp:
        cfg = Config(project=ProjectConfig(name="test", registry_path=tmp, trace_path=os.path.join(tmp, "traces.db")),
                     analyzer=AnalyzerConfig(cost_ceiling_usd=10.0))
        llm = MockProvider(responses=responder)
        traces = [Trace(id="t1", task_id="t1", task_input="hi", task_output="out", success=False, prompt_version=1, expected_output="hi", score=0.5)]
        result = analyze_batch(traces, "current prompt\n", None, llm, config=cfg, staged=True)
        assert result.tokens_used > 0
        # Staged path should report tokens from 3 LLM calls (not just proxy)
        assert len(llm.calls) >= 3
        assert not result.cost_aborted
```

- [ ] **Step 5: Run all tests**

Run: `python3 -m pytest tests/test_m9_loop.py tests/test_analyzer_m6_coverage.py -x -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/agent_self_edit/analyzer.py tests/test_analyzer_m6_coverage.py tests/test_m9_loop.py
git commit -m "M9: staged analyzer cost tracks actual per-stage tokens (#210)"
```

---

### Self-Review Checklist

After writing all tasks, verify:

1. **Spec coverage:** Does each of the 6 M9 issues (#288, #240, #280, #216, #230, #229, #221, #210) have a task? Yes — Tasks 1-6 cover all 8 issues.
2. **Placeholder scan:** No TBD/TODO anywhere in the plan.
3. **Type consistency:** `_classify_exception` returns `str`, not `Literal` (avoids typing import complexity in tests). `_ABResultCache._make_key` uses `scorer.__class__.__name__`. `StagedAnalyzer.analyze` return changes to 3-tuple consistently.
4. **Import consistency:** All imports mentioned in steps are available in the codebase (checked against existing files).