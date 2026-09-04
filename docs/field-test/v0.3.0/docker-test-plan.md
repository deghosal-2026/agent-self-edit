# Docker Test Plan — AgentSelfEdit v0.3.0

> Docker tests for the v0.3.0 self-improving prompt optimizer. Builds on the v0.2.0 Docker test suite, incorporating all M1–M10 correctness fixes.
> Authored per #302 (Docker test plan), #303 (Docker test authoring), #304 (Docker test execution).

## 1. What Changed in v0.3.0 (Affecting Docker Tests)

| Change | M | Impact on Docker tests |
|--------|---|-----------------------|
| **Two-tailed permutation** | M1 | A/B winner='a' path now live; Docker test assertions must accept both directions |
| **Tie detection epsilon** | M1 | Near-identical scores → `tie` not `inconclusive` |
| **`run_task` system role format** | M1 | Two-message format (system + user); mock provider validates |
| **Exponential backoff** | M1 | A/B test no longer fails on rate-limit; longer wall-clock but higher success rate |
| **Persistent A/B cache** | M1 | Identical `(task, prompt)` pairs skip re-run; cache persists across `run` calls |
| **`frozen_sections` config** | M3 | Gate config must include `frozen_sections` list; edits to frozen sections blocked |
| **Drift from original prompt** | M3 | Drift measured against v1, not current; affects drift threshold in config |
| **Prompt caching** | M4 | 1 disk read per loop, not 12+; Docker test should verify I/O not excessive |
| **In-flight trace safety** | M5 | Exception during Docker loop → traces released, not stuck `processed=-1` |
| **`batch_ready` guard** | M5 | `propose` checks incomplete batch; config must have `batch_size` matching seed count |
| **`max_edit_lines` configurable** | M6 | `analyzer.max_edit_lines` in Docker config |
| **`materialize_candidate_prompt`** | M10 | Raw `.replace()` replaced; missing `old_text` raises `ValueError` → proposal skipped |
| **`changed_section` in Meta** | M10 | Registry tracks which section was edited; verifiable in Docker test output |
| **Exception classification** | M9 | Loop distinguishes rate-limit/transient/fatal; Docker test should verify exit code |
| **File lock** | M9 | `fcntl.flock` on registry; multi-process safe |
| **Trigger modes** | M8 | `trigger: batch` works; Docker test uses `--once` for single-cycle |
| **Config schema** | M8 | New fields: `task_timeout_seconds`, `cache_enabled`, `llm_b`, `trigger_interval_hours` |
| **Coverage gate** | M11 | `--cov-fail-under=91` (was 92%) |

## 2. Objectives

| # | Objective | What it proves |
|---|-----------|----------------|
| 1 | Image builds | `Dockerfile` produces a working image with `[llm]` extra |
| 2 | OMLX reachable from host & container | Local OMLX server is up and serving the configured model |
| 3 | CLI works | All 10 commands listed in `--help` |
| 4 | Config loads | `validate` and `status` work with OMLX-backed config |
| 5 | **Classification full loop** | `run --once` completes: ingest → analyze → A/B → gate → promote/reject |
| 6 | **Extraction full loop** | Same loop on extraction corpus with `StructuredExtractionScorer` |
| 7 | **Generation full loop** | Same loop on generation corpus with `LLMJudgeScorer` + judge role |
| 8 | **Staged analyzer** | `analyze_batch(..., staged=True)` produces proposals |
| 9 | **Mixed-domain** | 30+ tasks, correct scorer per task type |
| 10 | **Adversarial** | 5/5 bad edits blocked; FP/FN measured |
| 11 | **Propose full** | `propose` (no `--dry-run`) completes with real LLM |
| 12 | **A/B cache** | Cache hit on identical re-run; cache miss on different prompt |
| 13 | **Materialize guard** | Missing `old_text` → proposal skipped, not silently A/B tested |
| 14 | **LLM I/O captured** | Every LLM call's request and response written to disk |
| 15 | **Prompt version changes** | Registry shows before/after prompt with `changed_section` |

## 3. Architecture

```
┌──────────────────────────────────────────────────────────┐
│ Host (macOS)                                             │
│                                                          │
│  ┌─────────────┐     host.docker.internal    ┌────────┐  │
│  │ OMLX server │◄────────────────────────────│ Docker │  │
│  │ :8000/v1     │     OpenAI-compatible API    │ agent- │  │
│  │ Qwen3.5-4B  │                              │ self-  │  │
│  └─────────────┘                              │ edit   │  │
│                                                └────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ field-test/v0.3.0/results/docker/                   │  │
│  │   omlx/qwen3.5-4b-4bit/                             │  │
│  │     docker-run-classification.json  (structured)    │  │
│  │     docker-run-extraction.json      (structured)    │  │
│  │     docker-run-generation.json      (structured)    │  │
│  │     docker-run-staged-analyzer.json (structured)    │  │
│  │     docker-run-mixed-domain.json    (structured)    │  │
│  │     docker-run-adversarial.json     (structured)    │  │
│  │     docker-propose-full.json         (structured)   │  │
│  │     llm-traffic-*.jsonl              (raw LLM I/O)  │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ docs/field-test/v0.3.0/                              │  │
│  │   docker-field-test-summary.md   (human report)     │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## 4. Test Matrix

| # | Test | Stages exercised | LLM | Pass condition | New in v0.3.0? |
|---|------|------------------|-----|----------------|-----------------|
| 1 | `test_docker_build` | build | none | exit 0, image exists | No (reused) |
| 2 | `test_omlx_is_up` | connectivity | none | non-empty model list | No (reused) |
| 3 | `test_omlx_model_available` | connectivity | none | model found | No (reused) |
| 4 | `test_omlx_reachable_from_container` | connectivity | none | model visible from container | No (reused) |
| 5 | `test_docker_help` | CLI | none | all 10 commands listed | No (reused) |
| 6 | `test_docker_validate` | config | none | exit 0 or 2 | No (reused) |
| 7 | `test_docker_status` | config | none | exit 0, 1, or 2 | No (reused) |
| 8 | **`test_docker_run_classification`** | ingest → analyze → A/B → gate → promote/reject | OMLX | All stages produce output, LLM I/O captured, two-message format | **Yes** — M1 run_task format, M10 materialize guard |
| 9 | **`test_docker_run_extraction`** | ingest → analyze → A/B → gate → promote/reject (extraction) | OMLX | `StructuredExtractionScorer` selected, all stages produce output | **Yes** — M7 extraction double-count fix |
| 10 | **`test_docker_run_generation`** | ingest → analyze → A/B → gate → promote/reject (generation) | OMLX | `LLMJudgeScorer` selected, judge role wired, all stages produce output | **Yes** — M7 verbose parse fix |
| 11 | **`test_docker_run_staged_analyzer`** | staged analyzer → A/B → gate → promote/reject | OMLX | Staged analyzer produces proposals, rejection context populated | **Yes** — M6 llm_provider routing, M9 staged cost |
| 12 | **`test_docker_run_mixed_domain`** | ingest → analyze → A/B → gate (30+ tasks) | OMLX | Correct scorer per task type, all stages produce output | **Yes** — M11 mixed-domain 30+ |
| 13 | **`test_docker_run_adversarial`** | inject bad edits → gate | OMLX | 5/5 blocked, FP/FN measured | **Yes** — M11 adversarial |
| 14 | `test_docker_propose_full` | analyze → propose → A/B → gate | OMLX | Proposals generated, gate decision, LLM I/O captured | **Yes** — M10 materialize guard, M5 batch_ready |
| 15 | **`test_docker_ab_cache`** | A/B cache hit/miss | OMLX | Cache hit on identical re-run, miss on different prompt | **Yes** — M1 cache |
| 16 | **`test_docker_materialize_guard`** | missing `old_text` → skip | OMLX | Proposal skipped, not silently A/B tested | **Yes** — M10 |

### v0.2.0 tests that are dropped or merged

- `test_docker_run_staged_analyzer` → kept and updated (v0.3.0 M6 changes)
- `test_docker_run_classification` → kept and updated (v0.3.0 M1 + M10 changes)

## 5. Config

```yaml
schema_version: 1
project:
  name: docker-full-loop
  registry_path: /config/registry
  trace_path: /config/traces.db
tasks:
  task_set_path: /config/corpus.yaml  # varies by test
  batch_size: 10
  sample_floor: 10
llm:
  provider: openai
  model: Qwen3.5-4B-4bit
  api_key: omlx-test
  base_url: http://host.docker.internal:8000/v1
  temperature: 0.0
  max_tokens: 4096
  timeout: 60
  extra_body: {}  # v0.3.0: configurable per-role
executor_role:
  provider: openai
  model: Qwen3.5-4B-4bit
  api_key: omlx-test
  base_url: http://host.docker.internal:8000/v1
analyzer_role:
  provider: openai
  model: Qwen3.5-4B-4bit
  api_key: omlx-test
  base_url: http://host.docker.internal:8000/v1
judge_role:
  provider: openai
  model: Qwen3.5-4B-4bit
  api_key: omlx-test
  base_url: http://host.docker.internal:8000/v1
ab_test:
  n_resamples: 100
  n_permutations: 100
  confidence_level: 0.95
  min_effect_size: 0.05
  cost_ceiling_usd: 0.50
  cache_enabled: true          # v0.3.0: new field
  task_timeout_seconds: 30     # v0.3.0: new field
gate:
  max_edit_distance: 20
  drift_threshold: 0.3
  near_miss_threshold: 0.5
  frozen_sections: []          # v0.3.0: new field
analyzer:
  max_proposals_per_batch: 3
  cost_ceiling_usd: 0.50
  max_edit_lines: 10           # v0.3.0: new field
trigger: batch
trace_retention_days: 90
```

## 6. Full Loop Test Assertions

Each full-loop test must verify:

```python
# CLI completed
assert result.returncode == 0

# LLM was called (analyzer + A/B test)
assert traffic_log.exists()
entries = [json.loads(l) for l in traffic_log.read_text().splitlines()]
assert len(entries) > 0

# Two-message format (M1 fix: system prompt as system role, task as user)
for entry in entries:
    messages = entry.get("messages", [])
    if len(messages) == 2:
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

# Each entry has full I/O, non-zero tokens and latency
for entry in entries:
    assert "messages" in entry
    assert "response" in entry
    assert entry["model"] == OMLX_MODEL
    assert entry["latency_ms"] > 0
    usage = entry.get("usage") or {}
    assert usage.get("completion_tokens", 0) > 0
    assert usage.get("prompt_tokens", 0) > 0

# CLI output shows all stages
stdout = result.stdout
assert "Analysis complete" in stdout
assert "A/B test" in stdout
assert "Gate:" in stdout

# A/B test produced valid statistics
import re
ab_match = re.search(r"A/B test:\s*(.+?)\s*\(p=([\d.]+),\s*n=(\d+)\)", stdout)
assert ab_match
p_value = float(ab_match.group(2))
n_tasks = int(ab_match.group(3))
assert 0.0 <= p_value <= 1.0
assert n_tasks > 0

# Registry state: v1 exists, Meta has changed_section if promoted
reg_dir = tmp_path / "registry"
v1_file = reg_dir / "v1.md"
v1_meta = reg_dir / "v1.meta.json"
assert v1_file.exists()
assert v1_meta.exists()
```

## 7. New Tests Detail

### 7.1 `test_docker_run_mixed_domain`

**Setup:**
- Config points to `field-test/corpus/synthetic/mixed-domain.yaml` (30+ tasks)
- Scorer auto-selected per task type via manifest metadata
- Same trace seeding pattern but with diverse task types

**Assertions:**
- `resolve_scorer()` selects correct scorer per task
- All stages produce output
- LLM I/O captured with non-zero tokens and latency

### 7.2 `test_docker_run_adversarial`

**Setup:**
- 5 intentionally bad edits injected as proposals
- Gate runs against each

**Assertions:**
- 5/5 blocked
- FP/FN rates measured
- Each rejection names the failing check

### 7.3 `test_docker_ab_cache`

**Setup:**
- First `run_ab_test(prompt_a, prompt_b, ...)` with cache enabled
- Second identical `run_ab_test(prompt_a, prompt_b, ...)` with cache enabled

**Assertions:**
- First call makes LLM calls
- Second call returns same result without LLM calls
- Cache key matches on `(task_set_hash, prompt_a, prompt_b, scorer_name, config_hash)`

### 7.4 `test_docker_materialize_guard`

**Setup:**
- Ingest traces with a proposal whose `old_text` is not in the current prompt
- Run `propose` or `run --once`

**Assertions:**
- Proposal is skipped (not silently A/B tested)
- Output contains "Skipping proposal" or equivalent warning
- Registry version unchanged

## 8. LLM Traffic Capture

`OpenAIProvider` writes every request/response to `AGENT_SELF_EDIT_LLM_LOG` (JSONL). Each entry:

```json
{
  "model": "Qwen3.5-4B-4bit",
  "base_url": "http://host.docker.internal:8000/v1",
  "messages": [
    {"role": "system", "content": "You are a prompt optimization analyst..."},
    {"role": "user", "content": "Failed traces: ..."}
  ],
  "temperature": 0.0,
  "response": "[{\"section\": \"...\", \"old_text\": \"...\", \"new_text\": \"...\", ...}]",
  "usage": {"prompt_tokens": 680, "completion_tokens": 243, "total_tokens": 923},
  "latency_ms": 12739
}
```

## 9. Results Structure

```
field-test/v0.3.0/results/docker/omlx/qwen3.5-4b-4bit/
  docker-run-classification.json
  docker-run-extraction.json
  docker-run-generation.json
  docker-run-staged-analyzer.json
  docker-run-mixed-domain.json
  docker-run-adversarial.json
  docker-propose-full.json
  llm-traffic-classification.jsonl
  llm-traffic-extraction.jsonl
  llm-traffic-generation.jsonl
  llm-traffic-staged-analyzer.jsonl
  llm-traffic-mixed-domain.jsonl
  llm-traffic-adversarial.jsonl
  llm-traffic-propose.jsonl
```

## 10. Test Runner

```bash
# Full v0.3.0 Docker test suite (16 tests)
pytest tests/test_docker.py -v -m docker --no-cov

# Individual tests
pytest tests/test_docker.py::test_docker_run_classification -v -m docker --no-cov
pytest tests/test_docker.py::test_docker_run_extraction -v -m docker --no-cov
pytest tests/test_docker.py::test_docker_run_generation -v -m docker --no-cov
pytest tests/test_docker.py::test_docker_run_staged_analyzer -v -m docker --no-cov
pytest tests/test_docker.py::test_docker_run_mixed_domain -v -m docker --no-cov
pytest tests/test_docker.py::test_docker_run_adversarial -v -m docker --no-cov
pytest tests/test_docker.py::test_docker_ab_cache -v -m docker --no-cov
pytest tests/test_docker.py::test_docker_materialize_guard -v -m docker --no-cov

# Or via the runner script
python field-test/scripts/run_docker_tests.py
```

Requires: Docker daemon running, OMLX server at `http://localhost:8000/v1`.

## 11. Environment

| Var | Purpose | Default |
|-----|---------|---------|
| `OMLX_URL` | Host OMLX endpoint | `http://localhost:8000/v1` |
| `OMLX_KEY` | OMLX API key | `omlx-test` |
| `OMLX_MODEL` | OMLX model name | `Qwen3.5-4B-4bit` |
| `AGENT_SELF_EDIT_LLM_LOG` | LLM traffic log path (in container) | `/results/llm-traffic-*.jsonl` |

## 12. v0.2.0 → v0.3.0 Docker Test Changes

| Aspect | v0.2.0 | v0.3.0 |
|--------|--------|--------|
| Total Docker tests | 12 | 16 |
| New tests | — | Mixed-domain, adversarial, A/B cache, materialize guard |
| A/B test format | Single message | Two-message (system + user) |
| Config schema | 26 fields | 30+ fields (`cache_enabled`, `task_timeout_seconds`, `max_edit_lines`, `frozen_sections`, `extra_body`) |
| Candidate prompt | `str.replace()` | `materialize_candidate_prompt()` with validation |
| Drift baseline | `current_prompt` | `original_prompt` (v1) |
| Gate atomicity | `check_all()` + separate log | `PromotionGate.check()` atomic |
| A/B result cache | None | Persistent SQLite `_ABResultCache` |
| Exception handling | `except Exception: pass` | Classified: rate-limit/transient/fatal |
| Heatmap | Bucketed by hypothesis | Bucketed by `changed_section` |
| Coverage gate | 92% | 91% |

## 13. References

- Issue #302 (Docker test plan)
- Issue #303 (Docker test authoring)
- Issue #304 (Docker test execution)
- [v0.2.0 Docker test plan](../v0.2.0/docker-test-plan.md)
- [WBS Part 6](../wbs/v0.3.0/wbs-v0.3.0-part6-field-test.md)