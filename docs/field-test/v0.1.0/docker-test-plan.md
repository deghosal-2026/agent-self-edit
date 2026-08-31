# Docker Test Plan — AgentSelfEdit v0.1.0

> Docker image build, smoke test, OMLX connectivity, and full-loop integration test for the self-improvement loop.

## 1. Objectives

1. **Build** — the Docker image builds successfully from `Dockerfile`.
2. **CLI smoke** — `agent-self-edit --help` works inside the container, all 10 commands listed.
3. **OMLX connectivity** — container can reach the host OMLX server and the configured model is available.
4. **Full loop integration** — the complete self-edit loop runs against real OMLX inside the container: ingest → analyze → propose → A/B test → gate → promote. LLM I/O captured.

## 2. Architecture

```
┌─────────────────────────────────────────────────────┐
│ Host (macOS)                                        │
│  ┌─────────────┐         ┌──────────────────────┐   │
│  │ OMLX server │◄────────│ Docker container     │   │
│  │ :8000/v1    │  host.  │ agent-self-edit      │   │
│  │ Qwen3.5-9B  │ docker. │  ingest → analyze    │   │
│  └─────────────┘ internal│  → A/B test → gate   │   │
│                         │  → promote            │   │
│                         └──────────────────────┘   │
│  ┌──────────────────────────────────────────────┐ │
│  │ field-test/v0.1.0/results/docker/             │ │
│  │   omlx/qwen3.5-9b-mlx-4bit/                    │ │
│  │     *-results.json  (per-test structured)       │ │
│  │     llm-traffic-*.jsonl (raw LLM I/O)          │ │
│  └──────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

## 3. Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage build: builder stage (pip install build → wheel + openai), runtime stage (pip install wheel → run) |
| `docker-compose.yml` | Defines the `agent-self-edit` service with volume mounts |
| `tests/test_docker.py` | Docker tests (marked `pytest.mark.docker`) — build, OMLX connectivity, smoke, full loop |
| `field-test/scripts/run_docker_tests.py` | Runner script: `pytest tests/test_docker.py -m docker` |
| `field-test/scripts/run_docker_field_test.py` | Standalone end-to-end test (to be rewritten — see #99) |

## 4. Test Matrix

| # | Test | What it verifies | LLM | Pass condition |
|---|------|------------------|-----|----------------|
| 1 | `test_docker_build` | `docker build` succeeds | none | exit 0, image exists |
| 2 | `test_omlx_is_up` | Host OMLX `/v1/models` reachable | none | non-empty model list |
| 3 | `test_omlx_model_available` | `Qwen3.5-9B-MLX-4bit` in model list | none | model found |
| 4 | `test_omlx_reachable_from_container` | Container reaches OMLX via `host.docker.internal` | none | model visible from container |
| 5 | `test_docker_help` | `--help` lists all 10 commands | none | all commands present |
| 6 | `test_docker_validate` | `validate` loads OMLX config | none | exit 0 or 2 |
| 7 | `test_docker_status` | `status` runs with OMLX config | none | exit 0, 1, or 2 |
| 8 | `test_docker_run_full_loop_omlx` | **Full loop** (not dry-run): ingest → analyze → A/B test → gate → promote | OMLX | all stages produce output, LLM I/O captured |
| 9 | `test_docker_propose_omlx` | `propose` (no dry-run): analyze → propose → A/B test → gate | OMLX | proposals generated, gate decision made, LLM I/O captured |

### Current gap (issues #98, #103)

Tests 8 and 9 currently run with `--dry-run`, which **skips A/B test and gate** (`run.py:46`). They must be rewritten to run the full loop with a configured task set so A/B test and gate execute.

## 5. Test Details

### 5.1 Build Test

```bash
docker build -t agent-self-edit:test .
```

- Image must build without errors.
- Image must include `openai>=1.0` package.

### 5.2 OMLX Connectivity Tests

```bash
# From host
curl http://localhost:8000/v1/models -H "Authorization: Bearer omlx-test"

# From container (via host.docker.internal)
docker run --rm --network=host --entrypoint python3 agent-self-edit:test -c "
import urllib.request, json
req = urllib.request.Request('http://host.docker.internal:8000/v1/models',
    headers={'Authorization': 'Bearer omlx-test'})
resp = urllib.request.urlopen(req, timeout=10)
print(json.loads(resp.read()))
"
```

### 5.3 CLI Smoke Test

```bash
docker run --rm agent-self-edit:test --help
```

- Must output usage text listing all 10 commands: `init`, `run`, `status`, `diff`, `rollback`, `guardrails`, `lineage`, `propose`, `ingest`, `validate`.
- Exit code 0.

### 5.4 Full Loop Integration Test (the real test)

This is the critical test. It must exercise the **entire self-edit loop** against OMLX:

```
1. Mount a volume with:
   - config.yaml (provider=openai, model=Qwen3.5-9B-MLX-4bit, base_url=host.docker.internal:8000/v1)
   - task_set.yaml (classification — so A/B test can run)
   - registry/ (with initial prompt version)
   - traces.db (with failed traces)

2. Run: agent-self-edit run --once --config /config/agent-self-edit.yaml
   (NO --dry-run)

3. Verify each stage:
   - Ingest: traces loaded
   - Analyze: LLM called with analyzer prompt → proposals returned
   - A/B test: run_ab_test() called with task set → winner determined
   - Gate: check_all() called → decision (promote/reject/near_miss)
   - Promote (if gate passes): registry.create() → new prompt version

4. Capture:
   - LLM input (messages) and output (response) for every LLM call
   - Latency, token usage per call
   - Proposals, gate decisions, promotions
   - Write to results/docker/omlx/qwen3.5-9b-mlx-4bit/
```

### 5.5 Propose Test

```
1. Same setup as 5.4

2. Run: agent-self-edit propose --config /config/agent-self-edit.yaml
   (NO --dry-run)

3. Verify:
   - Analyze: LLM called → proposals returned
   - A/B test: run_ab_test() → winner
   - Gate: check_all() → decision
   - LLM I/O captured
```

## 6. LLM Traffic Capture

The `OpenAIProvider` writes every request/response to `AGENT_SELF_EDIT_LLM_LOG` (env var, JSONL append-mode). Each entry:

```json
{
  "model": "Qwen3.5-9B-MLX-4bit",
  "base_url": "http://host.docker.internal:8000/v1",
  "messages": [{"role": "user", "content": "..."}],
  "temperature": 0.0,
  "response": "...",
  "usage": {"prompt_tokens": 680, "completion_tokens": 243, "total_tokens": 923},
  "latency_ms": 12739
}
```

The container mounts `field-test/v0.1.0/results/docker/omlx/qwen3.5-9b-mlx-4bit/` to `/results` and sets `AGENT_SELF_EDIT_LLM_LOG=/results/llm-traffic-*.jsonl`.

## 7. Results Structure

```
field-test/v0.1.0/results/docker/omlx/qwen3.5-9b-mlx-4bit/
  docker-run-full-loop-omlx.json         ← per-test structured result
  docker-propose-omlx.json
  llm-traffic-run.jsonl                  ← raw LLM request/response pairs
  llm-traffic-propose.jsonl
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

## 9. CI Integration

Docker tests are excluded from the default `pytest` run (marked `@pytest.mark.docker`). Run them explicitly:

```bash
# Via runner script
python field-test/scripts/run_docker_tests.py

# Direct
pytest tests/test_docker.py -v -m docker --no-cov
```

Requires: Docker daemon running, OMLX server at `http://localhost:8000/v1`.

## 10. Open Issues

| Issue | Problem |
|-------|---------|
| [#98](https://github.com/deghosal-2026/agent-self-edit/issues/98) | Docker integration test only runs `--dry-run` — skips A/B test and gate |
| [#99](https://github.com/deghosal-2026/agent-self-edit/issues/99) | `run_docker_field_test.py` is stale — duplicates `test_docker.py` |
| [#102](https://github.com/deghosal-2026/agent-self-edit/issues/102) | WBS row 23 marked ✅ but acceptance criteria never fully tested |
| [#103](https://github.com/deghosal-2026/agent-self-edit/issues/103) | A/B test engine not exercised in any field test |
