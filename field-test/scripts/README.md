# Field Test Scripts

All scripts run from the repo root. Results are stored under `field-test/v0.2.0/results/<provider>/<model>/`.

---

## Improvement Loop

`run_improvement_loop.py` calls the internal API directly (not the CLI) to run the full self-edit loop for N iterations. Per iteration it writes inspectable A/B artifacts.

### Recommended model

`Qwen3-4B-Instruct-2507-4bit` is the fastest model (~2s/call, ~35s/iteration). `Qwen3.5-4B-4bit` also works but is ~2x slower.

### Model role recommendation

Based on the v0.2.0 field test results:

- **Executor role:** `Qwen3-4B-Instruct-2507-4bit`
- **Analyzer role:** `Qwen3.5-9B-MLX-4bit`
- **Judge role:** `Qwen3.5-9B-MLX-4bit` (for generation runs)

Why:
- The 4B Instruct model is fast enough for repeated A/B tests and baseline execution
- It gets 60% on the held-out classification set with the current baseline prompt
- The 4B model is **not good enough as analyzer** — it keeps proposing the same edit every iteration and does not meaningfully use rejection feedback
- A stronger analyzer model is likely needed to generate diverse, useful prompt edits

**Important:** `run_improvement_loop.py` currently uses a single `OMLX_MODEL` for all roles. The runner does **not** yet support separate executor/analyzer/judge model env vars. The recommendation above is for future model-role-aware runs, not for the current runner.

### Run the improvement loop

```bash
export OMLX_KEY=omlx-test
export OMLX_MODEL=Qwen3-4B-Instruct-2507-4bit
export OMLX_URL=http://localhost:8000/v1
python3 field-test/scripts/run_improvement_loop.py --iterations 10
```

### Environment variables

| Var | Required | Description |
|-----|----------|-------------|
| `OMLX_KEY` | yes | API key (`omlx-test` for local) |
| `OMLX_MODEL` | yes | Model name |
| `OMLX_URL` | yes | API base URL |

### Run with real traces (analyzer quality only)

Real traces can be used to evaluate analyzer proposal quality on real trace distributions.
**Do not use for improvement measurement** — the A/B corpus is classification-only and
real traces have no matching scored task set. See `docs/field-test/v0.2.0/learnings.md` Issue 11.

Only use traces from `usable/` — traces in `telemetry/` have placeholder outputs and won't produce proposals.

```bash
export OMLX_KEY=omlx-test
export OMLX_MODEL=Qwen3-4B-Instruct-2507-4bit
export OMLX_URL=http://localhost:8000/v1

# HuggingFace open-agent traces (26 usable failures, 150 total)
python3 field-test/scripts/run_improvement_loop.py --iterations 10 \
  --real-traces field-test/corpus/real-traces/usable/hf-open-agent-traces.jsonl

# HuggingFace customer support traces (9 usable failures, 50 total)
python3 field-test/scripts/run_improvement_loop.py --iterations 10 \
  --real-traces field-test/corpus/real-traces/usable/hf-customer-support-traces.jsonl
```

Each run creates a separate output directory named after the trace file:
```
field-test/v0.2.0/results/omlx/<model>/
  synthetic/                    ← synthetic classification runs
    iteration-01/
    ...
  hf-open-agent-traces/         ← open-agent traces runs
    iteration-01/
    ...
  hf-customer-support-traces/   ← customer support traces runs
    iteration-01/
    ...
```

**Do not use** traces from `telemetry/` — they have placeholder outputs ("N chars produced", "Completed 0 tool calls") and the analyzer will produce 0 proposals.

**Do not use** `labeled/gold-corpus.jsonl` for the improvement loop — it's a labeled evaluation set, not a loop input.

### Options

| Flag | Description |
|------|-------------|
| `--iterations` | Number of self-edit iterations (default: 10) |
| `--traces-per-iteration` | Traces to seed each iteration (default: 10) |
| `--real-traces PATH` | Path to real traces JSONL file. Enables real-trace mode. |

### Output

```
field-test/v0.2.0/results/omlx/<model>/
  improvement-loop-report.json    ← aggregate: per-iteration accuracy, gate, cost
  llm-traffic.jsonl                ← all LLM request/response pairs
  iteration-01/
    prompt-a.md                    ← current prompt
    prompt-b.md                    ← candidate prompt (edit applied)
    results-a.json                 ← per-task: input, expected, llm_output, score, latency, tokens
    results-b.json                 ← same for prompt B
    ab-comparison.json             ← per-task deltas, winner, p-value, CI, effect size, gate decision
    analysis.json                  ← analyzer proposals (section, old_text, new_text, hypothesis)
    accuracy.json                  ← held-out set results
    prompt-after.md                ← prompt after gate decision
  iteration-02/
    ...
```

### Corpus used

| Corpus | Purpose | Tasks |
|--------|---------|-------|
| `classification-single-label.yaml` + `multi-label` + `ambiguous` + `boundary` | Seeding failures | 50 |
| `classification-promotion.yaml` | A/B test set | 40 |
| `classification-held-out.yaml` | Generalization measurement | 25 |
| `sentinel.yaml` | Regression detection | 20 |

---

## Docker Tests

### Run full pytest suite (12 tests: build, OMLX connectivity, smoke, multi-domain integration)

```bash
export OMLX_KEY=omlx-test
export OMLX_MODEL=Qwen3.5-4B-4bit
export OMLX_URL=http://localhost:8000/v1
pytest tests/test_docker.py -v -m docker --no-cov
```

Requires: Docker daemon running, OMLX server at `http://localhost:8000/v1`.

### Docker tests

| Test | What it does |
|------|-------------|
| `test_docker_build` | Builds the image |
| `test_omlx_is_up` | OMLX reachable from host |
| `test_omlx_model_available` | Model is loaded |
| `test_omlx_reachable_from_container` | Container can reach OMLX |
| `test_docker_help` | All 10 CLI commands listed |
| `test_docker_validate` | Config validation |
| `test_docker_status` | Status command |
| `test_docker_run_classification` | Full loop on classification corpus |
| `test_docker_run_extraction` | Full loop on extraction corpus with StructuredExtractionScorer |
| `test_docker_run_generation` | Full loop on generation corpus with LLMJudgeScorer + judge_role |
| `test_docker_run_staged_analyzer` | Staged analyzer (4-stage pipeline) in container |
| `test_docker_propose_full` | Propose command with real LLM |

---

## Hermetic CI Tests

These run without Docker or OMLX. They use mock providers only.

```bash
pytest --ignore=tests/test_docker.py --no-cov
```

### Hermetic tests

| Test | What it verifies |
|------|-----------------|
| `test_baseline_measurement` | Baseline accuracy on classification corpus |
| `test_dry_run_loop` | Full loop with --dry-run via CLI |
| `test_gate_rejects_bad_edits` | 5/5 bad edits rejected with correct failure modes |
| `test_gate_rejects_frozen_section_edit` | Frozen section violation caught |
| `test_gate_rejects_missing_old_text` | Missing old_text caught |
| `test_gate_rejects_excessive_edit_distance` | Excessive edit distance caught |
| `test_rollback` | Promote, rollback, verify lineage |
| `test_zero_llm_full_loop` | Full loop with mock providers only |
| `test_concurrent_traces` | 100 traces, no data loss |
| `test_registry_integrity_20_versions` | 20 versions, 0 corruption |
| `test_guardrail_stress_100_edits` | 100 random edits, 0 crashes |
| `test_sentinel_corpus_loads` | Sentinel corpus loads and validates |

---

## Adversarial Edit Tests

Run the hermetic adversarial tests:

```bash
pytest tests/test_field_test.py -k "gate_rejects" -v
```

To run adversarial tests with a real LLM (requires OMLX):

```bash
export OMLX_KEY=omlx-test
export OMLX_MODEL=Qwen3-4B-Instruct-2507-4bit
export OMLX_URL=http://localhost:8000/v1
pytest tests/test_field_test.py -k "gate_rejects or guardrail" -v
```

---

## Real-Trace Ingestion

### Import real traces from portfolio projects

```bash
python3 field-test/scripts/import_real_traces.py
```

Requires sibling repos at `~/Desktop/code/github/agent-exec-trace` and `~/Desktop/code/github/agent-eval-forge`.

### Download real traces from HuggingFace

```bash
pip install datasets
python3 field-test/scripts/download_hf_traces.py
```

Output goes to `field-test/corpus/real-traces/hf-*.jsonl`.

### Gold corpus

The real-trace gold corpus with human-labeled failure clusters is at `field-test/corpus/real-traces/gold-corpus.jsonl` (30 traces).

---

## Generate Synthetic Traces

```bash
python3 field-test/scripts/generate_traces.py \
  field-test/corpus/synthetic/classification.yaml \
  --output /tmp/traces.jsonl \
  --failure-rate 0.3
```
