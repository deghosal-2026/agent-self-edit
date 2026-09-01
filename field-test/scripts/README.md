# Field Test Scripts

All scripts run from the repo root. Results are stored under `field-test/v0.1.0/results/<provider>/<model>/`.

---

## 10-Iteration Improvement Loop

`run_improvement_loop.py` calls the internal API directly (not the CLI) to run the full self-edit loop for N iterations. Per iteration it writes inspectable A/B artifacts.

```bash
# Local OMLX (4B — recommended, fastest)
export OMLX_KEY=omlx-test
export OMLX_MODEL=Qwen3.5-4B-4bit
export OMLX_URL=http://localhost:8000/v1
python3 field-test/scripts/run_improvement_loop.py --iterations 10
```

### Environment variables

| Var | Required | Description |
|-----|----------|-------------|
| `OMLX_KEY` | yes | API key (`omlx-test` for local) |
| `OMLX_MODEL` | yes | Model name |
| `OMLX_URL` | yes | API base URL |

### Options

| Flag | Description |
|------|-------------|
| `--iterations` | Number of self-edit iterations (default: 10) |
| `--traces-per-iteration` | Traces to seed each iteration (default: 10) |

### Output

```
field-test/v0.1.0/results/omlx/qwen3.5-4b-4bit/
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

---

## Docker Tests

### Run full pytest suite (9 tests: build, OMLX connectivity, smoke, integration)

```bash
python3 field-test/scripts/run_docker_tests.py
```

Requires: Docker daemon running, OMLX server at `http://localhost:8000/v1`.

### Direct pytest

```bash
pytest tests/test_docker.py -v -m docker --no-cov
```

### Override OMLX connection

```bash
OMLX_URL=http://localhost:8000/v1 OMLX_MODEL=Qwen3.5-4B-4bit OMLX_KEY=omlx-test \
  python3 field-test/scripts/run_docker_tests.py
```

---

## Download Real Traces from HuggingFace

The `download_hf_traces.py` script downloads the `juliensimon/open-agent-traces` and `juliensimon/agent-traces-customer-support-triage` datasets from HuggingFace and converts them to the AgentSelfEdit Trace schema.

```bash
# Install dependency
pip install datasets

# Run the download script from the repo root
python3 field-test/scripts/download_hf_traces.py
```

Output goes to `field-test/v0.1.0/corpus/real-life/real-traces/hf-*.jsonl`.

## Import Portfolio Traces

The `import_real_traces.py` script converts real traces from sibling projects (agent-exec-trace, agent-eval-forge) into the AgentSelfEdit Trace schema. Generates unique task_ids for each trace (#97 fix).

```bash
python3 field-test/scripts/import_real_traces.py
```

Requires the sibling repos to be checked out at `~/Desktop/code/github/agent-exec-trace` and `~/Desktop/code/github/agent-eval-forge`.

## Generate Synthetic Traces

The `generate_traces.py` script produces synthetic traces from a task set (YAML) for hermetic testing.

```bash
# Generate traces from classification task set
python3 field-test/scripts/generate_traces.py \
  field-test/v0.1.0/corpus/synthetic/classification.yaml \
  --output /tmp/traces.jsonl \
  --failure-rate 0.3
```
