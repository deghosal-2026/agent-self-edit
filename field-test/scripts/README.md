# Field Test Scripts

All scripts run from the repo root. Results are stored under `field-test/v0.1.0/results/<provider>/<model>/`.

---

## Run Traces Through an LLM (synthetic or real)

`run_traces.py` takes any trace file (synthetic or real JSONL), runs each trace's `task_input` through an LLM, scores the output against `expected_output`, and records the full LLM request/response, latency, and token usage for debuggability.

### Required

`LLM_API_KEY` must be set in the environment. No fallbacks, no defaults.

### Local OMLX

```bash
export LLM_API_KEY=omlx-test

# Real traces (all 5 files)
for f in field-test/v0.1.0/corpus/real-life/real-traces/hf-*.jsonl; do
  python field-test/scripts/run_traces.py "$f" \
    --provider omlx --model qwen3.5-9b-mlx-4bit \
    --endpoint http://localhost:8000/v1 --system-prompt "You are a helpful assistant."
done

# Real traces (observatory + evalforge)
python field-test/scripts/run_traces.py \
  field-test/v0.1.0/corpus/real-life/real-traces/agent-observatory-traces.jsonl \
  --provider omlx --model qwen3.5-9b-mlx-4bit \
  --endpoint http://localhost:8000/v1 --system-prompt "You are a helpful assistant."

python field-test/scripts/run_traces.py \
  field-test/v0.1.0/corpus/real-life/real-traces/evalforge-failures.jsonl \
  --provider omlx --model qwen3.5-9b-mlx-4bit \
  --endpoint http://localhost:8000/v1 --system-prompt "You are a helpful assistant."

# Synthetic traces (generate them first, then run)
python field-test/scripts/generate_traces.py \
  field-test/v0.1.0/corpus/synthetic/classification.yaml \
  --output /tmp/synth-classification.jsonl --failure-rate 0.3

python field-test/scripts/run_traces.py /tmp/synth-classification.jsonl \
  --provider omlx --model qwen3.5-9b-mlx-4bit \
  --endpoint http://localhost:8000/v1 --system-prompt "You are a classifier."
```

### Cloud LLM (OpenAI-compatible)

```bash
export LLM_API_KEY=sk-...

# Same commands, different provider/model/endpoint
for f in field-test/v0.1.0/corpus/real-life/real-traces/hf-*.jsonl; do
  python field-test/scripts/run_traces.py "$f" \
    --provider openai --model gpt-4o-mini \
    --endpoint https://api.openai.com/v1 --system-prompt "You are a helpful assistant."
done

python field-test/scripts/run_traces.py \
  field-test/v0.1.0/corpus/real-life/real-traces/agent-observatory-traces.jsonl \
  --provider openai --model gpt-4o-mini \
  --endpoint https://api.openai.com/v1 --system-prompt "You are a helpful assistant."

python field-test/scripts/run_traces.py \
  field-test/v0.1.0/corpus/real-life/real-traces/evalforge-failures.jsonl \
  --provider openai --model gpt-4o-mini \
  --endpoint https://api.openai.com/v1 --system-prompt "You are a helpful assistant."

python field-test/scripts/run_traces.py /tmp/synth-classification.jsonl \
  --provider openai --model gpt-4o-mini \
  --endpoint https://api.openai.com/v1 --system-prompt "You are a classifier."
```

### All env vars are overridable

```bash
export LLM_API_KEY=...
export LLM_PROVIDER=omlx
export LLM_MODEL=qwen3.5-9b-mlx-4bit
export LLM_ENDPOINT=http://localhost:8000/v1
python field-test/scripts/run_traces.py field-test/v0.1.0/corpus/real-life/real-traces/hf-customer-support-traces.jsonl
```

### Output

| Var | Purpose | Example |
|-----|---------|--------|
| `LLM_API_KEY` | API key (required, no fallback) | `omlx-test`, `sk-...` |
| `LLM_PROVIDER` | `omlx` or `openai` | `omlx` |
| `LLM_MODEL` | Model name | `qwen3.5-9b-mlx-4bit`, `gpt-4o-mini` |
| `LLM_ENDPOINT` | API base URL | `http://localhost:8000/v1`, `https://api.openai.com/v1` |

Results are written to `field-test/v0.1.0/results/<provider>/<model>/`:

- `<trace-name>-results.json` — full report: meta (accuracy, tokens, latency) + per-trace LLM I/O and scoring
- `llm-traffic-<trace-name>.jsonl` — append-only raw request/response pairs

Example:

```
field-test/v0.1.0/results/omlx/qwen3.5-9b-mlx-4bit/
  hf-customer-support-traces-results.json
  llm-traffic-hf-customer-support-traces.jsonl
```

---

## Docker Tests

### Run full pytest suite (9 tests: build, OMLX connectivity, smoke, integration)

```bash
python field-test/scripts/run_docker_tests.py
```

Requires: Docker daemon running, OMLX server at `http://localhost:8000/v1`.

### Run standalone field test (one-shot end-to-end with LLM traffic capture)

```bash
python field-test/scripts/run_docker_field_test.py
```

Outputs go to `field-test/v0.1.0/results/docker/omlx/qwen3.5-9b-mlx-4bit/`.

### Override OMLX connection (for cloud LLM or different local model)

```bash
OMLX_URL=http://localhost:8000/v1 OMLX_MODEL=Qwen3.5-9B-MLX-4bit OMLX_KEY=omlx-test \
  python field-test/scripts/run_docker_tests.py
```

---

## Download Real Traces from HuggingFace

The `download_hf_traces.py` script downloads the `juliensimon/open-agent-traces` and `juliensimon/agent-traces-customer-support-triage` datasets from HuggingFace and converts them to the AgentSelfEdit Trace schema.

```bash
# Install dependency
pip install datasets

# Run the download script from the repo root
python field-test/scripts/download_hf_traces.py
```

Output goes to `field-test/v0.1.0/corpus/real-life/real-traces/hf-*.jsonl`.

## Import Portfolio Traces

The `import_real_traces.py` script converts real traces from sibling projects (agent-exec-trace, agent-eval-forge) into the AgentSelfEdit Trace schema.

```bash
python field-test/scripts/import_real_traces.py
```

Requires the sibling repos to be checked out at `~/Desktop/code/github/agent-exec-trace` and `~/Desktop/code/github/agent-eval-forge`.

## Generate Synthetic Traces

The `generate_traces.py` script produces synthetic traces from a task set (YAML) for hermetic testing.

```bash
# Generate traces from classification task set
python field-test/scripts/generate_traces.py \
  field-test/v0.1.0/corpus/synthetic/classification.yaml \
  --output /tmp/traces.jsonl \
  --failure-rate 0.3
```