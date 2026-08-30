# A/B Test Engine Design

> How AgentSelfEdit proves one prompt is better than another, safely and statistically.

## 1. The Core Question

The A/B test engine answers one question: **Is prompt B better than prompt A, on the tasks that matter, with statistical confidence?**

This is not a simple question. LLM outputs are stochastic — run the same prompt on the same task twice and you may get different results. A naive "win rate" comparison on a handful of trials is meaningless. The A/B test engine must handle noise, small samples, and the fact that "better" is task-specific.

## 2. Test Design: Paired Comparison

The engine uses a **paired design**: each task in the held-out set is run against **both** prompt versions. This is the most important design decision.

```
Task 1 → run with prompt A → output A1, score 0.7
        → run with prompt B → output B1, score 0.9  → B wins (+0.2)

Task 2 → run with prompt A → output A2, score 0.5
        → run with prompt B → output B2, score 0.4  → A wins (-0.1)

Task 3 → run with prompt A → output A3, score 0.8
        → run with prompt B → output B3, score 0.8  → tie (0.0)
```

**Why paired?** Because the same task run against two prompts removes task-level variance. Task difficulty is controlled for. The only variable is the prompt. This means fewer trials are needed to reach statistical significance compared to an unpaired design (different tasks for each prompt).

**What if the agent is stochastic?** The paired design doesn't control for LLM stochasticity (same prompt + same task can produce different outputs). To handle this, we add a **repeated-trials** option: run each (task, prompt) pair N times and aggregate scores. But this multiplies cost. The default is 1 trial per pair, with the bootstrap CI capturing the resulting variance.

## 3. Scoring: How Agent Output Is Evaluated

The scorer is a pluggable interface. Three built-in implementations cover the most common use cases:

### ExactMatchScorer

```
score(expected, actual) → (True, 1.0) if expected == actual else (False, 0.0)
```

Use for: classification, structured extraction, any task with a single correct answer.

### ContainsScorer

```
score("key_field: value", output) → (True, 1.0) if "key_field: value" in output
```

Use for: tasks where the output must contain specific information, but format may vary.

### LLMJudgeScorer

```
score(expected, actual) → (bool, float)
// Uses a separate LLM call with a rubric to judge output quality
// Returns: (passed, confidence_score)
```

Use for: generation tasks, summarization, translation — any task where quality is subjective.

**Scorer selection:** The scorer is specified per task in the held-out task set. Different tasks can use different scorers. The A/B test engine aggregates scores across all tasks into a per-prompt mean score.

## 4. Statistical Methodology

### 4.1 Step 1: Run the Experiment

For each task in the held-out set:
1. Run the task with prompt A → get score_a
2. Run the task with prompt B → get score_b
3. Compute the difference: `delta = score_b - score_a`

After all N tasks, we have a list of N deltas. If the prompt didn't change anything, the deltas should be centered around 0. If B is better, they should be positive on average.

### 4.2 Step 2: Bootstrap Confidence Interval

The bootstrap is a resampling technique that estimates the uncertainty of our metric without assuming a normal distribution.

```
def bootstrap_ci(deltas, n_resamples=10000):
    """
    Compute 95% CI for the mean delta using bootstrap resampling.
    
    1. Take the list of N deltas
    2. Randomly sample N deltas WITH replacement (some may be chosen multiple times, 
       some not at all — this simulates "what if we ran the experiment again")
    3. Compute the mean of this resampled set
    4. Repeat 10,000 times
    5. Sort the 10,000 means
    6. The 95% CI is the range from the 2.5th percentile to the 97.5th percentile
    """
    means = []
    for _ in range(n_resamples):
        sample = random.choices(deltas, k=len(deltas))
        means.append(sum(sample) / len(sample))
    means.sort()
    ci_low = means[int(0.025 * n_resamples)]
    ci_high = means[int(0.975 * n_resamples)]
    return {"mean": sum(deltas) / len(deltas), "ci_low": ci_low, "ci_high": ci_high}
```

**Interpretation:**
- If the CI is entirely above 0 → B is statistically better (p < 0.05)
- If the CI contains 0 → we cannot conclude B is better (could be noise)
- If the CI is entirely below 0 → A is better (B is worse)

**Example outputs:**

| Scenario | Mean Delta | 95% CI | Interpretation |
|----------|-----------|--------|----------------|
| Clear win | +0.15 | [+0.08, +0.22] | B is better |
| Clear loss | -0.10 | [-0.18, -0.03] | B is worse |
| Inconclusive | +0.05 | [-0.02, +0.12] | Not enough data |
| Narrow win | +0.08 | [+0.01, +0.15] | B is better, barely |
| Tight | +0.12 | [-0.01, +0.25] | Trend but not significant |

### 4.3 Step 3: Permutation Test (P-Value)

The p-value answers: "If the prompts were actually identical, how likely would we see a difference this large just by chance?"

```
def permutation_test(score_a, score_b, n_permutations=1000):
    """
    Compute p-value via label shuffling.
    
    NULL HYPOTHESIS: The two prompts produce the same score distribution.
    
    1. Pool all scores_a and scores_b together
    2. Randomly split the pool into two groups of the same sizes
    3. Compute the mean difference between the two random groups
    4. Repeat 1,000 times
    5. Count how often the random difference exceeds the REAL observed difference
    6. p-value = count / 1000
    """
    observed_diff = mean(scores_b) - mean(scores_a)
    pooled = scores_a + scores_b
    n_a = len(scores_a)
    count = 0
    
    for _ in range(n_permutations):
        random.shuffle(pooled)
        fake_a = pooled[:n_a]
        fake_b = pooled[n_a:]
        fake_diff = mean(fake_b) - mean(fake_a)
        if fake_diff >= observed_diff:
            count += 1
    
    return count / n_permutations
```

### 4.4 Step 4: Effect Size

Effect size measures how *big* the improvement is, not just whether it's statistically significant. A statistically significant improvement of 0.5% may not be worth deploying.

```
def effect_size(scores_a, scores_b):
    """
    Relative improvement = (mean_b - mean_a) / mean_a
    
    If mean_a = 0.70 and mean_b = 0.80, effect = 0.143 (14.3% improvement)
    """
    mean_a = sum(scores_a) / len(scores_a)
    mean_b = sum(scores_b) / len(scores_b)
    if mean_a == 0:
        return float('inf')  # Can't compute relative improvement from zero
    return (mean_b - mean_a) / mean_a
```

## 5. Sample Floor: How Many Tasks Are Enough?

The minimum number of tasks (sample floor) is configurable, defaulting to 30. Here's why:

- **n < 10**: Bootstrap CIs are unreliable. The resample doesn't have enough data to capture the true distribution.
- **n = 30**: Rule of thumb for the central limit theorem to kick in. Bootstrap CIs become reasonably reliable.
- **n = 50-100**: Tight CIs for most tasks. Smaller improvements can be detected reliably.
- **n > 100**: Diminishing returns. Each additional task adds less precision.

**The sample floor is enforced by the promotion gate.** If the A/B test ran on fewer tasks than the floor, the gate rejects the edit regardless of the results.

## 6. Cost Estimation

| Component | Cost | Notes |
|-----------|------|-------|
| Task runner (per task, per prompt) | 1 LLM call | Runs the agent's prompt on the task |
| LLMJudge scorer (if used) | 1 LLM call per task | Only if the task uses LLMJudgeScorer |
| Total per A/B test | 2 × N × (1 + scorer_cost) | 2 prompts × N tasks × calls per task |

**Example:** 30 tasks, ExactMatch scorer (no LLM judge), gpt-4o-mini (~$0.15/1M tokens):
- 60 task runs, ~200 tokens each ≈ 12K tokens ≈ $0.002

**Example:** 30 tasks, LLMJudge scorer, gpt-4o-mini:
- 60 task runs + 30 judge calls ≈ 18K tokens ≈ $0.003

The A/B test engine is cheap because it uses small models and short prompts. The analyzer (which proposes edits) is the expensive part.

## 7. What Happens When the Test Is Inconclusive?

Three outcomes:

| Outcome | What it means | What happens next |
|---------|---------------|-------------------|
| **Promote** | B is statistically better with meaningful effect size | Edit promoted to new baseline |
| **Reject (inconclusive)** | Cannot determine if B is better | Edit archived. Analyzer may propose a different edit next cycle. |
| **Reject (harmful)** | B is statistically worse | Edit archived. Analyzer learns not to propose similar edits. |

**For inconclusive results:** The system does not automatically run more trials. That would be a form of p-hacking (running more trials until you get significance). Instead, the analyzer is expected to propose a different, hopefully stronger, edit next cycle.

## 8. Concrete Example: Classification Agent

**Setup:**
- 30 held-out tasks (ticket text → category label)
- Baseline prompt (A) achieves 72% accuracy
- Analyzer proposes: "add a step to check the user's history before classifying ambiguous cases"
- Edit: 1 line changed in the prompt

**A/B test run:**
1. Run all 30 tasks with prompt A → 22/30 correct (73.3%)
2. Run all 30 tasks with prompt B → 26/30 correct (86.7%)
3. Deltas: [+1, 0, +1, 0, 0, -1, +1, 0, 0, +1, ...] (15 improvements, 1 regression, 14 ties)
4. Mean delta: +0.133 (13.3% improvement)
5. Bootstrap CI: [+0.067, +0.200] — entirely above 0
6. P-value: 0.002 — very unlikely to be noise
7. Effect size: +18.2% — meaningful improvement

**Result: Gate passes → edit promoted.**

## 9. Limitations

1. **Held-out set must represent real tasks.** If the set doesn't reflect the production distribution, the A/B test results won't either. The user is responsible for curating a representative set.

2. **No multi-task generalization measure.** The test measures performance on the held-out tasks, not on tasks the agent has never seen. A prompt that overfits to the held-out set could pass the test but perform worse in production.

3. **LLMJudge scorer quality depends on the judge LLM.** A poor judge produces unreliable scores. The judge should be a different model than the agent to avoid shared blind spots.

4. **Cost prohibitive for very large task sets.** 100+ tasks × 2 prompts = 200+ LLM calls per A/B test. The default held-out set size of 30 tasks balances cost and statistical power.