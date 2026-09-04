# Docker Field Test Summary — AgentSelfEdit v0.2.0

**Date:** 2026-09-03T01:09:19Z
**Image:** `agent-self-edit:test`
**OMLX Model:** `Qwen3.5-4B-4bit`
**OMLX Endpoint:** `http://localhost:8000/v1`

## Summary

**5/5 tests passed** (0 failed)

| # | Test | Result | LLM Calls | Exit Code |
|---|------|--------|------------|-----------|
| 1 | `docker-propose-full` | PASS | 13 | 0 |
| 2 | `docker-run-classification` | PASS | 13 | 0 |
| 3 | `docker-run-extraction` | PASS | 13 | 0 |
| 4 | `docker-run-generation` | PASS | 23 | 0 |
| 5 | `docker-run-staged-analyzer` | PASS | 13 | 0 |

## Observations

- **docker-propose-full**: 777 tokens (572 in / 205 out)
- **docker-propose-full**: 423 tokens (303 in / 120 out)
- **docker-propose-full**: 621 tokens (469 in / 152 out)
- **docker-propose-full**: 203 tokens (35 in / 168 out)
- **docker-propose-full**: 108 tokens (65 in / 43 out)
- **docker-propose-full**: LLM latency 10110ms (>10s)
- **docker-propose-full**: 415 tokens (33 in / 382 out)
- **docker-propose-full**: 119 tokens (63 in / 56 out)
- **docker-propose-full**: 217 tokens (34 in / 183 out)
- **docker-propose-full**: 131 tokens (64 in / 67 out)
- **docker-propose-full**: 184 tokens (33 in / 151 out)
- **docker-propose-full**: 149 tokens (63 in / 86 out)
- **docker-propose-full**: LLM latency 11026ms (>10s)
- **docker-propose-full**: 457 tokens (35 in / 422 out)
- **docker-propose-full**: 129 tokens (65 in / 64 out)
- **docker-run-classification**: 777 tokens (572 in / 205 out)
- **docker-run-classification**: 423 tokens (303 in / 120 out)
- **docker-run-classification**: 621 tokens (469 in / 152 out)
- **docker-run-classification**: 203 tokens (35 in / 168 out)
- **docker-run-classification**: 108 tokens (65 in / 43 out)
- **docker-run-classification**: 415 tokens (33 in / 382 out)
- **docker-run-classification**: 119 tokens (63 in / 56 out)
- **docker-run-classification**: 217 tokens (34 in / 183 out)
- **docker-run-classification**: 131 tokens (64 in / 67 out)
- **docker-run-classification**: 184 tokens (33 in / 151 out)
- **docker-run-classification**: 149 tokens (63 in / 86 out)
- **docker-run-classification**: LLM latency 11094ms (>10s)
- **docker-run-classification**: 457 tokens (35 in / 422 out)
- **docker-run-classification**: 129 tokens (65 in / 64 out)
- **docker-run-extraction**: LLM latency 12029ms (>10s)
- **docker-run-extraction**: 1581 tokens (1155 in / 426 out)
- **docker-run-extraction**: 628 tokens (519 in / 109 out)
- **docker-run-extraction**: 870 tokens (674 in / 196 out)
- **docker-run-extraction**: 56 tokens (37 in / 19 out)
- **docker-run-extraction**: 131 tokens (91 in / 40 out)
- **docker-run-extraction**: 268 tokens (58 in / 210 out)
- **docker-run-extraction**: 160 tokens (112 in / 48 out)
- **docker-run-extraction**: 177 tokens (47 in / 130 out)
- **docker-run-extraction**: 146 tokens (101 in / 45 out)
- **docker-run-extraction**: 151 tokens (47 in / 104 out)
- **docker-run-extraction**: 152 tokens (101 in / 51 out)
- **docker-run-extraction**: LLM latency 20840ms (>10s)
- **docker-run-extraction**: 837 tokens (41 in / 796 out)
- **docker-run-extraction**: 137 tokens (95 in / 42 out)
- **docker-run-generation**: LLM latency 11978ms (>10s)
- **docker-run-generation**: 1307 tokens (869 in / 438 out)
- **docker-run-generation**: 684 tokens (531 in / 153 out)
- **docker-run-generation**: 878 tokens (730 in / 148 out)
- **docker-run-generation**: 366 tokens (44 in / 322 out)
- **docker-run-generation**: 379 tokens (63 in / 316 out)
- **docker-run-generation**: 582 tokens (532 in / 50 out)
- **docker-run-generation**: 571 tokens (526 in / 45 out)
- **docker-run-generation**: 179 tokens (52 in / 127 out)
- **docker-run-generation**: 254 tokens (71 in / 183 out)
- **docker-run-generation**: 392 tokens (327 in / 65 out)
- **docker-run-generation**: 428 tokens (383 in / 45 out)
- **docker-run-generation**: LLM latency 20356ms (>10s)
- **docker-run-generation**: 813 tokens (41 in / 772 out)
- **docker-run-generation**: LLM latency 25524ms (>10s)
- **docker-run-generation**: 1058 tokens (60 in / 998 out)
- **docker-run-generation**: 1029 tokens (980 in / 49 out)
- **docker-run-generation**: 1257 tokens (1206 in / 51 out)
- **docker-run-generation**: 82 tokens (43 in / 39 out)
- **docker-run-generation**: 104 tokens (62 in / 42 out)
- **docker-run-generation**: 311 tokens (247 in / 64 out)
- **docker-run-generation**: 315 tokens (250 in / 65 out)
- **docker-run-generation**: LLM latency 18849ms (>10s)
- **docker-run-generation**: 766 tokens (44 in / 722 out)
- **docker-run-generation**: LLM latency 18208ms (>10s)
- **docker-run-generation**: 768 tokens (63 in / 705 out)
- **docker-run-generation**: 980 tokens (931 in / 49 out)
- **docker-run-generation**: 963 tokens (914 in / 49 out)
- **docker-run-staged-analyzer**: 777 tokens (572 in / 205 out)
- **docker-run-staged-analyzer**: 423 tokens (303 in / 120 out)
- **docker-run-staged-analyzer**: 621 tokens (469 in / 152 out)
- **docker-run-staged-analyzer**: 203 tokens (35 in / 168 out)
- **docker-run-staged-analyzer**: 108 tokens (65 in / 43 out)
- **docker-run-staged-analyzer**: 415 tokens (33 in / 382 out)
- **docker-run-staged-analyzer**: 119 tokens (63 in / 56 out)
- **docker-run-staged-analyzer**: 217 tokens (34 in / 183 out)
- **docker-run-staged-analyzer**: 131 tokens (64 in / 67 out)
- **docker-run-staged-analyzer**: 184 tokens (33 in / 151 out)
- **docker-run-staged-analyzer**: 149 tokens (63 in / 86 out)
- **docker-run-staged-analyzer**: LLM latency 12169ms (>10s)
- **docker-run-staged-analyzer**: 457 tokens (35 in / 422 out)
- **docker-run-staged-analyzer**: 129 tokens (65 in / 64 out)

## Issues

- None.

## Per-Test Details

Structured JSON results are in `field-test/v0.2.0/results/docker/omlx/qwen3.5-4b-4bit/` (5 files).

### docker-propose-full

- **Exit code:** 0
- **LLM calls:** 13
- **JSON:** `field-test/v0.2.0/results/docker/omlx/qwen3.5-4b-4bit/docker-propose-full.json`

### docker-run-classification

- **Exit code:** 0
- **LLM calls:** 13
- **JSON:** `field-test/v0.2.0/results/docker/omlx/qwen3.5-4b-4bit/docker-run-classification.json`

### docker-run-extraction

- **Exit code:** 0
- **LLM calls:** 13
- **JSON:** `field-test/v0.2.0/results/docker/omlx/qwen3.5-4b-4bit/docker-run-extraction.json`

### docker-run-generation

- **Exit code:** 0
- **LLM calls:** 23
- **JSON:** `field-test/v0.2.0/results/docker/omlx/qwen3.5-4b-4bit/docker-run-generation.json`

### docker-run-staged-analyzer

- **Exit code:** 0
- **LLM calls:** 13
- **JSON:** `field-test/v0.2.0/results/docker/omlx/qwen3.5-4b-4bit/docker-run-staged-analyzer.json`

