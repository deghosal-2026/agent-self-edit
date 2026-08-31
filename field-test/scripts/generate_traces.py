"""Generate synthetic traces for field test.

Reads a task set (YAML), runs tasks against a prompt with a mock LLM
provider, and outputs JSON-lines traces. Runs offline — no real LLM calls.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

# Add src to path so we can import agent_self_edit modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent_self_edit.tasks import load_task_set
from agent_self_edit.types import utc_now_iso


def generate_traces(
    task_set_path: str,
    prompt: str,
    output_path: str,
    failure_rate: float = 0.3,
    seed: int = 42,
    batch_size: int = 50,
) -> None:
    """Generate synthetic traces from a task set.

    Args:
        task_set_path: Path to YAML task set.
        prompt: The system prompt to use.
        output_path: Output JSON-lines file path.
        failure_rate: Fraction of traces to mark as failed (0.0-1.0).
        seed: Random seed for reproducibility.
        batch_size: Number of traces per batch.
    """
    random.seed(seed)
    ts = load_task_set(task_set_path)
    tasks = ts.list_tasks()
    prompt_version = 1

    with open(output_path, "w") as f:
        for i, task in enumerate(tasks):
            success = random.random() > failure_rate
            trace = {
                "task_id": task.id,
                "task_input": task.input,
                "final_output": task.expected_output if success else f"wrong_{task.id}",
                "expected_output": task.expected_output,
                "success": success,
                "failure_reason": None if success else "misclassified — expected output mismatch",
                "timestamp": utc_now_iso(),
                "prompt_version": prompt_version,
            }
            f.write(json.dumps(trace) + "\n")

    print(f"Generated {len(tasks)} traces to {output_path} "
          f"(failure_rate={failure_rate}, batch_size={batch_size})")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate synthetic traces for field test")
    parser.add_argument("task_set", help="Path to YAML task set")
    parser.add_argument("--output", "-o", default="traces.jsonl", help="Output file path")
    parser.add_argument("--prompt", default="You are a helpful assistant.", help="System prompt")
    parser.add_argument("--failure-rate", type=float, default=0.3, help="Fraction of failed traces")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size")
    args = parser.parse_args()

    generate_traces(
        task_set_path=args.task_set,
        prompt=args.prompt,
        output_path=args.output,
        failure_rate=args.failure_rate,
        seed=args.seed,
        batch_size=args.batch_size,
    )
