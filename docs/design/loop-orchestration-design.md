# D9 — Loop Orchestration, Caching & Concurrency Design

> **Milestone:** M9 (Loop Orchestration, Caching & Concurrency)
> **WBS:** [Part 5](../wbs/v0.3.0/wbs-v0.3.0-part5-loop-cli.md)
> **Issues:** #288, #240, #280, #216, #230, #229, #221, #210
> **Dependency:** M5–M8 (loop inputs: trace store, analyzer, gate, config, providers)
> **Produces for M10+:** cheap loop, atomic gate+audit, safe concurrency, correct cost.

---

## 1. Problem Statement

The self-improvement loop (`cli/run.py`, `cli/propose.py`) has six correctness and efficiency gaps:

1. **Per-proposal re-init (#288/#240):** `load_task_set()`, `_build_llm_for_role()` (×2), and `resolve_scorer()` are called inside the `for proposal in proposals:` loop — 3 proposals = 3 YAML reads + 6 LLM client inits + 3 scorer resolutions.
2. **Non-atomic gate+audit (#280/#216):** Code calls `check_all()` directly then `gate.log_result()` separately. If an exception occurs between, the audit log is missing the decision.
3. **No A/B caching (#230):** `run_ab_test()` re-runs identical `(prompt_a, prompt_b, task_set)` pairs every time, wasting tokens.
4. **No cross-process registry lock (#229):** `Registry` has `threading.Lock()` (in-process only). Two concurrent `run.py` processes can corrupt `v{N}.md`.
5. **Swallowed exceptions (#221):** `run.py:152` catches all `Exception`; the `run()` loop logs and continues forever — fatal errors never exit non-zero.
6. **Underreported staged cost (#210):** `analyze_batch()` staged path estimates cost as a single-pass proxy, ignoring the 4 actual LLM stage calls.

---

## 2. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| A/B cache scope | Persistent SQLite at `registry_path/ab_cache.db` | Survives across loop cycles; cache key embeds task_set + config hashes for natural invalidation |
| Registry lock | `fcntl.flock` on `.registry.lock` file | Unix-native, auto-released on process exit, simple context manager; macOS/Linux target confirmed in AGENTS.md |
| Exception classification | `ProviderError` subtype + message sniff | Minimal new code; reuses existing error types; `ProviderError` already has rate-limit detection logic in `run_task()` |

---

## 3. Fix 1: Hoist task set + LLM out of proposal loop (#288/#240)

### Current state

`cli/run.py` lines 98–110 and `cli/propose.py` lines 104–110 call these **inside** the `for proposal` loop:

```python
for proposal in result.proposals:
    task_set = load_task_set(config.tasks.task_set_path)      # re-reads YAML
    executor_llm = _build_llm_for_role(config, config.executor_role)  # re-inits client
    judge_llm = _build_llm_for_role(config, config.judge_role)         # re-inits client
    scorer = resolve_scorer(task_set, judge_llm=judge_llm)            # re-resolves
    ...
```

### Fix

Move all four calls **above** the loop. A batch of N proposals → 1 YAML read + 2 LLM client inits + 1 scorer resolution.

```python
task_set = load_task_set(config.tasks.task_set_path)
executor_llm = _build_llm_for_role(config, config.executor_role)
judge_llm = _build_llm_for_role(config, config.judge_role)
scorer = resolve_scorer(task_set, judge_llm=judge_llm)

for proposal in result.proposals:
    candidate_prompt = registry.current_prompt.replace(proposal.old_text, proposal.new_text)
    ab_result = run_ab_test(registry.current_prompt, candidate_prompt, task_set, executor_llm, scorer, config)
    ...
```

### Files

- `src/agent_self_edit/cli/run.py` — hoist 4 lines above loop (lines 98–110)
- `src/agent_self_edit/cli/propose.py` — hoist executor_llm + judge_llm + scorer above loop (lines 108–110; `task_set` already hoisted at line 104)

### Verification

- Mock `load_task_set` and `_build_llm_for_role`, assert call_count == 1 per batch regardless of proposal count
- Batch of 3 proposals → `load_task_set.call_count == 1`, `_build_llm_for_role.call_count == 2` (executor + judge)

---

## 4. Fix 2: Gate atomicity via `PromotionGate.check()` (#280/#216)

### Current state

`cli/run.py` lines 119–146 and `cli/propose.py` lines 135–162:

```python
gate = PromotionGate(audit_path=...)
gate_result = check_all(proposal, ab_result, registry.current_prompt, original_prompt, config)  # non-atomic
...
gate.log_result(gate_result, edit=proposal)  # separate call, can be missed
```

### Fix

Replace `check_all()` + `log_result()` with a single `gate.check()` call. `PromotionGate.check()` (gate.py:375–402) already runs all checks **and** writes the audit entry atomically within the same method. Remove the separate `log_result` call entirely.

```python
gate = PromotionGate(audit_path=...)
gate_result = gate.check(proposal, ab_result, registry.current_prompt, original_prompt, config)
# audit log already written atomically inside check()
```

### Files

- `src/agent_self_edit/cli/run.py` — replace lines 120–122 and remove line 146
- `src/agent_self_edit/cli/propose.py` — replace lines 136–138 and remove line 162

### Verification

- Test that `gate.check()` writes audit entry even when `check_all` raises (mock `check_all` to raise mid-way — the `check()` method calls it internally, so the audit log is written before the exception propagates only if we wrap; actually `check()` calls `check_all()` first then logs — need to verify this is truly atomic)
- **Edge case:** If `check_all` raises, `check()` does NOT log (the exception propagates before `self.audit.log()`). This is acceptable — the decision wasn't made, so there's nothing to audit. The fix is about removing the **separate** `log_result` call that could be skipped after a successful `check_all`.

---

## 5. Fix 3: A/B result caching — persistent SQLite (#230)

### Current state

`ab_test.py:run_ab_test()` runs every task pair every time. No caching.

### Design

**Cache location:** `config.project.registry_path / "ab_cache.db"` (SQLite)

**Cache key:** `sha256(prompt_a + prompt_b + task_set_hash + scorer_name + config_hash)`
- `task_set_hash` = `sha256` of all task definitions (id + input + expected_output) concatenated
- `config_hash` = `sha256` of `ABTestConfig` fields (`n_resamples`, `confidence_level`, `min_effect_size`, `cost_ceiling_usd`)
- Any change to task definitions or ABTestConfig naturally produces a different key → old entries unreachable

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS ab_cache (
    key TEXT PRIMARY KEY,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

**Flow:**

1. `run_ab_test()` computes cache key
2. If `config.ab_test.cache_enabled` is `False` → skip cache, run test directly
3. If cache hit → deserialize `ABResult` from `result_json`, return
4. If cache miss → run test, serialize `ABResult` to JSON, store in cache, return

**Serialization:** `ABResult` is a frozen dataclass with `PerTask` list. Use `dataclasses.asdict()` + `json.dumps()` for storage; reconstruct via `ABResult(**json.loads(...))` with `PerTask(**pt)` for each entry.

**Guard:** `config.ab_test.cache_enabled` flag (added in M8 #235) gates this. If `False`, no cache I/O.

**Cleanup:** Old entries accumulate but are harmless (different keys). A `--clear-ab-cache` CLI flag can truncate the table if needed (deferred to M10).

### Files

- `src/agent_self_edit/ab_test.py` — new `_ABResultCache` class, `run_ab_test()` wraps with cache lookup
- `src/agent_self_edit/cli/run.py` — pass cache path (already derived from `config.project.registry_path`)

### Verification

- Two calls with identical inputs → second returns cached result, `MockProvider.complete` not called on second
- Change task_set definition → cache miss (different `task_set_hash`)
- Change `ABTestConfig.confidence_level` → cache miss (different `config_hash`)
- `cache_enabled=False` → no cache I/O, test runs every time

---

## 6. Fix 4: File-based registry lock — fcntl.flock (#229)

### Current state

`registry.py` has `self._lock = threading.Lock()` (in-process only). `create()` and `rollback()` use `with self._lock:`.

### Design

Add a file-based lock using `fcntl.flock` for cross-process safety:

```python
import fcntl

class Registry:
    def __init__(self, path, git_backed=False):
        ...
        self._lock_path = self._path / ".registry.lock"

    @contextmanager
    def _file_lock(self):
        """Acquire exclusive flock; non-blocking with retry."""
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
            except OSError (errno.EACCES, errno.EAGAIN):
                time.sleep(0.5)
        raise RegistryError("registry locked by another process")
```

**Integration:** Wrap `create()` and `rollback()` with `with self._file_lock():` **inside** the existing `with self._lock:` (threading lock first, then file lock — nesting order matters to avoid deadlock).

```python
def create(self, prompt_text, **metadata):
    with self._lock:  # threading (in-process)
        with self._file_lock():  # fcntl (cross-process)
            ... existing logic ...
```

**Non-blocking + retry:** 3 attempts, 0.5s backoff → `RegistryError` if still locked.

**Platform:** `fcntl` is Unix-only. AGENTS.md confirms macOS/Linux target. On Windows (unsupported), `fcntl` doesn't exist — guard with `try: import fcntl` and fall back to threading-only lock with a warning log.

### Files

- `src/agent_self_edit/registry.py` — add `_file_lock()` context manager, wrap `create()` and `rollback()`

### Verification

- Two threads calling `registry.create()` concurrently → both succeed, no corruption
- Mock `fcntl.flock` to raise `EAGAIN` 3× → `RegistryError("registry locked")`
- Lockfile created at `registry_path/.registry.lock`
- Lock released after `create()` returns (second thread can acquire)

---

## 7. Fix 5: Exception classification (#221)

### Current state

`cli/run.py:152` catches all `Exception` and re-raises. The `run()` loop (lines 190, 199, 211) catches all `Exception` and just logs — fatal errors never exit non-zero.

### Design

Add `_classify_exception()`:

```python
from ..llm.base import ProviderError
from ..analyzer import AnalyzerError
from ..gate import GateError
from ..registry import RegistryError

def _classify_exception(exc: Exception) -> Literal["rate_limit", "transient", "fatal"]:
    if isinstance(exc, ProviderError):
        msg = str(exc).lower()
        if "rate" in msg or "429" in msg or "too many" in msg:
            return "rate_limit"
        return "fatal"
    if isinstance(exc, (GateError, AnalyzerError, RegistryError)):
        return "fatal"
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return "transient"
    return "fatal"  # unknown = fail-closed
```

**Integration into `_run_once`:**

Replace bare `except Exception:` (line 152) with classified handling — but `_run_once` already re-raises (line 158 `raise`). The classification happens in the `run()` loop.

**Integration into `run()` loop:**

```python
while not shutdown:
    try:
        _, rejection_context = _run_once(...)
    except Exception as e:
        category = _classify_exception(e)
        if category == "rate_limit":
            click.echo(f"Rate limited: {e}; backing off 10s", err=True)
            time.sleep(10)
            continue
        elif category == "transient":
            click.echo(f"Transient error: {e}; retrying in 5s", err=True)
            time.sleep(5)
            continue
        else:  # fatal
            click.echo(f"Fatal error: {e}", err=True)
            sys.exit(1)
    ...
```

**Fail-closed:** Unknown exceptions are `fatal` → exit 1. This prevents silent corruption from unexpected errors.

### Files

- `src/agent_self_edit/cli/run.py` — new `_classify_exception()`, modify `run()` loop exception handling

### Verification

- `ProviderError("429 too many requests")` → rate_limit → backoff + continue
- `RegistryError("version not found")` → fatal → exit 1
- `TimeoutError("connection timed out")` → transient → retry
- `RuntimeError("unexpected")` → fatal → exit 1
- Parametrized test covering all 4 categories

---

## 8. Fix 6: Staged analyzer cost underreport (#210)

### Current state

`analyzer.py:analyze_batch()` staged path (lines 578–582) estimates cost as:

```python
total_tokens = estimate_tokens(current_prompt) + sum(estimate_tokens(t.task_input) for t in failed)
total_cost = estimate_cost(total_tokens)
```

This is a single-pass proxy — it ignores the 4 actual LLM calls (stage 1: summarize, stage 2: section select, stage 3: propose, stage 4: validate) and their responses.

### Design

Track actual tokens per stage in `StagedAnalyzer`:

```python
class StagedAnalyzer:
    def __init__(self, llm):
        ...
        self._stage_tokens: list[int] = []

    def analyze(self, traces, current_prompt, frozen_sections, llm_provider=None, rejection_context=""):
        self._stage_tokens = []
        ...
        # Stage 1
        resp1 = self._llm_call(...)
        self._stage_tokens.append(estimate_tokens(prompt1) + estimate_tokens(resp1))
        # Stage 2
        resp2 = self._llm_call(...)
        self._stage_tokens.append(estimate_tokens(prompt2) + estimate_tokens(resp2))
        # Stage 3
        resp3 = self._llm_call(...)
        self._stage_tokens.append(estimate_tokens(prompt3) + estimate_tokens(resp3))
        # Stage 4: no LLM call (validation is code-only)
        ...
```

**Expose total:** Add `total_tokens` to the return. Change `analyze()` return from `tuple[list[EditProposal], str | None]` to `tuple[list[EditProposal], str | None, int]` where the third element is `sum(self._stage_tokens)`.

**Update callers:** `analyze_batch()` staged path reads the third return value for `tokens_used`:

```python
proposals, stage_reason, staged_tokens = sa.analyze(...)
total_tokens = staged_tokens
total_cost = estimate_cost(total_tokens)
```

**Update test mocks:** Existing mocks patch `StagedAnalyzer.analyze` with `return_value=([_proposal()], None)` — must update to `return_value=([_proposal()], None, 100)`.

### Files

- `src/agent_self_edit/analyzer.py` — `StagedAnalyzer.analyze()` token tracking, return signature change, `analyze_batch()` staged cost path
- `tests/test_analyzer_m6_coverage.py` — update mock return values

### Verification

- Staged path with 3 stages producing 100/200/150 tokens → `AnalysisResult.tokens_used == 450`
- Compare staged `tokens_used` vs single-pass `tokens_used` for same input → staged reflects 4 calls, not 1
- Mock return values updated to 3-tuple

---

## 9. Testing Strategy

All tests hermetic — `MockProvider` only, no paid LLM calls.

| Fix | Test | Assert |
|-----|------|--------|
| Hoist | Mock `load_task_set`, `_build_llm_for_role`; batch of 3 proposals | `call_count == 1` (task_set), `== 2` (LLM roles) per batch |
| Gate atomic | Mock `check_all` to raise; call `gate.check()` | Audit entry written before exception (or no entry if check_all raises — verify behavior) |
| A/B cache | Two identical `run_ab_test` calls | Second call: LLM not called, returns cached `ABResult` |
| A/B cache invalidation | Change task_set between calls | Cache miss, LLM called |
| File lock | Two threads, `registry.create()` concurrently | Both succeed, no corruption |
| File lock contention | Mock `fcntl.flock` → `EAGAIN` 3× | `RegistryError` raised |
| Exception classification | Parametrize 4 error types | `rate_limit` → continue, `fatal` → exit 1, `transient` → retry |
| Staged cost | 3 stages, known token counts | `tokens_used == sum(stages)` |

---

## 10. Exit Gate

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
