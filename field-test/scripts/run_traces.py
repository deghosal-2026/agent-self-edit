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

    # Override key via env: LLM_API_KEY, LLM_ENDPOINT, LLM_MODEL
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


def score_response(trace: dict, response: str) -> dict:
    expected = trace.get("expected_output", "")
    actual = trace.get("final_output", "")
    llm_output = response or ""

    exact_match = expected.strip().lower() == actual.strip().lower()
    llm_exact_match = expected.strip().lower() == llm_output.strip().lower()
    return {
        "expected_output": expected,
        "original_output": actual,
        "llm_output": llm_output,
        "exact_match": exact_match,
        "llm_exact_match": llm_exact_match,
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
    parser.add_argument("--system-prompt", default="You are a helpful assistant.",
                        help="System prompt for the LLM")
    parser.add_argument("--output", "-o", help="Output JSON file (default: auto-generated)")
    args = parser.parse_args()

    api_key = os.environ.get("LLM_API_KEY")
    if not api_key:
        print("ERROR: set LLM_API_KEY environment variable", file=sys.stderr)
        sys.exit(1)

    provider_slug = args.provider
    model_slug = args.model.lower().replace("/", "-").replace(":", "-")
    trace_path = Path(args.trace_file)
    trace_name = trace_path.stem.replace(".jsonl", "").replace("_", "-")

    result_dir = RESULTS_BASE / provider_slug / model_slug
    result_dir.mkdir(parents=True, exist_ok=True)

    global TRAFFIC_LOG
    traffic_log = result_dir / f"llm-traffic-{trace_name}.jsonl"
    TRAFFIC_LOG = str(traffic_log)

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = result_dir / f"{trace_name}-results.json"

    print(f"  Provider: {args.provider}")
    print(f"  Model:    {args.model}")
    print(f"  Endpoint: {args.endpoint or 'default'}")
    print(f"  Traces:   {args.trace_file}")
    print(f"  Traffic:  {traffic_log}")
    print(f"  Output:   {output_path}")
    print()

    client, model = build_llm(args.provider, args.model, args.endpoint, api_key)
    traces = load_traces(args.trace_file)

    results = []
    for i, trace in enumerate(traces):
        task_input = trace.get("task_input", "")
        system_prompt = args.system_prompt

        if (i + 1) % 10 == 0 or i == 0:
            print(f"  [{i+1}/{len(traces)}] {trace.get('task_id', '')[:40]}...")

        llm_result = call_llm(client, model, task_input, system_prompt)

        scoring = score_response(trace, llm_result.get("response", ""))

        results.append({
            "task_id": trace.get("task_id", f"trace-{i}"),
            "task_input": task_input,
            "llm_call": llm_result,
            "scoring": scoring,
        })

    passed = sum(1 for r in results if r["scoring"]["llm_exact_match"])
    failed = len(results) - passed

    total_tokens = sum(
        r["llm_call"].get("usage", {}).get("total_tokens", 0) or 0
        for r in results if r["llm_call"].get("usage")
    )
    total_latency = sum(
        r["llm_call"].get("latency_ms", 0) or 0
        for r in results
    )

    report = {
        "meta": {
            "provider": args.provider,
            "model": args.model,
            "endpoint": args.endpoint,
            "trace_file": str(trace_path),
            "system_prompt": args.system_prompt,
            "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "n_traces": len(traces),
            "n_passed": passed,
            "n_failed": failed,
            "accuracy": round(passed / len(traces) * 100, 1) if traces else 0,
            "total_tokens": total_tokens,
            "total_latency_ms": total_latency,
            "avg_latency_ms": round(total_latency / len(traces), 1) if traces else 0,
        },
        "results": results,
    }

    output_path.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(f"\n  Done: {passed}/{len(traces)} passed ({report['meta']['accuracy']}%)")
    print(f"  Tokens: {total_tokens} | Avg latency: {report['meta']['avg_latency_ms']}ms")
    print(f"  Results: {output_path}")
    print(f"  Traffic: {traffic_log}")


if __name__ == "__main__":
    main()