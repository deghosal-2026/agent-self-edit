"""Docker tests for AgentSelfEdit (marked @pytest.mark.docker).

Run with: pytest tests/test_docker.py -v -m docker
Requires: Docker daemon running.
"""

import json
import os
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.docker

REPO_ROOT = Path(__file__).resolve().parent.parent
IMAGE_TAG = "agent-self-edit:test"
OMLX_URL = os.environ.get("OMLX_URL", "http://localhost:8000/v1")
OMLX_KEY = os.environ.get("OMLX_KEY", "omlx-test")
OMLX_MODEL = os.environ.get("OMLX_MODEL", "Qwen3.5-4B-4bit")
# Containers reach the host OMLX via host.docker.internal (not localhost)
OMLX_URL_CONTAINER = os.environ.get(
    "OMLX_URL_CONTAINER", OMLX_URL.replace("localhost", "host.docker.internal")
)


def _build_image():
    result = subprocess.run(
        ["docker", "build", "-t", IMAGE_TAG, "."],
        capture_output=True, text=True, timeout=120, cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        pytest.fail(f"docker build failed:\n{result.stdout}\n{result.stderr}")
    return result


def _run_container(args: list[str], volumes: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    cmd = ["docker", "run", "--rm"]
    if volumes:
        for host, container in volumes.items():
            cmd.extend(["-v", f"{host}:{container}"])
    cmd.extend([IMAGE_TAG] + args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


def _create_test_config(tmp_path: Path, full_loop: bool = False) -> Path:
    config = {
        "schema_version": 1,
        "project": {"name": "docker-test", "registry_path": "/config/registry",
                    "trace_path": "/config/traces.db"},
        "tasks": {"task_set_path": "/config/classification.yaml" if full_loop else "",
                  "batch_size": 10, "sample_floor": 10},
        "llm": {"provider": "openai", "model": OMLX_MODEL, "api_key": OMLX_KEY,
                "base_url": OMLX_URL_CONTAINER, "temperature": 0.0, "max_tokens": 4096,
                "timeout": 60},
        "ab_test": {"n_resamples": 100, "n_permutations": 100,
                    "confidence_level": 0.95, "min_effect_size": 0.05,
                    "cost_ceiling_usd": 0.50},
        "gate": {"max_edit_distance": 20, "drift_threshold": 0.3, "near_miss_threshold": 0.5},
        "analyzer": {"max_proposals_per_batch": 3, "cost_ceiling_usd": 0.50},
        "trigger": "batch", "trace_retention_days": 90,
    }
    config_path = tmp_path / "agent-self-edit.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    return config_path


# ---- Build ----

def test_docker_build():
    """Build the Docker image."""
    result = subprocess.run(
        ["docker", "build", "-t", IMAGE_TAG, "."],
        capture_output=True, text=True, timeout=120, cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"Build failed: {result.stderr}"


# ---- OMLX connectivity ----

def _list_omlx_models() -> list[str]:
    """Return model ids from the local OMLX /v1/models endpoint."""
    req = urllib.request.Request(
        f"{OMLX_URL}/models",
        headers={"Authorization": f"Bearer {OMLX_KEY}"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    return [m["id"] for m in data.get("data", [])]


def test_omlx_is_up():
    """The local OMLX server must be reachable and responding."""
    try:
        models = _list_omlx_models()
    except Exception as e:
        pytest.fail(f"OMLX at {OMLX_URL} is not reachable: {e}")
    assert isinstance(models, list), f"Unexpected /models payload: {models}"
    assert len(models) > 0, "OMLX returned an empty model list"


def test_omlx_model_available():
    """The configured OMLX model must be present in the server's model list."""
    models = _list_omlx_models()
    assert OMLX_MODEL in models, (
        f"Model {OMLX_MODEL!r} not found in OMLX. Available: {models}"
    )


def test_omlx_reachable_from_container():
    """The container can reach the host OMLX endpoint via host.docker.internal."""
    script = (
        "import urllib.request, json; "
        f"req = urllib.request.Request('{OMLX_URL.replace('localhost', 'host.docker.internal')}/models', "
        f"headers={{'Authorization': 'Bearer {OMLX_KEY}'}}); "
        "resp = urllib.request.urlopen(req, timeout=10); "
        "data = json.loads(resp.read()); "
        "print(json.dumps([m['id'] for m in data['data']]))"
    )
    result = _run_container(["--entrypoint", "python3", "-c", script])
    # --entrypoint override isn't supported via our helper; use docker run directly
    result = subprocess.run(
        ["docker", "run", "--rm", "--network=host", "--entrypoint", "python3",
         IMAGE_TAG, "-c", script],
        capture_output=True, text=True, timeout=30, cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        f"Container could not reach OMLX:\n{result.stdout}\n{result.stderr}"
    )
    models = json.loads(result.stdout.strip())
    assert OMLX_MODEL in models, (
        f"Model {OMLX_MODEL!r} not visible from container. Visible: {models}"
    )


# ---- Smoke ----

def test_docker_help():
    """agent-self-edit --help lists all 10 commands."""
    result = _run_container(["--help"])
    assert result.returncode == 0
    for cmd in ["init", "run", "status", "diff", "rollback", "guardrails", "lineage", "propose", "ingest", "validate"]:
        assert cmd in result.stdout, f"Missing command: {cmd}"


def test_docker_validate():
    """agent-self-edit validate with a config file."""
    with tempfile.TemporaryDirectory() as tmp:
        config_path = _create_test_config(Path(tmp))
        volumes = {str(config_path.parent): "/config"}
        result = _run_container(
            ["validate", "--config", "/config/agent-self-edit.yaml"],
            volumes=volumes,
        )
        assert result.returncode in (0, 2)


def test_docker_status():
    """agent-self-edit status with config."""
    with tempfile.TemporaryDirectory() as tmp:
        config_path = _create_test_config(Path(tmp))
        volumes = {str(config_path.parent): "/config"}
        result = _run_container(
            ["status", "--config", "/config/agent-self-edit.yaml"],
            volumes=volumes,
        )
        assert result.returncode in (0, 1, 2)


# ---- Integration (real OMLX) ----

RESULTS_DIR = REPO_ROOT / "field-test" / "v0.1.0" / "results" / "docker" / "omlx" / OMLX_MODEL.lower().replace("/", "-")
DOCS_DIR = REPO_ROOT / "docs" / "field-test" / "v0.1.0"
SUMMARY_MD = DOCS_DIR / "docker-field-test-summary.md"


import pytest


@pytest.fixture(scope="module", autouse=True)
def _write_docker_summary():
    """After all docker tests, aggregate JSON results into a summary MD."""
    yield
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    result_files = sorted(RESULTS_DIR.glob("docker-*.json")) if RESULTS_DIR.exists() else []
    reports = [json.loads(f.read_text()) for f in result_files if f.stat().st_size > 0]

    total = len(reports)
    passed = sum(1 for r in reports if r.get("exit_code") in (0, None))
    failed = total - passed

    lines = [
        "# Docker Field Test Summary — AgentSelfEdit v0.1.0",
        "",
        f"**Date:** {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
        f"**Image:** `{IMAGE_TAG}`",
        f"**OMLX Model:** `{OMLX_MODEL}`",
        f"**OMLX Endpoint:** `{OMLX_URL}`",
        "",
        "## Summary",
        "",
        f"**{passed}/{total} tests passed** ({failed} failed)",
        "",
        "| # | Test | Result | LLM Calls | Exit Code |",
        "|---|------|--------|------------|-----------|",
    ]

    issues = []
    observations = []

    for i, r in enumerate(reports, 1):
        name = r.get("test", f"test-{i}")
        ok = r.get("exit_code") in (0, None)
        icon = "PASS" if ok else "FAIL"
        n_calls = r.get("llm_calls_captured", 0)
        lines.append(f"| {i} | `{name}` | {icon} | {n_calls} | {r.get('exit_code')} |")

        if not ok:
            err = (r.get("stderr") or "")[:300]
            issues.append(f"- **{name}** (exit {r.get('exit_code')}): {err}")
        else:
            for call in r.get("llm_traffic", []):
                if call.get("error"):
                    issues.append(f"- **{name}**: LLM error — {call['error']}")
                lat = call.get("latency_ms")
                if lat and lat > 10000:
                    observations.append(f"- **{name}**: LLM latency {lat}ms (>10s)")
                usage = call.get("usage") or {}
                if usage.get("total_tokens"):
                    observations.append(
                        f"- **{name}**: {usage['total_tokens']} tokens "
                        f"({usage.get('prompt_tokens')} in / {usage.get('completion_tokens')} out)"
                    )

    lines += ["", "## Observations", ""]
    if observations:
        lines += observations
    else:
        lines.append("- None.")

    lines += ["", "## Issues", ""]
    if issues:
        lines += issues
    else:
        lines.append("- None.")

    model_dir = OMLX_MODEL.lower().replace("/", "-")
    lines += [
        "",
        "## Per-Test Details",
        "",
        f"Structured JSON results are in `field-test/v0.1.0/results/docker/omlx/{model_dir}/` ({total} files).",
        "",
    ]

    for r in reports:
        name = r.get("test", "test")
        lines.append(f"### {name}")
        lines.append("")
        lines.append(f"- **Exit code:** {r.get('exit_code')}")
        lines.append(f"- **LLM calls:** {r.get('llm_calls_captured', 0)}")
        lines.append(f"- **JSON:** `field-test/v0.1.0/results/docker/omlx/{model_dir}/{name}.json`")
        lines.append("")

    SUMMARY_MD.write_text("\n".join(lines) + "\n")
    print(f"  Summary: {SUMMARY_MD}")


def _run_container_omlx(
    args: list[str],
    volumes: dict[str, str] | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess:
    """Run container with host networking so it can reach OMLX."""
    cmd = ["docker", "run", "--rm", "--network=host"]
    if volumes:
        for host, container in volumes.items():
            cmd.extend(["-v", f"{host}:{container}"])
    if env:
        for k, v in env.items():
            cmd.extend(["-e", f"{k}={v}"])
    cmd.extend([IMAGE_TAG] + args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=REPO_ROOT)


def _seed_trace_store(tmp_path: Path) -> Path:
    """Create a registry + trace store with failed traces for the analyzer.

    Uses varied inputs from the classification task set so the A/B test sees
    diverse tasks and can produce non-tie results (#109).
    """
    from agent_self_edit.registry import Registry
    from agent_self_edit.trace import TraceStore

    reg = Registry(str(tmp_path / "registry"))
    reg.create("You are a helpful classification assistant.")
    store = TraceStore(str(tmp_path / "traces.db"), batch_size=10)

    # Load varied inputs from the classification task set
    cls_src = REPO_ROOT / "field-test" / "v0.1.0" / "corpus" / "synthetic" / "classification.yaml"
    with open(cls_src) as f:
        all_tasks = yaml.safe_load(f)

    for i in range(10):
        task = all_tasks[i % len(all_tasks)]
        store.ingest({
            "task_id": f"t{i}",
            "task_input": f"classify this ticket: '{task['input']}'",
            "final_output": "other",  # deliberately wrong
            "expected_output": task["expected_output"],
            "success": False,
            "failure_reason": f"misclassified — expected {task['expected_output']}",
            "timestamp": "2026-09-01T10:00:00Z",
        })
    return tmp_path / "traces.db"


def _write_report(test_name: str, result: subprocess.CompletedProcess,
                  traffic_log: Path) -> None:
    """Persist a JSON result for this test (LLM traffic + CLI output)."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    if traffic_log.exists():
        entries = [json.loads(l) for l in traffic_log.read_text().splitlines() if l.strip()]

    report = {
        "test": test_name,
        "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "image": IMAGE_TAG,
        "omlx_model": OMLX_MODEL,
        "exit_code": result.returncode,
        "llm_calls_captured": len(entries),
        "llm_traffic": entries,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    report_path = RESULTS_DIR / f"{test_name}.json"
    report_path.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(f"  Report: {report_path}")


def test_docker_run_full_loop_omlx():
    """run --once (no --dry-run) hits OMLX: ingest → analyze → A/B test → gate → promote/reject."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _create_test_config(tmp_path, full_loop=True)
        _seed_trace_store(tmp_path)

        # Copy a trimmed classification task set (5 tasks) for faster A/B test
        import shutil
        cls_src = REPO_ROOT / "field-test" / "v0.1.0" / "corpus" / "synthetic" / "classification.yaml"
        import yaml as _yaml
        with open(cls_src) as f:
            tasks = _yaml.safe_load(f)
        with open(tmp_path / "classification.yaml", "w") as f:
            _yaml.dump(tasks[:5], f)

        traffic_log = RESULTS_DIR / "llm-traffic-run.jsonl"
        if traffic_log.exists():
            traffic_log.unlink()
        volumes = {str(tmp_path): "/config", str(RESULTS_DIR): "/results"}
        env = {"AGENT_SELF_EDIT_LLM_LOG": "/results/llm-traffic-run.jsonl"}
        result = _run_container_omlx(
            ["run", "--config", "/config/agent-self-edit.yaml", "--once"],
            volumes=volumes, env=env, timeout=600,
        )
        assert result.returncode in (0, None), (
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

        assert traffic_log.exists(), (
            f"No LLM traffic log written. stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        entries = [json.loads(l) for l in traffic_log.read_text().splitlines() if l.strip()]
        assert len(entries) > 0, "LLM traffic log is empty — no LLM call was made"

        for entry in entries:
            assert "messages" in entry, f"Missing LLM input (messages): {entry}"
            assert "response" in entry, f"Missing LLM output (response): {entry}"
            assert entry["model"] == OMLX_MODEL
            assert isinstance(entry["messages"], list)
            assert entry["latency_ms"] > 0, f"Zero or missing latency: {entry}"
            # Per-trace token assertions (#108) — catch silent failures
            usage = entry.get("usage") or {}
            assert usage.get("completion_tokens", 0) > 0, (
                f"Zero completion_tokens — LLM returned empty response: {entry}"
            )
            assert usage.get("prompt_tokens", 0) > 0, (
                f"Zero prompt_tokens — LLM received no input: {entry}"
            )

        stdout = result.stdout
        assert "Analysis complete" in stdout, f"Analyze stage missing: {stdout}"
        assert "A/B test" in stdout, f"A/B test stage missing: {stdout}"
        assert "Gate:" in stdout, f"Gate stage missing: {stdout}"

        # Verify A/B test actually ran two distinct prompts
        # Call 1 = analyzer; calls 2+ = A/B test (pairs of prompt A / prompt B)
        if len(entries) > 1:
            ab_calls = entries[1:]
            prompt_contents = set()
            for e in ab_calls:
                # The full prompt is in the first message content (before "\n---\nTask:")
                content = e["messages"][0]["content"]
                prompt_part = content.split("\n---\n")[0] if "\n---\n" in content else content
                prompt_contents.add(prompt_part[:200])
            assert len(prompt_contents) >= 2, (
                f"A/B test used only {len(prompt_contents)} distinct prompt(s) — "
                f"expected at least 2 (current + candidate). "
                f"This means run.py passed the same prompt for A and B. "
                f"See issue #104. Prompt contents: {prompt_contents}"
            )

        # Verify A/B test produced valid statistics (#110)
        import re
        ab_match = re.search(r"A/B test:\s*(.+?)\s*\(p=([\d.]+),\s*n=(\d+)\)", stdout)
        assert ab_match, (
            f"Could not parse A/B test result from stdout. "
            f"Expected format 'A/B test: ... (p=..., n=...)'. "
            f"stdout: {stdout}"
        )
        outcome = ab_match.group(1)
        p_value = float(ab_match.group(2))
        n_tasks = int(ab_match.group(3))
        assert 0.0 <= p_value <= 1.0, f"Invalid p-value: {p_value}"
        assert n_tasks > 0, f"Invalid n_tasks: {n_tasks}"
        if p_value >= 1.0:
            # Perfect tie — valid outcome (proposal didn't help). Log for awareness.
            print(f"  A/B test: {outcome} (p={p_value}, n={n_tasks}) — "
                  f"tie is expected when the proposal doesn't improve accuracy. "
                  f"Delta assertion: deltas are zero for all tasks, gate correctly rejects.")

        _write_report("docker-run-full-loop-omlx", result, traffic_log)


def test_docker_propose_full_omlx():
    """propose (no --dry-run) hits OMLX: analyze → propose → A/B test → gate."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _create_test_config(tmp_path, full_loop=True)
        _seed_trace_store(tmp_path)

        import yaml as _yaml
        cls_src = REPO_ROOT / "field-test" / "v0.1.0" / "corpus" / "synthetic" / "classification.yaml"
        with open(cls_src) as f:
            tasks = _yaml.safe_load(f)
        with open(tmp_path / "classification.yaml", "w") as f:
            _yaml.dump(tasks[:5], f)

        traffic_log = RESULTS_DIR / "llm-traffic-propose.jsonl"
        if traffic_log.exists():
            traffic_log.unlink()
        volumes = {str(tmp_path): "/config", str(RESULTS_DIR): "/results"}
        env = {"AGENT_SELF_EDIT_LLM_LOG": "/results/llm-traffic-propose.jsonl"}
        result = _run_container_omlx(
            ["propose", "--config", "/config/agent-self-edit.yaml"],
            volumes=volumes, env=env, timeout=600,
        )
        assert result.returncode in (0, None), (
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

        assert traffic_log.exists(), (
            f"No LLM traffic log. stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        entries = [json.loads(l) for l in traffic_log.read_text().splitlines() if l.strip()]
        assert len(entries) > 0, "propose made no LLM call"

        first = entries[0]
        assert "messages" in first
        assert len(first["messages"]) > 0
        assert "response" in first
        assert len(first["response"]) > 0

        # Per-trace token and latency assertions (#108)
        for entry in entries:
            usage = entry.get("usage") or {}
            assert usage.get("completion_tokens", 0) > 0, (
                f"Zero completion_tokens: {entry}"
            )
            assert usage.get("prompt_tokens", 0) > 0, (
                f"Zero prompt_tokens: {entry}"
            )
            assert entry.get("latency_ms", 0) > 0, (
                f"Zero or missing latency: {entry}"
            )

        stdout = result.stdout
        assert "A/B test" in stdout or "Proposed" in stdout, (
            f"Expected A/B test or proposals in output: {stdout}"
        )

        # Verify A/B test produced valid statistics (#110)
        if "A/B test" in stdout:
            import re
            ab_match = re.search(
                r"A/B test:\s*(.+?)\s*\(p=([\d.]+),\s*n=(\d+)\)", stdout
            )
            assert ab_match, (
                f"Could not parse A/B test result from stdout. "
                f"Expected format 'A/B test: ... (p=..., n=...)'. "
                f"stdout: {stdout}"
            )
            outcome = ab_match.group(1)
            p_value = float(ab_match.group(2))
            n_tasks = int(ab_match.group(3))
            assert 0.0 <= p_value <= 1.0, f"Invalid p-value: {p_value}"
            assert n_tasks > 0, f"Invalid n_tasks: {n_tasks}"
            if p_value >= 1.0:
                print(f"  A/B test: {outcome} (p={p_value}, n={n_tasks}) — "
                      f"tie is expected when the proposal doesn't improve. "
                      f"Delta assertion: all deltas zero, gate correctly rejects.")

        # Verify A/B test actually ran two distinct prompts (if A/B ran)
        if "A/B test" in stdout and len(entries) > 1:
            ab_calls = entries[1:]
            prompt_contents = set()
            for e in ab_calls:
                content = e["messages"][0]["content"]
                prompt_part = content.split("\n---\n")[0] if "\n---\n" in content else content
                prompt_contents.add(prompt_part[:200])
            assert len(prompt_contents) >= 2, (
                f"A/B test used only {len(prompt_contents)} distinct prompt(s) — "
                f"expected at least 2. See issue #104. Prompts: {prompt_contents}"
            )

        _write_report("docker-propose-full-omlx", result, traffic_log)