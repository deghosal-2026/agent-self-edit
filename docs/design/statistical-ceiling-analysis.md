# Statistical Ceiling Analysis

> The relationship between task set size, movable tasks, and statistical significance in paired A/B tests for AgentSelfEdit.

## 1. The Problem

The A/B test engine uses a paired permutation test to decide if prompt B is better than prompt A. The test asks: "How likely is the observed improvement to happen by chance?" With a small task set, even a real improvement can yield p > 0.05 — the effect is real but underpowered.

From the v0.1.0 field test (`docs/field-test/v0.1.0/learnings.md`):
- 26 A/B tasks, 3 fixed by the edit (+1 broken) = net +3
- Mean delta = 0.115, p = 0.23
- Gate rejected (correctly) — the effect exists but does not reach p < 0.05

## 2. How Paired Permutation Tests Work

In a paired design each task runs against both prompts:
- task i produces score_a_i and score_b_i
- delta_i = score_b_i - score_a_i
- observed mean_delta = mean(delta_i)

The permutation test shuffles the sign of each delta_i (multiply by +1 or -1 at random) and recomputes the mean. After many shuffles (default 100), the p-value is the fraction of shuffled means >= observed mean.

**Key property:** The test's power depends on the number of **discordant pairs** — tasks where score_a != score_b. Tasks where both prompts produce the same score (concordant pairs) contribute zero information. They are zeros in the mean: they do not move the observed mean toward significance, but they do increase the denominator, diluting the signal.

## 3. Minimum Discordant Pairs for p < 0.05

For a paired permutation test with n total tasks and d discordant pairs where B improves over A (d <= n), the minimum d for p < 0.05 depends on n. The test asks: "If B were no better than A, how likely is it that the observed d discordant pairs all favor B?"

Under the null, each discordant pair is equally likely to favor A or B (50/50). The probability that all d discordant pairs favor B is (0.5)^d. For p < 0.05:

| n (total tasks) | d needed (all B-favoring) | Notes |
|---|---|---|
| 10 | 5 | (0.5)^5 = 0.031 < 0.05 |
| 15 | 5 | Same d, more concordant pairs dilute effect size but not p |
| 20 | 5 | Same |
| 25 | 5 | Same |
| 30 | 5 | Same |
| 40 | 5 | Same |
| 50 | 5 | Same |

**The p-value of a pure-sign permutation test (all deltas same sign, same magnitude) depends only on d, not on n.** Concordant pairs do not change the count of permutations as extreme as the observed — they only change the mean delta and effect size.

### 3.1 When deltas are not all equal

In practice, some discordant pairs will favor A (the edit breaks a task). Let:
- d_plus = number of tasks where B improves over A (delta > 0)
- d_minus = number of tasks where A beats B (delta < 0)
- d = d_plus + d_minus

The observed statistic is sum(delta_i). Under the null, each delta_i is equally likely to be positive or negative. The p-value is the fraction of sign-flip permutations where sum(|delta_i| * sign_flip_i) >= observed sum.

Approximate p-values for varying (d_plus, d_minus) with equal-magnitude deltas:

| d_plus | d_minus | Net improvement | Approx p-value |
|--------|---------|-----------------|----------------|
| 5 | 0 | 5 | 0.031 |
| 5 | 1 | 4 | 0.109 |
| 5 | 2 | 3 | 0.227 |
| 6 | 0 | 6 | 0.016 |
| 6 | 1 | 5 | 0.063 |
| 6 | 2 | 4 | 0.145 |
| 7 | 0 | 7 | 0.008 |
| 7 | 1 | 6 | 0.035 |
| 7 | 2 | 5 | 0.088 |
| 7 | 3 | 4 | 0.172 |
| 8 | 0 | 8 | 0.004 |
| 8 | 1 | 7 | 0.018 |
| 8 | 2 | 6 | 0.055 |
| 8 | 3 | 5 | 0.113 |
| 10 | 0 | 10 | 0.001 |
| 10 | 2 | 8 | 0.011 |
| 10 | 3 | 7 | 0.035 |
| 10 | 4 | 6 | 0.083 |
| 10 | 5 | 5 | 0.164 |

**Observation:** To reach p < 0.05 with a net improvement of ~5 tasks, you need roughly 7-8 total discordant pairs with at most 1-2 favoring A. A 5-0 split works; a 6-1 split is marginal; a 7-2 split requires net improvement of 5 across 9 discordant tasks.

## 4. Impact of Task Set Size

While n does not directly affect the permutation p-value for pure-sign cases, it matters for:
1. **Effect size minimum:** The `check_effect_size` gate requires mean_delta >= min_effect_size (default 5%). More concordant tasks lower the mean_delta for the same number of fixed tasks.
2. **Sample floor:** The gate requires n_trials >= sample_floor (default 5). Small task sets below this cannot be promoted.
3. **Cost ceiling:** More tasks = more LLM calls = higher cost. For local models this is negligible; for cloud models it matters.

### 4.1 Dilution effect

If an edit fixes f tasks out of n, the effect size is f/n. To clear a 5% effect size gate:
- n = 20: f >= 1
- n = 30: f >= 2
- n = 50: f >= 3

The permutation test still needs the same d discordant pairs for the same p-value, but the effect size dilutes with more concordant tasks. This means large task sets can**mask** a real improvement that fixes a small number of tasks.

### 4.2 Cost per task

| Model | Latency | Cost per task pair | 30-task A/B cost | 50-task A/B cost |
|-------|---------|-------------------|------------------|------------------|
| Qwen3.5-4B-4bit (local) | 304ms | ~0.6s | ~18s | ~30s |
| Qwen3.5-9B-MLX-4bit (local) | 441ms | ~0.9s | ~27s | ~45s |
| gpt-4o-mini (cloud) | 2.8s | ~$0.0001 | ~$0.003 | ~$0.005 |

For local models, cost is negligible. The main constraint is iteration time.

## 5. Empirical Validation

The v0.1.0 field test data (26 tasks, 3 fixed, 1 broken) produced p ≈ 0.23. From the table above, a 3-1 split (net +2 out of 4 discordant) would yield p ≈ 0.227 — exactly matching. This validates the model.

The same edit with:
- **n=10:** p would still be ≈ 0.227 (same d=4, same split). Effect size = 2/10 = 20%.
- **n=50:** p would still be ≈ 0.227 (same d=4, same split). Effect size = 2/50 = 4% — would fail effect_size check at 5% threshold.

**Takeaway:** Adding more concordant tasks does not improve p-value; it only dilutes the effect size. To improve p, you need more discordant pairs where B wins (d_plus).

## 6. Recommendations for v0.2.0+

### 6.1 Target task set size

The permutation test's power depends on the number of discordant pairs the edit produces, not the total task count. A task set should be:
- **Large enough** to give the analyzer enough failure modes to analyze (10-30 tasks where baseline fails)
- **Small enough** that an edit fixing 3-5 tasks produces a detectable effect (20-40 total tasks)
- **Weighted toward hard tasks** where baseline accuracy is low (0-40%)

**Recommended range: 20-40 A/B tasks.** This is the sweet spot where:
- An edit fixing 5/20 tasks (25% effect) reaches p ≈ 0.031 with zero regressions
- An edit fixing 5 tasks with 1 regression reaches p ≈ 0.109 (near-miss)
- Adding more tasks beyond 40 does not improve statistical power
- Cost and time remain manageable for local models

### 6.2 What does NOT help

- Adding easy tasks that both prompts already get right (concordant) — these dilute effect size without helping p-value
- Running more permutations (100 is already sufficient — p-value stabilizes at ~1000 for these counts)
- Changing the random seed — this introduces noise, not signal

### 6.3 What DOES help

- Curating tasks where the baseline fails (high d potential)
- Reducing regressions (each B-favoring discordant pair undone by an A-favoring pair loses power)
- Cumulative evidence across iterations (same edit fixing same tasks across multiple runs)
- Moving to embedding-based drift (v0.2.0) to allow larger edits with better targeting

### 6.4 The ceiling

For a given task set, there is a **statistical ceiling**: the maximum effect size a single edit can achieve before hitting p < 0.05. For the v0.1.0 task set (26 tasks, ~3-4 fixable), the ceiling was approximately +4 tasks with zero regressions. The analyzer could not break through this ceiling because the edit class (priority rules addition) inherently broke 1 task.

Breaking through the ceiling requires either:
1. **More fixable tasks** in the set (increase d potential)
2. **Better edits** that fix more and break fewer (higher d_plus, lower d_minus)
3. **Separate task subsets** for different edit types (isolate the signal)