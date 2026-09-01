"""Run N self-improvement iterations via agent-self-edit run --once.

Seeds failed traces each iteration, runs the full loop (analyze → A/B test →
gate → promote/reject), measures accuracy on a held-out set, and reports
per-iteration metrics.

Usage:
    python field-test/scripts/run_improvement_loop.py --iterations 10

Requires: OMLX_KEY, OMLX_MODEL, OMLX_URL env vars set.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = REPO_ROOT / "field-test" / "v0.1.0" / "results" / "improvement-loop"
CLASSIFICATION_TASKS = REPO_ROOT / "field-test" / "v0.1.0" / "corpus" / "synthetic" / "classification.yaml"

HELD_OUT_TASKS: list[dict[str, str]] = [
    {"id": "classify-006", "input": "I think my account was compromised — someone logged in from an unknown IP.", "expected_output": "security"},
    {"id": "classify-011", "input": "I'm paying for a service I can't use because the login page is down.", "expected_output": "urgent"},
    {"id": "classify-015", "input": "When will the maintenance window end? Our team is blocked.", "expected_output": "urgent"},
    {"id": "classify-019", "input": "I'm getting a 403 Forbidden error on endpoints I used to access.", "expected_output": "security"},
    {"id": "classify-024", "input": "I want to request a new integration feature and also report that the billing page is broken.", "expected_output": "feature, billing"},
]

BASELINE_PROMPT = "You are a helpful classification assistant."


def _build_llm(config: dict):
    """Build LLM provider from config dict."""
    from agent_self_edit.llm.openai import OpenAIProvider
    return OpenAIProvider(
        model=config["llm"]["model"],
        api_key=config["llm"]["api_key"],
        base_url=config["llm"]["base_url"],
        timeout=config["llm"]["timeout"],
        max_tokens=config["llm"]["max_tokens"],
    )


def measure_accuracy(prompt: str, llm, tasks: list[dict]) -> dict:
    """Run prompt against held-out tasks and return accuracy metrics."""
    from agent_self_edit.scorers import ExactMatchScorer
    scorer = ExactMatchScorer()
    correct = 0
    results = []
    for task in tasks:
        try:
            output = llm.complete(prompt=task["input"], system_prompt=prompt, temperature=0.0)
        except Exception as e:
            output = ""
            error = str(e)
        passed, score = scorer.score(task["expected_output"], output)
        if passed:
            correct += 1
        results.append({
            "task_id": task["id"],
            "expected": task["expected_output"],
            "actual": output,
            "passed": passed,
            "score": score,
        })
    return {
        "accuracy": round(correct / len(tasks) * 100, 1),
        "correct": correct,
        "total": len(tasks),
        "results": results,
    }


def seed_trace_store(trace_path: str, task_set_path: str, n: int = 10) -> None:
    """Create a fresh TraceStore with n failed traces from the task set."""
    import yaml
    from agent_self_edit.trace import TraceStore

    # Remove existing db
    db_path = Path(trace_path)
    if db_path.exists():
        db_path.unlink()

    store = TraceStore(str(db_path), batch_size=n)
    with open(task_set_path) as f:
        tasks = yaml.safe_load(f)

    for i in range(min(n, len(tasks))):
        task = tasks[i]
        store.ingest({
            "task_id": f"iter-{i}",
            "task_input": task["input"],
            "final_output": "other",
            "expected_output": task["expected_output"],
            "success": False,
            "failure_reason": f"misclassified — expected {task['expected_output']}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })


def get_current_prompt(registry_path: str) -> str:
    """Read the current prompt from the registry."""
    from agent_self_edit.registry import Registry
    reg = Registry(registry_path)
    return reg.current_prompt


def write_config(work_dir: Path, config: dict) -> Path:
    """Write config YAML to work directory."""
    import yaml
    config_path = work_dir / "agent-self-edit.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    return config_path


def copy_task_set(work_dir: Path, n: int = 5) -> Path:
    """Copy first n tasks from classification.yaml to work dir."""
    import yaml
    with open(CLASSIFICATION_TASKS) as f:
        tasks = yaml.safe_load(f)
    task_set_path = work_dir / "classification.yaml"
    with open(task_set_path, "w") as f:
        yaml.dump(tasks[:n], f)
    return task_set_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run N self-improvement iterations")
    parser.add_argument("--iterations", type=int, default=10, help="Number of iterations")
    parser.add_argument("--traces-per-iteration", type=int, default=10, help="Traces to seed each iteration")
    parser.add_argument("--model", default=os.environ.get("OMLX_MODEL", ""))
    parser.add_argument("--endpoint", default=os.environ.get("OMLX_URL", ""))
    args = parser.parse_args()
    api_key = os.environ.get("OMLX_KEY", "")

    if not args.model or not args.endpoint or not api_key:
        print("ERROR: OMLX_KEY, OMLX_MODEL, and OMLX_URL must be set", file=sys.stderr)
        sys.exit(1)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = RESULTS_DIR / "improvement-loop-report.json"

    config = {
        "schema_version": 1,
        "project": {"name": "improvement-loop", "registry_path": "/tmp/ase-registry", "trace_path": "/tmp/ase-traces.db"},
        "tasks": {"task_set_path": "", "batch_size": args.traces_per_iteration, "sample_floor": 10},
        "llm": {"provider": "openai", "model": args.model, "api_key": api_key,
                "base_url": args.endpoint, "temperature": 0.0, "max_tokens": 4096, "timeout": 60},
        "ab_test": {"n_resamples": 100, "n_permutations": 100, "confidence_level": 0.95, "min_effect_size": 0.05, "cost_ceiling_usd": 0.50},
        "gate": {"max_edit_distance": 20, "drift_threshold": 0.3, "near_miss_threshold": 0.5},
        "analyzer": {"max_proposals_per_batch": 3, "cost_ceiling_usd": 0.50},
        "trigger": "batch", "trace_retention_days": 90,
    }

    # Initialize registry
    from agent_self_edit.registry import Registry
    reg = Registry(config["project"]["registry_path"])
    try:
        reg.create(BASELINE_PROMPT)
    except Exception:
        pass  # already exists

    llm = _build_llm(config)
    llm_traffic: list[dict] = []
    iterations: list[dict] = []

    # Baseline accuracy
    baseline = measure_accuracy(BASELINE_PROMPT, llm, HELD_OUT_TASKS)
    print(f"Baseline accuracy: {baseline['accuracy']}% ({baseline['correct']}/{baseline['total']})")
    iterations.append({"iteration": 0, "prompt": BASELINE_PROMPT, **baseline, "gate": "baseline", "cost": 0.0})

    for i in range(1, args.iterations + 1):
        print(f"\n=== Iteration {i}/{args.iterations} ===")

        # Create fresh work directory
        with tempfile.TemporaryDirectory(prefix=f"ase-iter-{i}-") as tmp:
            work_dir = Path(tmp)

            # Set up config paths
            config["project"]["trace_path"] = str(work_dir / "traces.db")
            config["project"]["registry_path"] = str(work_dir / "registry")
            config["tasks"]["task_set_path"] = str(copy_task_set(work_dir, 5))

            # Copy registry from previous iteration
            src_reg = Path(reg._path) if hasattr(reg, '_path') else Path(config["project"]["registry_path"])
            if src_reg.exists():
                shutil.copytree(src_reg, work_dir / "registry", dirs_exist_ok=True)

            config_path = write_config(work_dir, config)

            # Seed traces
            seed_trace_store(config["project"]["trace_path"], str(CLASSIFICATION_TASKS), args.traces_per_iteration)

            # Run the self-edit loop
            env = os.environ.copy()
            traffic_log = work_dir / "llm-traffic.jsonl"
            env["AGENT_SELF_EDIT_LLM_LOG"] = str(traffic_log)

            result = subprocess.run(
                [sys.executable, "-m", "agent_self_edit.cli", "run", "--config", str(config_path), "--once"],
                capture_output=True, text=True, timeout=600, env=env,
                cwd=REPO_ROOT,
            )
            stdout = result.stdout + "\n" + (result.stderr or "")

            # Read traffic
            iter_traffic = []
            if traffic_log.exists():
                for line in traffic_log.read_text().splitlines():
                    line = line.strip()
                    if line:
                        try:
                            iter_traffic.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass

            llm_traffic.extend(iter_traffic)

            # Parse results from stdout
            gate = "unknown"
            for line in stdout.splitlines():
                if "Gate:" in line:
                    gate = line.split("Gate:")[-1].strip()
                    break

            cost = 0.0
            for line in stdout.splitlines():
                if "cost=$" in line:
                    try:
                        cost = float(line.split("cost=$")[-1].split(")")[0])
                    except (ValueError, IndexError):
                        pass

            ab_result = "none"
            for line in stdout.splitlines():
                if "A/B test:" in line:
                    ab_result = line.strip()
                    break

            # Read current prompt from registry
            current_prompt = get_current_prompt(str(work_dir / "registry"))

            # Measure accuracy
            accuracy = measure_accuracy(current_prompt, llm, HELD_OUT_TASKS)

            iter_record = {
                "iteration": i,
                "prompt": current_prompt[:200],
                "prompt_hash": hashlib.md5(current_prompt.encode()).hexdigest()[:12],
                "gate": gate,
                "cost": cost,
                "ab_result": ab_result,
                "n_llm_calls": len(iter_traffic),
                **accuracy,
            }
            iterations.append(iter_record)

            print(f"  Gate: {gate}")
            print(f"  Accuracy: {accuracy['accuracy']}% ({accuracy['correct']}/{accuracy['total']})")
            print(f"  A/B: {ab_result}")
            print(f"  Cost: ${cost:.4f}")
            print(f"  LLM calls: {len(iter_traffic)}")

            # Copy registry to next iteration
            src = work_dir / "registry"
            if src.exists():
                dst = Path(config["project"]["registry_path"])
                dst.parent.mkdir(parents=True, exist_ok=True)
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)

    # Final report
    report = {
        "meta": {
            "model": args.model,
            "endpoint": args.endpoint,
            "n_iterations": args.iterations,
            "traces_per_iteration": args.traces_per_iteration,
            "baseline_accuracy": baseline["accuracy"],
            "final_accuracy": iterations[-1]["accuracy"],
            "improvement": round(iterations[-1]["accuracy"] - baseline["accuracy"], 1),
            "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "iterations": iterations,
        "llm_traffic": llm_traffic,
    }
    report_path.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(f"\nReport: {report_path}")

    print(f"\n=== Summary ===")
    print(f"  Baseline: {baseline['accuracy']}%")
    print(f"  Final:    {iterations[-1]['accuracy']}%")
    print(f"  Delta:    {report['meta']['improvement']}%")
    for it in iterations[1:]:
        print(f"  Iter {it['iteration']}: {it['accuracy']}% (gate: {it['gate']})")


if __name__ == "__main__":
    import hashlib
    main()