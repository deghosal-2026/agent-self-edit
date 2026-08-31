"""Download HuggingFace agent trace datasets for the field test corpus.

Usage:
    pip install datasets
    python field-test/scripts/download_hf_traces.py

Output: field-test/v0.1.0/corpus/real-traces/hf-*.jsonl
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "v0.1.0" / "corpus" / "real-life" / "real-traces"


def convert_events_to_trace(events: list[dict]) -> dict | None:
    """Convert a list of OCEL events (one agent run) into a single Trace."""
    if not events:
        return None

    run_id = events[0].get("run_id", "unknown")
    user_query = events[0].get("user_query", "")
    domain = events[0].get("domain", "unknown")

    has_deviation = any(e.get("is_deviation") for e in events)
    deviation_types = list(set(
        e.get("deviation_type", "") for e in events if e.get("is_deviation")
    ))

    steps = []
    total_tokens = 0
    total_latency = 0.0
    total_cost = 0.0
    final_output = ""

    for e in events:
        event_type = e.get("event_type", "")
        step = {
            "event_type": event_type,
            "agent_role": e.get("agent_role", ""),
            "model": e.get("model_name", ""),
            "sequence_number": e.get("sequence_number", 0),
        }
        if event_type == "llm_request_sent":
            step["input_tokens"] = e.get("input_tokens", 0)
        elif event_type == "llm_response_received":
            step["output_tokens"] = e.get("output_tokens", 0)
            step["latency_ms"] = e.get("latency_ms", 0)
            total_latency += e.get("latency_ms", 0) or 0
            total_tokens += (e.get("input_tokens", 0) or 0) + (e.get("output_tokens", 0) or 0)
            total_cost += e.get("cost_usd", 0) or 0
            final_output = e.get("completion", "")[:500]
        elif event_type == "tool_called":
            step["tool_name"] = e.get("tool_name", "")
            step["tool_input"] = str(e.get("tool_input", ""))[:500]
        elif event_type == "tool_returned":
            step["tool_output"] = str(e.get("tool_output", ""))[:500]
        steps.append(step)

    trace = {
        "task_id": run_id,
        "task_input": user_query or f"Agent task: {domain}",
        "final_output": final_output or f"Completed ({len(steps)} steps)",
        "expected_output": f"Successful {domain} task",
        "success": not has_deviation,
        "failure_reason": None if not has_deviation else f"deviation: {', '.join(deviation_types)}",
        "timestamp": events[0].get("timestamp", ""),
        "prompt_version": 1,
        "steps": steps,
        "metadata": {
            "source": "huggingface",
            "domain": domain,
            "total_tokens": total_tokens,
            "total_latency_ms": total_latency,
            "total_cost_usd": total_cost,
            "n_events": len(events),
            "deviation_types": deviation_types,
        },
    }
    return trace


def download_open_agent_traces(max_runs: int = 150) -> int:
    """Download and convert juliensimon/open-agent-traces."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("pip install datasets first")
        return 0

    output_path = OUTPUT_DIR / "hf-open-agent-traces.jsonl"
    print("Loading juliensimon/open-agent-traces...")
    dataset = load_dataset("juliensimon/open-agent-traces", split="train")

    # Group events by run_id
    runs: dict[str, list[dict]] = {}
    for row in dataset:
        rid = row.get("run_id", "unknown")
        if rid not in runs:
            runs[rid] = []
        runs[rid].append(dict(row))

    print(f"  Found {len(runs)} runs. Converting up to {max_runs}...")

    count = 0
    with open(output_path, "w") as f:
        for run_id, events in sorted(runs.keys())[:max_runs]:
            trace = convert_events_to_trace(runs[run_id])
            if trace:
                f.write(json.dumps(trace) + "\n")
                count += 1

    print(f"  Wrote {count} traces to {output_path}")
    return count


def download_customer_support_traces(max_runs: int = 100) -> int:
    """Download and convert juliensimon/agent-traces-customer-support-triage."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("pip install datasets first")
        return 0

    output_path = OUTPUT_DIR / "hf-customer-support-traces.jsonl"
    print("Loading juliensimon/agent-traces-customer-support-triage...")
    dataset = load_dataset("juliensimon/agent-traces-customer-support-triage", split="train")

    runs: dict[str, list[dict]] = {}
    for row in dataset:
        rid = row.get("run_id", "unknown")
        if rid not in runs:
            runs[rid] = []
        runs[rid].append(dict(row))

    print(f"  Found {len(runs)} runs. Converting up to {max_runs}...")

    count = 0
    with open(output_path, "w") as f:
        for run_id in list(runs.keys())[:max_runs]:
            trace = convert_events_to_trace(runs[run_id])
            if trace:
                f.write(json.dumps(trace) + "\n")
                count += 1

    print(f"  Wrote {count} traces to {output_path}")
    return count


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    total = download_open_agent_traces()
    total += download_customer_support_traces()
    print(f"\nTotal: {total} traces downloaded to {OUTPUT_DIR}")
