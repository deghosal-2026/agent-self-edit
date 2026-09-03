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

CORPORA: dict[str, dict] = {
    "classification": {
        "task_files": CLASSIFICATION_TASK_FILES,
        "promotion_path": PROMOTION_TASKS_PATH,
        "baseline_prompt": (
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
            'Input: "The search feature ignores filters." -> technical\n'
            'Input: "I was charged twice this month." -> billing\n'
            'Input: "Can you add dark mode?" -> feature\n'
            'Input: "Someone logged into my account from another country." -> security\n'
            'Input: "Our entire deployment pipeline is broken." -> urgent\n'
            'Input: "Great work on the new release!" -> other\n'
            'Input: "Is this a billing issue or a technical one? I\'m not sure." -> other\n\n'
            "Output ONLY the category name. Nothing else."
        ),
        "held_out": [
            {"id": "classify-006", "input": "I think my account was compromised \u2014 someone logged in from an unknown IP.", "expected_output": "security"},
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
            {"id": "classify-single-014", "input": "I found a bug in the search functionality \u2014 it ignores filters.", "expected_output": "technical"},
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
        ],
    },
    "extraction": {
        "task_files": [REPO_ROOT / "field-test" / "corpus" / "synthetic" / "extraction.yaml"],
        "promotion_path": REPO_ROOT / "field-test" / "corpus" / "synthetic" / "extraction.yaml",
        "baseline_prompt": "You are a structured data extraction assistant. Extract the requested fields from the input text. Output each field on its own line as 'field: value'.",
        "held_out": [
            {"id": "extract-001", "input": "My name is Alice Johnson and my email is alice@example.com.", "expected_output": "name: Alice Johnson\nemail: alice@example.com"},
            {"id": "extract-005", "input": "The build failed with error code E4032 on branch feature/new-auth.", "expected_output": "error: E4032\nbranch: feature/new-auth"},
            {"id": "extract-010", "input": "The server srv-db-01 has 240GB of 500GB used on the data volume. The backup volume set is 120GB.", "expected_output": "server: srv-db-01\nvolume: data\nused: 240GB\ntotal: 500GB\nbackup: 120GB"},
            {"id": "extract-015", "input": "The vulnerability was reported by an external researcher on 2025-03-01 via HackerOne. The VDP offers rewards up to $5000 for criticals.", "expected_output": "researcher: external\nreported_date: 2025-03-01\nsource: HackerOne\nmax_reward: $5000"},
            {"id": "extract-020", "input": "The server is running Ubuntu 22.04 with kernel 6.2.0 and nginx 1.24. The application stack is Python 3.11 with FastAPI and PostgreSQL 15.", "expected_output": "os: Ubuntu 22.04\nkernel: 6.2.0\nwebserver: nginx 1.24\nruntime: Python 3.11\nframework: FastAPI\ndatabase: PostgreSQL 15"},
        ],
    },
    "generation": {
        "task_files": [REPO_ROOT / "field-test" / "corpus" / "synthetic" / "generation.yaml"],
        "promotion_path": REPO_ROOT / "field-test" / "corpus" / "synthetic" / "generation.yaml",
        "baseline_prompt": "You are a text generation assistant. Given a topic and constraints, produce the requested output. Follow all constraints exactly.",
        "held_out": [
            {"id": "gen-001", "input": "Topic: outage postmortem. Constraints: 3 paragraphs, root cause section, action items.", "expected_output": "Postmortem for the 2026-08-30 outage"},
            {"id": "gen-006", "input": "Topic: on-call handoff notes. Constraints: include active incidents, pending actions, next steps.", "expected_output": "On-call handoff for 2026-09-01"},
            {"id": "gen-012", "input": "Topic: architecture decision record. Constraints: context, decision, consequences.", "expected_output": "ADR-014: Use PostgreSQL for audit storage"},
            {"id": "gen-018", "input": "Topic: policy document for data retention. Constraints: professional tone, sections for each data type, compliance references.", "expected_output": "Data Retention Policy v1.0"},
            {"id": "gen-024", "input": "Topic: incident summary for SLA breach. Constraints: root cause, timeline, business impact, remedial actions.", "expected_output": "Incident Summary: SLA Breach on 2026-09-01"},
        ],
    },
    "mixed-domain": {
        "task_files": [REPO_ROOT / "field-test" / "corpus" / "synthetic" / "mixed-domain.yaml"],
        "promotion_path": REPO_ROOT / "field-test" / "corpus" / "synthetic" / "mixed-domain.yaml",
        "baseline_prompt": "You are a multi-domain assistant. Handle classification, extraction, and generation tasks as specified. Follow the instructions in each task carefully.",
        "held_out": [
            {"id": "mixed-001", "input": "Classify this ticket AND extract the affected service: 'The payment gateway is returning 502 errors for all enterprise customers. This started at 14:00 UTC.'", "expected_output": "classification: urgent, technical\naffected_service: payment gateway"},
            {"id": "mixed-010", "input": "Extract all error codes from this log AND classify the overall system health: 'E4031 on auth-service (3 retries), E5002 on user-service (1 retry), E4031 on billing-service (5 retries). All services responding but with elevated error rates.'", "expected_output": "errors: E4031, E5002\nhealth: degraded"},
            {"id": "mixed-025", "input": "Classify this as capacity planning or incident response AND extract the resource metrics: 'The database is running at 85% disk usage. At current growth rates, we will run out of space in 14 days. The table with the fastest growth is audit_logs.'", "expected_output": "type: capacity planning\ndisk_usage: 85%\ntime_remaining: 14 days\nfastest_growth: audit_logs"},
            {"id": "mixed-050", "input": "Extract the performance metrics AND generate an optimization plan: 'Current metrics: p95 latency 800ms, p99 2400ms, throughput 1200 req/s. Target: p95 < 200ms. Bottleneck: N+1 queries in the order service ORM layer.'", "expected_output": "current_p95: 800ms\ncurrent_p99: 2400ms\nplan: add query batching, implement read replicas, enable connection pooling"},
            {"id": "mixed-075", "input": "Classify the technical debt item AND generate a paydown plan: 'Debt item: Legacy billing module uses deprecated payment SDK. 12K LOC. No tests. Blocks new feature development. Options: rewrite ($400K, 6 months) or wrapper ($100K, 2 months).'", "expected_output": "classification: technical\ndebt: legacy billing SDK, 12K LOC, no tests\nplan: wrapper approach $100K/2 months, then gradual rewrite"},
        ],
    },
}


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


def _seed_trace_store(trace_path: str, task_set_paths: list[Path], n: int, current_prompt: str, llm, judge_llm=None):
    import yaml

    from agent_self_edit.scorers import resolve_scorer
    from agent_self_edit.trace import TraceStore

    db_path = Path(trace_path)
    if db_path.exists():
        db_path.unlink()

    store = TraceStore(str(db_path), batch_size=n)

    ts = _load_task_set(task_set_paths)
    scorer = resolve_scorer(ts, allow_mixed=True, judge_llm=judge_llm or llm)

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


def measure_accuracy(prompt: str, llm, tasks: list[dict], scorer=None) -> dict:
    if scorer is None:
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
    analyzer_llm=None,
    judge_llm=None,
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
        failed, prompt_a, None, analyzer_llm or llm,
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

    scorer = resolve_scorer(task_set, allow_mixed=True, judge_llm=judge_llm or llm)
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
        description="Run N self-improvement iterations with inspectable A/B artifacts (v0.3.0)"
    )
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--traces-per-iteration", type=int, default=5)
    parser.add_argument("--corpus", default="classification",
                        choices=list(CORPORA.keys()),
                        help="Domain corpus to use")
    parser.add_argument("--model", default=os.environ.get("OMLX_MODEL", ""))
    parser.add_argument("--endpoint", default=os.environ.get("OMLX_URL", ""))
    parser.add_argument("--run-label", default="",
                        help="Unique label to avoid overwriting previous results")
    parser.add_argument("--held-out-sample", type=int, default=0,
                        help="Use first N held-out tasks only (0 = all)")
    parser.add_argument("--promotion-sample", type=int, default=0,
                        help="Use first N promotion tasks only (0 = all)")
    parser.add_argument(
        "--real-traces", type=str, default="",
        help="Path to real traces JSONL file. Enables real-trace mode.",
    )
    parser.add_argument("--analyzer-model", default="",
                        help="Override model for analyzer role (falls back to --model)")
    parser.add_argument("--analyzer-endpoint", default="",
                        help="Override endpoint for analyzer role (falls back to --endpoint)")
    parser.add_argument("--analyzer-key-env", default="ANALYZER_KEY",
                        help="Env var name for analyzer API key (falls back to OMLX_KEY)")
    parser.add_argument("--judge-model", default="",
                        help="Override model for judge role (falls back to analyzer or --model)")
    parser.add_argument("--judge-endpoint", default="",
                        help="Override endpoint for judge role (falls back to analyzer or --endpoint)")
    parser.add_argument("--judge-key-env", default="JUDGE_KEY",
                        help="Env var name for judge API key (falls back to ANALYZER_KEY or OMLX_KEY)")
    args = parser.parse_args()
    api_key = os.environ.get("OMLX_KEY", "")

    if not args.model or not args.endpoint or not api_key:
        print("ERROR: OMLX_KEY, OMLX_MODEL, and OMLX_URL must be set", file=sys.stderr)
        sys.exit(1)

    corpus_cfg = dict(CORPORA[args.corpus])
    corpus_label = args.corpus

    if args.held_out_sample > 0:
        corpus_cfg["held_out"] = corpus_cfg["held_out"][:args.held_out_sample]

    # Build executor LLM
    executor_model = args.model
    executor_endpoint = args.endpoint
    executor_key = api_key

    # Build analyzer LLM (falls back to executor)
    analyzer_model = args.analyzer_model or executor_model
    analyzer_endpoint = args.analyzer_endpoint or executor_endpoint
    analyzer_key = os.environ.get(args.analyzer_key_env, "") or executor_key

    # Build judge LLM (falls back to analyzer, then executor)
    judge_model = args.judge_model or analyzer_model
    judge_endpoint = args.judge_endpoint or analyzer_endpoint
    judge_key = os.environ.get(args.judge_key_env, "") or analyzer_key

    # Output dir includes analyzer model when different from executor
    model_slug = _slug_model(executor_model)
    if analyzer_model != executor_model:
        model_slug = model_slug + "+analyzer-" + _slug_model(analyzer_model)
    if judge_model != analyzer_model and judge_model != executor_model:
        model_slug = model_slug + "+judge-" + _slug_model(judge_model)
    provider = _provider_from_endpoint(executor_endpoint)
    run_slug = args.run_label if args.run_label else corpus_label
    model_dir = RESULTS_ROOT / provider / model_slug / run_slug
    model_dir.mkdir(parents=True, exist_ok=True)

    persist_registry_path = Path(tempfile.mkdtemp(prefix="ase-reg-")) / "registry"
    trace_db = Path(tempfile.mkdtemp(prefix="ase-traces-")) / "traces.db"

    task_set_path = str(corpus_cfg["task_files"][0])
    config = _build_config(executor_model, executor_key, executor_endpoint, str(persist_registry_path), str(trace_db), task_set_path)

    # Build analyzer config for the analyzer LLM
    if analyzer_model != executor_model:
        analyzer_config = _build_config(analyzer_model, analyzer_key, analyzer_endpoint, str(persist_registry_path), str(trace_db), task_set_path)
    else:
        analyzer_config = config

    if args.promotion_sample > 0:
        from agent_self_edit.tasks import TaskSet, load_task_set
        full_ts = load_task_set(str(corpus_cfg["promotion_path"]))
        all_tasks = list(full_ts.list_tasks())
        sampled = all_tasks[:args.promotion_sample]
        sampled_ts = TaskSet(tasks={t.id: t for t in sampled})
        ab_task_set = sampled_ts
    else:
        from agent_self_edit.tasks import load_task_set
        ab_task_set = load_task_set(str(corpus_cfg["promotion_path"]))

    traffic_log = model_dir / "llm-traffic.jsonl"
    os.environ["AGENT_SELF_EDIT_LLM_LOG"] = str(traffic_log)

    from agent_self_edit.registry import Registry
    registry = Registry(str(persist_registry_path))
    try:
        registry.create(corpus_cfg["baseline_prompt"])
        print(f"Registry initialized with {corpus_label} baseline prompt")
    except Exception:
        print("Registry already exists")

    llm = _build_llm(config)
    analyzer_llm = _build_llm(analyzer_config) if analyzer_model != executor_model else llm
    judge_llm = _build_llm(_build_config(judge_model, judge_key, judge_endpoint, str(persist_registry_path), str(trace_db), task_set_path)) if judge_model != executor_model else llm

    from agent_self_edit.scorers import resolve_scorer
    held_out_ts = _load_task_set(corpus_cfg["task_files"])
    accuracy_scorer = resolve_scorer(held_out_ts, allow_mixed=True, judge_llm=judge_llm)

    print("Measuring baseline accuracy...", flush=True)
    baseline = measure_accuracy(corpus_cfg["baseline_prompt"], llm, corpus_cfg["held_out"], scorer=accuracy_scorer)
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

    for i in range(1, args.iterations + 1):
        print(f"\n=== [{corpus_label}] Iteration {i}/{args.iterations} ===", flush=True)
        iter_start = time.time()
        iteration_dir = model_dir / corpus_label / f"iteration-{i:02d}"

        current_prompt = registry.current_prompt
        if args.real_traces and rp is not None:
            store = _seed_real_traces(str(trace_db), str(rp), args.traces_per_iteration)
        else:
            store = _seed_trace_store(str(trace_db), corpus_cfg["task_files"], args.traces_per_iteration, current_prompt, llm, judge_llm=judge_llm)

        try:
            iter_result = _run_iteration(
                i, iteration_dir, config, llm, ab_task_set, store, registry,
                rejection_context=rejection_context,
                analyzer_llm=analyzer_llm,
                judge_llm=judge_llm,
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
        accuracy = measure_accuracy(current_prompt, llm, corpus_cfg["held_out"], scorer=accuracy_scorer)
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
