"""Run traces through an LLM and capture full I/O, latency, and scoring.

Usage:
    # OMLX local
    python field-test/scripts/run_traces.py \
      field-test/v0.1.0/corpus/synthetic/classification.jsonl \
      --provider omlx \
      --model qwen3.5-9b-mlx-4bit \
      --endpoint http://localhost:8000/v1

    # OpenAI cloud
    python field-test/scripts/run_traces.py \
      field-test/v0.1.0/corpus/synthetic/classification.jsonl \
      --provider openai \
      --model gpt-4o-mini

    # Override key via env: OPENROUTER_API_KEY, LLM_ENDPOINT, LLM_MODEL
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_BASE = REPO_ROOT / "field-test" / "v0.1.0" / "results"
TRAFFIC_LOG = None


def build_llm(provider: str, model: str, endpoint: str | None, api_key: str):
    if provider == "omlx":
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=endpoint or "http://localhost:8000/v1")
        return client, model
    elif provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=endpoint)
        return client, model
    raise ValueError(f"Unsupported provider: {provider}")


def call_llm(client, model: str, prompt: str, system_prompt: str = "") -> dict:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    t0 = time.time()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.0,
            max_tokens=2048,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
    except Exception as e:
        return {
            "error": str(e),
            "latency_ms": int((time.time() - t0) * 1000),
            "messages": messages,
            "response": None,
            "usage": None,
        }

    latency_ms = int((time.time() - t0) * 1000)
    content = str(response.choices[0].message.content or "") if response.choices else ""
    usage = response.usage
    usage_dict = {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    } if usage else None

    entry = {
        "error": None,
        "latency_ms": latency_ms,
        "messages": messages,
        "response": content,
        "usage": usage_dict,
    }
    if TRAFFIC_LOG:
        try:
            with open(TRAFFIC_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass
    return entry


def load_traces(path: str) -> list[dict]:
    traces = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            traces.append(json.loads(line))
    return traces


_LABEL_PATTERNS = [
    "successful", "should pass", "no hallucination", "session",
    "task", "scenario", "detector", "agent task",
]

_DOMAIN_PROMPTS = {
    "customer-support": "You are a customer support agent. Respond helpfully and professionally to the customer's issue.",
    "open-agent": "You are a customer support agent. Respond helpfully and professionally to the customer's issue.",
    "pi-coding": "You are a coding assistant. Help the user complete the coding task.",
    "observatory": "You are an agent observability analyst. Describe what the agent did and whether it succeeded.",
    "evalforge": "You are a test scenario runner. Determine whether the agent passed or failed the scenario and explain why.",
    "classification": "You are a classifier. Classify the input into one of the provided categories. Output only the category label.",
    "extraction": "You are an information extraction assistant. Extract the requested fields from the input. Output only the extracted fields.",
    "generation": "You are a text generation assistant. Generate the requested text following all constraints.",
    "mixed": "You are a helpful assistant. Complete the task as instructed.",
}


def detect_domain(trace_file: str, first_trace: dict) -> str:
    name = Path(trace_file).stem.lower()
    metadata = first_trace.get("metadata") or {}
    domain = metadata.get("domain", "")
    source = metadata.get("source", "")
    task_input = first_trace.get("task_input", "")

    if "customer-support" in name or "triage" in domain:
        return "customer-support"
    if "open-agent" in name:
        return "open-agent"
    if "pi-coding" in name:
        return "pi-coding"
    if "observatory" in name or "detector" in task_input.lower():
        return "observatory"
    if "evalforge" in name or "scenario" in task_input.lower():
        return "evalforge"
    if "classification" in name:
        return "classification"
    if "extraction" in name:
        return "extraction"
    if "generation" in name:
        return "generation"
    if "mixed" in name:
        return "mixed"
    return "mixed"


def _is_label(expected: str) -> bool:
    """True if expected_output is a success label, not an actual answer."""
    low = expected.strip().lower()
    if not low:
        return True
    return any(p in low for p in _LABEL_PATTERNS) and len(low) < 80


def score_response(trace: dict, response: str, llm_error: str | None) -> dict:
    expected = trace.get("expected_output", "")
    actual = trace.get("final_output", "")
    llm_output = response or ""
    trace_success = trace.get("success", False)

    if _is_label(expected):
        # Real trace: expected_output is a label ("Successful ...", "no hallucination").
        # Pass = LLM produced a non-empty, non-error response.
        passed = bool(llm_output.strip()) and not llm_error
        return {
            "scoring_mode": "label",
            "expected_output": expected,
            "original_output": actual,
            "original_success": trace_success,
            "llm_output": llm_output,
            "passed": passed,
        }

    # Synthetic trace: expected_output is the actual answer.
    exact = expected.strip().lower() == llm_output.strip().lower()
    return {
        "scoring_mode": "exact_match",
        "expected_output": expected,
        "original_output": actual,
        "original_success": trace_success,
        "llm_output": llm_output,
        "passed": exact,
        "exact_match": exact,
    }


def main():
    parser = argparse.ArgumentParser(description="Run traces through LLM and capture results")
    parser.add_argument("trace_file", help="Path to JSONL trace file")
    parser.add_argument("--provider", default=os.environ.get("LLM_PROVIDER", "omlx"),
                        help="LLM provider (omlx, openai)")
    parser.add_argument("--model", default=os.environ.get("LLM_MODEL", "qwen3.5-9b-mlx-4bit"),
                        help="Model name")
    parser.add_argument("--endpoint", default=os.environ.get("LLM_ENDPOINT"),
                        help="API base URL")
    parser.add_argument("--system-prompt", default=None,
                        help="System prompt for the LLM (auto-detected if not provided)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Only run first N traces (for quick testing)")
    parser.add_argument("--output", "-o", help="Output JSON file (default: auto-generated)")
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: set OPENROUTER_API_KEY environment variable", file=sys.stderr)
        sys.exit(1)

    provider_slug = args.provider
    model_slug = args.model.lower().replace("/", "-").replace(":", "-")
    trace_path = Path(args.trace_file)
    trace_name = trace_path.stem.replace(".jsonl", "").replace("_", "-").strip("-")

    traces = load_traces(args.trace_file)
    if not traces:
        print("ERROR: no traces found in file", file=sys.stderr)
        sys.exit(1)
    if args.limit and args.limit > 0:
        traces = traces[:args.limit]

    domain = detect_domain(args.trace_file, traces[0])
    system_prompt = args.system_prompt or _DOMAIN_PROMPTS[domain]

    result_dir = RESULTS_BASE / provider_slug / model_slug
    result_dir.mkdir(parents=True, exist_ok=True)

    global TRAFFIC_LOG
    traffic_log = result_dir / f"llm-traffic-{trace_name}.jsonl"
    TRAFFIC_LOG = str(traffic_log)

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = result_dir / f"{trace_name}-results.json"

    print(f"  Provider:      {args.provider}")
    print(f"  Model:         {args.model}")
    print(f"  Endpoint:      {args.endpoint or 'default'}")
    print(f"  Domain:        {domain}")
    print(f"  System prompt: {system_prompt[:80]}")
    print(f"  Traces:   {args.trace_file}")
    print(f"  Traffic:  {traffic_log}")
    print(f"  Output:   {output_path}")
    print()

    client, model = build_llm(args.provider, args.model, args.endpoint, api_key)

    results = []
    def _write_results(partial: bool = False):
        passed = sum(1 for r in results if r["scoring"]["passed"])
        total_tokens = sum(
            r["llm_call"].get("usage", {}).get("total_tokens", 0) or 0
            for r in results if r["llm_call"].get("usage")
        )
        total_latency = sum(r["llm_call"].get("latency_ms", 0) or 0 for r in results)
        n_done = len(results)
        report = {
            "meta": {
                "provider": args.provider,
                "model": args.model,
                "endpoint": args.endpoint,
                "trace_file": str(trace_path),
                "system_prompt": system_prompt,
                "domain": domain,
                "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "n_traces": len(traces),
                "n_done": n_done,
                "partial": partial,
                "n_passed": passed,
                "n_failed": n_done - passed,
                "accuracy": round(passed / n_done * 100, 1) if n_done else 0,
                "total_tokens": total_tokens,
                "total_latency_ms": total_latency,
                "avg_latency_ms": round(total_latency / n_done, 1) if n_done else 0,
            },
            "results": results,
        }
        output_path.write_text(json.dumps(report, indent=2, default=str) + "\n")

    for i, trace in enumerate(traces):
        task_input = trace.get("task_input", "")

        if (i + 1) % 10 == 0 or i == 0:
            print(f"  [{i+1}/{len(traces)}] {trace.get('task_id', '')[:40]}...")

        llm_result = call_llm(client, model, task_input, system_prompt)
        scoring = score_response(trace, llm_result.get("response", ""), llm_result.get("error"))
        results.append({
            "task_id": trace.get("task_id", f"trace-{i}"),
            "task_input": task_input,
            "llm_call": llm_result,
            "scoring": scoring,
        })
        if (i + 1) % 10 == 0 or (i + 1) == len(traces):
            _write_results(partial=(i + 1 < len(traces)))

    passed = sum(1 for r in results if r["scoring"]["passed"])
    print(f"\n  Done: {passed}/{len(traces)} passed ({round(passed / len(traces) * 100, 1) if traces else 0}%)")
    print(f"  Tokens: {sum(r['llm_call'].get('usage', {}).get('total_tokens', 0) or 0 for r in results)} | Avg latency: {round(sum(r['llm_call'].get('latency_ms', 0) or 0 for r in results) / len(traces), 1)}ms")
    print(f"  Results: {output_path}")
    print(f"  Traffic: {traffic_log}")


if __name__ == "__main__":
    main()