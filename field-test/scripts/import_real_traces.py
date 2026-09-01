"""Generate real-traces corpus from portfolio data.

Converts agent-exec-trace telemetry and agent-eval-forge results
into the AgentSelfEdit Trace schema.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "src"))

from agent_self_edit.types import utc_now_iso

OUTPUT = Path(__file__).resolve().parent.parent / "v0.1.0" / "corpus" / "real-life" / "real-traces"


def _unique_task_id(prefix: str, counter: int) -> str:
    """Generate a unique task_id using a prefix and monotonic counter."""
    import hashlib
    import random
    unique = hashlib.md5(f"{prefix}-{counter}-{random.random()}".encode()).hexdigest()[:12]
    return f"{prefix}_{unique}"


def convert_agent_observatory_telemetry(input_path: str, output_name: str = "agent-observatory-traces.jsonl") -> int:
    """Convert agent-exec-trace JSONL telemetry to Trace schema.

    Input format (from agent-exec-trace m13-results):
        {trace_id, detector, model, latency_ms, prompt_tokens, completion_tokens,
         total_tokens, finish_reason, prompt_chars, system_chars, content_chars, cache_hit}

    Output format: Trace schema JSON-lines.
    """
    path = Path(input_path)
    if not path.exists():
        print(f"  Skipping: {input_path} not found")
        return 0

    output_path = OUTPUT / output_name
    count = 0
    with open(input_path) as f_in, open(output_path, "w") as f_out:
        for line in f_in:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue

            detector = raw.get("detector", "unknown")
            failure_detectors = {"semantic_loop", "hallucination", "quality_degradation", "confusion_pattern", "failure"}
            success = detector not in failure_detectors

            trace = {
                "task_id": _unique_task_id("obs", count),
                "task_input": f"Agent task with detector {detector}",
                "final_output": str(raw.get("content_chars", "0")) + " chars produced",
                "expected_output": "no hallucination, no loop, no degradation",
                "success": success,
                "failure_reason": detector if not success else None,
                "timestamp": utc_now_iso(),
                "prompt_version": 1,
                "steps": [
                    {
                        "action": "llm_call",
                        "model": raw.get("model", "unknown"),
                        "latency_ms": raw.get("latency_ms", 0),
                        "prompt_tokens": raw.get("prompt_tokens", 0),
                        "completion_tokens": raw.get("completion_tokens", 0),
                        "total_tokens": raw.get("total_tokens", 0),
                        "finish_reason": raw.get("finish_reason", "stop"),
                        "cache_hit": raw.get("cache_hit", False),
                    }
                ],
            }
            f_out.write(json.dumps(trace) + "\n")
            count += 1

    print(f"  Wrote {count} traces to {output_path}")
    return count


def convert_evalforge_failures(results_dir: str, output_name: str = "evalforge-failures.jsonl") -> int:
    """Convert EvalForge failed scenario results to Trace schema.

    Input: directory of agent-eval-forge field/results/tests/ with result.json + score-*.json.
    """
    result_dir = Path(results_dir)
    if not result_dir.exists():
        print(f"  Skipping: {results_dir} not found")
        return 0

    output_path = OUTPUT / output_name
    count = 0
    with open(output_path, "w") as f_out:
        for result_file in sorted(result_dir.rglob("result.json")):
            try:
                data = json.loads(result_file.read_text())
            except (json.JSONDecodeError, OSError):
                continue

            if data.get("status") == "passed":
                continue

            agent = data.get("agent_id", "unknown")
            scenario = data.get("scenario_id", "unknown")
            reason = data.get("reason", "failed")

            trace = {
                "task_id": _unique_task_id(f"{agent}", count),
                "task_input": f"Scenario: {scenario} for agent {agent}",
                "final_output": f"Agent {agent} failed scenario {scenario}",
                "expected_output": f"Scenario {scenario} should pass",
                "success": False,
                "failure_reason": reason[:200],
                "timestamp": data.get("started_at", utc_now_iso()),
                "prompt_version": 1,
                "steps": [
                    {
                        "action": "scenario_execution",
                        "agent": agent,
                        "model": data.get("model", "unknown"),
                        "tier": data.get("tier", "unknown"),
                        "duration_sec": data.get("duration_sec", 0),
                        "exit_code": data.get("exit_code", -1),
                        "status": data.get("status", "unknown"),
                    }
                ],
            }
            f_out.write(json.dumps(trace) + "\n")
            count += 1

    print(f"  Wrote {count} traces to {output_path}")
    return count


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    total = 0

    # agent-exec-trace paths
    home = Path.home()
    obs_paths = [
        home / "Desktop/code/github/agent-exec-trace/docs/field-test/m13-results/25-traces/llm-9b-telemetry.jsonl",
        home / "Desktop/code/github/agent-exec-trace/docs/field-test/m13-results/25-traces/llm-4b-telemetry.jsonl",
        home / "Desktop/code/github/agent-exec-trace/docs/field-test/m13-results/100-traces/llm-9b-telemetry.jsonl",
        home / "Desktop/code/github/agent-exec-trace/docs/field-test/m13-results/100-traces/llm-4b-telemetry.jsonl",
    ]
    for p in obs_paths:
        total += convert_agent_observatory_telemetry(str(p))

    # agent-eval-forge paths
    eval_paths = [
        home / "Desktop/code/github/agent-eval-forge/field/results/tests",
    ]
    for p in eval_paths:
        total += convert_evalforge_failures(str(p))

    print(f"\nTotal traces generated: {total}")
