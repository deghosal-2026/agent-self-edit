"""Run N self-improvement iterations with inspectable A/B test artifacts (v0.3.0).

Calls the internal API directly (not the CLI) so every A/B test result is
captured as structured data. Per iteration writes:

    results/<provider>/<model>/iteration-XX/
      prompt-a.md          — current prompt
      prompt-b.md          — candidate prompt (edit applied)
      results-a.json       — per-task: input, expected, llm_output, score, latency, tokens
      results-b.json       — same for prompt B
      ab-comparison.json   — per-task deltas, winner, p-value, CI, effect size, gate decision
      analysis.json        — analyzer proposals (section, old_text, new_text, hypothesis)
      accuracy.json        — held-out set results after this iteration
      llm-traffic.jsonl    — raw LLM request/response for every call

Usage:
    export OMLX_KEY=omlx-test OMLX_MODEL=Qwen3.5-4B-4bit OMLX_URL=http://localhost:8000/v1
    python3 field-test/scripts/run_improvement_loop.py --iterations 10
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

from agent_self_edit.scorers import ExactMatchScorer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

CLASSIFICATION_TASK_FILES = [
    REPO_ROOT / "field-test" / "corpus" / "synthetic" / "classification-single-label.yaml",
    REPO_ROOT / "field-test" / "corpus" / "synthetic" / "classification-multi-label.yaml",
    REPO_ROOT / "field-test" / "corpus" / "synthetic" / "classification-ambiguous.yaml",
    REPO_ROOT / "field-test" / "corpus" / "synthetic" / "classification-boundary.yaml",
]

SENTINEL_TASKS_PATH = REPO_ROOT / "field-test" / "corpus" / "synthetic" / "sentinel.yaml"
PROMOTION_TASKS_PATH = REPO_ROOT / "field-test" / "corpus" / "synthetic" / "classification-promotion.yaml"
REAL_TRACES_PATH = REPO_ROOT / "field-test" / "corpus" / "real-traces" / "labeled" / "gold-corpus.jsonl"

RESULTS_ROOT = REPO_ROOT / "field-test" / "v0.3.0" / "results"

HELD_OUT_TASKS: list[dict[str, str]] = [
    {"id": "classify-006", "input": "I think my account was compromised — someone logged in from an unknown IP.", "expected_output": "security"},
    {"id": "classify-011", "input": "I'm paying for a service I can't use because the login page is down.", "expected_output": "urgent"},
    {"id": "classify-015", "input": "When will the maintenance window end? Our team is blocked.", "expected_output": "urgent"},
    {"id": "classify-019", "input": "I'm getting a 403 Forbidden error on endpoints I used to access.", "expected_output": "security"},
    {"id": "classify-024", "input": "I want to request a new integration feature and also report that the billing page is broken.", "expected_output": "feature, billing"},
    {"id": "classify-single-001", "input": "My billing page shows the wrong amount for my subscription.", "expected_output": "technical"},
    {"id": "classify-single-003", "input": "When will the new feature be available in production?", "expected_output": "feature"},
    {"id": "classify-single-005", "input": "Can you add SSO support for our enterprise account?", "expected_output": "feature"},
    {"id": "classify-single-008", "input": "I need to downgrade my plan before the next billing cycle.", "expected_output": "billing"},
    {"id": "classify-single-010", "input": "This is a critical security vulnerability that needs immediate attention.", "expected_output": "urgent"},
    {"id": "classify-single-012", "input": "Can you help me reset my password?", "expected_output": "technical"},
    {"id": "classify-single-014", "input": "I found a bug in the search functionality — it ignores filters.", "expected_output": "technical"},
    {"id": "classify-single-016", "input": "I want to report a phishing email that appears to be from your company.", "expected_output": "security"},
    {"id": "classify-single-018", "input": "Our team needs a higher rate limit for the API.", "expected_output": "feature"},
    {"id": "classify-single-020", "input": "The invoice shows a different amount than what I agreed to in the contract.", "expected_output": "billing"},
    {"id": "classify-ambig-026", "input": "I can't log in and I think my payment failed. Which team should handle this?", "expected_output": "other"},
    {"id": "classify-ambig-027", "input": "The system is slow after the last update. Is this a bug or a feature regression?", "expected_output": "other"},
    {"id": "classify-ambig-029", "input": "Hi, I just wanted to say the new UI looks great! Keep up the good work.", "expected_output": "other"},
    {"id": "classify-ambig-030", "input": "Can you tell me about your company's sustainability initiatives?", "expected_output": "other"},
    {"id": "classify-multi-022", "input": "The API is down AND I'm being charged for premium tier that I can't use.", "expected_output": "technical, billing"},
    {"id": "classify-multi-023", "input": "Someone is using my stolen credit card on your platform and I need urgent help.", "expected_output": "urgent, security"},
    {"id": "classify-multi-025", "input": "The deployment failed and it exposed a security vulnerability in the auth module.", "expected_output": "technical, security"},
    {"id": "boundary-002", "input": "Is this a security issue or just a bug? The login page shows an SSL error but also has a typo.", "expected_output": "other"},
    {"id": "boundary-008", "input": "I need to cancel my subscription but there's no cancel button in the UI.", "expected_output": "billing"},
    {"id": "boundary-015", "input": "The deployment failed halfway through and now some users see the old version and some see the new version.", "expected_output": "urgent"},
]

BASELINE_PROMPT = (
    "You are a helpful classification assistant. Classify the input into exactly one of: "
    "urgent, billing, technical, feature, security, other.\n\n"
    "Rules:\n"
    "- urgent: immediate action (system down, blocked workflow, security breach)\n"
    "- billing: payments, invoices, refunds, subscriptions, charges\n"
    "- technical: bugs, errors, deployment issues, account access\n"
    "- feature: feature requests, integrations, enhancements\n"
    "- security: phishing, account compromise, unauthorized access\n"
    "- other: praise, general questions, unresolved ambiguity, meta-questions\n\n"
    "Examples:\n"
    "Input: \"The search feature ignores filters.\" -> technical\n"
    "Input: \"I was charged twice this month.\" -> billing\n"
    "Input: \"Can you add dark mode?\" -> feature\n"
    "Input: \"Someone logged into my account from another country.\" -> security\n"
    "Input: \"Our entire deployment pipeline is broken.\" -> urgent\n"
    "Input: \"Great work on the new release!\" -> other\n"
    "Input: \"Is this a billing issue or a technical one? I'm not sure.\" -> other\n\n"
    "Output ONLY the category name. Nothing else."
)


def _slug_model(model: str) -> str:
    return model.lower().replace("/", "-").replace(":", "-")


def _provider_from_endpoint(endpoint: str) -> str:
    return "omlx" if "localhost" in endpoint or "127.0.0.1" in endpoint else "openai"


def _build_config(model: str, api_key: str, endpoint: str, registry_path: str, trace_path: str, task_set_path: str) -> object:
    from agent_self_edit.config import (
        ABTestConfig,
        AnalyzerConfig,
        Config,
        GateConfig,
        LLMConfig,
        ProjectConfig,
        TasksConfig,
    )
    return Config(
        project=ProjectConfig(name="improvement-loop", registry_path=registry_path, trace_path=trace_path),
        tasks=TasksConfig(task_set_path=task_set_path, batch_size=10, sample_floor=5),
        llm=LLMConfig(provider="openai", model=model, api_key=api_key, base_url=endpoint, temperature=0.0, max_tokens=4096, timeout=60),
        ab_test=ABTestConfig(n_resamples=100, n_permutations=100, confidence_level=0.95, min_effect_size=0.05, cost_ceiling_usd=0.50),
        gate=GateConfig(max_edit_distance=20, drift_threshold=0.5, near_miss_threshold=0.5),
        analyzer=AnalyzerConfig(max_proposals_per_batch=3, cost_ceiling_usd=0.50),
    )


def _build_llm(config):
    from agent_self_edit.llm.openai import OpenAIProvider
    return OpenAIProvider(
        model=config.llm.model,
        api_key=config.llm.api_key,
        base_url=config.llm.base_url,
        timeout=config.llm.timeout,
        max_tokens=config.llm.max_tokens,
    )


def _load_task_set(paths: list[Path]):
    import yaml

    from agent_self_edit.tasks import Task, TaskSet
    ts = TaskSet()
    for path in paths:
        with open(path) as f:
            raw = yaml.safe_load(f)
        for item in raw:
            ts.add_task(Task(id=item["id"], input=item["input"], expected_output=item["expected_output"], metadata=item.get("metadata", {})))
    return ts


def _seed_trace_store(trace_path: str, task_set_paths: list[Path], n: int, current_prompt: str, llm):
    import yaml

    from agent_self_edit.scorers import resolve_scorer
    from agent_self_edit.trace import TraceStore

    db_path = Path(trace_path)
    if db_path.exists():
        db_path.unlink()

    store = TraceStore(str(db_path), batch_size=n)

    ts = _load_task_set(task_set_paths)
    scorer = resolve_scorer(ts, allow_mixed=True)

    tasks = []
    for path in task_set_paths:
        with open(path) as f:
            tasks.extend(yaml.safe_load(f))

    seeded = 0
    for task in tasks:
        if seeded >= n:
            break
        try:
            model_output = llm.complete(prompt=task["input"], system_prompt=current_prompt, temperature=0.0)
        except Exception:
            model_output = ""

        passed, _ = scorer.score(task["expected_output"], model_output)
        if passed:
            continue

        store.ingest({
            "task_id": task["id"],
            "task_input": task["input"],
            "final_output": model_output,
            "expected_output": task["expected_output"],
            "success": False,
            "failure_reason": f"model said '{model_output.strip()}', expected '{task['expected_output']}'",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        seeded += 1

    print(f"  Seeded {seeded} real failures (model output \u2260 expected)", flush=True)
    return store


def measure_accuracy(prompt: str, llm, tasks: list[dict]) -> dict:
    scorer = ExactMatchScorer()
    correct = 0
    results = []
    for i, task in enumerate(tasks):
        if i % 5 == 0:
            print(f"  Accuracy: {i}/{len(tasks)}...", flush=True)
        error = None
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
            "input": task["input"],
            "expected": task["expected_output"],
            "actual": output,
            "passed": passed,
            "score": score,
            "error": error,
        })
    return {
        "accuracy": round(correct / len(tasks) * 100, 1),
        "correct": correct,
        "total": len(tasks),
        "results": results,
    }


def _run_iteration(
    iteration: int,
    iteration_dir: Path,
    config,
    llm,
    task_set,
    store,
    registry,
    rejection_context: str = "",
) -> dict:
    from agent_self_edit.ab_test import run_ab_test
    from agent_self_edit.analyzer import analyze_batch
    from agent_self_edit.gate import check_all
    from agent_self_edit.scorers import resolve_scorer

    iteration_dir.mkdir(parents=True, exist_ok=True)

    batch = store.get_batch(min(config.tasks.batch_size, store.count_pending()))
    if not batch:
        return {"iteration": iteration, "error": "no pending traces", "gate": "no_traces"}
    failed = [t for t in batch if not t.success]

    prompt_a = registry.current_prompt
    (iteration_dir / "prompt-a.md").write_text(prompt_a)

    print(f"  Analyzing {len(failed)} failed traces...", flush=True)
    analysis = analyze_batch(
        failed, prompt_a, None, llm,
        max_proposals=config.analyzer.max_proposals_per_batch,
        rejection_context=rejection_context,
        config=config,
    )

    analysis_data = {
        "n_proposals": len(analysis.proposals),
        "cost_usd": analysis.cost_usd,
        "tokens_used": analysis.tokens_used,
        "proposals": [
            {
                "section": p.section,
                "old_text": p.old_text,
                "new_text": p.new_text,
                "hypothesis": p.hypothesis,
                "expected_improvement": p.expected_improvement,
                "evidence_traces": p.evidence_traces,
            }
            for p in analysis.proposals
        ],
    }
    (iteration_dir / "analysis.json").write_text(json.dumps(analysis_data, indent=2) + "\n")

    if not analysis.proposals:
        store.release_in_flight(batch)
        return {"iteration": iteration, "gate": "no_proposals", "n_proposals": 0, "prompt_a": prompt_a[:200]}

    scorer = resolve_scorer(task_set, allow_mixed=True)
    all_results: list[dict] = []

    for pi, proposal in enumerate(analysis.proposals):
        prompt_b = prompt_a.replace(proposal.old_text, proposal.new_text)
        (iteration_dir / "prompt-b.md").write_text(prompt_b)

        print(f"  A/B test proposal {pi+1}/{len(analysis.proposals)}...", flush=True)
        ab_result = run_ab_test(prompt_a, prompt_b, task_set, llm, scorer, config)

        results_a = []
        results_b = []
        for pt in ab_result.per_task:
            results_a.append({
                "task_id": pt.task_id,
                "input": pt.task_input,
                "expected": pt.expected_output,
                "llm_output": pt.output_a,
                "score": pt.score_a,
                "latency_ms": pt.latency_a_ms,
                "tokens": pt.tokens_a,
                "error": pt.error_a,
            })
            results_b.append({
                "task_id": pt.task_id,
                "input": pt.task_input,
                "expected": pt.expected_output,
                "llm_output": pt.output_b,
                "score": pt.score_b,
                "latency_ms": pt.latency_b_ms,
                "tokens": pt.tokens_b,
                "error": pt.error_b,
            })

        (iteration_dir / "results-a.json").write_text(json.dumps(results_a, indent=2) + "\n")
        (iteration_dir / "results-b.json").write_text(json.dumps(results_b, indent=2) + "\n")

        baseline_prompt = registry.get(1)[0] if registry.current_version >= 1 else prompt_a
        gate_result = check_all(proposal, ab_result, prompt_a, baseline_prompt, config)
        print(f"  Gate: {gate_result.decision} \u2014 {gate_result.reason}", flush=True)

        ab_comparison = {
            "winner": ab_result.winner,
            "mean_delta": ab_result.mean_delta,
            "ci_low": ab_result.ci_low,
            "ci_high": ab_result.ci_high,
            "p_value": ab_result.p_value,
            "effect_size": ab_result.effect_size,
            "n_trials": ab_result.n_trials,
            "cost_usd": ab_result.cost_usd,
            "token_count": ab_result.token_count,
            "per_task": [
                {
                    "task_id": pt.task_id,
                    "score_a": pt.score_a,
                    "score_b": pt.score_b,
                    "delta": pt.delta,
                    "output_a": pt.output_a,
                    "output_b": pt.output_b,
                }
                for pt in ab_result.per_task
            ],
            "gate": {
                "decision": gate_result.decision,
                "reason": gate_result.reason,
                "checks": [
                    {"name": c.name, "passed": c.passed, "value": c.value, "threshold": c.threshold, "details": c.details}
                    for c in gate_result.checks
                ],
            },
        }
        (iteration_dir / "ab-comparison.json").write_text(json.dumps(ab_comparison, indent=2) + "\n")

        if gate_result.decision == "promote":
            registry.create(
                prompt_b,
                hypothesis=proposal.hypothesis,
                ab_results={
                    "winner": ab_result.winner,
                    "mean_delta": ab_result.mean_delta,
                    "p_value": ab_result.p_value,
                    "effect_size": ab_result.effect_size,
                    "n_trials": ab_result.n_trials,
                },
                gate_result={"decision": gate_result.decision, "reason": gate_result.reason},
            )
            print(f"  Promoted to version {registry.current_version}", flush=True)

        all_results.append({
            "proposal_index": pi,
            "section": proposal.section,
            "gate": gate_result.decision,
            "winner": ab_result.winner,
            "p_value": ab_result.p_value,
            "mean_delta": ab_result.mean_delta,
            "n_trials": ab_result.n_trials,
        })

    prompt_after = registry.current_prompt
    (iteration_dir / "prompt-after.md").write_text(prompt_after)

    store.acknowledge_rows(batch)

    return {
        "iteration": iteration,
        "prompt_a": prompt_a[:200],
        "prompt_after": prompt_after[:200],
        "n_proposals": len(analysis.proposals),
        "results": all_results,
        "analysis_cost": analysis.cost_usd,
    }


def _seed_real_traces(trace_path: str, real_traces_path: str, n: int) -> object:
    """Load real traces from a JSONL file and ingest them into a fresh TraceStore."""
    from agent_self_edit.trace import TraceStore

    db_path = Path(trace_path)
    if db_path.exists():
        db_path.unlink()

    store = TraceStore(str(db_path), batch_size=n)

    traces = []
    with open(real_traces_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            traces.append(json.loads(line))

    seeded = 0
    for t in traces:
        if seeded >= n:
            break
        try:
            store.ingest(t)
            seeded += 1
        except Exception as e:
            print(f"  Skipping invalid trace: {e}", flush=True)

    print(f"  Seeded {seeded} real traces from {Path(real_traces_path).name}", flush=True)
    return store


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run N self-improvement iterations with inspectable A/B artifacts (v0.2.0)"
    )
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--traces-per-iteration", type=int, default=10)
    parser.add_argument("--model", default=os.environ.get("OMLX_MODEL", ""))
    parser.add_argument("--endpoint", default=os.environ.get("OMLX_URL", ""))
    parser.add_argument(
        "--real-traces", type=str, default="",
        help="Path to real traces JSONL file. Enables real-trace mode.",
    )
    args = parser.parse_args()
    api_key = os.environ.get("OMLX_KEY", "")

    if not args.model or not args.endpoint or not api_key:
        print("ERROR: OMLX_KEY, OMLX_MODEL, and OMLX_URL must be set", file=sys.stderr)
        sys.exit(1)

    model_slug = _slug_model(args.model)
    provider = _provider_from_endpoint(args.endpoint)
    model_dir = RESULTS_ROOT / provider / model_slug
    model_dir.mkdir(parents=True, exist_ok=True)

    persist_registry_path = Path(tempfile.mkdtemp(prefix="ase-reg-")) / "registry"
    trace_db = Path(tempfile.mkdtemp(prefix="ase-traces-")) / "traces.db"

    task_set_path = str(CLASSIFICATION_TASK_FILES[0])
    config = _build_config(args.model, api_key, args.endpoint, str(persist_registry_path), str(trace_db), task_set_path)

    traffic_log = model_dir / "llm-traffic.jsonl"
    os.environ["AGENT_SELF_EDIT_LLM_LOG"] = str(traffic_log)

    from agent_self_edit.registry import Registry
    registry = Registry(str(persist_registry_path))
    try:
        registry.create(BASELINE_PROMPT)
        print("Registry initialized with baseline prompt")
    except Exception:
        print("Registry already exists")

    llm = _build_llm(config)

    from agent_self_edit.tasks import load_task_set
    ab_task_set = load_task_set(str(PROMOTION_TASKS_PATH))

    print("Measuring baseline accuracy...", flush=True)
    baseline = measure_accuracy(BASELINE_PROMPT, llm, HELD_OUT_TASKS)
    print(f"Baseline accuracy: {baseline['accuracy']}% ({baseline['correct']}/{baseline['total']})", flush=True)

    iterations: list[dict] = [{"iteration": 0, "accuracy": baseline["accuracy"], "gate": "baseline"}]
    rejection_context = ""

    if args.real_traces:
        rp = Path(args.real_traces)
        if not rp.is_absolute():
            rp = REPO_ROOT / args.real_traces
        corpus_label = rp.stem
    else:
        rp = None
        corpus_label = "synthetic"

    for i in range(1, args.iterations + 1):
        print(f"\n=== [{corpus_label}] Iteration {i}/{args.iterations} ===", flush=True)
        iter_start = time.time()
        iteration_dir = model_dir / corpus_label / f"iteration-{i:02d}"

        current_prompt = registry.current_prompt
        if args.real_traces and rp is not None:
            store = _seed_real_traces(str(trace_db), str(rp), args.traces_per_iteration)
        else:
            store = _seed_trace_store(str(trace_db), CLASSIFICATION_TASK_FILES, args.traces_per_iteration, current_prompt, llm)

        try:
            iter_result = _run_iteration(
                i, iteration_dir, config, llm, ab_task_set, store, registry,
                rejection_context=rejection_context,
            )
        except Exception as e:
            print(f"  ERROR: {e}", flush=True)
            iter_result = {"iteration": i, "error": str(e), "gate": "error"}
            iteration_dir.mkdir(parents=True, exist_ok=True)
            (iteration_dir / "error.txt").write_text(str(e))

        results = iter_result.get("results", [])
        if results:
            latest = results[0]
            rejection_context = (
                f"Previous proposal in section '{latest.get('section', '')}' was {latest.get('gate', '')}. "
                f"A/B winner={latest.get('winner', '')}, p={latest.get('p_value', '')}, "
                f"mean_delta={latest.get('mean_delta', '')}, n={latest.get('n_trials', '')}."
            )
        else:
            rejection_context = ""

        current_prompt = registry.current_prompt
        print("  Measuring accuracy...", flush=True)
        accuracy = measure_accuracy(current_prompt, llm, HELD_OUT_TASKS)
        (iteration_dir / "accuracy.json").write_text(json.dumps(accuracy, indent=2) + "\n")

        iter_record = {
            **iter_result,
            "accuracy": accuracy["accuracy"],
            "accuracy_correct": accuracy["correct"],
            "accuracy_total": accuracy["total"],
            "duration_s": round(time.time() - iter_start, 1),
        }
        iterations.append(iter_record)

        print(f"  Accuracy: {accuracy['accuracy']}% ({accuracy['correct']}/{accuracy['total']})", flush=True)
        print(f"  Duration: {iter_record['duration_s']}s", flush=True)

        report = {
            "meta": {
                "provider": provider,
                "model": args.model,
                "endpoint": args.endpoint,
                "n_iterations": args.iterations,
                "baseline_accuracy": baseline["accuracy"],
                "current_accuracy": accuracy["accuracy"],
                "improvement": round(accuracy["accuracy"] - baseline["accuracy"], 1),
                "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            "iterations": iterations,
        }
        report_path = model_dir / "improvement-loop-report.json"
        report_path.write_text(json.dumps(report, indent=2, default=str) + "\n")

    final_report = {
        "meta": {
            "provider": provider,
            "model": args.model,
            "endpoint": args.endpoint,
            "n_iterations": args.iterations,
            "baseline_accuracy": baseline["accuracy"],
            "final_accuracy": iterations[-1].get("accuracy", 0),
            "improvement": round(iterations[-1].get("accuracy", 0) - baseline["accuracy"], 1),
            "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "iterations": iterations,
    }
    report_path = model_dir / "improvement-loop-report.json"
    report_path.write_text(json.dumps(final_report, indent=2, default=str) + "\n")

    print("\n=== Summary ===")
    print(f"  Baseline: {baseline['accuracy']}%")
    print(f"  Final:    {iterations[-1].get('accuracy', 0)}%")
    print(f"  Delta:    {final_report['meta']['improvement']}%")
    for it in iterations[1:]:
        print(f"  Iter {it['iteration']}: {it.get('accuracy', 0)}% (gate: {it.get('gate', '?')})")
    print(f"\nResults: {model_dir}/")
    print(f"Report:  {model_dir}/improvement-loop-report.json")


if __name__ == "__main__":
    main()
