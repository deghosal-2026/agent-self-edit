# Docker Field Test Summary — AgentSelfEdit v0.3.0

**Date:** 2026-09-03T05:49:21Z
**Image:** `agent-self-edit:test`
**OMLX Model:** `Qwen3-4B-Instruct-2507-4bit`
**OMLX Endpoint:** `http://localhost:8000/v1`

## Summary

**9/9 tests passed** (0 failed)

| # | Test | Result | LLM Calls | Exit Code |
|---|------|--------|------------|-----------|
| 1 | `docker-ab-cache` | PASS | 13 | 0 |
| 2 | `docker-materialize-guard` | PASS | 13 | 0 |
| 3 | `docker-propose-full` | PASS | 13 | 0 |
| 4 | `docker-run-adversarial` | PASS | 13 | 0 |
| 5 | `docker-run-classification` | PASS | 13 | 0 |
| 6 | `docker-run-extraction` | PASS | 13 | 0 |
| 7 | `docker-run-generation` | PASS | 23 | 0 |
| 8 | `docker-run-mixed-domain` | PASS | 13 | 0 |
| 9 | `docker-run-staged-analyzer` | PASS | 13 | 0 |

## Observations

- **docker-ab-cache**: LLM latency 13160ms (>10s)
- **docker-ab-cache**: 851 tokens (554 in / 297 out)
- **docker-ab-cache**: 559 tokens (434 in / 125 out)
- **docker-ab-cache**: 853 tokens (675 in / 178 out)
- **docker-ab-cache**: LLM latency 16533ms (>10s)
- **docker-ab-cache**: 531 tokens (31 in / 500 out)
- **docker-ab-cache**: 131 tokens (64 in / 67 out)
- **docker-ab-cache**: LLM latency 12497ms (>10s)
- **docker-ab-cache**: 327 tokens (29 in / 298 out)
- **docker-ab-cache**: 110 tokens (62 in / 48 out)
- **docker-ab-cache**: 88 tokens (30 in / 58 out)
- **docker-ab-cache**: 205 tokens (63 in / 142 out)
- **docker-ab-cache**: 211 tokens (29 in / 182 out)
- **docker-ab-cache**: 252 tokens (62 in / 190 out)
- **docker-ab-cache**: 161 tokens (31 in / 130 out)
- **docker-ab-cache**: 287 tokens (64 in / 223 out)
- **docker-materialize-guard**: LLM latency 10132ms (>10s)
- **docker-materialize-guard**: 847 tokens (554 in / 293 out)
- **docker-materialize-guard**: 549 tokens (428 in / 121 out)
- **docker-materialize-guard**: 808 tokens (665 in / 143 out)
- **docker-materialize-guard**: LLM latency 15360ms (>10s)
- **docker-materialize-guard**: 474 tokens (31 in / 443 out)
- **docker-materialize-guard**: 104 tokens (59 in / 45 out)
- **docker-materialize-guard**: 305 tokens (29 in / 276 out)
- **docker-materialize-guard**: 187 tokens (57 in / 130 out)
- **docker-materialize-guard**: 88 tokens (30 in / 58 out)
- **docker-materialize-guard**: 297 tokens (58 in / 239 out)
- **docker-materialize-guard**: 211 tokens (29 in / 182 out)
- **docker-materialize-guard**: 189 tokens (57 in / 132 out)
- **docker-materialize-guard**: 220 tokens (31 in / 189 out)
- **docker-materialize-guard**: 382 tokens (59 in / 323 out)
- **docker-propose-full**: LLM latency 14986ms (>10s)
- **docker-propose-full**: 856 tokens (554 in / 302 out)
- **docker-propose-full**: 576 tokens (439 in / 137 out)
- **docker-propose-full**: 833 tokens (691 in / 142 out)
- **docker-propose-full**: LLM latency 13053ms (>10s)
- **docker-propose-full**: 467 tokens (31 in / 436 out)
- **docker-propose-full**: 49 tokens (46 in / 3 out)
- **docker-propose-full**: 304 tokens (29 in / 275 out)
- **docker-propose-full**: 47 tokens (44 in / 3 out)
- **docker-propose-full**: 88 tokens (30 in / 58 out)
- **docker-propose-full**: 80 tokens (45 in / 35 out)
- **docker-propose-full**: 211 tokens (29 in / 182 out)
- **docker-propose-full**: 48 tokens (44 in / 4 out)
- **docker-propose-full**: 230 tokens (31 in / 199 out)
- **docker-propose-full**: 121 tokens (46 in / 75 out)
- **docker-run-adversarial**: LLM latency 13196ms (>10s)
- **docker-run-adversarial**: 847 tokens (554 in / 293 out)
- **docker-run-adversarial**: 530 tokens (428 in / 102 out)
- **docker-run-adversarial**: 791 tokens (646 in / 145 out)
- **docker-run-adversarial**: LLM latency 16504ms (>10s)
- **docker-run-adversarial**: 541 tokens (31 in / 510 out)
- **docker-run-adversarial**: 117 tokens (54 in / 63 out)
- **docker-run-adversarial**: LLM latency 10404ms (>10s)
- **docker-run-adversarial**: 325 tokens (29 in / 296 out)
- **docker-run-adversarial**: 118 tokens (52 in / 66 out)
- **docker-run-adversarial**: 97 tokens (30 in / 67 out)
- **docker-run-adversarial**: 194 tokens (53 in / 141 out)
- **docker-run-adversarial**: 211 tokens (29 in / 182 out)
- **docker-run-adversarial**: LLM latency 17641ms (>10s)
- **docker-run-adversarial**: 507 tokens (52 in / 455 out)
- **docker-run-adversarial**: 209 tokens (31 in / 178 out)
- **docker-run-adversarial**: 266 tokens (54 in / 212 out)
- **docker-run-classification**: LLM latency 14201ms (>10s)
- **docker-run-classification**: 850 tokens (554 in / 296 out)
- **docker-run-classification**: 551 tokens (431 in / 120 out)
- **docker-run-classification**: 817 tokens (667 in / 150 out)
- **docker-run-classification**: LLM latency 13362ms (>10s)
- **docker-run-classification**: 474 tokens (31 in / 443 out)
- **docker-run-classification**: 132 tokens (61 in / 71 out)
- **docker-run-classification**: 314 tokens (29 in / 285 out)
- **docker-run-classification**: 180 tokens (59 in / 121 out)
- **docker-run-classification**: 88 tokens (30 in / 58 out)
- **docker-run-classification**: 263 tokens (60 in / 203 out)
- **docker-run-classification**: 213 tokens (29 in / 184 out)
- **docker-run-classification**: 236 tokens (59 in / 177 out)
- **docker-run-classification**: 230 tokens (31 in / 199 out)
- **docker-run-classification**: 312 tokens (61 in / 251 out)
- **docker-run-extraction**: LLM latency 16024ms (>10s)
- **docker-run-extraction**: 1448 tokens (1131 in / 317 out)
- **docker-run-extraction**: 534 tokens (423 in / 111 out)
- **docker-run-extraction**: 803 tokens (650 in / 153 out)
- **docker-run-extraction**: 81 tokens (33 in / 48 out)
- **docker-run-extraction**: 60 tokens (50 in / 10 out)
- **docker-run-extraction**: LLM latency 11670ms (>10s)
- **docker-run-extraction**: 439 tokens (54 in / 385 out)
- **docker-run-extraction**: 115 tokens (71 in / 44 out)
- **docker-run-extraction**: 159 tokens (43 in / 116 out)
- **docker-run-extraction**: 85 tokens (60 in / 25 out)
- **docker-run-extraction**: 104 tokens (43 in / 61 out)
- **docker-run-extraction**: 97 tokens (60 in / 37 out)
- **docker-run-extraction**: LLM latency 30720ms (>10s)
- **docker-run-extraction**: 929 tokens (37 in / 892 out)
- **docker-run-extraction**: LLM latency 16660ms (>10s)
- **docker-run-extraction**: 503 tokens (54 in / 449 out)
- **docker-run-generation**: LLM latency 12569ms (>10s)
- **docker-run-generation**: 1151 tokens (851 in / 300 out)
- **docker-run-generation**: 574 tokens (437 in / 137 out)
- **docker-run-generation**: 853 tokens (690 in / 163 out)
- **docker-run-generation**: LLM latency 10802ms (>10s)
- **docker-run-generation**: 365 tokens (40 in / 325 out)
- **docker-run-generation**: LLM latency 12680ms (>10s)
- **docker-run-generation**: 433 tokens (63 in / 370 out)
- **docker-run-generation**: 567 tokens (525 in / 42 out)
- **docker-run-generation**: 611 tokens (570 in / 41 out)
- **docker-run-generation**: 220 tokens (48 in / 172 out)
- **docker-run-generation**: 148 tokens (71 in / 77 out)
- **docker-run-generation**: 403 tokens (362 in / 41 out)
- **docker-run-generation**: 309 tokens (268 in / 41 out)
- **docker-run-generation**: LLM latency 17655ms (>10s)
- **docker-run-generation**: 582 tokens (37 in / 545 out)
- **docker-run-generation**: 374 tokens (60 in / 314 out)
- **docker-run-generation**: 785 tokens (742 in / 43 out)
- **docker-run-generation**: 555 tokens (512 in / 43 out)
- **docker-run-generation**: 68 tokens (39 in / 29 out)
- **docker-run-generation**: 89 tokens (62 in / 27 out)
- **docker-run-generation**: 268 tokens (227 in / 41 out)
- **docker-run-generation**: 266 tokens (225 in / 41 out)
- **docker-run-generation**: LLM latency 19226ms (>10s)
- **docker-run-generation**: 778 tokens (40 in / 738 out)
- **docker-run-generation**: LLM latency 20541ms (>10s)
- **docker-run-generation**: 885 tokens (63 in / 822 out)
- **docker-run-generation**: 980 tokens (937 in / 43 out)
- **docker-run-generation**: 1064 tokens (1021 in / 43 out)
- **docker-run-mixed-domain**: LLM latency 13496ms (>10s)
- **docker-run-mixed-domain**: 1576 tokens (1230 in / 346 out)
- **docker-run-mixed-domain**: 641 tokens (487 in / 154 out)
- **docker-run-mixed-domain**: 953 tokens (757 in / 196 out)
- **docker-run-mixed-domain**: 158 tokens (56 in / 102 out)
- **docker-run-mixed-domain**: 177 tokens (78 in / 99 out)
- **docker-run-mixed-domain**: 73 tokens (50 in / 23 out)
- **docker-run-mixed-domain**: 170 tokens (72 in / 98 out)
- **docker-run-mixed-domain**: 140 tokens (64 in / 76 out)
- **docker-run-mixed-domain**: 200 tokens (86 in / 114 out)
- **docker-run-mixed-domain**: 226 tokens (62 in / 164 out)
- **docker-run-mixed-domain**: 236 tokens (84 in / 152 out)
- **docker-run-mixed-domain**: 80 tokens (68 in / 12 out)
- **docker-run-mixed-domain**: 227 tokens (90 in / 137 out)
- **docker-run-staged-analyzer**: LLM latency 12049ms (>10s)
- **docker-run-staged-analyzer**: 855 tokens (554 in / 301 out)
- **docker-run-staged-analyzer**: 559 tokens (439 in / 120 out)
- **docker-run-staged-analyzer**: 845 tokens (675 in / 170 out)
- **docker-run-staged-analyzer**: LLM latency 15470ms (>10s)
- **docker-run-staged-analyzer**: 481 tokens (31 in / 450 out)
- **docker-run-staged-analyzer**: 135 tokens (62 in / 73 out)
- **docker-run-staged-analyzer**: 312 tokens (29 in / 283 out)
- **docker-run-staged-analyzer**: 102 tokens (60 in / 42 out)
- **docker-run-staged-analyzer**: 88 tokens (30 in / 58 out)
- **docker-run-staged-analyzer**: 165 tokens (61 in / 104 out)
- **docker-run-staged-analyzer**: 209 tokens (29 in / 180 out)
- **docker-run-staged-analyzer**: 241 tokens (60 in / 181 out)
- **docker-run-staged-analyzer**: 161 tokens (31 in / 130 out)
- **docker-run-staged-analyzer**: 250 tokens (62 in / 188 out)

## Issues

- None.

## Per-Test Details

Structured JSON results are in `field-test/v0.3.0/results/docker/omlx/qwen3-4b-instruct-2507-4bit/` (9 files).

### docker-ab-cache

- **Exit code:** 0
- **LLM calls:** 13
- **JSON:** `field-test/v0.3.0/results/docker/omlx/qwen3-4b-instruct-2507-4bit/docker-ab-cache.json`

### docker-materialize-guard

- **Exit code:** 0
- **LLM calls:** 13
- **JSON:** `field-test/v0.3.0/results/docker/omlx/qwen3-4b-instruct-2507-4bit/docker-materialize-guard.json`

### docker-propose-full

- **Exit code:** 0
- **LLM calls:** 13
- **JSON:** `field-test/v0.3.0/results/docker/omlx/qwen3-4b-instruct-2507-4bit/docker-propose-full.json`

### docker-run-adversarial

- **Exit code:** 0
- **LLM calls:** 13
- **JSON:** `field-test/v0.3.0/results/docker/omlx/qwen3-4b-instruct-2507-4bit/docker-run-adversarial.json`

### docker-run-classification

- **Exit code:** 0
- **LLM calls:** 13
- **JSON:** `field-test/v0.3.0/results/docker/omlx/qwen3-4b-instruct-2507-4bit/docker-run-classification.json`

### docker-run-extraction

- **Exit code:** 0
- **LLM calls:** 13
- **JSON:** `field-test/v0.3.0/results/docker/omlx/qwen3-4b-instruct-2507-4bit/docker-run-extraction.json`

### docker-run-generation

- **Exit code:** 0
- **LLM calls:** 23
- **JSON:** `field-test/v0.3.0/results/docker/omlx/qwen3-4b-instruct-2507-4bit/docker-run-generation.json`

### docker-run-mixed-domain

- **Exit code:** 0
- **LLM calls:** 13
- **JSON:** `field-test/v0.3.0/results/docker/omlx/qwen3-4b-instruct-2507-4bit/docker-run-mixed-domain.json`

### docker-run-staged-analyzer

- **Exit code:** 0
- **LLM calls:** 13
- **JSON:** `field-test/v0.3.0/results/docker/omlx/qwen3-4b-instruct-2507-4bit/docker-run-staged-analyzer.json`

