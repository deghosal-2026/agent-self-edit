# Docker Test Plan — AgentSelfEdit v0.1.0

> Docker tests for the self-improving agent prompt optimizer. The Docker image must build, reach the local OMLX LLM, and run the **complete self-edit loop** end-to-end: trace → analyze → A/B test → gate → promote.

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

## 2. Objectives

| # | Objective | What it proves |
|---|-----------|----------------|
| 1 | Image builds | `Dockerfile` produces a working image with `openai>=1.0` installed |
| 2 | OMLX reachable from host | Local OMLX server is up and serving the configured model |
| 3 | OMLX reachable from container | Container can reach host OMLX via `host.docker.internal` |
| 4 | CLI works | All 10 commands listed in `--help` |
| 5 | Config loads | `validate` and `status` work with OMLX-backed config |
| 6 | **Full loop runs** | `agent-self-edit run --once` (no `--dry-run`) completes: ingest → analyze → A/B test → gate → promote/reject |
| 7 | **Propose runs** | `agent-self-edit propose` (no `--dry-run`): analyze → propose → A/B test → gate |
| 8 | **LLM I/O captured** | Every LLM call's request and response written to disk for debuggability |
| 9 | **Prompt version changes** | Registry shows before/after prompt if gate promoted |

## 3. Architecture

```
┌──────────────────────────────────────────────────────────┐
│ Host (macOS)                                             │
│                                                          │
│  ┌─────────────┐     host.docker.internal    ┌────────┐  │
│  │ OMLX server │◄────────────────────────────│ Docker │  │
│  │ :8000/v1    │     OpenAI-compatible API    │ agent- │  │
│  │ Qwen3.5-9B  │                              │ self-  │  │
│  └─────────────┘                              │ edit   │  │
│                                                └────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ field-test/v0.1.0/results/docker/                  │  │
│  │   omlx/qwen3.5-4b-4bit/                            │  │
│  │     docker-run-full-loop.json    (structured)       │  │
│  │     docker-propose-full.json     (structured)       │  │
│  │     llm-traffic-run.jsonl        (raw LLM I/O)     │  │
│  │     llm-traffic-propose.jsonl    (raw LLM I/O)     │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ docs/field-test/v0.1.0/                             │  │
│  │   docker-field-test-summary.md   (human report)    │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## 4. Test Matrix

| # | Test | Stages exercised | LLM | Pass condition | Issue |
|---|------|------------------|-----|----------------|-------|
| 1 | `test_docker_build` | build | none | exit 0, image exists | — |
| 2 | `test_omlx_is_up` | connectivity | none | non-empty model list | — |
| 3 | `test_omlx_model_available` | connectivity | none | `Qwen3.5-9B-MLX-4bit` found | — |
| 4 | `test_omlx_reachable_from_container` | connectivity | none | model visible from container | — |
| 5 | `test_docker_help` | CLI | none | all 10 commands listed | — |
| 6 | `test_docker_validate` | config | none | exit 0 or 2 | — |
| 7 | `test_docker_status` | config | none | exit 0, 1, or 2 | — |
| 8 | `test_docker_run_full_loop` | **ingest → analyze → A/B test → gate → promote** | OMLX | all stages produce output, LLM I/O captured | #98 |
| 9 | `test_docker_propose_full` | **analyze → propose → A/B test → gate** | OMLX | proposals generated, gate decision, LLM I/O captured | #98 |

### Current state

Tests 1-7 pass. Tests 8-9 **now pass** (previously broken with `--dry-run`, fixed — see #98 closed).

## 5. Full Loop Test (the critical test)

This is the test that proves the project works. It must exercise every stage of the self-edit loop against real OMLX.

### 5.1 Setup

The container needs:

```
/config/
  agent-self-edit.yaml     ← config with provider=openai, model=Qwen3.5-9B-MLX-4bit,
                            base_url=host.docker.internal:8000/v1, task_set_path=/config/classification.yaml
  classification.yaml      ← held-out task set (30 classification tasks, ExactMatch scorer)
  registry/                ← prompt registry (initialized with baseline prompt)
  traces.db                 ← trace store (seeded with 10 failed classification traces)
/results/                  ← mounted from field-test/v0.1.0/results/docker/omlx/qwen3.5-4b-4bit/
```

### 5.2 Execution

```bash
docker run --rm --network=host \
  -v /tmp/test-config:/config \
  -v field-test/v0.1.0/results/docker/omlx/qwen3.5-4b-4bit:/results \
  -e AGENT_SELF_EDIT_LLM_LOG=/results/llm-traffic-run.jsonl \
  agent-self-edit:test \
  run --config /config/agent-self-edit.yaml --once
```

**No `--dry-run`.** The loop must execute:

1. **Ingest** — TraceStore loads 10 failed traces, batch is ready
2. **Analyze** — LLM receives the analyzer system prompt + failed traces, returns JSON proposals
3. **A/B test** — `run_ab_test()` runs both prompts (current + proposed) against the classification task set via OMLX, scores with ExactMatch, computes win rate + bootstrap CI + permutation p-value
4. **Gate** — `check_all()` runs 6 deterministic checks: sample floor, effect size, confidence, frozen sections, edit distance, drift
5. **Promote or reject** — if gate says promote, registry creates new prompt version; if reject, archived with reasoning

### 5.3 Assertions

```python
# CLI completed
assert result.returncode == 0

# LLM was called (analyzer + A/B test)
assert traffic_log.exists()
entries = [json.loads(l) for l in traffic_log.read_text().splitlines()]
assert len(entries) >= 2  # at least 1 analyzer call + 1 A/B test call

# Each entry has full I/O
for entry in entries:
    assert "messages" in entry     # LLM input
    assert "response" in entry     # LLM output
    assert entry["model"] == OMLX_MODEL
    assert entry["latency_ms"] > 0

# CLI output shows all stages
assert "Analysis complete" in stdout        # stage 2
assert "A/B test" in stdout                 # stage 3
assert "Gate:" in stdout                    # stage 4
# "Promoted" or "Rejected" — either is valid (gate decides)
```

### 5.4 Config

```yaml
schema_version: 1
project:
  name: docker-full-loop
  registry_path: /config/registry
  trace_path: /config/traces.db
tasks:
  task_set_path: /config/classification.yaml  # REQUIRED for A/B test
  batch_size: 10
  sample_floor: 10
llm:
  provider: openai
  model: Qwen3.5-9B-MLX-4bit
  api_key: omlx-test
  base_url: http://host.docker.internal:8000/v1
  temperature: 0.0
  max_tokens: 4096
  timeout: 60
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

### 5.5 Seeded traces

10 failed classification traces — same `task_input` as the classification task set but `final_output` is wrong and `success: false`:

```json
{"task_id": "ft-001", "task_input": "My billing page shows the wrong amount.", "final_output": "billing", "expected_output": "technical", "success": false, "timestamp": "2026-09-01T10:00:00Z"}
```

## 6. LLM Traffic Capture

The `OpenAIProvider` writes every request/response to `AGENT_SELF_EDIT_LLM_LOG` (env var, JSONL append-mode). Each entry:

```json
{
  "model": "Qwen3.5-9B-MLX-4bit",
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

The container mounts `results/docker/omlx/qwen3.5-4b-4bit/` to `/results` and sets `AGENT_SELF_EDIT_LLM_LOG=/results/llm-traffic-*.jsonl`.

## 7. Results Structure

```
field-test/v0.1.0/results/docker/omlx/qwen3.5-4b-4bit/
  docker-run-full-loop.json          ← structured: meta + per-stage results + LLM I/O
  docker-propose-full.json           ← structured: meta + per-stage results + LLM I/O
  llm-traffic-run.jsonl              ← raw LLM request/response pairs (all calls)
  llm-traffic-propose.jsonl          ← raw LLM request/response pairs (all calls)
```

Summary report: `docs/field-test/v0.1.0/docker-field-test-summary.md`

## 8. Environment

| Var | Purpose | Default |
|-----|---------|---------|
| `OMLX_URL` | Host OMLX endpoint | `http://localhost:8000/v1` |
| `OMLX_KEY` | OMLX API key | `omlx-test` |
| `OMLX_MODEL` | OMLX model name | `Qwen3.5-9B-MLX-4bit` |
| `AGENT_SELF_EDIT_LLM_LOG` | LLM traffic log path (in container) | `/results/llm-traffic-*.jsonl` |

Container reaches OMLX via `host.docker.internal:8000` (not `localhost`).

## 9. Runner Scripts

```bash
# Full pytest suite (9 tests)
python field-test/scripts/run_docker_tests.py

# Direct
pytest tests/test_docker.py -v -m docker --no-cov
```

Requires: Docker daemon running, OMLX server at `http://localhost:8000/v1`.

## 10. Open Issues

| Issue | Problem | Status |
|-------|---------|--------|
| [#98](https://github.com/deghosal-2026/agent-self-edit/issues/98) | Docker integration test only runs `--dry-run` — skips A/B test and gate | closed (fixed) |
| [#99](https://github.com/deghosal-2026/agent-self-edit/issues/99) | `run_docker_field_test.py` is stale — duplicates `test_docker.py` | open |
| [#102](https://github.com/deghosal-2026/agent-self-edit/issues/102) | WBS row 23 marked ✅ but acceptance criteria never fully tested | open |
| [#103](https://github.com/deghosal-2026/agent-self-edit/issues/103) | A/B test engine not exercised in any field test | closed (fixed) |
