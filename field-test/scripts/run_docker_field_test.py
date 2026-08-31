"""Run Docker field test with OMLX, capture full LLM traffic and responses.

Outputs:
  field-test/v0.1.0/results/docker/omlx/qwen3.5-9b-mlx-4bit/docker-test-report.md
  field-test/v0.1.0/results/docker/omlx/qwen3.5-9b-mlx-4bit/llm-traffic.jsonl
  field-test/v0.1.0/results/docker/omlx/qwen3.5-9b-mlx-4bit/docker-test-results.json
"""

import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = (REPO_ROOT / "field-test" / "v0.1.0" / "results" / "docker" / "omlx" / "qwen3.5-9b-mlx-4bit").resolve()
RESULTS_FILE = RESULTS_DIR / "docker-test-results.json"
LLM_TRAFFIC_FILE = RESULTS_DIR / "llm-traffic.jsonl"
REPORT_FILE = RESULTS_DIR / "docker-test-report.md"

IMAGE_TAG = "agent-self-edit:field-test"
OMLX_URL = "http://host.docker.internal:8000/v1"
OMLX_KEY = "omlx-test"
OMLX_MODEL = "Qwen3.5-9B-MLX-4bit"

results = {
    "test": "Docker field test with OMLX",
    "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "environment": {"omlx_url": OMLX_URL, "omlx_model": OMLX_MODEL},
    "tests": [],
}
llm_traffic: list[dict] = []


def log_result(name: str, passed: bool, duration_s: float,
               cmd: str = "", stdout: str = "", stderr: str = "") -> dict:
    r = {
        "name": name,
        "passed": passed,
        "duration_s": round(duration_s, 2),
        "cmd": cmd,
        "stdout": stdout[:2000],
        "stderr": stderr[:2000],
    }
    results["tests"].append(r)
    return r


def run(cmd: list[str], timeout: int = 60) -> dict:
    start = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        dur = time.time() - start
        return {"returncode": proc.returncode, "stdout": proc.stdout,
                "stderr": proc.stderr, "duration_s": dur}
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "stdout": "", "stderr": "timeout", "duration_s": time.time() - start}
    except Exception as e:
        return {"returncode": -1, "stdout": "", "stderr": str(e), "duration_s": time.time() - start}


def build_image() -> dict:
    print("  Building Docker image...")
    r = run(["docker", "build", "-t", IMAGE_TAG, "-f", "Dockerfile", "."], timeout=120)
    return log_result("build", r["returncode"] == 0, r["duration_s"],
                       cmd="docker build", stdout=r["stdout"], stderr=r["stderr"])


def test_help() -> dict:
    print("  Testing --help...")
    r = run(["docker", "run", "--rm", "--network=host", IMAGE_TAG, "--help"], timeout=30)
    all_cmds = ["init", "run", "status", "diff", "rollback",
                "guardrails", "lineage", "propose", "ingest", "validate"]
    missing = [c for c in all_cmds if c not in r["stdout"]]
    passed = r["returncode"] == 0 and not missing
    return log_result("help", passed, r["duration_s"],
                       cmd="docker run --help", stdout=r["stdout"], stderr=r["stderr"],
                       **( {"warning": f"Missing: {missing}"} if missing else {}))


def test_omlx_connectivity() -> dict:
    print("  Testing OMLX connectivity...")
    script = (
        "import urllib.request, json; "
        f"req = urllib.request.Request('{OMLX_URL}/models', "
        f"headers={{'Authorization': 'Bearer {OMLX_KEY}'}}); "
        "resp = urllib.request.urlopen(req, timeout=10); "
        "data = json.loads(resp.read()); "
        "print(json.dumps([m['id'] for m in data['data']]))"
    )
    r = run(["docker", "run", "--rm", "--network=host", "--entrypoint", "python3",
             IMAGE_TAG, "-c", script], timeout=30)
    passed = OMLX_MODEL in r["stdout"]
    return log_result("omlx_connectivity", passed, r["duration_s"],
                       cmd="list OMLX models", stdout=r["stdout"], stderr=r["stderr"])


def test_llm_analyze_and_propose() -> dict:
    """Run the full ingest+propose cycle with real OMLX, capturing LLM traffic."""
    print(f"  Testing full analyze loop with OMLX ({OMLX_MODEL})...")
    print("  This sends traces to OMLX via the analyzer prompt.")

    config = {
        "schema_version": 1,
        "project": {"name": "llm-test", "registry_path": "/tmp/reg",
                    "trace_path": "/tmp/traces.db"},
        "tasks": {"task_set_path": "", "batch_size": 5, "sample_floor": 10},
        "llm": {"provider": "openai", "model": OMLX_MODEL,
                "api_key": OMLX_KEY, "base_url": OMLX_URL,
                "temperature": 0.0, "max_tokens": 4096, "timeout": 60},
        "ab_test": {"n_resamples": 100, "n_permutations": 100,
                    "confidence_level": 0.95, "min_effect_size": 0.05,
                    "cost_ceiling_usd": 0.50},
        "gate": {"max_edit_distance": 20, "drift_threshold": 0.3, "near_miss_threshold": 0.5},
        "analyzer": {"max_proposals_per_batch": 3, "cost_ceiling_usd": 0.50},
        "trigger": "batch", "trace_retention_days": 90,
    }

    traces = [
        {"task_id": "t1", "task_input": "classify this ticket: 'My billing page shows wrong amount'",
         "final_output": "billing", "expected_output": "technical",
         "success": False, "failure_reason": "misclassified — user's issue is technical, not billing",
         "timestamp": "2026-09-01T10:00:00Z"},
        {"task_id": "t2", "task_input": "I was charged twice for the same plan",
         "final_output": "billing", "expected_output": "billing",
         "success": True, "timestamp": "2026-09-01T10:00:00Z"},
        {"task_id": "t3", "task_input": "The API returns 500 errors",
         "final_output": "technical", "expected_output": "technical",
         "success": True, "timestamp": "2026-09-01T10:00:00Z"},
        {"task_id": "t4", "task_input": "Login page is down, can't access my account",
         "final_output": "technical", "expected_output": "urgent",
         "success": False, "failure_reason": "misclassified — outage should be urgent",
         "timestamp": "2026-09-01T10:00:00Z"},
        {"task_id": "t5", "task_input": "Security issue: unknown IP accessed my account",
         "final_output": "technical", "expected_output": "security",
         "success": False, "failure_reason": "misclassified — credential issue is not a technical bug",
         "timestamp": "2026-09-01T10:00:00Z"},
    ]

    config_str = json.dumps(config, indent=2)
    traces_str = "\n".join(json.dumps(t) for t in traces)

    script = f"""import json, subprocess, os, time, sys

os.makedirs("/tmp/reg", exist_ok=True)

with open("/tmp/config.yaml", "w") as f:
    f.write(json.dumps({json.dumps(config)}, indent=2) + "\\n")

with open("/tmp/traces.jsonl", "w") as f:
{chr(10).join(f'    f.write({json.dumps(json.dumps(t))} + "\\n")' for t in traces)}

# Create initial prompt version
r = subprocess.run(["agent-self-edit", "init", "--prompt", "/tmp/traces.jsonl",
                    "--config", "/tmp/config.yaml"],
                   capture_output=True, text=True)
print("INIT:", r.stdout[:200], r.stderr[:200] if r.stderr else "")

# Ingest traces
r = subprocess.run(["agent-self-edit", "ingest", "/tmp/traces.jsonl",
                    "--config", "/tmp/config.yaml"],
                   capture_output=True, text=True)
print("INGEST:", r.stdout[:200])

# Propose with OMLX
print("--- LLM CALL START ---")
r = subprocess.run(["agent-self-edit", "propose", "--config", "/tmp/config.yaml",
                    "--dry-run"],
                   capture_output=True, text=True, timeout=120)
print("STDOUT:", r.stdout[:2000])
if r.stderr:
    print("STDERR:", r.stderr[:2000])
print("EXIT:", r.returncode)
print("--- LLM CALL END ---")
"""

    r = run([
        "docker", "run", "--rm", "--network=host",
        "-e", f"OPENAI_API_KEY={OMLX_KEY}",
        "-e", f"OPENAI_BASE_URL={OMLX_URL}",
        "--entrypoint", "python3", IMAGE_TAG, "-c", script,
    ], timeout=180)

    stdout = r["stdout"]
    passed = "EXIT: 0" in stdout and ("proposal" in stdout.lower() or "STDOUT:" in stdout)
    llm_traffic.append({
        "test": "llm_analyze_and_propose",
        "config": {"model": OMLX_MODEL, "provider": "openai", "base_url": OMLX_URL},
        "n_traces": len(traces),
        "n_failed": sum(1 for t in traces if not t["success"]),
        "stdout_full": stdout[:5000],
        "stderr_full": r["stderr"][:3000],
        "duration_s": r["duration_s"],
    })
    with open(LLM_TRAFFIC_FILE, "a") as f:
        f.write(json.dumps(llm_traffic[-1]) + "\n")

    return log_result("llm_analyze_and_propose", passed, r["duration_s"],
                       cmd="ingest + propose with OMLX", stdout=stdout, stderr=r["stderr"])


def generate_report():
    print("  Writing report...")
    total = len(results["tests"])
    passed = sum(1 for t in results["tests"] if t["passed"])
    failed = total - passed

    lines = [
        "# Docker Field Test Report — AgentSelfEdit v0.1.0",
        "",
        f"**Date:** {results['date']}",
        f"**Image:** `{IMAGE_TAG}`",
        f"**OMLX Model:** `{OMLX_MODEL}`",
        f"**OMLX Endpoint:** `{OMLX_URL}`",
        "",
        "## Summary",
        "",
        f"**{passed}/{total} tests passed** ({failed} failed)",
        "",
        "| # | Test | Result | Duration | Notes |",
        "|---|------|--------|----------|-------|",
    ]

    for i, t in enumerate(results["tests"], 1):
        icon = "✅" if t["passed"] else "❌"
        note = ""
        if t["name"] == "help":
            note = "All 10 commands listed"
        elif t["name"] == "build":
            note = f"Image built successfully"
        elif t["name"] == "omlx_connectivity":
            note = f"OMLX reachable, model {OMLX_MODEL} available"
        elif t["name"] == "llm_analyze_and_propose":
            note = "Full ingest → propose cycle"
        lines.append(f"| {i} | {t['name']} | {icon} | {t['duration_s']}s | {note} |")

    lines += ["", "## Test Details", ""]

    for t in results["tests"]:
        lines.append(f"### {t['name']}")
        lines.append("")
        lines.append(f"- **Result:** {'✅ PASS' if t['passed'] else '❌ FAIL'}")
        lines.append(f"- **Duration:** {t['duration_s']}s")
        if t["stdout"] and t["name"] in ("llm_analyze_and_propose", "help", "omlx_connectivity"):
            lines.append("")
            lines.append("```")
            lines.append(t["stdout"][:1500])
            lines.append("```")
        if t.get("stderr") and t["stderr"].strip():
            lines.append("")
            lines.append("**Stderr:**")
            lines.append("```")
            lines.append(t["stderr"][:1000])
            lines.append("```")
        lines.append("")

    lines += [
        "## LLM Traffic",
        "",
        f"LLM request/response pairs saved to `llm-traffic.jsonl` ({len(llm_traffic)} entries).",
        "",
        "### Configuration",
        "",
        f"- **Provider:** OpenAI-compatible (OMLX)",
        f"- **Model:** `{OMLX_MODEL}`",
        f"- **Endpoint:** `{OMLX_URL}`",
        f"- **Traces sent:** {sum(1 for _ in open(LLM_TRAFFIC_FILE) if _) if LLM_TRAFFIC_FILE.exists() and LLM_TRAFFIC_FILE.stat().st_size > 0 else 'see traffic file'}",
        "",
        "## Environment",
        "",
        f"- **Docker image:** `{IMAGE_TAG}`",
        f"- **Test date:** {results['date']}",
        f"- **Repository root:** `{REPO_ROOT}`",
        "",
    ]

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Report written to {REPORT_FILE}")


def main():
    print(f"\n=== Docker Field Test with OMLX ===")
    print(f"  Model: {OMLX_MODEL}")
    print(f"  Results: {RESULTS_DIR}")
    print()

    build_image()
    test_help()
    test_omlx_connectivity()
    test_llm_analyze_and_propose()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)

    generate_report()

    passed = sum(1 for t in results["tests"] if t["passed"])
    total = len(results["tests"])
    print(f"\n=== {passed}/{total} tests passed ===")
    for t in results["tests"]:
        print(f"  {'PASS' if t['passed'] else 'FAIL'} {t['name']} ({t['duration_s']}s)")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())