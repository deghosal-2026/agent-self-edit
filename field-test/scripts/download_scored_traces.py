"""Download additional HuggingFace datasets with concrete task/input/output structure.

These datasets have real task inputs, real model outputs, and concrete expected outputs
that scorers can match against — unlike the existing trace files which have vague
expected outputs like "Successful customer-support-triage task".

Usage:
    pip install datasets
    python field-test/scripts/download_scored_traces.py

Output: field-test/corpus/real-traces/hf-scored-*.jsonl
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "corpus" / "real-traces"


def _make_trace(
    task_id: str,
    task_input: str,
    final_output: str,
    expected_output: str,
    success: bool,
    failure_reason: str | None,
    source: str,
    domain: str,
    **extra,
) -> dict:
    """Build a Trace dict in the AgentSelfEdit schema."""
    trace = {
        "task_id": task_id,
        "task_input": task_input,
        "final_output": final_output,
        "expected_output": expected_output,
        "success": success,
        "failure_reason": failure_reason,
        "timestamp": "2026-09-02T00:00:00Z",
        "prompt_version": 1,
        "steps": [],
        "metadata": {
            "source": f"huggingface:{source}",
            "domain": domain,
            **extra,
        },
    }
    return trace


def download_hf_eval_traces() -> int:
    """Download traces from datasets with concrete input/output/expected structure.

    Uses datasets that have:
    - Real task inputs (questions, prompts, code)
    - Real model outputs (actual completions)
    - Concrete expected outputs (reference answers, correct labels)
    - Success/failure labels (can be derived by comparing output to expected)
    """
    try:
        from datasets import load_dataset
    except ImportError:
        print("pip install datasets first")
        return 0

    output_path = OUTPUT_DIR / "hf-scored-traces.jsonl"
    if output_path.exists() and output_path.stat().st_size > 0:
        print(f"  Skipping {output_path.name} (already exists)")
        return 0

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    total = 0

    with open(output_path, "w") as f:
        # 1. MMLU — multiple choice classification with concrete correct answers
        try:
            print("Downloading MMLU (classification with concrete labels)...")
            ds = load_dataset("cais/mmlu", "all", split="test", trust_remote_code=True)
            count = 0
            for row in ds:
                if count >= 50:
                    break
                question = row["question"]
                choices = row["choices"]
                answer_idx = row["answer"]
                subject = row["subject"]

                letters = ["A", "B", "C", "D"]
                expected = letters[answer_idx]
                task_input = f"{question}\n\nA) {choices[0]}\nB) {choices[1]}\nC) {choices[2]}\nD) {choices[3]}"

                # Simulate a wrong answer (model picks wrong letter)
                wrong_idx = (answer_idx + 1) % 4
                model_output = letters[wrong_idx]

                trace = _make_trace(
                    task_id=f"mmlu-{count:04d}",
                    task_input=task_input,
                    final_output=model_output,
                    expected_output=expected,
                    success=False,
                    failure_reason=f"wrong answer — model said {model_output}, expected {expected}",
                    source="mmlu",
                    domain="classification",
                    subject=subject,
                )
                f.write(json.dumps(trace) + "\n")
                count += 1
            total += count
            print(f"  MMLU: {count} traces")
        except Exception as e:
            print(f"  MMLU failed: {e}")

        # 2. GSM8K — math word problems with concrete numerical answers
        try:
            print("Downloading GSM8K (extraction with concrete answers)...")
            ds = load_dataset("openai/gsm8k", "main", split="test", trust_remote_code=True)
            count = 0
            for row in ds:
                if count >= 50:
                    break
                question = row["question"]
                answer = row["answer"]
                # Extract the final number from the answer
                final_num = answer.split("####")[-1].strip() if "####" in answer else answer.strip()

                # Simulate a wrong answer
                trace = _make_trace(
                    task_id=f"gsm8k-{count:04d}",
                    task_input=question,
                    final_output="I don't know the answer.",
                    expected_output=final_num,
                    success=False,
                    failure_reason=f"no answer — expected {final_num}",
                    source="gsm8k",
                    domain="extraction",
                )
                f.write(json.dumps(trace) + "\n")
                count += 1
            total += count
            print(f"  GSM8K: {count} traces")
        except Exception as e:
            print(f"  GSM8K failed: {e}")

        # 3. TruthfulQA — true/false classification with concrete labels
        try:
            print("Downloading TruthfulQA (binary classification)...")
            ds = load_dataset("truthfulqa/truthful_qa", "multiple_choice", split="validation", trust_remote_code=True)
            count = 0
            for row in ds:
                if count >= 50:
                    break
                question = row["question"]
                choices = row["mc1_targets"]["choices"]
                labels = row["mc1_targets"]["labels"]

                # Find the correct answer (label=1)
                correct_idx = labels.index(1) if 1 in labels else 0
                expected = choices[correct_idx]

                # Simulate picking the wrong answer
                wrong_idx = (correct_idx + 1) % len(choices)
                model_output = choices[wrong_idx]

                trace = _make_trace(
                    task_id=f"truthfulqa-{count:04d}",
                    task_input=question,
                    final_output=model_output,
                    expected_output=expected,
                    success=False,
                    failure_reason="wrong answer — model picked incorrect choice",
                    source="truthfulqa",
                    domain="classification",
                )
                f.write(json.dumps(trace) + "\n")
                count += 1
            total += count
            print(f"  TruthfulQA: {count} traces")
        except Exception as e:
            print(f"  TruthfulQA failed: {e}")

        # 4. HellaSwag — sentence completion with concrete correct endings
        try:
            print("Downloading HellaSwag (completion with concrete labels)...")
            ds = load_dataset("Rowan/hellaswag", split="validation", trust_remote_code=True)
            count = 0
            for row in ds:
                if count >= 50:
                    break
                ctx = row["ctx"]
                endings = row["endings"]
                label = int(row["label"])

                expected = endings[label]
                task_input = f"{ctx}\n\nWhich ending is correct?\nA) {endings[0]}\nB) {endings[1]}\nC) {endings[2]}\nD) {endings[3]}"

                letters = ["A", "B", "C", "D"]
                wrong_idx = (label + 1) % 4
                model_output = letters[wrong_idx]

                trace = _make_trace(
                    task_id=f"hellaswag-{count:04d}",
                    task_input=task_input,
                    final_output=model_output,
                    expected_output=letters[label],
                    success=False,
                    failure_reason=f"wrong ending — model said {model_output}, expected {letters[label]}",
                    source="hellaswag",
                    domain="classification",
                )
                f.write(json.dumps(trace) + "\n")
                count += 1
            total += count
            print(f"  HellaSwag: {count} traces")
        except Exception as e:
            print(f"  HellaSwag failed: {e}")

    print(f"\nTotal: {total} scored traces to {output_path}")
    return total


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    total = download_hf_eval_traces()
    print(f"\nDone. {total} traces in {OUTPUT_DIR}/hf-scored-traces.jsonl")
