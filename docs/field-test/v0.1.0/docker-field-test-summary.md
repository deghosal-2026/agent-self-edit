# Docker Field Test Summary — AgentSelfEdit v0.1.0

**Date:** 2026-09-01T00:09:45Z
**Image:** `agent-self-edit:test`
**OMLX Model:** `Qwen3.5-4B-4bit`
**OMLX Endpoint:** `http://localhost:8000/v1`

## Summary

**2/2 tests passed** (0 failed)

| # | Test | Result | LLM Calls | Exit Code |
|---|------|--------|------------|-----------|
| 1 | `docker-propose-full-omlx` | PASS | 11 | 0 |
| 2 | `docker-run-full-loop-omlx` | PASS | 11 | 0 |

## Observations

- **docker-propose-full-omlx**: 926 tokens (680 in / 246 out)
- **docker-propose-full-omlx**: 203 tokens (35 in / 168 out)
- **docker-propose-full-omlx**: 77 tokens (76 in / 1 out)
- **docker-propose-full-omlx**: 415 tokens (33 in / 382 out)
- **docker-propose-full-omlx**: 75 tokens (74 in / 1 out)
- **docker-propose-full-omlx**: 217 tokens (34 in / 183 out)
- **docker-propose-full-omlx**: 143 tokens (75 in / 68 out)
- **docker-propose-full-omlx**: 184 tokens (33 in / 151 out)
- **docker-propose-full-omlx**: 163 tokens (74 in / 89 out)
- **docker-propose-full-omlx**: LLM latency 10541ms (>10s)
- **docker-propose-full-omlx**: 457 tokens (35 in / 422 out)
- **docker-propose-full-omlx**: 166 tokens (76 in / 90 out)
- **docker-run-full-loop-omlx**: 926 tokens (680 in / 246 out)
- **docker-run-full-loop-omlx**: 203 tokens (35 in / 168 out)
- **docker-run-full-loop-omlx**: 77 tokens (76 in / 1 out)
- **docker-run-full-loop-omlx**: 415 tokens (33 in / 382 out)
- **docker-run-full-loop-omlx**: 75 tokens (74 in / 1 out)
- **docker-run-full-loop-omlx**: 217 tokens (34 in / 183 out)
- **docker-run-full-loop-omlx**: 143 tokens (75 in / 68 out)
- **docker-run-full-loop-omlx**: 184 tokens (33 in / 151 out)
- **docker-run-full-loop-omlx**: 163 tokens (74 in / 89 out)
- **docker-run-full-loop-omlx**: LLM latency 10454ms (>10s)
- **docker-run-full-loop-omlx**: 457 tokens (35 in / 422 out)
- **docker-run-full-loop-omlx**: 166 tokens (76 in / 90 out)

## Issues

- None.

## Per-Test Details

Structured JSON results are in `field-test/v0.1.0/results/docker/omlx/qwen3.5-4b-4bit/` (2 files).

### docker-propose-full-omlx

- **Exit code:** 0
- **LLM calls:** 11
- **JSON:** `field-test/v0.1.0/results/docker/omlx/qwen3.5-4b-4bit/docker-propose-full-omlx.json`

### docker-run-full-loop-omlx

- **Exit code:** 0
- **LLM calls:** 11
- **JSON:** `field-test/v0.1.0/results/docker/omlx/qwen3.5-4b-4bit/docker-run-full-loop-omlx.json`

