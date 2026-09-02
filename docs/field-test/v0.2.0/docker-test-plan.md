# Docker Test Plan — AgentSelfEdit v0.2.0

> Docker tests for the v0.2.0 self-improving prompt optimizer. Builds on the v0.1.0 Docker test suite with multi-domain, model-role separation, and staged analyzer coverage.

## 1. What This Project Does

AgentSelfEdit is a sidecar that observes execution traces and rewrites its own system prompt:

```
Agent executes task ──▶ Execution trace stored (SQLite)
                                │
                                ▼
                      Feedback Analyzer (LLM)
                      reviews traces, proposes concrete edits,
                      each with a written hypothesis
                                │
                                ▼
       ─────────────────────  A/B Test Engine  ─────────────────────
         candidate edit vs current prompt on a held-out task set:
         win rate, bootstrap confidence interval, effect size,
         permutation p-value, per-task breakdown
       ────────────────────────────────────────────────────────────
                                │
                                ▼
                Promotion Gate (deterministic checks)
                1. Sample floor     4. Frozen sections
                2. Effect size      5. Edit-distance limit
                3. Confidence p-val 6. Drift detection
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
          Promoted         Near-miss        Rejected
     prompt updated in     logged for       archived with
     versioned Registry    human review     full reasoning
```

The docker test must prove this loop works inside a container against a real LLM.

## 2. What Changed in v0.2.0

| Change | Impact on Docker tests |
|--------|-----------------------|
| **Model role separation** (executor/analyzer/judge) | Need to test multi-role configs |
| **Multi-domain corpora** (extraction, generation, mixed) | Full loop must work on non-classification benchmarks |
| **Staged analyzer** (4-stage pipeline) | Verify staged mode works inside container |
| **Structured extraction scorer** | Extraction benchmark must use correct scorer |
| **LLMJudgeScorer with rubrics** | Generation benchmark needs judge role wired |
| **Scorer consistency enforcement** | Manifest-based scorer selection must work |
| **Row-safe trace ack** (in-flight reservation) | No regression in trace processing |
| **Promotion-seeking corpus** | Larger A/B set exercises more varied prompts |
| **Sentinel benchmark** | Verify sentinel runs alongside A/B |

## 3. Objectives

| # | Objective | What it proves |
|---|-----------|----------------|
| 1 | Image builds | `Dockerfile` produces a working image with `[llm]` extra |
| 2 | OMLX reachable from host & container | Local OMLX server is up and serving the configured model |
| 3 | CLI works | All 10 commands listed in `--help` |
| 4 | Config loads | `validate` and `status` work with OMLX-backed config |
| 5 | **Classification full loop runs** | `run --once` completes: ingest → analyze → A/B test → gate → promote/reject on classification corpus |
| 6 | **Extraction full loop runs** | Same loop on extraction corpus with `StructuredExtractionScorer` |
| 7 | **Generation full loop runs** | Same loop on generation corpus with `LLMJudgeScorer` (judge role) |
| 8 | **Model role separation works** | `executor_role` / `analyzer_role` / `judge_role` configs are respected |
| 9 | **Staged analyzer works** | `analyze_batch(..., staged=True)` produces proposals |
| 10 | **Propose runs** | `propose` (no `--dry-run`) completes with real LLM |
| 11 | **LLM I/O captured** | Every LLM call's request and response written to disk |
| 12 | **Prompt version changes** | Registry shows before/after prompt |

## 4. Architecture

```
┌──────────────────────────────────────────────────────────┐
│ Host (macOS)                                             │
│                                                          │
│  ┌─────────────┐     host.docker.internal    ┌────────┐  │
│  │ OMLX server │◄────────────────────────────│ Docker │  │
│  │ :8000/v1    │     OpenAI-compatible API    │ agent- │  │
│  │ Qwen3.5-4B  │                              │ self-  │  │
│  └─────────────┘                              │ edit   │  │
│                                                └────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ field-test/v0.2.0/results/docker/                   │  │
│  │   omlx/qwen3.5-4b-4bit/                             │  │
│  │     docker-run-classification.json  (structured)    │  │
│  │     docker-run-extraction.json      (structured)    │  │
│  │     docker-run-generation.json      (structured)    │  │
│  │     docker-run-staged-analyzer.json (structured)    │  │
│  │     docker-propose-full.json         (structured)   │  │
│  │     llm-traffic-*.jsonl              (raw LLM I/O)  │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ docs/field-test/v0.2.0/                              │  │
│  │   docker-field-test-summary.md   (human report)     │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## 5. Test Matrix

| # | Test | Stages exercised | LLM | Pass condition | New in v0.2.0? |
|---|------|------------------|-----|----------------|-----------------|
| 1 | `test_docker_build` | build | none | exit 0, image exists | No (reused) |
| 2 | `test_omlx_is_up` | connectivity | none | non-empty model list | No (reused) |
| 3 | `test_omlx_model_available` | connectivity | none | model found | No (reused) |
| 4 | `test_omlx_reachable_from_container` | connectivity | none | model visible from container | No (reused) |
| 5 | `test_docker_help` | CLI | none | all 10 commands listed | No (reused) |
| 6 | `test_docker_validate` | config | none | exit 0 or 2 | No (reused) |
| 7 | `test_docker_status` | config | none | exit 0, 1, or 2 | No (reused) |
| 8 | **`test_docker_run_classification`** | ingest → analyze → A/B → gate → promote/reject | OMLX | All stages produce output, LLM I/O captured, distinct prompts, tokens>0, latency>0, A/B p-value in [0,1] | **Yes** — uses new corpus, scorer consistency |
| 9 | **`test_docker_run_extraction`** | ingest → analyze → A/B → gate → promote/reject on extraction corpus | OMLX | StructuredExtractionScorer selected, all stages produce output, LLM I/O captured | **Yes** — new domain |
| 10 | **`test_docker_run_generation`** | ingest → analyze → A/B → gate → promote/reject on generation corpus | OMLX | LLMJudgeScorer selected, judge role wired, all stages produce output | **Yes** — new domain, judge role |
| 11 | **`test_docker_run_staged_analyzer`** | staged analyzer → A/B → gate → promote/reject | OMLX | Staged analyzer produces proposals, rejection context populated | **Yes** — new feature |
| 12 | `test_docker_propose_full` | analyze → propose → A/B → gate | OMLX | Proposals generated, gate decision, LLM I/O captured | No (reused, path updated) |

### v0.1.0 tests that are dropped or merged

- `test_docker_run_full_loop_omlx` → replaced by `test_docker_run_classification` (same concept, new corpus path)
- `test_docker_propose_full_omlx` → kept as `test_docker_propose_full` (updated path)

## 6. Full Loop Test (the critical test)

This is the test that proves the project works. It must exercise every stage of the self-edit loop against real OMLX.

### 6.1 Setup

The container needs:

```
/config/
  agent-self-edit.yaml     ← config with provider=openai, executor/analyzer/judge roles,
                             task_set_path=/config/corpus.yaml
  corpus.yaml              ← held-out task set (varies by test: classification, extraction, generation)
  registry/                ← prompt registry (initialized with baseline prompt)
  traces.db                 ← trace store (seeded with 10 failed traces)
/results/                  ← mounted from field-test/v0.2.0/results/docker/omlx/qwen3.5-4b-4bit/
```

### 6.2 Execution

```bash
docker run --rm --network=host \
  -v /tmp/test-config:/config \
  -v field-test/v0.2.0/results/docker/omlx/qwen3.5-4b-4bit:/results \
  -e AGENT_SELF_EDIT_LLM_LOG=/results/llm-traffic-classification.jsonl \
  agent-self-edit:test \
  run --config /config/agent-self-edit.yaml --once
```

**No `--dry-run`.** The loop must execute:

1. **Ingest** — TraceStore loads 10 failed traces, batch is ready
2. **Analyze** — LLM receives the analyzer system prompt + failed traces, returns JSON proposals
3. **A/B test** — `run_ab_test()` runs both prompts (current + proposed) against the task set via OMLX, scores with the resolver-selected scorer, computes win rate + bootstrap CI + permutation p-value
4. **Gate** — `check_all()` runs 6 deterministic checks: sample floor, effect size, confidence, frozen sections, edit distance, drift
5. **Promote or reject** — if gate says promote, registry creates new prompt version; if reject, archived with reasoning

### 6.3 Assertions

```python
# CLI completed
assert result.returncode == 0

# LLM was called (analyzer + A/B test)
assert traffic_log.exists()
entries = [json.loads(l) for l in traffic_log.read_text().splitlines()]
assert len(entries) > 0  # at least 1 LLM call

# Each entry has full I/O, non-zero tokens and latency
for entry in entries:
    assert "messages" in entry     # LLM input
    assert "response" in entry     # LLM output
    assert entry["model"] == OMLX_MODEL
    assert entry["latency_ms"] > 0
    usage = entry.get("usage") or {}
    assert usage.get("completion_tokens", 0) > 0
    assert usage.get("prompt_tokens", 0) > 0

# CLI output shows all stages
stdout = result.stdout
assert "Analysis complete" in stdout        # stage 2
assert "A/B test" in stdout                 # stage 3
assert "Gate:" in stdout                    # stage 4

# A/B test used ≥2 distinct prompts
if len(entries) > 1:
    ab_calls = entries[1:]
    prompt_contents = set()
    for e in ab_calls:
        content = e["messages"][0]["content"]
        prompt_part = content.split("\n---\n")[0] if "\n---\n" in content else content
        prompt_contents.add(prompt_part[:200])
    assert len(prompt_contents) >= 2

# A/B test produced valid statistics (p-value in [0,1])
import re
ab_match = re.search(r"A/B test:\s*(.+?)\s*\(p=([\d.]+),\s*n=(\d+)\)", stdout)
assert ab_match
p_value = float(ab_match.group(2))
n_tasks = int(ab_match.group(3))
assert 0.0 <= p_value <= 1.0
assert n_tasks > 0

# Registry state inspection
reg_dir = tmp_path / "registry"
v1_file = reg_dir / "v1.md"
v1_meta = reg_dir / "v1.meta.json"
assert reg_dir.exists()
assert v1_file.exists()
assert v1_meta.exists()
```

### 6.4 Config

```yaml
schema_version: 1
project:
  name: docker-full-loop
  registry_path: /config/registry
  trace_path: /config/traces.db
tasks:
  task_set_path: /config/corpus.yaml  # REQUIRED for A/B test — varies by domain
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
gate:
  max_edit_distance: 20
  drift_threshold: 0.3
  near_miss_threshold: 0.5
analyzer:
  max_proposals_per_batch: 3
  cost_ceiling_usd: 0.50
trigger: batch
trace_retention_days: 90
```

### 6.5 Seeded traces

10 failed classification traces — each with a different task input loaded from the corpus to ensure diversity:

```json
{"task_id": "t0", "task_input": "classify this ticket: 'My billing page shows the wrong amount for my subscription.'", "final_output": "other", "expected_output": "technical", "success": false, ...}
{"task_id": "t1", "task_input": "classify this ticket: 'I was charged twice for the same plan.'", "final_output": "other", "expected_output": "billing", "success": false, ...}
```

For extraction tests, traces use extraction-style inputs. For generation tests, traces use generation-style inputs.

## 7. New Tests Detail

### 7.1 `test_docker_run_classification`

Same as v0.1.0 full loop but uses the consolidated `field-test/corpus/synthetic/` path and the new corpus structure. Verifies scorer consistency enforcement works (manifest-based `SingleLabelScorer` selection).

### 7.2 `test_docker_run_extraction`

**Setup:**
- Config points to `field-test/corpus/synthetic/extraction.yaml`
- Scorer auto-selected: `StructuredExtractionScorer`
- Same trace seeding pattern but with extraction tasks

**Assertions:**
- `StructuredExtractionScorer` is used
- All stages produce output
- LLM I/O captured with non-zero tokens and latency

### 7.3 `test_docker_run_generation`

**Setup:**
- Config points to `field-test/corpus/synthetic/generation.yaml`
- `judge_role` configured with same OMLX model
- Scorer auto-selected: `LLMJudgeScorer`
- Judge provider wired from `judge_role` config

**Assertions:**
- `LLMJudgeScorer` is used
- Judge role is populated from `judge_role` config
- All stages produce output
- LLM I/O captured with non-zero tokens and latency

### 7.4 `test_docker_run_staged_analyzer`

**Setup:**
- Same config as classification
- `analyze_batch(..., staged=True)` is the default

**Assertions:**
- Staged analyzer produces proposals
- Analyzer output includes structured failure patterns
- All stages downstream still work

## 8. LLM Traffic Capture

The `OpenAIProvider` writes every request/response to `AGENT_SELF_EDIT_LLM_LOG` (env var, JSONL append-mode). Each entry:

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

This captures:
- **Analyzer calls** — the system prompt + failed traces → JSON proposals
- **A/B test calls** — each prompt variant run against each task in the held-out set
- **Judge calls** (generation only) — evaluation rubric + output → score

The container mounts `results/docker/omlx/qwen3.5-4b-4bit/` to `/results` and sets `AGENT_SELF_EDIT_LLM_LOG=/results/llm-traffic-*.jsonl`.

## 9. Results Structure

```
field-test/v0.2.0/results/docker/omlx/qwen3.5-4b-4bit/
  docker-run-classification.json        ← structured: meta + stages + LLM I/O
  docker-run-extraction.json            ← structured: extraction domain
  docker-run-generation.json            ← structured: generation domain + judge role
  docker-run-staged-analyzer.json       ← structured: staged analyzer test
  docker-propose-full.json              ← structured: propose command
  llm-traffic-classification.jsonl      ← raw LLM request/response pairs
  llm-traffic-extraction.jsonl          ← raw LLM request/response pairs
  llm-traffic-generation.jsonl          ← raw LLM request/response pairs
  llm-traffic-staged-analyzer.jsonl     ← raw LLM request/response pairs
  llm-traffic-propose.jsonl             ← raw LLM request/response pairs
```

Summary report: `docs/field-test/v0.2.0/docker-field-test-summary.md`

## 10. Test Runner

```bash
# Full v0.2.0 Docker test suite (12 tests)
pytest tests/test_docker.py -v -m docker --no-cov

# Individual tests
pytest tests/test_docker.py::test_docker_run_classification -v -m docker --no-cov
pytest tests/test_docker.py::test_docker_run_extraction -v -m docker --no-cov
pytest tests/test_docker.py::test_docker_run_generation -v -m docker --no-cov
pytest tests/test_docker.py::test_docker_run_staged_analyzer -v -m docker --no-cov

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

Container reaches OMLX via `host.docker.internal:8000` (not `localhost`).

## 12. Open Issues

| Issue | Problem | Status |
|-------|---------|--------|
| #198 | Add scoring rubrics to generation corpus | Open |
| #199 | Expand mixed-domain corpus to 30+ tasks | Open |
| #200 | Create real-trace gold corpus | Open |