# Docker Test Plan — AgentSelfEdit v0.1.0

> Docker image build, smoke test, and integration test for the self-improvement loop.

## 1. Objectives

1. **Build** — the Docker image builds successfully from `Dockerfile`.
2. **CLI smoke** — `agent-self-edit --help` works inside the container.
3. **Integration** — the full loop (trace → analyze → A/B test → gate → promote) runs with mock providers inside the container.

## 2. Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage build: builder stage (pip install build → wheel), runtime stage (pip install wheel → run) |
| `docker-compose.yml` | Defines the `agent-self-edit` service with volume mounts for config, registry, traces |
| `tests/test_docker.py` | Hermetic tests (marked `pytest.mark.docker`) that run `docker build` and `docker run` |

## 3. Tests

### 3.1 Build Test

```bash
docker build -t agent-self-edit .
```

- Image must build without errors.
- Final image must be < 300 MB.

### 3.2 CLI Smoke Test

```bash
docker run --rm agent-self-edit --help
```

- Must output usage text listing all 10 commands.
- Exit code 0.

### 3.3 CLI Command Tests

```bash
# Validate with a mounted config
docker run --rm -v $(pwd)/test-config:/config agent-self-edit validate --config /config/agent-self-edit.yaml

# Status with empty registry
docker run --rm -v $(pwd)/test-config:/config agent-self-edit status --config /config/agent-self-edit.yaml
```

### 3.4 Integration Test

Run the full loop with mock providers inside the container:

1. Create a config, registry, and trace file on a mounted volume.
2. Run `agent-self-edit run --once --dry-run` with the config.
3. Verify loop completes without errors.

## 4. CI Integration

Docker tests are excluded from the default `pytest` run (marked `@pytest.mark.docker`). Run them explicitly:

```bash
pytest tests/test_docker.py -v -m docker
```

## 5. Volume Mounts

| Host path | Container path | Purpose |
|-----------|---------------|---------|
| `./test-config/` | `/config/` | Config file, registry, traces |
| `./test-config/registry/` | `/config/registry/` | Prompt registry persistence |
| `./test-config/traces.db` | `/config/traces.db` | Trace store |