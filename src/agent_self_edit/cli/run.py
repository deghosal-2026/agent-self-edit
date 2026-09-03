"""run command: start the self-improvement loop."""

import signal
import sys
import time
from typing import Literal

import click

from ..config import Config, load_config
from ..registry import Registry, RegistryError
from ..trace import TraceStore


def _classify_exception(exc: Exception) -> Literal["rate_limit", "transient", "fatal"]:
    """Classify an exception for loop retry/exit decisions."""
    from ..analyzer import AnalyzerError
    from ..gate import GateError
    from ..llm.base import ProviderError

    if isinstance(exc, ProviderError):
        msg = str(exc).lower()
        if "rate" in msg or "429" in msg or "too many" in msg:
            return "rate_limit"
        return "fatal"
    if isinstance(exc, (GateError, AnalyzerError, RegistryError)):
        return "fatal"
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return "transient"
    return "fatal"


def _run_once(
    config_path: str,
    batch_size: int | None,
    dry_run: bool,
    rejection_context: str = "",
    *,
    store: TraceStore | None = None,
    registry: Registry | None = None,
    config: Config | None = None,
) -> tuple[bool, str]:
    """Run one self-edit cycle. Returns ``(had_work, new_rejection_context)``."""
    # Reuse passed-in store/registry/config to avoid per-cycle reconstruction (fix 255)
    if config is None:
        config = load_config(config_path)
    if store is None:
        store = TraceStore(
            config.project.trace_path, batch_size=batch_size or config.tasks.batch_size
        )
    if registry is None:
        registry = Registry(config.project.registry_path)

    if not store.batch_ready():
        click.echo("No pending traces ready for analysis.")
        return (False, rejection_context)

    batch = store.get_batch(min(batch_size or config.tasks.batch_size, store.count_pending()))
    if not batch:
        return (False, rejection_context)

    failed = [t for t in batch if not t.success]
    click.echo(f"Processing {len(batch)} traces ({len(failed)} failed)")

    if not failed:
        store.acknowledge_rows(batch)
        click.echo("All traces succeeded; no analysis needed.")
        return (True, rejection_context)

    # Ensure in-flight batch is released on any exception (fix 213/281)
    try:
        from ..ab_test import run_ab_test
        from ..analyzer import analyze_batch
        from ..gate import GateAuditLog, PromotionGate
        from ..scorers import resolve_scorer
        from ..tasks import load_task_set
        from .propose import _build_llm_for_role

        analyzer_llm = _build_llm_for_role(config, config.analyzer_role)
        # Load recent near-misses for dedup (fix 249/282 — previously always None)
        audit_path = config.project.registry_path + "/audit.jsonl"
        try:
            near_misses = GateAuditLog(audit_path).near_misses(limit=20)
        except Exception:
            near_misses = []
        result = analyze_batch(
            failed,
            registry.current_prompt,
            None,
            analyzer_llm,
            max_proposals=config.analyzer.max_proposals_per_batch,
            config=config,
            near_misses=near_misses,
            rejection_context=rejection_context,
        )

        msg = f"Analysis complete: {len(result.proposals)} proposals, cost=${result.cost_usd:.4f}"
        click.echo(msg)

        if dry_run or not result.proposals:
            store.acknowledge_rows(batch)
            # Clear stale context when analyzer produced no proposals (fix 251/289)
            if not result.proposals and not dry_run:
                return (True, "")
            return (True, rejection_context)

        rejection_context_lines: list[str] = []
        if rejection_context:
            rejection_context_lines.append(rejection_context)

        # Drift must be measured against original v1, not current (fix 276/206)
        try:
            original_prompt = (
                registry.get(1)[0]
                if registry.current_version >= 1
                else registry.current_prompt
            )
        except Exception:
            original_prompt = registry.current_prompt

        task_set = load_task_set(config.tasks.task_set_path)
        executor_llm = _build_llm_for_role(config, config.executor_role)
        judge_llm = _build_llm_for_role(config, config.judge_role)
        scorer = resolve_scorer(task_set, judge_llm=judge_llm)

        for proposal in result.proposals:
            candidate_prompt = registry.current_prompt.replace(
                proposal.old_text, proposal.new_text
            )
            ab_result = run_ab_test(
                registry.current_prompt, candidate_prompt, task_set, executor_llm, scorer, config
            )
            click.echo(
                f"  A/B test: {ab_result.winner} "
                f"(p={ab_result.p_value:.4f}, n={ab_result.n_trials})"
            )

            gate = PromotionGate(audit_path=config.project.registry_path + "/audit.jsonl")
            gate_result = gate.check(
                proposal, ab_result, registry.current_prompt, original_prompt, config
            )
            click.echo(f"  Gate: {gate_result.decision}")

            if gate_result.decision in ("reject", "near_miss"):
                rejection_context_lines.append(
                    f"Previous edit '{proposal.hypothesis}' was {gate_result.decision}: "
                    f"{gate_result.reason}"
                )

            if gate_result.decision == "promote":
                registry.create(
                    candidate_prompt,
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
                click.echo(f"  Promoted to version {registry.current_version}")

        store.acknowledge_rows(batch)

        new_rejection_context = "\n".join(rejection_context_lines)
        return (True, new_rejection_context)
    except Exception:
        # Release in-flight on failure so batch can be retried (fix 213/281)
        try:
            store.release_in_flight(batch)
        except Exception:
            pass
        raise


@click.command()
@click.option("--config", "config_path", default="agent-self-edit.yaml", help="Config file path")
@click.option("--batch-size", type=int, help="Override batch size")
@click.option("--once", "once_flag", is_flag=True, help="Run one cycle and exit")
@click.option("--dry-run", "dry_run", is_flag=True, help="Analyze only, no A/B test or gate")
def run(config_path: str, batch_size: int | None, once_flag: bool, dry_run: bool) -> None:
    """Start the self-improvement loop."""
    shutdown = False
    rejection_context = ""
    # Create store/registry/config once to avoid per-cycle reconstruction (fix 255)
    config = load_config(config_path)
    store = TraceStore(config.project.trace_path, batch_size=batch_size or config.tasks.batch_size)
    registry = Registry(config.project.registry_path)

    def _handler(signum: int, frame: object) -> None:
        nonlocal shutdown
        shutdown = True
        click.echo("Shutdown signal received; finishing current cycle...")

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)

    while not shutdown:
        try:
            _, rejection_context = _run_once(
                config_path, batch_size, dry_run, rejection_context,
                store=store, registry=registry, config=config,
            )
        except Exception as e:
            category = _classify_exception(e)
            if category in ("rate_limit", "transient"):
                sleep_s = 10 if category == "rate_limit" else 5
                click.echo(f"{category}: {e}; retrying in {sleep_s}s", err=True)
                time.sleep(sleep_s)
                continue
            click.echo(f"Fatal error: {e}", err=True)
            sys.exit(1)

        if config.trigger == "manual":
            break
        if once_flag or shutdown:
            break
        if config.trigger == "time":
            interval = config.trigger_interval_hours * 3600
            time.sleep(interval)
        else:
            time.sleep(5)

    click.echo("Loop stopped.")
