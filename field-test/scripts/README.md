# Field Test Scripts

All scripts run from the repo root. Results are stored under `field-test/v0.1.0/results/<provider>/<model>/`.

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