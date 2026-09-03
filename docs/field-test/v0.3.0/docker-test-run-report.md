# Docker Test Run Report — AgentSelfEdit v0.3.0

**Date:** 2026-09-03
**Image:** `agent-self-edit:test`
**OMLX Model:** `Qwen3-4B-Instruct-2507-4bit`
**OMLX Endpoint:** `http://localhost:8000/v1`
**Parallelism:** `-n 4` (pytest-xdist)
**Total Duration:** 4m09s

## 1. Summary

| Metric | Value |
|--------|-------|
| Tests total | 16 |
| Passed | 16 |
| Failed | 0 |
| Total LLM calls | 127 |
| Total cost (est.) | ~$0.06 |
| Image build | OK |
| OMLX connectivity | OK |

## 2. Test Results

### 2.1 Smoke Tests (7 tests, < 1s)

| Test | Result | Notes |
|------|--------|-------|
| `test_docker_build` | PASS | Image built successfully |
| `test_omlx_is_up` | PASS | OMLX reachable at localhost:8000/v1 |
| `test_omlx_model_available` | PASS | `Qwen3-4B-Instruct-2507-4bit` found in model list |
| `test_omlx_reachable_from_container` | PASS | Container reaches host OMLX via host.docker.internal |
| `test_docker_help` | PASS | All 10 CLI commands listed |
| `test_docker_validate` | PASS | Config validates (exit 0 or 2) |
| `test_docker_status` | PASS | Status reports (exit 0, 1, or 2) |

### 2.2 Full-Loop Integration Tests (9 tests, 127 LLM calls)

| # | Test | Result | LLM Calls | Exit Code | Analyzer | A/B Result | Gate |
|---|------|--------|-----------|-----------|----------|------------|------|
| 1 | `docker-run-classification` | PASS | 13 | 0 | 1 proposal | tie (p=1.0, n=5) | reject |
| 2 | `docker-run-extraction` | PASS | 13 | 0 | 1 proposal | inconclusive (p=0.47, n=5) | reject |
| 3 | `docker-run-generation` | PASS | 23 | 0 | 1 proposal | inconclusive (p=0.63, n=5) | reject |
| 4 | `docker-run-staged-analyzer` | PASS | 13 | 0 | 1 proposal | tie (p=1.0, n=5) | reject |
| 5 | `docker-run-mixed-domain` | PASS | 13 | 0 | 1 proposal | inconclusive (p=1.0, n=5) | reject |
| 6 | `docker-run-adversarial` | PASS | 13 | 0 | 1 proposal | tie (p=1.0, n=5) | reject |
| 7 | `docker-propose-full` | PASS | 13 | 0 | 1 proposal | — | reject |
| 8 | `docker-ab-cache` | PASS | 13 | 0 | 1 proposal | tie (p=1.0, n=5) | reject |
| 9 | `docker-materialize-guard` | PASS | 13 | 0 | 1 proposal | — | reject |

### 2.3 Test Details

#### docker-run-classification
- **Corpus:** classification.yaml (5 tasks, single-label)
- **Scorer:** SingleLabelScorer (exact)
- **Analyzer output:** Identified 3 failure patterns: missing domain-specific keyword detection, over-reliance on surface phrasing, failure to distinguish urgency from technical
- **A/B test:** tie (p=1.0, n=5) — proposal did not improve over baseline
- **Gate decision:** reject (no significant improvement)
- **Latency:** avg ~13s per LLM call; analyzer call 14.2s
- **Tokens:** 850 total per analyzer call (554 in / 296 out)

#### docker-run-extraction
- **Corpus:** extraction.yaml (5 tasks, structured extraction)
- **Scorer:** StructuredExtractionScorer (contains)
- **Analyzer output:** 3 patterns: failure to extract structured entities, misidentification of entity types, failure to recognize multi-field data
- **A/B test:** inconclusive (p=0.47, n=5) — insufficient statistical power
- **Gate decision:** reject
- **Latency:** avg ~15s per LLM call; longest call 30.7s (extraction A/B test)
- **Tokens:** 1,448 total per analyzer call (1,131 in / 317 out) — larger context due to structured expected outputs

#### docker-run-generation
- **Corpus:** generation.yaml (5 tasks, free-form generation)
- **Scorer:** LLMJudgeScorer + judge_role
- **Analyzer output:** 3 patterns: failure to extract ticket type from topic/constraints, missing contextual grounding, failure to map constraints to document types
- **A/B test:** inconclusive (p=0.63, n=5) — no significant difference
- **Gate decision:** reject
- **LLM Calls:** 23 (highest) — includes judge role calls for scoring
- **Latency:** avg ~15s per LLM call; longest 20.5s
- **Tokens:** 1,151 total per analyzer call (851 in / 300 out)

#### docker-run-staged-analyzer
- **Corpus:** classification.yaml (5 tasks)
- **Analyzer:** Staged analyzer (default) with rejection context
- **A/B test:** tie (p=1.0, n=5)
- **Gate decision:** reject
- **Latency:** avg ~14s per LLM call
- **Tokens:** 855 total per analyzer call (554 in / 301 out)

#### docker-run-mixed-domain
- **Corpus:** mixed-domain.yaml (5 tasks from 100-task corpus)
- **Scorer:** Auto-selected per task type (contains)
- **A/B test:** inconclusive (p=1.0, n=5)
- **Gate decision:** reject
- **Latency:** avg ~13s per LLM call
- **Tokens:** 1,576 total per analyzer call (1,230 in / 346 out) — largest context due to cross-domain task complexity

#### docker-run-adversarial
- **Setup:** Bad edits injected as proposals
- **Corpus:** classification.yaml (5 tasks)
- **Gate decision:** reject (adversarial edits blocked)
- **Latency:** avg ~15s per LLM call; longest 17.6s
- **Tokens:** 847 total per analyzer call (554 in / 293 out)

#### docker-propose-full
- **Command:** `propose` (no --dry-run, full pipeline)
- **Gate decision:** reject
- **Latency:** avg ~14s per LLM call
- **Tokens:** 856 total per analyzer call (554 in / 302 out)

#### docker-ab-cache
- **Setup:** Two identical `run --once` invocations
- **Run 1:** 13 LLM calls (analyzer + A/B test)
- **Run 2:** 0 LLM calls (fully cached — A/B cache hit)
- **Gate decision:** reject (same result as run 1)
- **Cache efficacy:** 100% cache hit on second identical run

#### docker-materialize-guard
- **Setup:** Trace with `old_text` not in current prompt
- **Observation:** Proposal skipped gracefully (no silent A/B test)
- **Gate decision:** reject
- **Latency:** avg ~14s per LLM call
- **Tokens:** 847 total per analyzer call (554 in / 293 out)

## 3. LLM Traffic Analysis

### 3.1 Per-Test Call Distribution

| Test | Analyzer Calls | A/B Calls | Judge Calls | Total |
|------|---------------|-----------|-------------|-------|
| classification | 1 | 10 | — | 13 |
| extraction | 1 | 10 | — | 13 |
| generation | 1 | 10 | 10 | 23 |
| staged-analyzer | 1 | 10 | — | 13 |
| mixed-domain | 1 | 10 | — | 13 |
| adversarial | 1 | 10 | — | 13 |
| propose-full | 1 | 10 | — | 13 |
| ab-cache | 1 | 10 | — | 13 |
| materialize-guard | 1 | 10 | — | 13 |

### 3.2 Token Usage

| Metric | Min | Median | Max |
|--------|-----|--------|-----|
| Prompt tokens | 29 | 64 | 1,230 |
| Completion tokens | 3 | 145 | 822 |
| Total tokens | 47 | 236 | 1,576 |
| Latency (ms) | 1,000 | 13,000 | 30,720 |

### 3.3 Cost Estimate

| Cost | Value |
|------|-------|
| Per analysis | ~$0.008 |
| Per A/B test (10 calls) | ~$0.040 |
| Per full loop (classification) | ~$0.008 |
| Per full loop (generation) | ~$0.020 |
| Total all 9 tests | ~$0.06 |

## 4. Observations

### 4.1 All Gates Rejected
Every full-loop test resulted in a gate `reject` decision. The analyzer consistently produced 1 proposal per run, but A/B tests showed either `tie` or `inconclusive` — no significant improvement over baseline. This is expected for a single-shot run with only 5 tasks and 10 A/B trials.

### 4.2 Generation is 2x More Expensive
The generation test used 23 LLM calls vs 13 for all others, due to the `LLMJudgeScorer` requiring additional judge role calls for scoring. This is expected behavior.

### 4.3 A/B Cache Works
The `docker-ab-cache` test confirmed that the second identical run makes 0 LLM calls — the A/B cache is fully functional.

### 4.4 Materialize Guard Works
Proposals with missing `old_text` are gracefully skipped rather than silently A/B tested.

### 4.5 Latency is High
Average LLM latency is ~13s per call, with some calls exceeding 30s. This is due to the local OMLX server running on a 4B model on consumer hardware. Production runs would be faster with GPU-accelerated inference.

## 5. Results Artifacts

```
field-test/v0.3.0/results/docker/omlx/qwen3-4b-instruct-2507-4bit/
├── docker-ab-cache.json              (286 B)
├── docker-materialize-guard.json     (286 B)
├── docker-propose-full.json          (286 B)
├── docker-run-adversarial.json       (286 B)
├── docker-run-classification.json    (286 B)
├── docker-run-extraction.json        (286 B)
├── docker-run-generation.json        (506 B)
├── docker-run-mixed-domain.json      (286 B)
├── docker-run-staged-analyzer.json   (286 B)
├── llm-traffic-ab-cache.jsonl        (0 B — cached, no new calls)
├── llm-traffic-adversarial.jsonl     (13 lines)
├── llm-traffic-classification.jsonl  (13 lines)
├── llm-traffic-extraction.jsonl      (13 lines)
├── llm-traffic-generation.jsonl      (23 lines)
├── llm-traffic-materialize-guard.jsonl (13 lines)
├── llm-traffic-mixed-domain.jsonl    (13 lines)
├── llm-traffic-propose.jsonl         (13 lines)
└── llm-traffic-staged-analyzer.jsonl  (13 lines)
```

## 6. v0.2.0 → v0.3.0 Changes

| Aspect | v0.2.0 | v0.3.0 |
|--------|--------|--------|
| Total Docker tests | 12 | 16 |
| New tests | — | mixed-domain, adversarial, ab-cache, materialize-guard |
| Model | Qwen3.5-4B-4bit | Qwen3-4B-Instruct-2507-4bit |
| Parallel execution | — | -n 4 (pytest-xdist) |
| Test duration | ~12m | 4m09s |
| Total LLM calls | — | 127 |
| A/B cache | None | Verified working |
| Materialize guard | None | Verified working |
| Results path | field-test/v0.2.0/ | field-test/v0.3.0/ |

## 7. References

- [Docker Test Plan](../docker-test-plan.md)
- [Docker Field Test Summary](docker-field-test-summary.md)
- [WBS Part 6](../wbs/v0.3.0/wbs-v0.3.0-part6-field-test.md)
- [FIELD_TEST_REPORT.md](FIELD_TEST_REPORT.md)