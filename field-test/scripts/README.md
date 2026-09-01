# Field Test Scripts

All scripts run from the repo root. Results are stored under `field-test/v0.1.0/results/`.

---

## 10-Iteration Improvement Loop

`run_improvement_loop.py` runs the actual self-edit loop (`agent-self-edit run --once`) for N iterations, measuring accuracy on a held-out set after each iteration. This is the core field test for #100.

```bash
# Local OMLX — 10 iterations (default model: Qwen3.5-4B-4bit)
python3 field-test/scripts/run_improvement_loop.py --iterations 10 \
  --model Qwen3.5-4B-4bit --endpoint http://localhost:8000/v1 --api-key omlx-test

# Cloud (OpenRouter)
python3 field-test/scripts/run_improvement_loop.py --iterations 10 \
  --model openai/gpt-4o-mini --endpoint https://openrouter.ai/api/v1 --api-key sk-or-v1-...
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--iterations` | 10 | Number of self-edit iterations |
| `--traces-per-iteration` | 10 | Traces to seed each iteration |
| `--model` | `Qwen3.5-4B-4bit` | LLM model name |
| `--endpoint` | `http://localhost:8000/v1` | API base URL |
| `--api-key` | `omlx-test` | API key |

### Output

Results go to `field-test/v0.1.0/results/improvement-loop/`:
- `improvement-loop-report.json` — per-iteration accuracy, gate outcomes, cost, LLM traffic

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
