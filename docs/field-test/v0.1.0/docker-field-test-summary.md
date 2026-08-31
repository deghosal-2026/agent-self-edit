# Docker Field Test Summary — AgentSelfEdit v0.1.0

**Date:** 2026-08-31T07:00:49Z
**Image:** `agent-self-edit:test`
**OMLX Model:** `Qwen3.5-9B-MLX-4bit`
**OMLX Endpoint:** `http://localhost:8000/v1`

## Summary

**2/2 tests passed** (0 failed)

| # | Test | Result | LLM Calls | Exit Code |
|---|------|--------|------------|-----------|
| 1 | `docker-propose-dry-run-omlx` | PASS | 1 | 0 |
| 2 | `docker-run-dry-run-omlx` | PASS | 1 | 0 |

## Observations

- **docker-propose-dry-run-omlx**: LLM latency 10506ms (>10s)
- **docker-propose-dry-run-omlx**: 923 tokens (680 in / 243 out)
- **docker-run-dry-run-omlx**: LLM latency 12785ms (>10s)
- **docker-run-dry-run-omlx**: 923 tokens (680 in / 243 out)

## Issues

- None.

## Per-Test Details

Structured JSON results are in `field-test/v0.1.0/results/docker/omlx/qwen3.5-9b-mlx-4bit/` (2 files).

### docker-propose-dry-run-omlx

- **Exit code:** 0
- **LLM calls:** 1
- **JSON:** `field-test/v0.1.0/results/docker/omlx/qwen3.5-9b-mlx-4bit/docker-propose-dry-run-omlx.json`

### docker-run-dry-run-omlx

- **Exit code:** 0
- **LLM calls:** 1
- **JSON:** `field-test/v0.1.0/results/docker/omlx/qwen3.5-9b-mlx-4bit/docker-run-dry-run-omlx.json`

