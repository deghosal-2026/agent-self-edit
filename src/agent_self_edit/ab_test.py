"""Task runner, A/B test engine, statistics, and cost tracking."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import random
import sqlite3
import statistics
import time
from dataclasses import dataclass, field
from typing import Literal

from .config import ABTestConfig, Config
from .llm.base import LLMProvider, ProviderError
from .scorers import Scorer
from .tasks import Task, TaskSet
from .types import utc_now_iso  # noqa: F401  (re-export convenience)

_COST_PER_1K_TOKENS = 0.0033  # approx gpt-4o-mini blend ($ per 1K tokens)
_MAX_RETRIES = 3  # rate-limit retries (fix 231)


@dataclass(frozen=True)
class TaskResult:
    """Result of running one task against one prompt."""

    output: str
    success: bool
    latency_ms: float
    token_count: int
    error: str | None = None


@dataclass(frozen=True)
class PerTask:
    """Paired per-task comparison for the A/B result."""

    task_id: str
    task_input: str
    expected_output: str
    output_a: str
    score_a: float
    output_b: str
    score_b: float
    delta: float
    latency_a_ms: float
    latency_b_ms: float
    tokens_a: int
    tokens_b: int
    error_a: str | None = None
    error_b: str | None = None


@dataclass(frozen=True)
class ABResult:
    """Statistical result of comparing prompt B against prompt A."""

    winner: Literal["a", "b", "tie", "inconclusive"]
    mean_delta: float
    ci_low: float
    ci_high: float
    p_value: float
    effect_size: float
    n_trials: int
    per_task: list[PerTask] = field(default_factory=list)
    cost_usd: float = 0.0
    token_count: int = 0


@dataclass(frozen=True)
class BootstrapResult:
    mean: float
    ci_low: float
    ci_high: float
    std: float


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token."""
    return max(1, len(text) // 4)


def estimate_cost(token_count: int, price_per_1k: float = _COST_PER_1K_TOKENS) -> float:
    """Estimate USD cost for ``token_count`` tokens."""
    return token_count * price_per_1k / 1000.0


# ---------------------------------------------------------------------------
# Task runner (#16)
# ---------------------------------------------------------------------------


_TIE_EPSILON = 1e-9


def run_task(task: Task, prompt: str, llm: LLMProvider) -> TaskResult:
    """Run ``task`` against one ``prompt`` and measure latency + tokens.

    Retries on rate-limit errors with exponential backoff (fix 231).
    """
    if not prompt.strip():
        return TaskResult(output="", success=False, latency_ms=0.0, token_count=0,
                          error="empty prompt")

    start = time.monotonic()
    last_error: str | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            output = llm.complete(prompt=task.input, system_prompt=prompt, temperature=0.0)
            latency_ms = (time.monotonic() - start) * 1000.0
            tokens = estimate_tokens(prompt) + estimate_tokens(task.input) + estimate_tokens(output)
            return TaskResult(
                output=output,
                success=True,
                latency_ms=latency_ms,
                token_count=tokens,
            )
        except ProviderError as e:
            err_str = str(e)
            is_rate = ("rate" in err_str.lower() or "429" in err_str
                       or "too many" in err_str.lower())
            if is_rate and attempt < _MAX_RETRIES - 1:
                wait = 2 ** attempt
                time.sleep(wait)
                continue
            last_error = err_str
            break
    return TaskResult(output="", success=False, latency_ms=0.0, token_count=0,
                      error=last_error or "unknown error")


# ---------------------------------------------------------------------------
# Statistics (#19, #20, #21)
# ---------------------------------------------------------------------------


def bootstrap_ci(
    scores_a: list[float],
    scores_b: list[float],
    n_resamples: int = 10000,
    ci_level: float = 0.95,
    seed: int | None = None,
) -> BootstrapResult:
    """Bootstrap CI for the mean delta = mean(score_b - score_a).

    ``seed=None`` (default) uses fresh randomness in production; pass
    ``seed=0`` in tests for reproducibility.
    """
    n = len(scores_a)
    if n == 0:
        return BootstrapResult(mean=0.0, ci_low=0.0, ci_high=0.0, std=0.0)
    if n < 2:
        return BootstrapResult(mean=0.0, ci_low=0.0, ci_high=0.0, std=0.0)

    deltas = [b - a for a, b in zip(scores_a, scores_b)]
    mean_delta = sum(deltas) / n

    if n_resamples <= 0:
        return BootstrapResult(mean=mean_delta, ci_low=mean_delta, ci_high=mean_delta, std=0.0)

    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(n_resamples):
        sample = [rng.choice(deltas) for _ in range(n)]
        means.append(sum(sample) / n)

    means.sort()
    tail = (1.0 - ci_level) / 2.0
    low_idx = int(tail * n_resamples)
    high_idx = int((1.0 - tail) * n_resamples) - 1
    ci_low = means[low_idx]
    ci_high = means[high_idx]
    std = statistics.stdev(means) if len(means) > 1 else 0.0
    return BootstrapResult(mean=mean_delta, ci_low=ci_low, ci_high=ci_high, std=std)


def permutation_test(
    scores_a: list[float],
    scores_b: list[float],
    n_permutations: int = 1000,
    seed: int | None = None,
) -> float:
    """Two-tailed permutation p-value: how often |random| >= |observed|.

    ``seed=None`` (default) uses fresh randomness in production; pass
    ``seed=0`` in tests for reproducibility.
    """
    n = len(scores_a)
    if n == 0:
        return 1.0
    observed_diff = sum(scores_b) / n - sum(scores_a) / n
    pooled = list(scores_a) + list(scores_b)
    rng = random.Random(seed)

    count = 0
    for _ in range(n_permutations):
        rng.shuffle(pooled)
        fake_a = pooled[:n]
        fake_b = pooled[n:]
        fake_diff = sum(fake_b) / n - sum(fake_a) / n
        if abs(fake_diff) >= abs(observed_diff):
            count += 1
    return count / n_permutations


def effect_size(scores_a: list[float], scores_b: list[float]) -> float:
    """Relative improvement = (mean_b - mean_a) / mean_a.

    Baseline of 0 renders ``inf`` for any positive improvement (handled by
    the caller), and 0.0 for no change.
    """
    if not scores_a or not scores_b:
        return 0.0
    mean_a = sum(scores_a) / len(scores_a)
    mean_b = sum(scores_b) / len(scores_b)
    if mean_a == 0:
        if mean_b > 0:
            return float("inf")
        return 0.0
    return (mean_b - mean_a) / mean_a


# ---------------------------------------------------------------------------
# A/B test runner (#18)
# ---------------------------------------------------------------------------


def _resolve_ab_config(config: Config | None) -> ABTestConfig:
    return config.ab_test if config is not None else ABTestConfig()


# ---------------------------------------------------------------------------
# A/B result cache (persistent SQLite) — fix #230
# ---------------------------------------------------------------------------


@dataclass
class _ABResultCache:
    """Persistent SQLite cache for A/B results keyed by content hash."""

    path: str
    enabled: bool = True
    _conn: sqlite3.Connection | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.enabled:
            return
        db_path = os.path.join(self.path, "ab_cache.db")
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS ab_cache ("
            "key TEXT PRIMARY KEY, result_json TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        self._conn.commit()

    def _make_key(
        self,
        prompt_a: str,
        prompt_b: str,
        tasks: list[Task],
        scorer_name: str,
        ab_config: ABTestConfig,
    ) -> str:
        task_data = json.dumps(
            [{"id": t.id, "input": t.input, "expected_output": t.expected_output} for t in tasks],
            sort_keys=True,
        )
        task_hash = hashlib.sha256(task_data.encode()).hexdigest()
        config_data = json.dumps(dataclasses.asdict(ab_config), sort_keys=True, default=str)
        config_hash = hashlib.sha256(config_data.encode()).hexdigest()
        combined = prompt_a + prompt_b + task_hash + scorer_name + config_hash
        return hashlib.sha256(combined.encode()).hexdigest()

    def get(self, key: str) -> ABResult | None:
        if not self.enabled or self._conn is None:
            return None
        row = self._conn.execute(
            "SELECT result_json FROM ab_cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        return _deserialize_ab_result(row[0])

    def set(self, key: str, result: ABResult) -> None:
        if not self.enabled or self._conn is None:
            return
        data = {
            "winner": result.winner,
            "mean_delta": result.mean_delta,
            "ci_low": result.ci_low,
            "ci_high": result.ci_high,
            "p_value": result.p_value,
            "effect_size": result.effect_size,
            "n_trials": result.n_trials,
            "per_task": [dataclasses.asdict(pt) for pt in result.per_task],
            "cost_usd": result.cost_usd,
            "token_count": result.token_count,
        }
        self._conn.execute(
            "INSERT OR REPLACE INTO ab_cache (key, result_json, created_at) "
            "VALUES (?, ?, datetime('now'))",
            (key, json.dumps(data)),
        )
        self._conn.commit()


def _serialize_ab_result(result: ABResult) -> str:
    data = {
        "winner": result.winner,
        "mean_delta": result.mean_delta,
        "ci_low": result.ci_low,
        "ci_high": result.ci_high,
        "p_value": result.p_value,
        "effect_size": result.effect_size,
        "n_trials": result.n_trials,
        "per_task": [dataclasses.asdict(pt) for pt in result.per_task],
        "cost_usd": result.cost_usd,
        "token_count": result.token_count,
    }
    return json.dumps(data)


def _deserialize_ab_result(json_str: str) -> ABResult:
    data = json.loads(json_str)
    return ABResult(
        winner=data["winner"],
        mean_delta=data["mean_delta"],
        ci_low=data["ci_low"],
        ci_high=data["ci_high"],
        p_value=data["p_value"],
        effect_size=data["effect_size"],
        n_trials=data["n_trials"],
        per_task=[PerTask(**pt) for pt in data.get("per_task", [])],
        cost_usd=data.get("cost_usd", 0.0),
        token_count=data.get("token_count", 0),
    )


def run_ab_test(
    prompt_a: str,
    prompt_b: str,
    task_set: TaskSet,
    llm: LLMProvider,
    scorer: Scorer,
    config: Config | None = None,
    llm_b: LLMProvider | None = None,
    cache: _ABResultCache | None = None,
) -> ABResult:
    """Run the paired A/B comparison of ``prompt_b`` vs ``prompt_a``.

    When ``llm_b`` is provided, use it for prompt_b; otherwise ``llm`` is used for both sides.
    When ``cache`` is provided and enabled, skip re-running identical pairs.
    """
    ab_config = _resolve_ab_config(config)
    tasks = task_set.list_tasks()

    cache_key: str | None = None
    if cache is not None and cache.enabled:
        cache_key = cache._make_key(prompt_a, prompt_b, tasks, scorer.__class__.__name__, ab_config)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    results: list[PerTask] = []
    total_tokens = 0
    failures = 0
    llm_for_b = llm_b or llm

    for task in tasks:
        result_a = run_task(task, prompt_a, llm)
        result_b = run_task(task, prompt_b, llm_for_b)

        score_a = (
            scorer.score(task.expected_output, result_a.output)[1]
            if not result_a.error
            else 0.0
        )
        score_b = (
            scorer.score(task.expected_output, result_b.output)[1]
            if not result_b.error
            else 0.0
        )

        if result_a.error or result_b.error:
            failures += 1

        total_tokens += result_a.token_count + result_b.token_count
        results.append(
            PerTask(
                task_id=task.id,
                task_input=task.input,
                expected_output=task.expected_output,
                output_a=result_a.output,
                score_a=score_a,
                output_b=result_b.output,
                score_b=score_b,
                delta=score_b - score_a,
                latency_a_ms=result_a.latency_ms,
                latency_b_ms=result_b.latency_ms,
                tokens_a=result_a.token_count,
                tokens_b=result_b.token_count,
                error_a=result_a.error,
                error_b=result_b.error,
            )
        )

        # Cost ceiling abort (D3 §8.1)
        if estimate_cost(total_tokens) > ab_config.cost_ceiling_usd:
            return _inconclusive(results, total_tokens)

    if tasks and failures / len(tasks) > 0.2:
        return _inconclusive(results, total_tokens)

    scores_a = [r.score_a for r in results]
    scores_b = [r.score_b for r in results]
    mean_a = sum(scores_a) / len(scores_a) if scores_a else 0.0
    mean_b = sum(scores_b) / len(scores_b) if scores_b else 0.0

    if not scores_a:
        return _inconclusive([], 0)

    deltas = [r.delta for r in results]
    if all(abs(d) < _TIE_EPSILON for d in deltas):
        winner: Literal["a", "b", "tie", "inconclusive"] = "tie"
        ci = BootstrapResult(mean=0.0, ci_low=0.0, ci_high=0.0, std=0.0)
        p_value = 1.0
    else:
        ci = bootstrap_ci(
            scores_a, scores_b,
            n_resamples=ab_config.n_resamples,
        )
        p_value = permutation_test(
            scores_a, scores_b,
            n_permutations=ab_config.n_permutations,
        )
        effect = effect_size(scores_a, scores_b)
        alpha = 1.0 - ab_config.confidence_level
        if (
            ci.ci_low > 0
            and p_value < alpha
            and effect >= ab_config.min_effect_size
        ):
            winner = "b"
        elif ci.ci_high < 0 and p_value < alpha:
            winner = "a"
        else:
            winner = "inconclusive"

    result = ABResult(
        winner=winner,
        mean_delta=mean_b - mean_a,
        ci_low=ci.ci_low,
        ci_high=ci.ci_high,
        p_value=p_value,
        effect_size=effect_size(scores_a, scores_b),
        n_trials=len(results),
        per_task=results,
        cost_usd=estimate_cost(total_tokens),
        token_count=total_tokens,
    )
    if cache is not None and cache_key is not None:
        cache.set(cache_key, result)
    return result


def _inconclusive(
    per_task: list[PerTask],
    token_count: int,
) -> ABResult:
    return ABResult(
        winner="inconclusive",
        mean_delta=0.0,
        ci_low=0.0,
        ci_high=0.0,
        p_value=1.0,
        effect_size=0.0,
        n_trials=len(per_task),
        per_task=per_task,
        cost_usd=estimate_cost(token_count),
        token_count=token_count,
    )
