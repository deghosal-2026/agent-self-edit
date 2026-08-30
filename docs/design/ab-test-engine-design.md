# A/B Test Engine — Deep Dive

> How the A/B test engine works end-to-end: data flow, task runner, scoring, statistical analysis, and operational concerns.

## 1. The Big Picture

The A/B test engine sits between the feedback analyzer (proposes edits) and the promotion gate (decides whether to promote). It takes two prompt versions and a held-out task set, and produces a statistically valid answer to: **Is prompt B better than prompt A on these tasks?**

```
Analyzer → EditProposal → A/B Test Engine → ABResult → Promotion Gate → GateResult
                              ↑
                      Held-out TaskSet
```

## 2. Concrete Data Flow

### 2.1 Inputs

```
prompt_a: str          # Current prompt (e.g., "You are a classifier...")
prompt_b: str          # Candidate prompt (same as prompt_a with one line changed)
task_set: TaskSet      # 30 held-out tasks
llm_provider: LLMProvider  # The agent's LLM (e.g., gpt-4o-mini)
scorer: Scorer         # How to evaluate agent output
```

### 2.2 Output

```python
@dataclass
class ABResult:
    winner: Literal["a", "b", "tie", "inconclusive"]
    mean_delta: float          # mean(scores_b) - mean(scores_a)
    ci_low: float              # 95% CI lower bound
    ci_high: float             # 95% CI upper bound
    p_value: float             # from permutation test
    effect_size: float         # relative improvement
    n_trials: int              # number of tasks tested
    per_task: list[TaskResult] # detailed per-task results
    cost_usd: float            # total cost of this A/B test
    token_count: int           # total tokens used
```

### 2.3 Per-Task Result

```python
@dataclass
class TaskResult:
    task_id: str
    task_input: str
    expected_output: str
    output_a: str              # Agent's output with prompt A
    score_a: float             # Scorer's score for output_a
    output_b: str              # Agent's output with prompt B
    score_b: float             # Scorer's score for output_b
    delta: float               # score_b - score_a
    latency_a_ms: float
    latency_b_ms: float
    tokens_a: int
    tokens_b: int
    error_a: str | None        # Error message if prompt A failed
    error_b: str | None        # Error message if prompt B failed
```

## 3. The Task Runner

### 3.1 How the Agent Is Called

The agent is assumed to be a stateless LLM call: system prompt + task input → output. The task runner wraps this call:

```python
def run_task(
    task: Task,                # task.input, task.expected_output
    prompt: str,               # The system prompt to test
    llm: LLMProvider,          # The agent's LLM
) -> TaskOutput:
    """
    Run a single task against a single prompt version.
    
    1. Construct the full prompt: system prompt + task input
    2. Call the LLM
    3. Measure latency, tokens, cost
    4. Handle errors gracefully
    """
    full_prompt = f"{prompt}\n\n---\n\nTask: {task.input}"
    
    try:
        start = time.time()
        output = llm.complete(
            prompt=full_prompt,
            system_prompt="",  # System prompt is already in full_prompt
            temperature=0.0,   # Zero temperature for reproducibility
        )
        latency = time.time() - start
        
        return TaskOutput(
            output=output,
            latency_ms=latency * 1000,
            token_count=estimate_tokens(full_prompt) + estimate_tokens(output),
            error=None,
        )
    except LLMError as e:
        return TaskOutput(
            output="",
            latency_ms=0,
            token_count=0,
            error=str(e),
        )
```

### 3.2 Why Temperature = 0.0

The A/B test runs with temperature = 0.0. This minimizes stochastic noise, making the comparison more about the prompt than about random sampling. The bootstrap CI still captures residual variance (from temperature-0 non-determinism in LLMs, which is small but real).

### 3.3 Error Handling

| Error | What Happens | Impact on Results |
|-------|-------------|-------------------|
| LLM timeout | Task fails. `error` field populated. | Task excluded from both prompts (paired design requires both outputs). If > 20% of tasks fail, the entire A/B test is aborted. |
| Malformed output | Output is empty string. | Score will be 0.0. This is legitimate data — a prompt that causes malformed output is worse. |
| Rate limit | Retry with exponential backoff (3 attempts). | Adds latency. If all 3 fail, treated as timeout. |
| Cost ceiling exceeded | Abort mid-run. | Partial results discarded. A/B test marked as "aborted — cost ceiling exceeded." |

### 3.4 Parallel Execution

For the v0.1.0 MVP, tasks run sequentially. This is simpler and avoids rate-limit issues. For larger task sets, parallel execution can be added in v0.2.0.

```
For each task in task_set:
    run_task(task, prompt_a, llm)  # sequential
    run_task(task, prompt_b, llm)  # sequential
```

Run order: A then B for each task. This minimizes the time between runs, reducing the chance that the LLM provider's behavior changes between the two runs.

## 4. Scoring: How Agent Output Is Evaluated

### 4.1 The Scorer Interface

```python
class Scorer(ABC):
    @abstractmethod
    def score(self, expected: str, actual: str) -> tuple[bool, float]:
        """
        Score an agent's output against the expected output.
        
        Returns: (passed, score)
        - passed: bool — whether the output is acceptable
        - score: float — 0.0 (completely wrong) to 1.0 (perfect)
        """
        pass
```

### 4.2 ExactMatchScorer

```python
class ExactMatchScorer(Scorer):
    def score(self, expected: str, actual: str) -> tuple[bool, float]:
        """
        Exact string match after normalization.
        - Strip whitespace
        - Lowercase
        - Compare
        """
        normalized_expected = expected.strip().lower()
        normalized_actual = actual.strip().lower()
        passed = normalized_expected == normalized_actual
        return (passed, 1.0 if passed else 0.0)
```

**Edge cases handled:**
- Trailing/leading whitespace → stripped
- Capitalization differences → lowercased
- Empty expected output → only passes if actual is also empty
- Empty actual output → fails (agent produced nothing)

### 4.3 ContainsScorer

```python
class ContainsScorer(Scorer):
    def __init__(self, required_fields: list[str] = None):
        self.required_fields = required_fields
    
    def score(self, expected: str, actual: str) -> tuple[bool, float]:
        """
        Check if expected content appears in the actual output.
        Used for extraction tasks where the exact format may vary.
        """
        if not actual.strip():
            return (False, 0.0)
        
        # Split expected into individual fields to check
        expected_lines = expected.strip().split('\n')
        found = 0
        for line in expected_lines:
            if line.lower() in actual.lower():
                found += 1
        
        if self.required_fields:
            # All required fields must be present
            required_present = all(f.lower() in actual.lower() for f in self.required_fields)
            if not required_present:
                return (False, found / len(expected_lines))
        
        score = found / len(expected_lines) if expected_lines else 0.0
        return (score >= 1.0, score)
```

**Edge cases handled:**
- Empty actual output → score 0.0
- Partial match → partial score (e.g., 3/4 fields found = 0.75)
- Required fields check → fails if any required field is missing
- Substring matching → case-insensitive

### 4.4 LLMJudgeScorer

```python
class LLMJudgeScorer(Scorer):
    def __init__(self, judge_llm: LLMProvider, rubric: str = ""):
        self.judge_llm = judge_llm
        self.rubric = rubric
    
    def score(self, expected: str, actual: str) -> tuple[bool, float]:
        """
        Use a separate LLM to judge output quality.
        The judge LLM should be a DIFFERENT model than the agent.
        
        Judge prompt:
        "You are evaluating an AI agent's output.
         
         Expected output: {expected}
         Actual output: {actual}
         
         Rubric: {rubric}
         
         Score the actual output from 0.0 (completely wrong) to 1.0 (perfect).
         Output ONLY a number between 0.0 and 1.0."
        """
        judge_prompt = f"""You are evaluating an AI agent's output.

Expected output: {expected}

Actual output: {actual}

{rubric if self.rubric else "Score the actual output from 0.0 (completely wrong) to 1.0 (perfect)."}

Output ONLY a number between 0.0 and 1.0."""
        
        try:
            response = self.judge_llm.complete(
                prompt=judge_prompt,
                system_prompt="You are a strict but fair evaluator.",
                temperature=0.0,
            )
            score = float(response.strip())
            score = max(0.0, min(1.0, score))  # Clamp to [0, 1]
            passed = score >= 0.5  # Default threshold
            return (passed, score)
        except (ValueError, LLMError):
            return (False, 0.0)  # Judge failed — treat as wrong
```

**Edge cases handled:**
- Judge LLM fails → score 0.0 (conservative)
- Judge returns non-numeric output → score 0.0
- Score outside [0, 1] → clamped
- Empty actual output → judge will likely score 0.0

**Important: The judge LLM must be a different model than the agent LLM.** Using the same model for both the agent and the judge creates a shared blind spot — the judge may not detect errors that the agent's model family is prone to. The judge LLM is configured separately in the config file.

## 5. The A/B Test Runner

### 5.1 Main Loop

```python
def run_ab_test(
    prompt_a: str,
    prompt_b: str,
    task_set: TaskSet,
    llm: LLMProvider,
    scorer: Scorer,
    config: Config,
) -> ABResult:
    """
    Run the full A/B test.
    
    1. For each task, run with both prompts
    2. Score each output
    3. Compute statistics
    4. Return result
    """
    tasks = task_set.list_tasks()
    results: list[TaskResult] = []
    total_tokens = 0
    total_cost = 0.0
    failures = 0
    
    for task in tasks:
        # Run with prompt A
        result_a = run_task(task, prompt_a, llm)
        output_a = result_a.output
        score_a = scorer.score(task.expected_output, output_a)[1] if not result_a.error else 0.0
        
        # Run with prompt B
        result_b = run_task(task, prompt_b, llm)
        output_b = result_b.output
        score_b = scorer.score(task.expected_output, output_b)[1] if not result_b.error else 0.0
        
        # Track failures
        if result_a.error or result_b.error:
            failures += 1
        
        # Track cost
        total_tokens += result_a.token_count + result_b.token_count
        
        results.append(TaskResult(
            task_id=task.id,
            task_input=task.input,
            expected_output=task.expected_output,
            output_a=output_a,
            score_a=score_a,
            output_b=output_b,
            score_b=score_b,
            delta=score_b - score_a,
            latency_a_ms=result_a.latency_ms,
            latency_b_ms=result_b.latency_ms,
            tokens_a=result_a.token_count,
            tokens_b=result_b.token_count,
            error_a=result_a.error,
            error_b=result_b.error,
        ))
        
        # Check cost ceiling
        total_cost = estimate_cost(total_tokens)
        if total_cost > config.ab_test.cost_ceiling_usd:
            return ABResult(
                winner="inconclusive",
                mean_delta=0.0,
                ci_low=0.0, ci_high=0.0,
                p_value=1.0,
                effect_size=0.0,
                n_trials=len(results),
                per_task=results,
                cost_usd=total_cost,
                token_count=total_tokens,
            )
    
    # Abort if too many failures
    if failures / len(tasks) > 0.2:
        return ABResult(
            winner="inconclusive",
            mean_delta=0.0,
            ci_low=0.0, ci_high=0.0,
            p_value=1.0,
            effect_size=0.0,
            n_trials=len(results),
            per_task=results,
            cost_usd=total_cost,
            token_count=total_tokens,
        )
    
    # Compute statistics
    deltas = [r.delta for r in results]
    scores_a = [r.score_a for r in results]
    scores_b = [r.score_b for r in results]
    
    mean_a = sum(scores_a) / len(scores_a) if scores_a else 0.0
    mean_b = sum(scores_b) / len(scores_b) if scores_b else 0.0
    mean_delta = mean_b - mean_a
    
    # Bootstrap CI
    ci = bootstrap_ci(deltas, n_resamples=config.ab_test.bootstrap_trials)
    
    # Permutation test
    p_value = permutation_test(scores_a, scores_b, n_permutations=config.ab_test.permutation_trials)
    
    # Effect size
    effect = effect_size(scores_a, scores_b)
    
    # Determine winner
    if ci["ci_low"] > 0 and p_value < config.ab_test.confidence_level and effect >= config.ab_test.effect_size_min:
        winner = "b"
    elif ci["ci_high"] < 0 and p_value < config.ab_test.confidence_level:
        winner = "a"
    elif ci["ci_low"] <= 0 <= ci["ci_high"]:
        winner = "inconclusive"
    else:
        winner = "inconclusive"
    
    return ABResult(
        winner=winner,
        mean_delta=mean_delta,
        ci_low=ci["ci_low"],
        ci_high=ci["ci_high"],
        p_value=p_value,
        effect_size=effect,
        n_trials=len(results),
        per_task=results,
        cost_usd=total_cost,
        token_count=total_tokens,
    )
```

### 5.2 What Happens When a Task Fails

When a task fails for one prompt but not the other, the task is **excluded from the analysis**. This is important because the paired design requires both scores to compute a delta. If only one prompt produces a result, we can't say whether the other prompt would have also failed.

However, the failure rate itself is informative. If prompt B causes 5/30 tasks to fail while prompt A causes 0/30, that's a strong signal that prompt B is worse. The per-task breakdown captures this data even though the statistical analysis excludes the failed tasks.

**If > 20% of tasks fail for either prompt, the entire A/B test is aborted.** This prevents a bad prompt from degrading the agent's reliability without being caught — the failure rate itself is a signal that the prompt is broken.

### 5.3 Cold Start Problem

The first A/B test runs on a held-out set that the agent has never seen. The agent may perform poorly on the first run regardless of the prompt. This is expected — the baseline measurement captures this, and subsequent A/B tests measure improvement from the baseline.

To mitigate the cold start, the user can run a few "warm-up" tasks through the agent before the first A/B test. These tasks are not scored — they just give the agent a chance to "settle" into the prompt.

## 6. Statistical Analysis in Detail

### 6.1 Bootstrap CI — Step by Step

```python
def bootstrap_ci(
    deltas: list[float],    # e.g., [+0.2, -0.1, 0.0, +0.3, ...]
    n_resamples: int = 10000,
    ci_level: float = 0.95,
) -> dict:
    """
    Compute confidence interval for the mean delta.
    
    Example with 3 tasks (deltas = [+0.2, -0.1, +0.3]):
    
    Step 1: Compute observed mean = (+0.2 + -0.1 + 0.3) / 3 = 0.133
    
    Step 2: Resample 10,000 times:
    Resample 1:  [+0.2, +0.2, -0.1]  → mean = 0.100
    Resample 2:  [+0.3, -0.1, +0.3]  → mean = 0.167
    Resample 3:  [-0.1, +0.2, +0.3]  → mean = 0.133
    ...
    Resample 10,000: [...]
    
    Step 3: Sort the 10,000 means
    Step 4: 2.5th percentile = lower bound of 95% CI
           97.5th percentile = upper bound of 95% CI
    """
    n = len(deltas)
    if n < 2:
        return {"mean": sum(deltas) / n if n > 0 else 0, "ci_low": 0, "ci_high": 0, "std": 0}
    
    rng = random.Random(0)  # Deterministic seed for reproducibility
    means = []
    
    for _ in range(n_resamples):
        # Sample WITH replacement (same task can appear multiple times)
        sample = [rng.choice(deltas) for _ in range(n)]
        means.append(sum(sample) / n)
    
    means.sort()
    tail = (1 - ci_level) / 2
    low_idx = int(tail * n_resamples)
    high_idx = int((1 - tail) * n_resamples) - 1
    
    return {
        "mean": sum(deltas) / n,
        "ci_low": means[low_idx],
        "ci_high": means[high_idx],
        "std": statistics.stdev(means),
    }
```

### 6.2 Permutation Test — Step by Step

```python
def permutation_test(
    scores_a: list[float],   # e.g., [0.7, 0.5, 0.8, ...]
    scores_b: list[float],   # e.g., [0.9, 0.4, 0.8, ...]
    n_permutations: int = 1000,
) -> float:
    """
    Compute p-value: "If the prompts were identical, how likely would we
    see a difference this large by chance?"
    
    NULL HYPOTHESIS: The two prompts produce the same score distribution.
    
    ALTERNATIVE: Prompt B produces higher scores than prompt A (one-tailed).
    
    Example with 3 tasks:
    scores_a = [0.7, 0.5, 0.8]
    scores_b = [0.9, 0.4, 0.8]
    
    Step 1: Observe mean difference = mean(b) - mean(a) = 0.7 - 0.667 = 0.033
    
    Step 2: Pool all scores: [0.7, 0.5, 0.8, 0.9, 0.4, 0.8]
    
    Step 3: Shuffle 1000 times, each time splitting into two groups of 3:
    Shuffle 1: [0.7, 0.9, 0.4] vs [0.5, 0.8, 0.8] → diff = 0.667 - 0.7 = -0.033
    Shuffle 2: [0.5, 0.8, 0.9] vs [0.7, 0.4, 0.8] → diff = 0.733 - 0.633 = 0.100
    ...
    
    Step 4: Count how many shuffled differences >= 0.033 (observed diff)
    Step 5: p-value = count / 1000
    """
    observed_diff = sum(scores_b) / len(scores_b) - sum(scores_a) / len(scores_a)
    pooled = scores_a + scores_b
    n = len(scores_a)
    count = 0
    
    for _ in range(n_permutations):
        random.shuffle(pooled)
        fake_a = pooled[:n]
        fake_b = pooled[n:]
        fake_diff = sum(fake_b) / len(fake_b) - sum(fake_a) / len(fake_a)
        if fake_diff >= observed_diff:
            count += 1
    
    return count / n_permutations
```

### 6.3 What the P-Value Actually Means

The p-value answers one specific question: **"If the two prompts were actually identical, how likely would we see a difference this large (or larger) purely by chance?"**

**Concrete example:**
- You run the A/B test and get p = 0.02
- This means: if the prompts were identical, there's only a 2% chance you'd observe a difference this big or bigger just from random noise
- Therefore, it's unlikely that noise explains the result — the prompt change probably made a real difference

**What the p-value is NOT:**
- NOT the probability that prompt B is better (that's a Bayesian concept, not what this test measures)
- NOT the probability that the result is a false positive
- NOT a measure of effect size (a tiny improvement can have a very small p-value if you have enough data)

### 6.4 How the Promotion Gate Uses the P-Value

The gate checks: `p_value < confidence_level` (default: p < 0.05).

| p-value | Gate Decision | Meaning |
|---------|---------------|---------|
| 0.001 | ✅ Pass | Very strong evidence B is better. Only 0.1% chance this is noise. |
| 0.02 | ✅ Pass | Strong evidence. Only 2% chance this is noise. |
| 0.049 | ✅ Pass (barely) | Passes the threshold. 4.9% chance this is noise. |
| 0.051 | ❌ Fail (barely) | Fails the threshold. 5.1% chance this is noise. |
| 0.30 | ❌ Fail | Weak evidence. 30% chance this is noise — not convincing. |
| 0.50 | ❌ Fail | No evidence. 50/50 — the difference is as likely as not to be noise. |
| 1.00 | ❌ Fail | Identical distributions. Zero evidence of any difference. |

**Why 0.05?** It's the conventional threshold in statistical testing. It means we're willing to accept a 5% chance of a false positive (promoting an edit that isn't actually better). This is a reasonable default — the guardrails (frozen sections, edit distance, drift) provide additional safety layers.

### 6.5 Common Misinterpretations

| Misinterpretation | Truth |
|-------------------|-------|
| "p = 0.01 means there's a 99% chance B is better" | **Wrong.** p = 0.01 means "if the prompts were identical, there's a 1% chance of seeing this difference." It doesn't directly give the probability that B is better. |
| "p = 0.06 means B is probably better, we just need more data" | **Dangerous.** This is p-hacking. Running more trials until p < 0.05 inflates your false positive rate. The system does NOT automatically run more trials. |
| "p < 0.05 means the effect is large" | **Wrong.** A tiny effect can achieve p < 0.05 with enough data. The gate also checks effect size (default: 5% minimum improvement) to catch this. |
| "p < 0.05 means the result is practically significant" | **Wrong.** Statistical significance ≠ practical significance. An improvement from 72% to 72.5% might be statistically significant with enough data, but it's not worth deploying. The effect size check prevents this. |

### 6.6 Why Not a T-Test?

A standard t-test assumes the data follows a normal distribution. Our deltas (score differences) often don't — they're bounded between -1 and +1, and many tasks may tie (delta = 0). The permutation test makes no normality assumption. It works by shuffling the actual observed data, which preserves the true distribution. This is more robust for our use case.

### 6.7 Why Not a Bayesian Approach?

A Bayesian approach would give us a probability distribution over the effect size, which is arguably more useful. But it requires specifying a prior, which adds complexity and subjectivity. The frequentist approach (CI + p-value) is simpler, more standard, and easier for users to understand. Bayesian analysis can be added as an option in a future version.

### 6.3 Interpreting the Results

| CI entirely above 0 | p-value < 0.05 | Effect > 5% | Winner | Action |
|---|---|---|---|---|
| ✅ | ✅ | ✅ | B | Promote |
| ✅ | ✅ | ❌ | Inconclusive | Don't promote (improvement too small) |
| ✅ | ❌ | ✅ | Inconclusive | Don't promote (could be noise) |
| ❌ | ❌ | ❌ | Inconclusive | Don't promote (not enough data) |
| CI entirely below 0 | ✅ | — | A | Reject (B is worse) |

## 7. The Scoring Problem for Free-Form Text

For generation tasks (summarization, translation, creative writing), there is no single "correct" answer. The LLMJudgeScorer handles this, but it has limitations.

**How the LLMJudgeScorer works in practice:**

1. The user provides a rubric in the task definition: "Rate the output on: accuracy (0-1), completeness (0-1), tone (0-1)."
2. The judge LLM reads the rubric, the expected output, and the actual output.
3. The judge produces a score from 0.0 to 1.0.
4. The score is clamped to [0, 1] and treated as a continuous value.

**Limitations:**
- The judge is itself an LLM and may have biases
- The judge adds cost (~1 LLM call per task per prompt version)
- The judge's scoring is stochastic (even at temperature 0)
- The judge may not detect subtle errors that a human would catch

**Mitigation:**
- The judge LLM should be a different model than the agent
- The rubric should be specific and task-grounded
- The user can provide custom scorers for domain-specific evaluation

## 8. Operational Concerns

### 8.1 Cost Ceiling

The A/B test engine tracks token usage in real-time. If the estimated cost exceeds the configured ceiling, the test is aborted. Partial results are discarded — they are not used for promotion decisions.

**Default ceiling:** $0.10 per A/B test. This covers ~30 tasks × 2 prompts × 500 tokens each = 30K tokens on gpt-4o-mini.

### 8.2 Timeout

Each task run has a configurable timeout (default: 30 seconds). If the LLM call exceeds this timeout, the task is marked as failed. The paired design requires both prompts to complete — if prompt A times out, the task result is excluded from analysis.

### 8.3 Parallel Execution (Future)

For v0.1.0, tasks run sequentially. For v0.2.0, parallel execution can be added:

```
Thread pool with N workers:
    Worker 1: task 1, prompt A → task 1, prompt B
    Worker 2: task 2, prompt A → task 2, prompt B
    ...
```

Parallel execution requires rate-limit awareness. The LLM provider may throttle requests. The number of parallel workers should be configurable.

### 8.4 Caching

Identical (task, prompt) pairs produce the same output at temperature 0.0 (within LLM non-determinism). The task runner can cache results to avoid redundant LLM calls.

**Cache key:** `hash(task.input + prompt + llm_provider.model)`
**Cache storage:** SQLite (same as trace store)
**Cache invalidation:** Prompt version changes → cache invalidated for that prompt

## 9. Edge Cases and Failure Modes

| Edge Case | What Happens | Mitigation |
|-----------|-------------|------------|
| All tasks tie | Delta = 0 for all tasks. CI = [0, 0]. p = 1.0. Winner = "tie." | Result is "tie" — no promotion. |
| All tasks fail | > 20% failure rate. A/B test aborted. | Check LLM provider, check task format. |
| Only 1 task in set | Bootstrap CI is meaningless. Gate rejects (sample floor = 30). | Sample floor must be >= 30. |
| Scores are identical | All deltas = 0. CI = [0, 0]. No improvement. | Correct — prompts are equivalent. |
| Prompt B causes errors | B fails on 5/30 tasks. Those 5 are excluded. | Failure rate is captured in per-task data. If > 20%, aborted. |
| Cost ceiling hit mid-run | A/B test aborted. Partial results discarded. | Increase ceiling or reduce task set size. |
| LLM provider is down | All tasks fail. A/B test aborted. | Retry with backoff. Check provider status. |
| Task set is empty | A/B test returns immediately with n_trials = 0. | Gate rejects (sample floor not met). |

## 11. LLM Model Comparison in A/B Testing

The A/B test engine is designed primarily to compare **prompt versions** using the same LLM. But the self-improvement loop raises a natural question: should we also compare different LLM models?

### 11.1 When Model Comparison Matters

There are three scenarios where model choice matters:

| Scenario | Question | When It Happens |
|----------|----------|-----------------|
| **Analyzer proposes a model change** | "Should we switch from gpt-4o-mini to gpt-4o for this agent?" | The analyzer identifies that the prompt is hitting a capability ceiling. A better model might improve results even with the same prompt. |
| **Field test calibration** | "Does the self-improvement loop work better with model X vs model Y?" | During the field test, we want to understand how loop performance varies by model. |
| **User onboarding** | "Which model should I use for my agent?" | The user wants to know the cost-quality tradeoff. |

### 11.2 How Model Comparison Works

The A/B test engine can be extended to compare models, not just prompts. The same paired design works, but now both the prompt and the model may differ:

```
Scenario A: prompt_current + model_current
Scenario B: prompt_current + model_candidate

OR

Scenario A: prompt_current + model_current  
Scenario B: prompt_candidate + model_candidate
```

The key insight is that the A/B test engine already supports this — it takes a `llm_provider` parameter. To compare models, we simply pass different providers:

```python
# Compare prompts with same model (standard)
result = run_ab_test(
    prompt_a=current_prompt,
    prompt_b=candidate_prompt,
    llm=llm_current,   # Same model for both
    task_set=task_set,
    scorer=scorer,
)

# Compare models with same prompt (model evaluation)
result = run_ab_test(
    prompt_a=current_prompt,
    prompt_b=current_prompt,  # Same prompt
    llm_a=llm_current,        # Different models
    llm_b=llm_candidate,
    task_set=task_set,
    scorer=scorer,
)
```

### 11.3 When Model Comparison Is NOT the Analyzer's Job

The analyzer proposes **prompt edits**, not model changes. Model comparison is a separate concern:

- **Prompt optimization** = analyzer proposes edits → A/B test validates → gate promotes
- **Model selection** = user or operator runs a separate model comparison → decides which model to use

The self-improvement loop optimizes the prompt for a given model. If the user wants to change the model, they update the config and the loop starts fresh with the new model.

### 11.4 Model Comparison in the Field Test

The field test validates the self-improvement loop across multiple models to understand how the loop performs with different LLMs. This is not a built-in feature of the A/B test engine — it's an analysis done during the field test.

| Model | Role in Field Test | Expected Cost | Expected Quality |
|-------|-------------------|---------------|------------------|
| gpt-4o-mini | Default analyzer + A/B test model | Low | Good |
| gpt-4o | Comparison for quality | Medium | Better |
| Local OMLX/Ollama model | Hermetic CI testing | Zero | Lower |

**What the field test measures per model:**
- Improvement rate over 10 iterations
- Cost per iteration
- Proposal validity rate (analyzer quality)
- Guardrail pass/fail patterns
- Cold-start behavior (first edit quality)

**The field test does NOT use the A/B test engine to compare models.** Model comparison is done by running the full loop with each model independently and comparing the results. The A/B test engine is only used to compare prompt versions within a single loop run.

---

## 12. How A/B Testing Works During the Field Test

The field test (M10) runs the full self-improvement loop 10 times. Each iteration involves A/B testing. Here is exactly how it works.

### 12.1 Field Test Structure

```
Iteration 0: baseline → measure accuracy on held-out set → record
Iteration 1: run traces → analyze → propose edit 1 → A/B test → gate → promote or reject → measure accuracy
Iteration 2: run traces → analyze → propose edit 2 → A/B test → gate → promote or reject → measure accuracy
...
Iteration 10: run traces → analyze → propose edit 10 → A/B test → gate → promote or reject → measure accuracy
```

### 12.2 Per-Iteration A/B Test Flow

Within each iteration, the A/B test works exactly as described in this document:

```
1. Traces have accumulated (from training tasks)
2. Analyzer reviews traces → proposes 1-3 edits
3. For each edit proposal:
   a. Current prompt becomes prompt_a
   b. Current prompt + edit becomes prompt_b
   c. A/B test runs: prompt_a vs prompt_b on held-out task set
   d. If B is better: gate promotes → new prompt version
   e. If not: edit archived, next proposal tested
4. After all proposals processed: run agent on training tasks with new prompt
5. Measure accuracy on held-out set
6. Record per-iteration results
```

### 12.3 What the Field Test Validates About the A/B Test Engine

| Test | What It Validates | How |
|------|-------------------|-----|
| **Baseline calibration** | A/B test engine produces correct results on known data | Feed known-better and known-worse prompts through the engine. Verify it correctly identifies the winner. |
| **Bootstrap CI accuracy** | Bootstrap CI contains the true mean 95% of the time | Run synthetic calibration: generate 1000 datasets with known true mean, verify 95% CI covers it ~95% of the time. |
| **Permutation test calibration** | P-values are uniform under null hypothesis | Run synthetic calibration: shuffle labels, verify p-values are uniformly distributed. |
| **Sample floor enforcement** | Gate rejects when n < sample_floor | Run A/B test with 5, 15, 30, 50 tasks. Verify gate behavior at each size. |
| **Cost ceiling enforcement** | A/B test aborts when cost exceeds ceiling | Set low ceiling, run A/B test with large task set. Verify abort. |
| **Error handling** | Task failures are handled correctly | Simulate LLM failures, rate limits, timeouts. Verify correct behavior. |
| **Reproducibility** | Same inputs produce same results | Run same A/B test twice. Verify same winner, same CI, same p-value. |

### 12.4 Field Test: A/B Calibration Test Script

The field test includes a calibration script that validates the A/B test engine against known ground truth:

```python
# scripts/calibrate_ab_test.py
"""
Calibrate the A/B test engine against known ground truth.

1. Create a prompt that is known to be better (e.g., includes explicit instructions)
2. Create a prompt that is known to be worse (e.g., missing key instructions)
3. Run A/B test on both
4. Verify: winner = "b", CI above 0, p < 0.05, effect size > min
5. Repeat with known-equal prompts → verify "inconclusive" or "tie"

This validates that the A/B test engine produces correct results
before we trust it to evaluate real edits.
"""
```

### 12.5 Field Test: Synthetic Data Calibration

The A/B test engine is also validated on synthetic data where the ground truth is known:

```python
# Generate synthetic scores with known effect size
scores_a = [0.5, 0.6, 0.7, 0.5, 0.6]  # mean = 0.58
scores_b = [0.7, 0.8, 0.9, 0.7, 0.8]  # mean = 0.78, effect = +34%

result = run_ab_test_with_scores(scores_a, scores_b)
assert result.winner == "b"
assert result.effect_size > 0.20
assert result.ci_low > 0
assert result.p_value < 0.05
```

This is a hermetic test (no LLM calls) that validates the statistical methodology independently of the LLM.

---

## 13. Multi-Turn and Tool-Using Agents

The A/B test engine assumes a **single-turn stateless LLM call**. Real agents may use tools, have memory, or perform multi-turn tasks. This section describes how the engine handles these cases.

### 13.1 Multi-Turn Tasks

A multi-turn task requires the agent to make multiple LLM calls, potentially with tool invocations between them. The A/B test engine does not directly support multi-turn tasks in v0.1.0.

**Workaround:** If the user wants to test a multi-turn task, they can flatten it into a single-turn task by providing the full conversation history in the task input and expecting the agent to produce the final output.

**Example:**
```
Task input: "Customer: 'I need to reset my password.' 
Agent: 'Sure, I can help you with that. First, let me verify your identity.'
Customer: 'My email is user@example.com.'
Agent: 'I found your account. Let me send a verification code.'
Customer: 'I received the code: 123456.'
Agent: 'Thank you. I've reset your password. You'll receive a new one via email.'

Expected output: 'Password reset completed for user@example.com'"
```

This is not ideal — it tests the agent's ability to follow a conversation, not its ability to conduct one. Multi-turn A/B testing is deferred to v0.2.0.

### 13.2 Tool-Using Agents

The A/B test engine assumes the agent is a pure LLM call with no tool access. If the agent uses tools, the A/B test engine cannot directly test it because tool calls require external state.

**Workaround:** The user can test the agent's **prompt** in isolation by providing tool call results as part of the task input. This tests whether the prompt correctly interprets tool results, but not whether the prompt correctly selects which tools to call.

**Example:**
```
Task input: "Tool result: search('billing API') returned: 
[{'name': 'BillingAPI', 'version': 'v2', 'status': 'deprecated'},
 {'name': 'BillingService', 'version': 'v3', 'status': 'active'}]

Expected output: 'Use BillingService v3'"
```

### 13.3 Future: Agent Adapter Interface

For v0.2.0, the A/B test engine will support a **TaskRunner** adapter interface that allows the user to provide a custom runner for their agent. This runner can handle tool calls, multi-turn conversations, and any other agent-specific logic.

```python
class TaskRunner(ABC):
    @abstractmethod
    def run(self, task: Task, prompt: str) -> TaskOutput:
        """Run a task with a given prompt. May involve multiple LLM calls."""
        pass
```

The user provides a TaskRunner that wraps their agent. The A/B test engine calls `runner.run(task, prompt)` and gets back the output. This is deferred to v0.2.0.

---

## 14. A/B Test Engine Validation During Field Test

The field test validates the A/B test engine at multiple levels:

### 14.1 Unit Tests (Hermetic, CI-safe)

| Test | What It Validates | Files |
|------|-------------------|-------|
| Bootstrap CI on known data | CI covers true mean 95% of the time | `tests/test_ab_test.py` |
| Permutation test on known data | P-values are uniform under null | `tests/test_ab_test.py` |
| ExactMatchScorer | Correct for exact/partial/no match | `tests/test_scorers.py` |
| ContainsScorer | Correct for substring/required fields | `tests/test_scorers.py` |
| LLMJudgeScorer | Correct for known-good/bad outputs | `tests/test_scorers.py` |
| Task runner | Correct output, latency, token tracking | `tests/test_ab_test.py` |
| Cost ceiling | Abort when ceiling exceeded | `tests/test_ab_test.py` |
| Error handling | Timeouts, failures handled correctly | `tests/test_ab_test.py` |

### 14.2 Integration Tests (Hermetic, CI-safe)

| Test | What It Validates | Files |
|------|-------------------|-------|
| Full A/B test with mock provider | End-to-end: task runner → scorer → statistics → result | `tests/test_ab_test.py` |
| A/B test with known-better prompt | Winner = "b", CI above 0 | `tests/test_ab_test.py` |
| A/B test with identical prompts | Winner = "inconclusive" | `tests/test_ab_test.py` |
| A/B test with known-worse prompt | Winner = "a" | `tests/test_ab_test.py` |
| A/B test with empty task set | n_trials = 0, no crash | `tests/test_ab_test.py` |

### 14.3 Calibration Tests (Hermetic, CI-safe)

| Test | What It Validates | Files |
|------|-------------------|-------|
| Bootstrap calibration on synthetic data | 95% CI contains true mean ~95% of the time | `tests/test_ab_test.py` |
| Permutation calibration on synthetic data | P-values uniformly distributed under null | `tests/test_ab_test.py` |
| Effect size calibration on synthetic data | Effect size matches known ground truth | `tests/test_ab_test.py` |

### 14.4 LLM Tests (Requires API Key, CI-skipped)

| Test | What It Validates | Files |
|------|-------------------|-------|
| Full A/B test with real LLM | End-to-end with real provider | `tests/test_ab_test.py` |
| A/B test with gpt-4o-mini | Loop works with cheap model | Manual |
| A/B test with gpt-4o | Loop works with capable model | Manual |
| A/B test with local model | Loop works with OMLX/Ollama | Manual |

### 14.5 Calibration Script

The field test includes a calibration script (`scripts/calibrate_ab_test.py`) that validates the A/B test engine:

```bash
# Run calibration (hermetic, no LLM calls)
python scripts/calibrate_ab_test.py
# Output:
# Bootstrap CI calibration: 94.7% coverage (target: 95%) ✓
# Permutation test calibration: p-values uniform ✓
# Effect size calibration: +34.2% vs expected +35% ✓
# Known-better prompt: winner=b ✓
# Known-worse prompt: winner=a ✓
# Identical prompts: inconclusive ✓
```

---

## 15. Configuration Summary

```yaml
ab_test:
  held_out_tasks: ./tasks/held-out.yaml
  sample_floor: 30           # Minimum tasks before promotion
  effect_size_min: 0.05      # Minimum 5% relative improvement
  confidence_level: 0.95      # p < 0.05
  bootstrap_trials: 10000     # Bootstrap resamples
  permutation_trials: 1000    # Permutation shuffles
  cost_ceiling_usd: 0.10      # Abort if cost exceeds $0.10
  task_timeout_seconds: 30    # Per-task timeout
  parallel_workers: 1         # Sequential for v0.1.0
  judge_model: "gpt-4o-mini"  # LLMJudgeScorer model (different from agent)
  cache_enabled: true         # Cache identical (task, prompt) pairs
  temperature: 0.0            # LLM temperature for reproducibility
  agent_model: "gpt-4o-mini"  # The agent's LLM (used for running tasks)
  max_failure_rate: 0.20      # Abort if > 20% of tasks fail
```

## 16. Summary

The A/B test engine works by:

1. **Running each task against both prompts** (paired design, temperature 0.0)
2. **Scoring each output** (ExactMatch, Contains, or LLMJudge)
3. **Computing confidence intervals** (bootstrap, 10K resamples)
4. **Computing p-values** (permutation test, 1K shuffles)
5. **Computing effect size** (relative improvement)
6. **Returning a structured result** with per-task breakdown

**Model comparison is separate from prompt comparison.** The analyzer optimizes prompts for a given model. Model selection is done by the user via configuration. The field test validates the loop across multiple models independently.

**The field test validates the A/B test engine** through hermetic calibration tests, integration tests with known prompts, and real LLM tests. The calibration script validates that the statistical methodology produces correct results before the engine is trusted to evaluate real edits.

The promotion gate then checks: sample floor ≥ 30, CI entirely above 0, p < 0.05, effect size ≥ 5%. If all pass, the edit is promoted. If any fail, the edit is rejected with a clear reason.

**For multi-turn and tool-using agents:** The v0.1.0 engine supports single-turn stateless tasks. Multi-turn and tool-using support is deferred to v0.2.0 via a TaskRunner adapter interface.