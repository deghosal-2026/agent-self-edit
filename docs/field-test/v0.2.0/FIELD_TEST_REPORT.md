# Final Field Test Report — AgentSelfEdit v0.2.0

> **BLUF:** v0.2.0 successfully proves the self-edit framework is mechanically sound, safety-gated, multi-domain capable in Docker, and observable enough to diagnose optimizer failures. It does **not** prove successful prompt self-improvement. The strongest analyzer tested produced directional gains, but no model generated an edit strong enough to clear the promotion gate. The main unsolved problem is analyzer quality / search quality, not plumbing.

**Date:** 2026-09-02  
**Primary local execution model:** `Qwen3-4B-Instruct-2507-4bit`  
**Best analyzer candidate tested:** `mistralai/mistral-small-3.2-24b-instruct`  
**Synthetic iterations:** 5 per model  
**Promotion corpus:** `classification-promotion.yaml` (40 tasks)  
**Held-out corpus:** `classification-held-out.yaml` (25 tasks)  
**Sentinel corpus:** `sentinel.yaml` (20 tasks)  
**Gate config:** confidence_level=0.95 (alpha=0.05), min_effect_size=5%, drift_threshold=0.5

---

## 1. Executive Summary

v0.1.0 ended with an honest but frustrating result: the gate worked, but the loop never promoted an edit. At that point it was still unclear whether the system was blocked by:

- A/B test bugs
- fabricated or low-value failure traces
- weak corpus design
- analyzer repetition
- or the analyzer model itself

v0.2.0 was supposed to answer that.

It did.

What v0.2.0 proved:

1. **The framework works end-to-end.**
2. **The gate is correctly rejecting weak edits.**
3. **Multi-domain Docker validation works** across classification, extraction, generation, and staged analyzer paths.
4. **Model-role plumbing works** (including judge role in generation runs).
5. **The optimizer still does not produce a promotable edit.**

That means the central unresolved problem is no longer “is the system broken?” It is now: **why is the analyzer still not finding edits that move enough tasks to get promoted?**

---

## 2. What Changed From v0.1.0 to v0.2.0

### 2.1 Major correctness fixes

v0.2.0 fixed the core correctness and observability issues that made v0.1.0 hard to interpret:

- candidate prompt materialization now uses the full prompt, not just the edited fragment
- gate edit-distance and drift checks use the full candidate prompt
- A/B significance semantics use `alpha = 1 - confidence_level`
- scorer selection is runtime-aware instead of hardcoded to exact match
- the staged analyzer was introduced and later fixed so Stage 4 fuzzy matching actually propagates corrected proposals
- the promotion A/B corpus is now a dedicated 40-task set instead of a fragile hardcoded subset
- rejection context is now threaded into staged analyzer prompts
- field-test corpora were consolidated under `field-test/corpus/`
- Docker tests were expanded to cover extraction, generation, staged analyzer, and judge role

### 2.2 What this means

v0.2.0 made the system much stronger as a **framework**:

- more correct
- more observable
- more reproducible
- easier to diagnose

But it did **not** automatically make the analyzer stronger.

---

## 3. Guardrail Effectiveness

### 3.1 The gate is still the real product

The promotion gate remains the clearest success in the project. Across synthetic runs and Docker integration runs, it rejected every edit that lacked strong evidence.

### 3.2 False positives: 0%

A false positive would mean promoting a weak or harmful edit. That did not happen.

This is backed by repeated real opportunities for the gate to make the wrong decision. In v0.2.0, candidate edits were actually generated, A/B tests actually ran on the 40-task promotion corpus, and the gate saw real p-values and effect sizes. Even under those conditions, it never promoted an edit that lacked evidence. So the 0% false-positive result is evidence of safety, not just absence of success.

### 3.3 False negatives: not observed

No candidate met the promotion bar, so there is no evidence yet of the gate incorrectly rejecting a truly promotable edit.

That does not mean the gate can never reject a good edit. It means the tested v0.2.0 runs never produced an edit that clearly should have been promoted. Some candidates showed directional movement, but none crossed both the effect-size and confidence thresholds.

### 3.4 The 6 checks in practice

| Check | What it tests | v0.2.0 observed behavior |
|-------|---------------|--------------------------|
| sample_floor | enough trials | PASS (`n=40`) |
| effect_size | minimum practical gain | often FAIL |
| confidence | p < 0.05 | FAIL on all tested edits |
| frozen_sections | protected prompt content preserved | PASS |
| edit_distance | edit not too large | PASS after staged-analyzer fixes |
| drift | edit not too far from baseline | PASS after original-baseline fix |

In the later runs, the most common gate blocker was **effect size**, followed by **confidence**.

### 3.5 What promotion would require

For a promotion, an edit must move enough tasks in the 40-task promotion corpus to satisfy both:

- effect size >= 5%
- p-value < 0.05

So far the analyzer has only found weak, local edits that produce too little movement.

The repeated pattern is that the analyzer stays near a tiny local search neighborhood: billing disambiguation, urgent-rule tightening, or output-format tightening. Those edits are plausible, but they do not move enough tasks to become promotable.

---

## 4. Synthetic Improvement-Loop Results

This is the only mode that currently makes conceptual sense for improvement measurement, because it has:

- concrete task inputs
- concrete expected outputs
- scorer-compatible task sets
- a dedicated promotion corpus

### 4.1 Local OMLX: `Qwen3-4B-Instruct-2507-4bit`

| Metric | Value |
|--------|-------|
| Baseline | 60.0% |
| Final | 60.0% |
| Improvement | 0.0% |
| Iterations | 5 |

Per-iteration results:

| Iter | Winner | p-value | n | Mean delta | Accuracy |
|------|--------|---------|---|------------|----------|
| 1 | inconclusive | 0.73 | 40 | -0.05 | 60% |
| 2 | inconclusive | 0.71 | 40 | -0.025 | 60% |
| 3 | inconclusive | 0.46 | 40 | +0.025 | 60% |
| 4 | inconclusive | 0.67 | 40 | -0.025 | 60% |
| 5 | tie | 1.0 | 40 | 0.0 | 60% |

Interpretation:
- the loop runs correctly
- A/B comparisons are real
- rejection feedback is no longer fully ignored
- but the model still cannot generate a strong enough edit to improve the held-out set

#### What this model actually failed on

Held-out accuracy breakdown from the v0.2.0 synthetic classification set:

| Category | Pass | Fail | Failure pattern |
|----------|------|------|-----------------|
| Single-label | 10/10 | 0 | All correct |
| Ambiguous | 2/4 | 2 | Model over-classifies as security/technical instead of `other` |
| Multi-label | 0/3 | 3 | Model returns a single label instead of comma-separated pairs |
| Boundary | 1/3 | 2 | Model picks technical when answer is billing or `other` |
| Legacy | 3/5 | 2 | Multi-label and boundary confusion |

The important point is that the model is **not** failing uniformly. The weak spots are concentrated in:
- multi-label classification
- ambiguous `other` cases
- billing vs technical boundary cases

That means the prompt-edit search problem is real and targeted, not random noise.

#### Why the 4B model still failed as analyzer

The local 4B instruct model could execute the loop quickly, but its analyzer behavior remained weak:
- it stayed close to one local edit family
- it did not discover a stronger intervention than “tighten a rule”
- even after rejection-context wiring, it still produced only small or noisy movement

So the local 4B model is useful to validate mechanics, but not sufficient to prove successful self-editing.

The key point is that this is no longer a “pipeline is broken” result. The loop runs, the A/B test is real, the gate is real, and yet the optimizer still fails to produce a strong edit. That makes this a search-quality problem, not a system-correctness problem.

### 4.2 OpenRouter: `mistralai/mistral-small-3.2-24b-instruct`

| Metric | Value |
|--------|-------|
| Baseline | 64.0% |
| Final | 64.0% |
| Improvement | 0.0% |
| Iterations | 5 |

Per-iteration results:

| Iter | Winner | p-value | n | Mean delta | Accuracy |
|------|--------|---------|---|------------|----------|
| 1 | inconclusive | 0.55 | 40 | +0.025 | 64% |
| 2 | inconclusive | 0.52 | 40 | +0.025 | 64% |
| 3 | tie | 1.0 | 40 | 0.0 | 64% |
| 4 | inconclusive | 0.52 | 40 | +0.025 | 64% |
| 5 | inconclusive | 0.77 | 40 | -0.025 | 64% |

Interpretation:
- this is the strongest analyzer candidate tested
- it explores nearby edit variants better than the local 4B model
- but it still does not produce a promotable edit
- held-out accuracy stays flat in the final rerun

#### Why this model is still the best analyzer candidate

Even though the latest rerun finished at 0% improvement, Mistral still showed the strongest optimizer behavior overall:
- earlier v0.2.0 runs produced a **+4% held-out gain**
- the model explored multiple nearby edit variants in the `urgent` rule instead of literal repeats
- it consistently produced real, non-zero A/B deltas in some iterations

The weakness is that it remained trapped in the same local region of the prompt. It varied the wording of urgency constraints but did not jump to a different failure family or a different part of the prompt.

Examples of edit variants it tried:
1. add `active` to `security breach`
2. add `only if critical to business continuity`
3. add `requires immediate intervention (e.g. ...)`

So Mistral is a better analyzer than the local 4B model, but still not strong enough to find a promotable edit.

### 4.3 OpenRouter: `qwen/qwen3-30b-a3b-instruct-2507`

Observed summary:
- baseline 64%
- final 64%
- real non-zero deltas
- no promotion

Interpretation:
- stronger than the local 4B in some respects
- weaker than Mistral as analyzer
- still no path to promotion

### 4.4 OpenRouter: `meta-llama/llama-3.2-1b-instruct`

Observed summary:
- baseline 36%
- final 36%
- no proposals in practice

Interpretation:
- too weak to serve as analyzer

---

## 5. Docker Multi-Domain Validation

Docker is where v0.2.0 clearly succeeded.

### 5.1 Results

**12/12 Docker tests passed**.

| # | Test | Result | LLM Calls |
|---|------|--------|-----------|
| 1 | Docker build | PASS | 0 |
| 2 | OMLX connectivity (host) | PASS | 0 |
| 3 | OMLX model available | PASS | 0 |
| 4 | OMLX reachable from container | PASS | 0 |
| 5 | Docker help | PASS | 0 |
| 6 | Docker validate | PASS | 0 |
| 7 | Docker status | PASS | 0 |
| 8 | Classification full loop | PASS | 13 |
| 9 | Extraction full loop | PASS | 13 |
| 10 | Generation full loop | PASS | 23 |
| 11 | Staged analyzer full loop | PASS | 13 |
| 12 | Propose full | PASS | 13 |

### 5.2 What Docker proved

- image builds cleanly
- container can reach OMLX
- classification, extraction, and generation all run through the loop
- `StructuredExtractionScorer` is wired correctly
- `LLMJudgeScorer` + judge role wiring is real (generation = 23 calls)
- staged analyzer path runs mechanically inside the container
- LLM traffic is captured and persisted

This is strong evidence that the framework itself is sound.

It also removes a lot of escape hatches. After Docker passed, promotion failure could no longer be blamed on packaging, missing dependencies, or missing role plumbing. That narrowed the remaining problem to optimizer quality much more clearly.

---

## 6. Real-Trace Findings

### 6.1 The real-trace corpus audit

The real trace files were reorganized into:

- `usable/` — traces with real inputs, real outputs, and failures
- `telemetry/` — traces with placeholder / metadata-only outputs
- `labeled/` — gold corpus for analyzer-quality evaluation

### 6.2 What is actually usable?

| Bucket | Meaning | Suitable for improvement loop? |
|--------|---------|--------------------------------|
| `usable/` | real outputs, but vague expected outputs | No |
| `telemetry/` | placeholder outputs / metadata traces | No |
| `labeled/` | gold labels for analyzer-quality evaluation | No (not as loop input) |

#### Full audit of real trace usability

| File | Total | Failed | Usable failures | Why / why not |
|------|-------|--------|-----------------|---------------|
| `telemetry/agent-observatory-traces.jsonl` | 336 | 336 | 0 | Generic inputs and placeholder outputs like `43 chars produced` |
| `telemetry/evalforge-failures.jsonl` | 34 | 34 | 0 | Outputs are only `Agent X failed scenario Y` |
| `telemetry/hf-pi-coding-agent-traces.jsonl` | 200 | 72 | 0 | Failed outputs are `Completed 0 tool calls` |
| `usable/hf-open-agent-traces.jsonl` | 150 | 27 | 26 | Real customer-support inputs and full model outputs |
| `usable/hf-customer-support-traces.jsonl` | 50 | 9 | 9 | Same basic format as open-agent traces |

This gave **35 usable failed traces total**, but they are still not suitable for the improvement loop because their expected outputs are vague (`Successful customer-support-triage task`) and do not support scorer-driven A/B testing.

### 6.3 Why the real traces did not close the loop

Even the “usable” traces still do not have the structure needed for loop promotion:

- they do not have scorer-compatible expected outputs
- the runner still uses the classification promotion corpus for A/B
- the analyzer is analyzing one domain while A/B scores another

So real traces are useful for **analyzer-quality evaluation**, not for direct improvement-loop promotion in the current architecture.

This distinction matters because it prevents wasting time on invalid experiments. A real-trace run that still scores edits on the classification promotion corpus is not evidence about self-improvement on those real traces; it is just a mismatched experiment.

#### Gold corpus lesson

The gold corpus was useful to clarify this boundary. It is a labeled evaluation set with:
- `failure_cluster`
- `ideal_intervention`

That makes it appropriate for measuring whether analyzer proposals are relevant. It does **not** make it appropriate as a direct loop input.

---

## 7. The Key Bugs and Fixes That Changed the Interpretation

These were the most important field-test fixes during v0.2.0:

1. **Stage 4 fuzzy-match propagation bug**
   - corrected proposals were not propagating out of validation
   - fixed by returning `(errors, corrected_proposal)`

2. **A/B corpus wiring bug**
   - runner still used stale hardcoded task IDs
   - fixed by loading `classification-promotion.yaml` directly

3. **Rejection-context bug in staged analyzer**
   - staged prompts ignored rejection feedback entirely
   - fixed by threading `rejection_context` through Stage 1/2/3 prompts
   - this invalidated some earlier diversification conclusions

4. **Real-traces conceptual mismatch**
   - real traces were being forced through a classification A/B harness
   - documented as wrong mode for real-trace evaluation

5. **Row-safe trace handling and drift baseline fixes**
   - ensured later loop results are actually trustworthy mechanically

### 7.1 Stage 4 validation bug in detail

The staged analyzer originally failed because Stage 3 generated `old_text` from the model’s memory of the prompt rather than as a verbatim substring. That led to repeated errors like:

`Stage 4 validation failed: ['old_text not found in current prompt']`

The specific problems were:
1. `old_text` differed from the prompt by small formatting changes
2. fuzzy matching only checked same-length line windows
3. corrected matches were rebuilt only locally and not propagated back to the caller
4. the threshold was too strict for structured prompt text

The fixes were:
1. `stage4_validate()` now returns `(errors, corrected_proposal)`
2. fuzzy matching now uses multiple strategies
3. corrected proposals flow through to A/B and gate
4. Stage 3 now sees the raw prompt, not only the annotated prompt

This is why the later runs are trustworthy and the early runs are not.

### 7.2 Rejection-context bug in detail

The staged analyzer originally ignored `rejection_context` entirely because the context never reached:
- `STAGE1_SUMMARIZE_PROMPT`
- `STAGE2_SELECT_PROMPT`
- `STAGE3_SYNTHESIZE_PROMPT`

So earlier conclusions like “the model repeats the same proposal even after rejection” were partly stale. After the fix, later runs showed small behavioral differences across iterations, which means the rejection-context wiring did have some effect. It just was not enough to create a strong optimizer.

GitHub issue: `#205`

These fixes matter because they shift the conclusion from “the system might be broken” to “the system works, but the analyzer still fails to find strong edits.”

---

## 8. Model Conclusions

### 8.1 Instruction models are the right class

Instruction-tuned models are the fastest practical choice for this workflow.

### 8.2 Executor vs analyzer

The evidence strongly suggests these should not be treated as the same role:

- **executor:** small instruct model is fine
- **analyzer:** likely needs a stronger model and/or stronger search loop
- **judge:** can be stronger still for generation

This is one of the clearest structural learnings from v0.2.0: the same model does not need to be optimal for all three roles. Fast executor and stronger analyzer is now a justified direction, even though it still needs a proper comparative runner path.

### 8.2.1 What this means operationally

For v0.2.0, the practical model conclusions are:

- **Executor / mechanical validation:** local 4B instruct is the best speed/cost choice
- **Analyzer experiments:** Mistral Small 24B Instruct is the strongest tested candidate
- **Very small models (1B):** not useful as analyzers

This is the first version where the role-separation idea is actually supported by evidence, even though the runner still uses a single model per run.

### 8.3 Best current choices

- best local executor / mechanical validation model: `Qwen3-4B-Instruct-2507-4bit`
- best analyzer candidate tested: `mistralai/mistral-small-3.2-24b-instruct`

But neither produced a promotable edit.

So model choice matters, but model choice alone did not solve the optimization problem.

---

## 9. Expectations vs Results

| Expectation | Result |
|-------------|--------|
| Loop runs end-to-end | ✅ confirmed |
| Multi-domain support works | ✅ confirmed |
| Docker validation works | ✅ confirmed |
| Model-role plumbing works | ✅ confirmed |
| Rejection feedback improves analyzer search | ⚠️ partially improved, still weak |
| Some model produces a promotable edit | ❌ not confirmed |
| Real traces drive the loop directly | ❌ not in current architecture |

---

## 10. Final Conclusion

v0.2.0 succeeds as a **framework release**.

It proves that AgentSelfEdit can:

- ingest failures
- propose prompt edits
- run statistically grounded A/B tests
- apply deterministic safety gates
- reject weak edits correctly
- operate across classification, extraction, and generation in Docker
- support model roles and judge wiring

It does **not** prove successful prompt self-improvement to the point of promotion.

The strongest honest claim is:

> AgentSelfEdit v0.2.0 demonstrates a safe, reproducible prompt-optimization framework. It can generate edits, evaluate them with real A/B tests, and reject them correctly when they are weak or statistically insufficient. It does not yet demonstrate reliable successful self-improvement.

The honest conclusion is:

- **framework proved**
- **safety proved**
- **search / optimizer still too weak**

That is enough to close M8 honestly.

It is also the right project conclusion. Calling v0.2.0 a self-improvement success would overstate the evidence. Calling it a failure of the whole system would understate what was actually proven. The right conclusion is a working framework with an underperforming optimizer.

---

## 11. Recommended Follow-Up

1. Build a dedicated **real-trace analyzer-quality** path
2. Improve optimizer search quality:
   - generate multiple candidate edits
   - score them cheaply on the failure batch
   - A/B only the best candidate
3. Run true role-separated experiments with a stronger analyzer path
4. If needed, widen or redesign the promotion corpus so a good edit can move enough tasks to become promotable

---

## Appendix A: Historical Debugging Record That Changed Interpretation

This appendix preserves the key detailed learnings from the session log so `learnings.md` is no longer required as a source of truth.

### A.1 Early synthetic run (superseded)

Before the later fixes, an early 10-iteration synthetic run with `Qwen3-4B-Instruct-2507-4bit` produced:

| Metric | Value |
|--------|-------|
| Baseline accuracy | 60.0% (15/25) |
| Final accuracy | 60.0% (15/25) |
| Improvement | 0.0% |
| Total LLM calls | 565 |
| Total duration | ~7.5 minutes |

At that point:
- iteration 1 reached the full pipeline
- iterations 2-10 failed at Stage 4 validation with `old_text not found in current prompt`

This run is **superseded** and should not be used for the final conclusion, but it was critical for exposing the Stage 4 bug.

### A.2 Stage 4 validation bug details

The staged analyzer originally failed because Stage 3 generated `old_text` from model memory rather than copying exact prompt text.

Four specific problems were identified:

1. The model generated `old_text` that was not an exact substring of the prompt
2. The fuzzy fallback only compared same-length line windows
3. The corrected proposal was rebuilt only locally and not propagated to the caller
4. The threshold was too strict for structured prompt text

Applied fixes:

1. `stage4_validate()` now returns `(errors, corrected_proposal)`
2. `_fuzzy_fix_old_text()` uses multiple matching strategies
3. threshold lowered to `0.80`
4. `analyze()` uses the corrected proposal
5. Stage 3 prompt now includes the raw prompt and explicit verbatim-copy instructions

### A.3 Empty A/B task set bug

After the Stage 4 fix, the next synthetic run still produced unusable A/B results:

- `n_trials = 0`
- `results-a.json = []`
- `results-b.json = []`

Root cause:
- the runner was still filtering tasks using stale v0.1.0 task IDs
- the split corpus introduced new IDs like `classify-single-*`, `classify-multi-*`, `classify-ambig-*`

Applied fix:
- removed the hardcoded filter
- loaded `classification-promotion.yaml` directly as the A/B corpus

### A.4 Runner script issues found and fixed

The runner script itself introduced several interpretation bugs:

| Issue | Status | Impact |
|-------|--------|--------|
| Rejection context never populated | Fixed | Analyzer now receives feedback from prior rejections |
| Trace acknowledgement still using task_id | Fixed | Row-safe ack prevents data loss |
| Drift baseline using current instead of original | Fixed | Drift now measures against original v1 prompt |
| A/B task set empty due to stale hardcoded IDs | Fixed | Uses 40-task promotion corpus |
| Scorer mixed-hints error in runner | Fixed | `allow_mixed=True` for runner scorer resolution |
| Results overwriting across modes | Fixed | corpus label added into result path |
| Error handler writing into missing iteration dir | Fixed | ensure dir exists before `error.txt` write |

### A.5 Real-traces mode was conceptually wrong

`--real-traces` originally only changed the seed source, but still reused:
- classification held-out accuracy
- classification promotion corpus

That made real-trace runs conceptually invalid for loop-improvement claims.

Correct interpretation:
- real traces are useful for analyzer-quality evaluation
- real traces are **not** valid direct inputs to the current improvement loop

### A.6 Gold corpus lesson

The gold corpus was created as a labeled evaluation set with:
- `failure_cluster`
- `ideal_intervention`

It should be used to evaluate whether the analyzer proposes relevant interventions, not to drive the A/B loop.

### A.7 Real trace usability audit

All real trace files were audited:

| File | Total | Failed | Usable failures | Notes |
|------|-------|--------|-----------------|-------|
| `telemetry/agent-observatory-traces.jsonl` | 336 | 336 | 0 | outputs are placeholder telemetry (`43 chars produced`) |
| `telemetry/evalforge-failures.jsonl` | 34 | 34 | 0 | outputs are generic scenario-failure summaries |
| `telemetry/hf-pi-coding-agent-traces.jsonl` | 200 | 72 | 0 | failed outputs are `Completed 0 tool calls` |
| `usable/hf-open-agent-traces.jsonl` | 150 | 27 | 26 | real inputs and outputs, but vague expected outputs |
| `usable/hf-customer-support-traces.jsonl` | 50 | 9 | 9 | same as above |

This produced **35 usable failed traces**, but they are only usable for analyzer-quality evaluation, not for A/B promotion scoring.

### A.8 Post-fix local 4B rerun

After the key runner and staged-analyzer fixes, a clean 5-iteration synthetic rerun with `Qwen3-4B-Instruct-2507-4bit` produced:

| Metric | Value |
|--------|-------|
| Baseline | 60.0% |
| Final | 60.0% |
| Improvement | 0.0% |
| Iterations | 5 |

Per-iteration A/B results varied:
- `p = 0.73, 0.71, 0.46, 0.67, 1.0`
- `mean_delta = -0.05, -0.025, +0.025, -0.025, 0.0`

This showed the rejection-context fix did affect the run mechanics, but still did not produce improvement.

### A.9 Post-fix cloud rerun: Mistral 24B

The cloud rerun with `mistralai/mistral-small-3.2-24b-instruct` produced:

| Metric | Value |
|--------|-------|
| Baseline | 64.0% |
| Final | 64.0% |
| Improvement | 0.0% |
| Iterations | 5 |

Per-iteration results:
- Iter 1: `p=0.55`, `mean_delta=+0.025`
- Iter 2: `p=0.52`, `mean_delta=+0.025`
- Iter 3: `p=1.0`, `mean_delta=0.0`
- Iter 4: `p=0.52`, `mean_delta=+0.025`
- Iter 5: `p=0.77`, `mean_delta=-0.025`

This model explored nearby variants better than the local 4B model, but still stayed trapped in a weak local search region.

### A.10 Why v0.2.0 still looks stuck after v0.1.0

v0.1.0 left an ambiguous picture because it mixed:
- real bugs
- weak task sets
- fabricated or low-value traces
- analyzer repetition

v0.2.0 removed many confounders, so the remaining flat result is more informative.

The current answer is no longer:
- “is the system broken?”

It is now:
- “the system works; why is the analyzer still not finding strong edits?”

That is the main value of v0.2.0.
