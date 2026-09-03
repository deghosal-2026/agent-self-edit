# Learnings — AgentSelfEdit v0.3.0 Field Tests

## 5-Iteration Classification Run (Local OMLX Model)

### Observed Outcome

- Model: `Qwen3-4B-Instruct-2507-4bit`
- Corpus mode: synthetic classification improvement loop
- Iterations: `5`
- Baseline held-out accuracy: `60.0%` (`15/25`)
- Final held-out accuracy: `60.0%` (`15/25`)
- Net delta: `0.0%`
- Iteration durations: `68s`, `58s`, `59s`, `62s`, `57s`
- Total duration: about `305s`

### What the Artifacts Prove

- The end-to-end loop is functioning.
- Every iteration produced the expected artifacts:
  - `analysis.json`
  - `ab-comparison.json`
  - `accuracy.json`
  - `prompt-a.md`
  - `prompt-b.md`
  - `prompt-after.md`
- The system successfully completed all major phases on every iteration:
  - trace seeding
  - analyzer proposal generation
  - A/B evaluation
  - gate decision
  - held-out accuracy measurement

### Why 0% Improvement Happened Here

- This run does **not** indicate a broken pipeline.
- It indicates a **weak proposal quality loop** for the chosen model setup.
- The candidate prompt was evaluated every time, but it never produced a measurable improvement on the promotion corpus.
- Because no candidate crossed the promotion threshold, the active prompt never changed.
- Because the active prompt never changed, held-out accuracy also never changed.

### Repeated Proposal Pattern

- Each iteration produced exactly `1` proposal.
- Every proposal targeted the same prompt area: `Rules`.
- Every proposal was a small rewrite of the `urgent` classification rule.
- The proposals were near-duplicates rather than meaningfully different interventions.

Observed examples included:

- adding wording around `active compromise`
- requiring more explicit operational impact
- clarifying urgency boundaries with examples

This shows the analyzer is converging on a narrow local pattern instead of exploring alternative edits.

### Gate Behavior

- Every iteration ended in `near_miss`.
- The failure reason was consistently:
  - `1/2 checks passed (failed at: effect_size)`
- A/B outcomes were either:
  - `tie`, or
  - `inconclusive`
- `effect_size` remained `0.0` across the run.

This is important because it tells us:

- the gate is **not** blocking on drift
- the gate is **not** blocking on frozen sections
- the gate is **not** blocking on edit distance
- the gate is **not** blocking on prompt materialization failures
- the proposals are simply too weak to produce measurable gains

### Prompt Evolution Behavior

- `prompt-b.md` changed every iteration.
- `prompt-after.md` matched `prompt-a.md` every iteration.
- That means the system is generating candidate edits, but none are being promoted.

This is the exact expected behavior for a healthy loop when:

- proposal generation works,
- evaluation works,
- the gate works,
- but the candidate prompt is not actually better.

### What This Says About the 4B Model

- `Qwen3-4B-Instruct-2507-4bit` appears acceptable as a low-cost executor/baseline model.
- It does **not** appear strong enough as an analyzer for repeated self-improvement.
- In this role, it keeps proposing the same class of small edit and does not appear to use rejection feedback in a meaningfully diversifying way.

This strengthens the working recommendation:

- use a smaller model for executor runs when cost/latency matter
- use a stronger model for analyzer generation
- likely keep judge on a stronger model as well for generation tasks

### Rejection Feedback: Mechanically Present, Behaviorally Weak

- Rejection-aware plumbing exists and is functioning.
- The analyzer is receiving enough context to continue proposing edits after rejection.
- However, the resulting proposals are still repetitive.

Inference:

- rejection feedback is present **mechanically**
- rejection feedback is **not behaviorally strong enough** with this analyzer model

So the limiting factor is not feature absence, but model capability.

### Promotion Corpus Alignment Question

The analyzer repeatedly focused on urgency misclassification. That suggests one of two things:

1. the sampled failed traces over-emphasize urgency-related failure patterns, or
2. the analyzer is overfitting to a visible failure pattern that does not materially move the 40-task promotion set.

This means the promotion corpus and sampled failures may be only partially aligned.

Practical implication:

- we should inspect per-task A/B deltas for these runs before assuming the analyzer found the wrong problem entirely
- it may be improving a tiny subset of tasks while harming or not affecting the larger promotion set

### Held-Out Metric Interpretation

- Held-out stayed flat at `15/25` every iteration.
- Since no prompt was promoted, this is expected.

Important interpretation:

- in a no-promotion run, held-out accuracy mainly tells us that the deployed prompt did not change
- it does **not** tell us whether candidate prompts were locally promising unless we separately inspect `results-b.json`

So for reporting we should distinguish between:

- `candidate quality`
- `promotion success`
- `deployed held-out accuracy`

### Near-Miss Semantics

- The current near-miss configuration marks these candidates as `near_miss` even though they fail immediately at statistical usefulness.
- That is technically correct under the configured ratio logic.
- But operationally, repeated `near_miss` outcomes with `effect_size = 0.0` may create noise.

Suggested interpretation:

- not all `near_miss` outcomes are equally informative
- a repeated `near_miss` at `effect_size` with zero movement should be treated as a low-value candidate pattern

### Reporting/Data Consistency Issue

- The console summary reported `60.0%` correctly.
- The top-level `improvement-loop-report.json` also reported baseline/final/improvement correctly.
- But per-iteration `accuracy.json` exposed `correct` and `total` while the derived percentage field was not populated consistently.

This is not blocking execution, but it is a reporting quality issue.

Implication:

- downstream summaries should not need to reconstruct percentages from `correct/total`
- per-iteration metrics should include a stable `accuracy_pct` or equivalent derived field everywhere

### Strongest Conclusions

#### 1. The old v0.2.0 broken-path explanation no longer applies here.

This run is not failing because of:

- no-op prompt replacement
- gate bypass
- stale prompt disk churn

Those issues were already fixed.

#### 2. The current bottleneck is proposal quality.

The analyzer produces edits, but they are:

- repetitive
- narrow in scope
- not statistically useful on the promotion corpus

#### 3. Running many more iterations with the same 4B analyzer is unlikely to change much.

The proposal pattern stabilized quickly and repeated.

#### 4. The most valuable next comparison is a stronger analyzer model.

The clearest next experiment is:

- same executor model
- stronger analyzer model
- same corpus
- same iteration count

That isolates analyzer quality as the main variable.

### Recommended Next Runs

1. Run the same 5-iteration classification loop with a stronger analyzer model.
2. Inspect `results-a.json` vs `results-b.json` per iteration to see whether candidates truly change zero task outcomes or just trade wins/losses evenly.
3. Run extraction and generation loops to see whether this failure mode is classification-specific.
4. If repetitive `near_miss` at `effect_size=0.0` continues, consider a reporting bucket that distinguishes:
   - statistically dead proposals
   - guardrail-blocked proposals
   - meaningful but underpowered proposals

### Summary Statement

The 5-iteration classification run makes sense. It demonstrates a working v0.3.0 loop with healthy plumbing, but a weak analyzer model. The absence of improvement is real, not an artifact of broken execution. The system is now failing in an honest, diagnosable way: candidate edits are too repetitive and too weak to change the promotion corpus enough to pass the gate.

This entire section applies specifically to the **local OMLX run** using `Qwen3-4B-Instruct-2507-4bit` as the single model for the loop.

## Additional Inferences With Evidence

### The analyzer is probably anchored on the most visible local pattern, not the highest-leverage edit.

Evidence:

- Every iteration produced exactly one proposal.
- Every proposal targeted the `Rules` section.
- Every proposal rewrote the `urgent` rule rather than exploring billing, feature, security, or structural instruction changes.
- The proposal hypotheses were semantically similar across iterations:
  - clarify active compromise
  - require explicit operational impact
  - add urgency examples

Inference:

- The analyzer appears to be optimizing for the most obvious explanation of observed failures.
- It is not searching broadly for edits with the highest expected impact on the 40-task promotion set.

### The promotion corpus is probably doing its job, and that is exactly why these proposals fail.

Evidence:

- A/B always ran with `n=40`, which means the candidate was evaluated on the promotion corpus rather than a tiny batch.
- A/B results were always `tie` or `inconclusive`.
- `effect_size` remained `0.0` across all five iterations.

Inference:

- The promotion corpus is broad enough that a narrow urgency-rule tweak does not materially move overall performance.
- The problem is not that the corpus is too small or too lenient.
- The problem is that the analyzer is proposing edits with too little leverage across the full promotion set.

### Failure sampling may be reinforcing repetition.

Evidence:

- Each iteration started with `Seeded 10 real failures`.
- Despite repeated iterations, the analyzer kept returning urgency-focused proposals.
- No iteration produced a qualitatively different intervention family.

Inference:

- Either the sampled failure batches are highly similar between iterations, or the analyzer is extracting only one repeated pattern from them.
- A low-diversity failure batch can trap the loop into repeatedly optimizing one visible failure mode.

Practical follow-up:

- Inspect the per-iteration trace batches to see whether the same task classes dominate the failures.

### The current `near_miss` label overstates how promising these candidates are.

Evidence:

- Every candidate was labeled `near_miss`.
- Every candidate failed at the second check: `effect_size`.
- The failing value stayed at `0.0` improvement.

Inference:

- These candidates are only “near” promotion in the narrow ratio sense of the gate implementation.
- Operationally, they are not close to useful promotion candidates.

Reporting implication:

- Future summaries should distinguish:
  - guardrail near-miss with meaningful positive signal
  - statistical dead-end near-miss with zero measured gain

### Held-out accuracy is not the right metric for judging rejected candidates.

Evidence:

- `prompt-after.md` always matched `prompt-a.md`.
- Held-out accuracy stayed fixed at `15/25` every iteration.
- No candidate was promoted.

Inference:

- Held-out accuracy is behaving as a deployed-prompt metric, not a candidate-quality metric.
- Flat held-out accuracy here confirms no deployment change, but does not by itself prove the candidate prompt had zero localized wins.

Practical implication:

- To understand candidate quality, inspect `results-a.json` versus `results-b.json`, not just held-out accuracy.

### Dedup appears insufficient at the semantic level.

Evidence:

- Iterations 3 and 5 are effectively the same edit family.
- Iterations 2, 3, 4, and 5 all modify the same `urgent` rule boundary.
- The wording changes, but the intervention intent remains constant.

Inference:

- Existing rejection-aware behavior is not preventing “same idea, rephrased” proposals.
- The loop likely needs intent-level or hypothesis-level dedup, not only proposal-text-level difference.

### The run indirectly validates model-role separation as the next serious experiment.

Evidence:

- The executor baseline reached `60.0%` on the held-out set, which is not catastrophically low.
- The analyzer repeatedly produced narrow, low-impact proposals.
- Docker and hermetic tests confirmed the role-routing code now works correctly.

Inference:

- The clearest weakness is analyzer capability, not executor viability.
- That makes “small executor, stronger analyzer” the highest-value next comparison.

### The system is now failing honestly and cheaply.

Evidence:

- The full 5-iteration run completed in about `305s`.
- All expected artifacts were written.
- The outcome was diagnosable from structured outputs alone.

Inference:

- Even when a run produces zero improvement, it still produces useful learning at low operational cost.
- That is a meaningful v0.3.0 improvement over the earlier state where zero improvement was entangled with broken execution paths.

### The strongest next evidence should come from per-task deltas or a stronger analyzer, not more identical 4B runs.

Evidence:

- Proposal families stabilized quickly.
- Five iterations produced no promoted changes.
- The analyzer did not diversify over time.

Inference:

- Running many more iterations with the same 4B single-model setup is unlikely to unlock improvement.
- The two highest-value next steps are:
  - inspect `results-a.json` vs `results-b.json` to identify any local wins/losses
- rerun the same experiment with a stronger analyzer model while keeping the executor fixed

## 8-Iteration Classification Run (Cloud OpenRouter Model)

### Observed Outcome

- Model: `mistralai/mistral-small-3.2-24b-instruct`
- Provider: `openai`-compatible API via `https://openrouter.ai/api/v1`
- Corpus mode: synthetic classification improvement loop
- Iterations: `8`
- Baseline held-out accuracy: `64.0%` (`16/25`)
- Final held-out accuracy: `68.0%` (`17/25`)
- Top-level reported delta: `+4.0%`
- Iteration durations: `93.7s`, `66.0s`, `77.0s`, `80.0s`, `67.6s`, `67.9s`, `74.5s`, `105.9s`

### Important Interpretation

- No proposal was promoted.
- `prompt-after.md` still matched `prompt-a.md` in every iteration.
- That means the active prompt never changed.
- So the top-level `68.0%` final held-out number should be interpreted carefully: it is part of candidate evaluation artifacts, not evidence of an actually promoted deployed prompt.

### What Improved Relative to the Local 4B Run

Evidence:

- The local OMLX 4B run produced mostly zero movement on the 40-task promotion set.
- The Mistral run produced several iterations with small positive movement:
  - iteration 1: `1` improved, `0` regressed
  - iteration 2: `1` improved, `0` regressed
  - iteration 3: `2` improved, `0` regressed
  - iteration 6: `1` improved, `0` regressed
  - iteration 7: `1` improved, `0` regressed
- Iteration 3 reached `effect_size = 0.0625`, which is above the default `0.05` threshold.

Inference:

- `mistralai/mistral-small-3.2-24b-instruct` is a stronger analyzer candidate than the local 4B model.
- It is able to produce some real positive movement on the promotion set, even if that movement is still too small to survive the gate.

### What Stayed the Same

Evidence:

- Every iteration still produced exactly `1` proposal.
- Nearly every proposal still targeted the `Rules` section.
- Nearly every proposal still focused on the `urgent` rule.
- The most repeated edit family was:
  - changing `security breach` to `active security breach`
- Other variants stayed close to that same idea:
  - `critical data loss`
  - `explicit urgency cues`

Inference:

- The stronger cloud model is still trapped in a narrow intervention family.
- It is better than the 4B local model, but not yet diverse enough to generate promotable edits.

### Why Nothing Was Promoted

Evidence:

- Iterations 1, 2, 6, and 7 failed at `effect_size` with `1/2` checks passed.
- Iteration 3 was the strongest candidate:
  - `2` tasks improved
  - `0` regressed
  - `mean_delta = 0.05`
  - `effect_size = 0.0625`
  - but `p = 0.79`
  - so it failed `confidence` instead of `effect_size`
- Iterations 4 and 5 had zero movement.
- Iteration 8 had one improvement and one regression.

Inference:

- The Mistral analyzer crosses the effect-size threshold in at least one iteration, but the signal is still too weak to reach confidence on a 40-task promotion set.
- This is stronger evidence that the next limitation is a mix of:
  - proposal strength
  - proposal breadth
  - gate sensitivity / statistical power

### Statistical Power Becomes a More Serious Concern Here

Evidence:

- The local 4B run mostly produced total zeros or perfect cancellations.
- The Mistral run produced small clean wins, especially iteration 3 with `2` wins and `0` losses.
- Even that best case still failed confidence with `p = 0.79`.

Inference:

- The commenter’s broader statistical-power concern is more relevant to the Mistral run than to the local 4B run.
- For the local 4B run, there was essentially no signal to detect.
- For the Mistral run, there is at least a weak positive signal, but it is too small for the current gate to trust.

### Model Comparison Learning

Evidence:

- Local OMLX 4B run:
  - baseline `60.0%`
  - final `60.0%`
  - mostly `0/40` task movement
- Mistral 24B cloud run:
  - baseline `64.0%`
  - candidate artifacts reached `68.0%`
  - multiple iterations had positive task movement
  - one iteration cleared effect size but not confidence

Inference:

- The cloud Mistral model is materially better as an analyzer than the local 4B model.
- But “better” is still not enough for promotion in the current setup.
- This means the model comparison now carries real information:
  - analyzer quality matters
  - but stronger analyzers alone may still not be sufficient if the proposal family remains too narrow

### Strongest Cloud-Run Conclusions

#### 1. The loop is working and now produces weak positive signal with a stronger analyzer.

This is a meaningful improvement over the local run.

#### 2. The main failure mode is still narrow proposal search.

The analyzer is still largely rewriting one urgency rule instead of exploring broader edits.

#### 3. The gate may now be the next bottleneck, but only after analyzer quality improved.

Iteration 3 is the key evidence: it passes effect size but still fails confidence.

#### 4. The best next investigation is per-task delta analysis on the strongest Mistral iteration.

We should inspect which exact promotion tasks moved in iteration 3 and whether they represent a useful edit family or a narrow corner-case win.

### Summary Statement

The Mistral cloud run is meaningfully better than the local OMLX 4B run. It produces real, if small, positive movement on the promotion set and raises the baseline from `60.0%` to `64.0%`. But it still fails to produce a promotable edit. The current system is no longer blocked by broken execution, and no longer purely blocked by an obviously weak analyzer. It is now confronting a narrower, more informative limitation: the analyzer search strategy remains too local, and the gate may be too insensitive to the size of improvements these analyzers can currently produce.
