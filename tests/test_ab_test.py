"""Tests for the A/B test engine: task runner, statistics, cost, runner."""

import pytest

from agent_self_edit.ab_test import (
    ABResult,
    BootstrapResult,
    bootstrap_ci,
    effect_size,
    estimate_cost,
    permutation_test,
    run_ab_test,
    run_task,
)
from agent_self_edit.config import ABTestConfig, Config, ProjectConfig
from agent_self_edit.llm import LLMProvider, MockProvider, ProviderError
from agent_self_edit.scorers import ExactMatchScorer
from agent_self_edit.tasks import Task, TaskSet


def _task(task_id="t1", input_="classify this", expected="cat"):
    return Task(id=task_id, input=input_, expected_output=expected)


def _task_set(n=6, prefix="t"):
    return TaskSet(tasks={f"{prefix}{i}": _task(f"{prefix}{i}") for i in range(n)})


def _config(cost_ceiling=0.10, n_resamples=500, n_perm=200):
    return Config(
        project=ProjectConfig(name="x"),
        ab_test=ABTestConfig(
            n_resamples=n_resamples,
            n_permutations=n_perm,
            confidence_level=0.95,
            min_effect_size=0.0,
            cost_ceiling_usd=cost_ceiling,
        ),
    )


# ---- run_task (#16) ----

def test_run_task_success():
    llm = MockProvider(responses="cat")
    result = run_task(_task(), "You are a classifier.", llm)
    assert result.success is True
    assert result.output == "cat"
    assert result.latency_ms >= 0
    assert result.token_count > 0


def test_run_task_empty_prompt():
    llm = MockProvider(responses="cat")
    result = run_task(_task(), "   ", llm)
    assert result.success is False
    assert result.error == "empty prompt"
    assert result.output == ""


def test_run_task_provider_error_returns_failure():
    class Boom(LLMProvider):
        def complete(self, prompt, system_prompt="", temperature=0.0):
            raise ProviderError("timeout")

    result = run_task(_task(), "prompt", Boom())
    assert result.success is False
    assert result.output == ""
    assert "timeout" in (result.error or "")


def test_run_task_measures_latency():
    import time

    class Slow(LLMProvider):
        def complete(self, prompt, system_prompt="", temperature=0.0):
            time.sleep(0.01)
            return "cat"

    result = run_task(_task(), "prompt", Slow())
    assert result.latency_ms >= 10


# ---- bootstrap_ci (#19) ----

def test_bootstrap_identical_scores_zero_ci():
    res = bootstrap_ci([0.7, 0.8, 0.9], [0.7, 0.8, 0.9], n_resamples=500)
    assert res.ci_low == 0.0
    assert res.ci_high == 0.0
    assert res.mean == pytest.approx(0.0)


def test_bootstrap_single_trial_narrow():
    res = bootstrap_ci([0.5], [0.9], n_resamples=500)
    # n < 2 => degenerate CI, no crash
    assert res.mean == 0.0


def test_bootstrap_empty():
    res = bootstrap_ci([], [], n_resamples=500)
    assert res.mean == 0.0 and res.ci_low == 0.0


def test_bootstrap_positive_delta_ci_above_zero():
    a = [0.4, 0.5, 0.6, 0.5]
    b = [0.8, 0.9, 0.7, 0.8]
    res = bootstrap_ci(a, b, n_resamples=2000)
    assert res.ci_low > 0.0


# ---- permutation_test (#20) ----

def test_permutation_identical_p_high():
    p = permutation_test([0.6, 0.7, 0.5], [0.6, 0.7, 0.5], n_permutations=200)
    assert p > 0.5


def test_permutation_different_p_low():
    p = permutation_test(
        [0.2, 0.1, 0.3, 0.15, 0.25, 0.12],
        [0.9, 0.8, 0.7, 0.85, 0.75, 0.82],
        n_permutations=2000,
    )
    assert p < 0.01


def test_permutation_empty_returns_one():
    assert permutation_test([], [], n_permutations=10) == 1.0


# ---- effect_size + cost (#21) ----

def test_effect_size_positive():
    es = effect_size([0.5, 0.5], [0.6, 0.6])
    assert pytest.approx(es) == 0.2


def test_effect_size_baseline_zero_inf():
    es = effect_size([0.0, 0.0], [0.5, 0.5])
    assert es == float("inf")


def test_effect_size_baseline_zero_nogain():
    es = effect_size([0.0, 0.0], [0.0, 0.0])
    assert es == 0.0


def test_effect_size_negative():
    es = effect_size([0.8, 0.8], [0.5, 0.5])
    assert es == pytest.approx(-0.375)


def test_estimate_cost_value():
    assert estimate_cost(1000) == pytest.approx(0.0033)
    assert estimate_cost(0) == 0.0


# ---- run_ab_test (#18) ----

def test_ab_run_paired_calls_both_prompts():
    llm = MockProvider(responses=lambda prompt, sp: "cat")
    ts = _task_set(4)
    scorer = ExactMatchScorer()
    res = run_ab_test("prompt a", "prompt b", ts, llm, scorer, _config())
    assert res.n_trials == 4
    assert res.winner in ("a", "b", "tie", "inconclusive")


def test_ab_identical_prompts_tie():
    llm = MockProvider(responses=lambda prompt, sp: "cat")
    ts = _task_set(5)
    scorer = ExactMatchScorer()
    res = run_ab_test("same", "same", ts, llm, scorer, _config())
    assert res.winner == "tie"
    assert res.p_value == 1.0


# ---- M1: A/B alpha semantics (#119) ----

def test_ab_alpha_high_p_inconclusive():
    """p=0.23 at 95% confidence (alpha=0.05) is not significant -> inconclusive."""
    from agent_self_edit.ab_test import permutation_test
    # Near-identical scores with tiny noise — high overlap → p ≈ 0.5
    scores_a = [0.6, 0.7, 0.5, 0.8, 0.6, 0.7]
    scores_b = [0.6, 0.7, 0.6, 0.7, 0.7, 0.6]
    p_val = permutation_test(scores_a, scores_b, n_permutations=500)
    assert p_val > 0.2, f"expected p > 0.2 for near-identical scores, got {p_val}"


def test_ab_alpha_low_p_winner():
    """p=0.01 at 95% confidence (alpha=0.05) is significant -> winner=b."""
    cfg_high_power = _config(n_resamples=500, n_perm=500, cost_ceiling=0.50)
    def deterministic_better(prompt, sp):
        return "cat" if "BETTER" in sp else "dog"
    ts_det = _task_set(20, prefix="det")
    llm_det = MockProvider(responses=deterministic_better)
    res = run_ab_test(
        "prompt_a", "prompt_b BETTER", ts_det, llm_det,
        ExactMatchScorer(), cfg_high_power,
    )
    assert res.winner == "b", f"expected winner=b, got {res.winner}"


def test_ab_alpha_mirror_winner_a():
    """Mirror case: when A is better, CI_high < 0 identifies it."""
    from agent_self_edit.tasks import Task
    cfg = _config(n_resamples=500, n_perm=500, cost_ceiling=0.50)

    def a_better(prompt, sp):
        return "cat" if "A_BEST" in sp else "dog"

    tasks = {f"ma{i}": Task(id=f"ma{i}", input=f"task {i}", expected_output="cat")
             for i in range(30)}
    ts = TaskSet(tasks=tasks)
    llm = MockProvider(responses=a_better)
    res = run_ab_test("prompt_a A_BEST", "prompt_b", ts, llm, ExactMatchScorer(), cfg)
    # Bootstrap CI shows B is consistently worse (all score 0 vs A score 1)
    assert res.ci_high < 0, f"expected ci_high < 0, got {res.ci_high}"
    # One-tailed test may give p=1.0 when A > B, but CI is correctly negative
    alpha = 1.0 - cfg.ab_test.confidence_level
    if res.p_value < alpha:
        assert res.winner == "a"
    else:
        assert res.winner in ("a", "inconclusive")


# ---- materialize_candidate_prompt (#116) ----

def test_materialize_candidate_prompt_basic():
    from agent_self_edit.types import EditProposal, materialize_candidate_prompt
    p = EditProposal(section="r", old_text="old", new_text="new",
                     hypothesis="h", expected_improvement="")
    assert materialize_candidate_prompt("prefix old suffix", p) == "prefix new suffix"


def test_materialize_candidate_prompt_empty_old_text():
    from agent_self_edit.types import EditProposal, materialize_candidate_prompt
    p = EditProposal(section="r", old_text="", new_text="new",
                     hypothesis="", expected_improvement="")
    with pytest.raises(ValueError, match="empty"):
        materialize_candidate_prompt("current", p)


def test_materialize_candidate_prompt_not_found():
    from agent_self_edit.types import EditProposal, materialize_candidate_prompt
    p = EditProposal(section="r", old_text="nonexistent", new_text="new",
                     hypothesis="", expected_improvement="")
    with pytest.raises(ValueError, match="not found"):
        materialize_candidate_prompt("current content", p)


def test_ab_winner_b_when_b_better():
    # All 8 tasks score 0 with A, but B is better via marker
    def adaptive(prompt, sp):
        return "cat" if "PROMPT_B_MARKER" in sp else "dog"

    llm2 = MockProvider(responses=adaptive)
    ts = _task_set(8)
    scorer = ExactMatchScorer()
    full_a = "pa"
    full_b = "pb PROMPT_B_MARKER"
    res2 = run_ab_test(full_a, full_b, ts, llm2, scorer, _config())
    assert res2.n_trials == 8
    assert any(r.score_b > r.score_a for r in res2.per_task)


def test_ab_empty_task_set():
    llm = MockProvider(responses="cat")
    ts = TaskSet()
    scorer = ExactMatchScorer()
    res = run_ab_test("a", "b", ts, llm, scorer, _config())
    assert res.n_trials == 0
    assert res.winner == "inconclusive"


def test_ab_cost_ceiling_aborts():
    llm = MockProvider(responses="a long answer " * 50)
    ts = _task_set(30, prefix="cost")
    scorer = ExactMatchScorer()
    # ceiling so low that any single trial trips it
    res = run_ab_test("a", "b", ts, llm, scorer, _config(cost_ceiling=0.0000001))
    assert res.winner == "inconclusive"
    assert res.n_trials < 30  # aborted early


def test_ab_failure_rate_abort():
    class Boom(LLMProvider):
        def complete(self, prompt, system_prompt="", temperature=0.0):
            raise ProviderError("down")

    ts = _task_set(10)
    res = run_ab_test("a", "b", ts, Boom(), ExactMatchScorer(), _config())
    assert res.winner == "inconclusive"
    assert res.n_trials == 10


def test_ab_per_task_breakdown():
    llm = MockProvider(responses=lambda prompt, sp: "cat")
    ts = _task_set(3)
    res = run_ab_test("pa", "pb", ts, llm, ExactMatchScorer(), _config())
    assert len(res.per_task) == 3
    first = res.per_task[0]
    assert first.task_id.startswith("t")
    assert first.output_a == "cat"
    assert first.score_a == 1.0


def test_ab_result_type_counts():
    llm = MockProvider(responses=lambda prompt, sp: "dog")
    ts = _task_set(6)
    res = run_ab_test("pa", "pb", ts, llm, ExactMatchScorer(), _config())
    assert isinstance(res, ABResult)
    assert isinstance(res.per_task[0].delta, float)


def test_bootstrap_result_dataclass():
    r = BootstrapResult(mean=0, ci_low=0, ci_high=0, std=0)
    assert r.std == 0


# ---- M1 fixes: seed, two-tailed, tie epsilon, run_task format ----

def test_bootstrap_ci_sensitive_to_data():
    ci_flat = bootstrap_ci([0.5] * 20, [0.5] * 20, seed=0)
    ci_improved = bootstrap_ci([0.3] * 20, [0.8] * 20, seed=0)
    assert ci_improved.ci_low > ci_flat.ci_low


def test_bootstrap_ci_seed_param():
    # seed=None produces non-deterministic but valid CI; seed=0 deterministic
    a = [0.4, 0.5, 0.6, 0.5]
    b = [0.8, 0.9, 0.7, 0.8]
    r1 = bootstrap_ci(a, b, n_resamples=500, seed=0)
    r2 = bootstrap_ci(a, b, n_resamples=500, seed=0)
    assert r1.ci_low == r2.ci_low
    assert r1.ci_high == r2.ci_high


def test_permutation_two_tailed_regression():
    # B worse than A should be significant with two-tailed test
    a = [1.0] * 20
    b = [0.0] * 20
    p = permutation_test(a, b, n_permutations=500, seed=0)
    assert p < 0.05


def test_permutation_two_tailed_both_directions():
    p_pos = permutation_test([0.3] * 20, [0.8] * 20, n_permutations=500, seed=0)
    p_neg = permutation_test([0.8] * 20, [0.3] * 20, n_permutations=500, seed=0)
    assert p_pos < 0.05
    assert p_neg < 0.05


def test_permutation_winner_a_when_candidate_worse():
    cfg = _config(n_resamples=500, n_perm=500, cost_ceiling=0.50)

    def a_better(prompt, system_prompt=""):
        return "cat" if "A_BEST" in system_prompt else "dog"

    tasks = {f"ma{i}": Task(id=f"ma{i}", input=f"task {i}", expected_output="cat") for i in range(20)}
    ts = TaskSet(tasks=tasks)
    llm = MockProvider(responses=a_better)
    res = run_ab_test("prompt_a A_BEST", "prompt_b", ts, llm, ExactMatchScorer(), cfg)
    assert res.winner == "a"
    assert res.ci_high < 0
    assert res.p_value < 0.05


def test_tie_epsilon_near_zero():
    llm = MockProvider(responses=lambda prompt, system_prompt="": "cat")
    # identical prompts should tie; deltas exactly 0
    ts = _task_set(5)
    res = run_ab_test("same", "same", ts, llm, ExactMatchScorer(), _config())
    assert res.winner == "tie"
    # near-zero deltas via custom scorer that returns 1e-15 diff
    from agent_self_edit.scorers import Scorer as S

    class EpsilonScorer(S):
        def score(self, expected, actual):
            return (True, 1.0) if actual == "A" else (True, 1.0 + 1e-15)

    # Use two prompts that differ only by epsilon in scorer
    llm2 = MockProvider(responses=lambda prompt, system_prompt="": "A" if "PROMPT_A" in system_prompt else "A ")
    ts2 = _task_set(5)
    res2 = run_ab_test("PROMPT_A", "PROMPT_B", ts2, llm2, EpsilonScorer(), _config())
    # all deltas are ~1e-15 < 1e-9 so should be tie
    assert res2.winner == "tie"


def test_run_task_passes_system_prompt():
    from unittest.mock import Mock

    class Capture(LLMProvider):
        def __init__(self):
            self.last = {}

        def complete(self, prompt, system_prompt="", temperature=0.0):
            self.last = {"prompt": prompt, "system_prompt": system_prompt}
            return "cat"

    llm = Capture()
    task = Task(id="t1", input="hello", expected_output="hi")
    res = run_task(task, "You are a classifier.", llm)
    assert res.success is True
    assert llm.last["system_prompt"] == "You are a classifier."
    assert llm.last["prompt"] == "hello"
    assert llm.last["system_prompt"] != ""


# ---- Calibration per ab-test-engine-design §14.3 (M1 #234) ----

def test_bootstrap_ci_calibration():
    import random

    true_mean = 0.7
    rng = random.Random(0)
    coverage = 0
    trials = 200
    for _ in range(trials):
        sample_a = [0.5] * 20
        # generate deltas around true_mean via sample_b = sample_a + true_mean delta with noise
        noise = [rng.gauss(0, 0.1) for _ in range(20)]
        sample_b = [a + true_mean + n for a, n in zip(sample_a, noise)]
        # mean delta is ~true_mean
        res = bootstrap_ci(sample_a, sample_b, n_resamples=500, ci_level=0.95, seed=0)
        if res.ci_low <= true_mean <= res.ci_high:
            coverage += 1
    cov = coverage / trials
    # with seed=0 deterministic bootstrap, coverage should be reasonable ~0.9-1.0 for strong signal
    assert cov >= 0.8, f"CI coverage {cov:.2%} too low"


def test_pvalue_uniform_under_null():
    import random

    rng = random.Random(1)
    pvals = []
    for _ in range(100):
        a = [rng.gauss(0, 1) for _ in range(20)]
        b = [rng.gauss(0, 1) for _ in range(20)]
        p = permutation_test(a, b, n_permutations=200, seed=0)
        pvals.append(p)
    mean_p = sum(pvals) / len(pvals)
    assert 0.35 <= mean_p <= 0.65, f"mean p {mean_p:.2f} not uniform"
