# Final Field Test Report — AgentSelfEdit v0.3.0

> **BLUF:** v0.3.0 proves the self-edit framework is mechanically sound, safety-gated, multi-domain validated in Docker, and now honest enough to distinguish framework correctness from optimizer weakness. The local 4B analyzer still fails to produce promotable edits. A stronger cloud analyzer, `mistralai/mistral-small-3.2-24b-instruct`, produces weak positive movement, but still not enough to clear the promotion gate. The main unresolved problem is now a combination of analyzer search quality and gate sensitivity to small improvements, not broken execution.

**Date:** 2026-09-03  
**Primary local execution model:** `Qwen3-4B-Instruct-2507-4bit`  
**Best analyzer candidate tested:** `mistralai/mistral-small-3.2-24b-instruct`  
**Synthetic iterations completed:** 5 local + 8 cloud  
**Promotion corpus:** `classification-promotion.yaml` (40 tasks)  
**Held-out corpus:** `classification-held-out.yaml` (25 tasks)  
**Sentinel corpus:** `sentinel.yaml` (20 tasks)  
**Gate config:** confidence_level=0.95 (alpha=0.05), min_effect_size=5%, drift_threshold=0.3  
**Hermetic suite:** 807 tests passing  
**Docker suite:** 16/16 passing

---

## 1. Executive Summary

v0.2.0 established that the framework was probably sound but left two questions unresolved:

- was the loop still being distorted by hidden execution bugs?
- or was the optimizer simply too weak to find edits that the gate could trust?

v0.3.0 answers both more clearly.

What v0.3.0 proved:

1. **The framework is mechanically correct end-to-end.**
2. **The promotion gate is functioning as designed and remains the strongest safety component.**
3. **Docker multi-domain validation now covers the complete planned surface area.**
4. **The local 4B model is usable for executor/baseline work, but too weak as an analyzer.**
5. **A stronger analyzer model produces real positive signal, but still not enough to promote.**
6. **The unresolved problem is now narrower and more informative: local search quality plus statistical power.**

That means the central unresolved problem is no longer “is the system broken?” It is now: **can the analyzer find edits with enough breadth and magnitude to satisfy a statistically conservative gate?**

That distinction matters because v0.2.0 still had enough ambiguity that a 0% improvement run could be dismissed as a pipeline artifact. In v0.3.0, that defense is no longer available. The loop now produces structured artifacts, per-iteration prompt candidates, paired A/B outputs, gate reasons, Docker integration evidence, and corpus-backed regression checks. When the optimizer fails in v0.3.0, it fails in public and with receipts.

The evidence base for that claim is broad:

- **mechanical correctness**: 807 non-Docker tests pass, including direct `_run_once` coverage, rollback, guardrails, rejection-aware behavior, seeded-prompts validation, and role-routing tests
- **integration correctness**: 16/16 Docker tests pass, covering classification, extraction, generation, staged analyzer, mixed-domain, adversarial, A/B cache, and materialize guard
- **corpus maturity**: mixed-domain expanded to 100 tasks, gold corpus operationalized at 30 traces, seeded prompts validated at 15 prompts, sentinel stabilized at 20 tasks
- **field execution evidence**: the local 4B run and cloud Mistral run both produced complete iteration artifacts and interpretable gate failures

So the correct high-level reading of v0.3.0 is not “self-improvement still failed.” It is:

- the framework is now strong enough to falsify weak optimizer behavior cleanly
- the analyzer is the active bottleneck
- once analyzer quality improves, confidence sensitivity becomes the next bottleneck

### 1.1 Evidence snapshot

| Area | Evidence | What it means |
|------|----------|---------------|
| Unit/hermetic correctness | `807` tests passing | Core behavior is stable and regression-tested |
| Coverage | `94.86%` | Most relevant paths are exercised |
| Static quality | `ruff` clean, `mypy --strict` clean | Low implementation ambiguity |
| Docker integration | `16/16` pass | End-to-end CLI + container behavior is proven |
| Local synthetic run | `60% -> 60%` | Weak analyzer, null edits |
| Cloud synthetic run | `64% -> 68%` reported, `0` promotions | Better analyzer, but still below promotion bar |
| Adversarial gate run | `8/8` blocked | Safety gate rejects bad edits |
| Sentinel run | regression detected | Regression defenses are operational |

---

## 2. What Changed From v0.2.0 to v0.3.0

### 2.1 Major correctness and observability improvements

v0.3.0 completed the remaining M10–M12 foundation work that makes field-test results interpretable:

- `materialize_candidate_prompt()` replaced raw `str.replace()` and loudly rejects missing `old_text`
- `PromotionGate.check()` is now wired into the real `propose` path
- drift is measured against the original prompt, not the current prompt
- Oracle Drift Guard was implemented and wired into gate order
- mixed-domain corpus expanded from 30 to 100 tasks
- adversarial edit corpus is operational and tested end-to-end
- rollback was validated using a real promoted version with lineage metadata
- seeded-prompts corpus is now loadable and validated
- gold real-trace corpus is now operationalized at `labeled/gold-corpus.jsonl`
- Docker tests expanded from 12 to 16 and now cover mixed-domain, adversarial, A/B cache, and materialize guard
- field-test runner and docs were moved fully to `v0.3.0` result paths

### 2.2 What this means

v0.3.0 strengthens the system in three important ways:

- it removes the major ambiguity around hidden execution faults
- it makes the optimizer’s failure mode visible at proposal and per-task levels
- it makes multi-model comparison more trustworthy

The loop can now fail honestly, with inspectable reasons.

More concretely, v0.3.0 changes the epistemic status of the project.

Before these fixes, a failed run could mean any of the following:

- the edit never actually changed the candidate prompt
- the gate was bypassed
- the current prompt was stale
- the scorer was mismatched to the task type
- the analyzer prompt pipeline silently collapsed into a no-op

After these fixes, the failure surface is much smaller. A failed run now usually means one of three things:

1. the analyzer found a weak edit
2. the analyzer found a small but statistically underpowered edit
3. the analyzer remained trapped in a low-diversity local search neighborhood

That is an enormous improvement in reportability even if the optimizer still does not succeed.

### 2.3 Artifact paths that matter

The key evidence now lives in stable, inspectable locations:

| Artifact class | Path |
|----------------|------|
| Docker execution results | `field-test/v0.3.0/results/docker/omlx/qwen3-4b-instruct-2507-4bit/` |
| Local synthetic loop | `field-test/v0.3.0/results/omlx/qwen3-4b-instruct-2507-4bit/` |
| Cloud synthetic loop | `field-test/v0.3.0/results/openai/mistralai-mistral-small-3.2-24b-instruct/` |
| Gold corpus analyzer sample | `field-test/v0.3.0/results/gold-corpus-analyzer.json` |
| Detailed Docker report | `docs/field-test/v0.3.0/docker-test-run-report.md` |
| Learnings log | `docs/field-test/v0.3.0/learnings.md` |

---

## 3. Guardrail Effectiveness

### 3.1 The gate is still the real product

The promotion gate remains the clearest success in the project. Across hermetic tests, Docker tests, and synthetic improvement runs, it rejected every edit that lacked strong evidence.

### 3.2 False positives: 0%

A false positive would mean promoting a weak or harmful edit. That did not happen.

This result is stronger in v0.3.0 than it was in v0.2.0 because:

- candidate prompts were actually materialized correctly
- A/B tests actually ran on the 40-task promotion corpus
- the full gate actually ran in the real propose path
- adversarial edits were explicitly injected and blocked

So the 0% false-positive outcome is evidence of safety, not just absence of success.

There is concrete supporting evidence for this claim across three layers:

1. **Hermetic adversarial coverage**
   - `test_adversarial_edits_all_blocked()` validates 8/8 intentionally bad edits are blocked
   - false negatives observed there: `0`
2. **Docker adversarial coverage**
   - `test_docker_run_adversarial` passed in the real OMLX integration suite
   - proposals were generated, evaluated, and still rejected under live model execution
3. **Synthetic improvement loops**
   - both local and cloud multi-iteration runs repeatedly generated plausible edits
   - none were promoted without meeting statistical and practical gain thresholds

This is the correct product posture for an optimization framework: conservative promotion, verbose rejection, and inspectable reasons.

### 3.3 False negatives: not proven, but now more plausible

The local 4B run did not generate any serious evidence of false negatives because most candidates had zero or cancelling task movement.

The Mistral cloud run changed that slightly:

- iteration 3 produced `2` improvements and `0` regressions
- it reached `effect_size = 0.0625`
- but still failed `confidence` with `p = 0.79`

That does not prove the gate rejected a truly promotable edit. It does show that once proposal quality improves, **gate sensitivity / statistical power becomes a serious practical question**.

### 3.4 The 7 checks in practice

| Check | What it tests | v0.3.0 observed behavior |
|-------|---------------|--------------------------|
| sample_floor | enough trials | PASS (`n=40`) |
| effect_size | minimum practical gain | FAIL on most local and many cloud iterations |
| confidence | p < 0.05 | FAIL on every tested edit |
| frozen_sections | protected prompt content preserved | PASS |
| edit_distance | edit not too large | PASS |
| drift | edit not too far from baseline | PASS |
| oracle_drift | shared wrong success definition | PASS in normal runs; unit-tested for failures |

In real synthetic improvement runs:

- the local 4B model most often failed at **effect_size**
- the cloud Mistral run sometimes cleared **effect_size** and then failed at **confidence**

### 3.5 What promotion would require

For a promotion, an edit must move enough tasks in the 40-task promotion corpus to satisfy both:

- effect size >= 5%
- p-value < 0.05

The current analyzers are still generating edits that are:

- too narrow in scope
- too localized to one rule family
- too weak to reliably move enough tasks

That means the gate is doing exactly what it was built to do: reject weak evidence.

It is also worth being explicit about what the current evidence does **not** show.

The results do not prove that the gate is too strict in a general sense. They show a narrower fact:

- local 4B proposals are mostly null and deserve rejection
- stronger cloud proposals sometimes show weak positive signal
- that weak signal is still insufficient to cross a conservative confidence threshold on a 40-task promotion set

So the next research question is not “remove the gate.” It is “what size of proposal improvement is realistically achievable, and is the current promotion set calibrated for that scale?”

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
| Total runtime | 305s |

Per-iteration results:

| Iter | Winner | p-value | n | Mean delta | Accuracy | Gate |
|------|--------|---------|---|------------|----------|------|
| 1 | tie | 1.0 | 40 | 0.0 | 60% | near_miss |
| 2 | tie | 1.0 | 40 | 0.0 | 60% | near_miss |
| 3 | inconclusive | 1.0 | 40 | 0.0 | 60% | near_miss |
| 4 | tie | 1.0 | 40 | 0.0 | 60% | near_miss |
| 5 | inconclusive | 1.0 | 40 | 0.0 | 60% | near_miss |

Interpretation:

- the loop runs correctly
- candidate prompts are generated and evaluated
- the gate honestly rejects them
- but the model cannot generate a strong enough edit to change the held-out set or the promotion set in a meaningful way

The local run is best understood as a mechanical validation run with optimizer failure, not as a failed experiment in the same sense as v0.2.0. In v0.2.0, a 0% result still had to be discounted against possible framework bugs. In v0.3.0, this local run is informative precisely because the framework is no longer the most likely culprit.

#### What this model actually failed on

Per-task delta analysis shows the local 4B analyzer was even weaker than a flat 0% summary implies:

- iteration 1: `0` improved, `0` regressed, `40` unchanged
- iteration 2: `0` improved, `0` regressed, `40` unchanged
- iteration 3: `1` improved, `1` regressed, `38` unchanged
- iteration 4: `0` improved, `0` regressed, `40` unchanged
- iteration 5: `1` improved, `1` regressed, `38` unchanged

The strongest evidence is that iterations 3 and 5 moved the same two tasks in opposite directions:

- `promote-040` improved: `The database migration script is corrupting data in the users table.` → expected `urgent`
- `promote-026` regressed: `The SQL query timeout is affecting our reporting dashboard.` → expected `technical`

So the local run is **not** a case where a good edit was hidden by averaging. In most iterations the edit changed nothing; in the remaining iterations it produced a perfect cancel.

This is one of the strongest pieces of evidence in the entire report. It means the local analyzer is not being unfairly punished by the gate. In most iterations, the proposal literally does not move the promotion corpus. That is optimizer weakness, not statistical bad luck.

#### Why the 4B model failed as analyzer

The local 4B analyzer quickly converged on one local intervention family:

- rewrites of the `urgent` rule
- slightly more explicit operational-impact wording
- urgency-boundary examples

That means:

- rejection-aware plumbing exists
- but the model does not use that feedback to diversify proposal search

The local 4B model is useful to validate mechanics, but not sufficient to prove successful self-editing.

There is also a practical product learning here: the local 4B model may still be perfectly adequate for:

- cheap executor runs
- held-out measurement
- Docker integration validation
- low-cost smoke testing

Its weakness is specifically in analyzer search quality under repeated self-editing pressure.

### 4.2 OpenRouter: `mistralai/mistral-small-3.2-24b-instruct`

| Metric | Value |
|--------|-------|
| Baseline | 64.0% |
| Final (reported) | 68.0% |
| Improvement (reported) | +4.0% |
| Iterations | 8 |
| Promotions | 0 |

Per-iteration results:

| Iter | Winner | p-value | n | Mean delta | Effect size | Accuracy | Gate |
|------|--------|---------|---|------------|-------------|----------|------|
| 1 | inconclusive | 1.0 | 40 | +0.025 | 0.0303 | 64% | near_miss |
| 2 | inconclusive | 1.0 | 40 | +0.025 | 0.0303 | 64% | near_miss |
| 3 | inconclusive | 0.79 | 40 | +0.05 | 0.0625 | 64% | near_miss |
| 4 | tie | 1.0 | 40 | 0.0 | 0.0 | 64% | near_miss |
| 5 | tie | 1.0 | 40 | 0.0 | 0.0 | 64% | near_miss |
| 6 | inconclusive | 1.0 | 40 | +0.025 | 0.0303 | 64% | near_miss |
| 7 | inconclusive | 1.0 | 40 | +0.025 | 0.0303 | 64% | near_miss |
| 8 | inconclusive | 1.0 | 40 | 0.0 | 0.0 | 68% | near_miss |

Interpretation:

- this is a materially stronger analyzer candidate than the local 4B model
- it produced small real positive movement on the promotion corpus
- but it still did not produce a promotable edit

This is the most important model-comparison result in v0.3.0. The stronger analyzer is not just “different”; it is measurably better in the only way that matters here: it creates non-zero forward motion on the promotion corpus. That makes this run qualitatively different from the local null-edit run.

#### Why this model is the best analyzer candidate so far

Compared to the local 4B run, Mistral did improve proposal quality:

- iteration 1: `1` improved, `0` regressed
- iteration 2: `1` improved, `0` regressed
- iteration 3: `2` improved, `0` regressed
- iteration 6: `1` improved, `0` regressed
- iteration 7: `1` improved, `0` regressed

That is the first time the system produced sustained **positive** movement instead of null or cancelling edits.

#### Why it still failed

The strongest candidate was iteration 3:

- `2` improved
- `0` regressed
- `mean_delta = 0.05`
- `effect_size = 0.0625`

That cleared the 5% effect-size bar, but failed confidence:

- `p = 0.79`

So the cloud run reveals something new:

- analyzer quality is better
- local search is still too narrow
- once proposal quality improves, the next bottleneck becomes statistical power / confidence sensitivity

That last point is especially important. The cloud run is the first place where it becomes intellectually honest to ask whether the gate is underpowered for the size of improvements analyzers can presently achieve. That question was premature in the local run, because the local run mostly had no signal at all.

#### What stayed weak

Proposal diversity remained poor:

- nearly every proposal targeted `Rules`
- nearly every proposal rewrote the same `urgent` rule boundary
- the dominant variant was `security breach` → `active security breach`

So Mistral is stronger, but still trapped in the same narrow edit neighborhood.

### 4.3 What both runs together prove

The local 4B and cloud Mistral runs together are more informative than either alone.

| Dimension | Local OMLX 4B | Cloud Mistral 24B |
|-----------|----------------|-------------------|
| Baseline held-out | 60.0% | 64.0% |
| Positive task movement | mostly none | repeated small wins |
| Best effect size | 0.0 | 0.0625 |
| Promotions | 0 | 0 |
| Proposal diversity | low | still low |
| Main blocker | no signal | weak signal + confidence failure |

This means:

- analyzer capability matters
- the loop is no longer blocked by correctness bugs
- stronger analyzers help, but not enough yet
- the next question is whether the gate can trust the size of improvements these analyzers realistically produce

This is exactly the kind of narrowing a good field test should produce. The result is not success, but it is highly actionable failure.

### 4.4 Evidence-backed interpretation of the two-model comparison

There are now three distinct states the project has moved through:

| Stage | What a 0% result meant |
|-------|------------------------|
| v0.1.0 | potentially broken system, unclear evidence |
| v0.2.0 | system probably works, but optimizer failure still partly confounded |
| v0.3.0 local 4B | healthy loop, weak analyzer, mostly null edits |
| v0.3.0 cloud Mistral | healthy loop, stronger analyzer, weak positive signal, still below promotion bar |

That progression is meaningful. It shows the project is moving from ambiguity to diagnosis, even though it has not yet reached successful self-improvement.

### 4.5 Per-model artifact evidence

| Model | Artifact root | Iterations | Proposals / iter | Promotions | Strongest iteration | Traffic log |
|-------|---------------|------------|------------------|------------|---------------------|-------------|
| `Qwen3-4B-Instruct-2507-4bit` | `field-test/v0.3.0/results/omlx/qwen3-4b-instruct-2507-4bit/` | 5 | 1 | 0 | iter 3/5 (`1` up, `1` down) | `llm-traffic.jsonl` |
| `mistralai/mistral-small-3.2-24b-instruct` | `field-test/v0.3.0/results/openai/mistralai-mistral-small-3.2-24b-instruct/` | 8 | 1 | 0 | iter 3 (`2` up, `0` down) | `llm-traffic.jsonl` |

### 4.6 Proposal-family breakdown

Across both synthetic runs, proposals concentrated in a very small number of edit families.

| Proposal family | Local 4B | Cloud Mistral | Evidence |
|-----------------|----------|---------------|----------|
| Urgency-rule tightening | dominant | dominant | repeated rewrites of `urgent: immediate action ...` |
| Billing disambiguation | seen once | not significant | local iteration 1 full Rules rewrite |
| Explicit urgency cues / examples | repeated | repeated | `active security breach`, `critical data loss`, `explicit urgency cues` |
| Structural prompt changes | not observed | not observed | no role, format, or output-schema edits |
| Multi-family exploration | absent | absent | all proposals remained in same prompt neighborhood |

This is strong evidence that the search problem is not “the analyzer never proposes anything.” The problem is that it proposes almost the same kind of thing over and over.

### 4.7 Held-out metric interpretation

Held-out accuracy in these runs needs careful interpretation.

#### What held-out *does* tell us

- whether the currently active prompt changed in a way that affected the held-out set
- whether a promoted edit improved deployed behavior

#### What held-out *does not* tell us by itself

- whether an unpromoted candidate had localized wins on the promotion corpus
- whether a candidate edit was directionally promising but statistically underpowered

Evidence:

- in both model runs, `prompt-after.md` matched `prompt-a.md` in every iteration
- no prompt was promoted in either run
- therefore held-out should be read as a deployment metric, not a candidate-quality metric

This is why the Mistral run's reported `68.0%` final held-out value must be interpreted with caution: it is a measurement artifact in a no-promotion run, not evidence that the deployed prompt improved.

### 4.8 Statistical power and gate sensitivity

This becomes a first-class issue only after the analyzer starts producing real positive movement.

#### What the local run shows

- mostly `0/40` tasks moved
- sometimes `1` up and `1` down
- no meaningful positive signal

Interpretation:

- statistical power is not the main story in the local run
- the proposals themselves are too weak

#### What the Mistral run shows

- repeated `+1/40` improvements
- one `+2/40, 0/40 down` iteration
- `effect_size = 0.0625` at the strongest point
- still `p = 0.79`

Interpretation:

- this is the first run where it becomes reasonable to ask whether the gate is too insensitive to micro-improvements
- the gate may still be correct, but the field-test now has enough evidence to treat statistical power as an open design question rather than a speculative complaint

This is a major improvement in diagnostic quality over v0.2.0.

### 4.9 False-negative interpretation by model

| Model | Evidence for false-negative concern? | Why |
|-------|-------------------------------------|-----|
| Local OMLX 4B | weak / no | mostly zero movement; gate is not suppressing real gains |
| Cloud Mistral 24B | partial | iteration 3 cleared effect-size threshold but failed confidence |

The correct conclusion is not “the gate is too strict.” It is narrower:

- local 4B gives no credible evidence of a promotable edit
- cloud Mistral gives the first evidence of a weak positive candidate that may be statistically underpowered

---

## 5. Docker Multi-Domain Validation

Docker is where v0.3.0 clearly succeeded.

### 5.1 Results

**16/16 Docker tests passed**.

| # | Test | Result | LLM Calls |
|---|------|--------|-----------|
| 1 | Docker build | PASS | 0 |
| 2 | OMLX connectivity (host) | PASS | 0 |
| 3 | OMLX model available | PASS | 0 |
| 4 | OMLX reachable from container | PASS | 0 |
| 5 | Docker help | PASS | 0 |
| 6 | Docker validate | PASS | 0 |
| 7 | Docker status | PASS | 0 |
| 8 | Docker classification full loop | PASS | 13 |
| 9 | Docker extraction full loop | PASS | 13 |
| 10 | Docker generation full loop | PASS | 23 |
| 11 | Docker staged analyzer | PASS | 13 |
| 12 | Docker mixed-domain full loop | PASS | 13 |
| 13 | Docker adversarial | PASS | 13 |
| 14 | Docker propose full | PASS | 13 |
| 15 | Docker A/B cache | PASS | 13 |
| 16 | Docker materialize guard | PASS | 13 |

### 5.2 What Docker proved

Docker validation now covers the complete planned v0.3.0 integration surface:

- classification full loop
- extraction full loop
- generation full loop with judge role
- staged analyzer path
- mixed-domain corpus path
- adversarial gate path
- A/B cache behavior
- materialize guard behavior

This is important because it means the mechanical claims in the synthetic runs are backed by real integration execution in containerized conditions.

It also matters for another reason: Docker validation reduces the chance that the optimizer results are an artifact of a special local harness. The same framework behavior now survives:

- real container startup
- real config loading
- real model connectivity
- real analyzer + A/B + gate execution
- real LLM traffic capture

That does not prove the optimizer is good. It proves the optimizer is being judged in a realistic environment.

### 5.3 Cost and observability

Docker runs captured:

- 127 LLM calls
- 49,495 tokens
- full traffic logs for each integration path
- structured JSON reports for each test

Concrete evidence from the Docker run report:

- classification loop: 13 LLM calls
- extraction loop: 13 LLM calls
- generation loop: 23 LLM calls due to judge-role scoring
- mixed-domain loop: 13 LLM calls over 100-task corpus sampling
- total suite wall-clock: 4m09s with `-n 4`
- total suite cost equivalent: about `$0.06`

This is enough evidence to say the Docker suite is no longer a smoke test. It is a meaningful integration harness.

That level of observability is enough to support detailed diagnosis even when the optimizer does not succeed.

---

## 6. M11 Foundations Summary

v0.3.0 fully completed the M11 field-test foundations:

- Oracle Drift Guard implemented and tested
- mixed-domain corpus expanded to 100 tasks
- sentinel regression benchmark validated end-to-end
- adversarial edit injection validated end-to-end
- rollback tested with a real promoted version
- hermetic CI suite completed and passing
- coverage measured at 94.86%
- ruff and mypy confirmed clean

These foundations matter because they make the M12 optimizer results trustworthy.

Without M11, the M12 model-comparison conclusions would not be credible. With M11 complete, the M12 failures can now be interpreted as honest optimizer limitations instead of probable system bugs.

---

## 7. Corpora and Evaluation Assets

### 7.1 Synthetic corpora

| Corpus | Size |
|--------|------|
| classification-single-label | 20 |
| classification-multi-label | 5 |
| classification-ambiguous | 5 |
| classification-boundary | 20 |
| classification-promotion | 40 |
| classification-held-out | 25 |
| sentinel | 20 |
| extraction | 25 |
| generation | 25 |
| mixed-domain | 100 |

### 7.2 Other assets

| Asset | Size | Purpose |
|-------|------|---------|
| seeded-prompts | 15 | known-failure prompt evaluation |
| adversarial-edits | 8 | intentionally bad edits for gate validation |
| gold-corpus | 30 | real-trace analyzer quality evaluation |
| usable real traces | 200 | real trace replay / analyzer input |

All required v0.3.0 corpora now exist and validate.

That closes another ambiguity from prior versions. Corpus incompleteness is no longer a plausible explanation for why the current classification runs fail to promote edits.

---

## 8. Gold Corpus Analyzer Evaluation

The gold corpus is now operationalized at:

- `field-test/corpus/real-traces/labeled/gold-corpus.jsonl`

Corpus properties:

| Property | Value |
|----------|-------|
| Traces | 30 |
| Failure clusters | 7 |
| Ideal interventions | 7 |
| Validation | `test_gold_corpus_loads` |

Observed evaluation status:

- a sample analyzer run over the gold corpus produced very sparse useful output with the local 4B analyzer
- results were saved to `field-test/v0.3.0/results/gold-corpus-analyzer.json`
- this is consistent with the broader finding that the local 4B model is too weak as an analyzer

What this proves:

- the gold corpus is structurally usable
- the analyzer can be pointed at it
- but strong analyzer-quality measurement will require a stronger model or a fuller evaluation pass

This is still meaningful progress relative to earlier versions, where the corpus existed conceptually but was not operational in the testing workflow.

---

## 9. Key Learnings

### 9.1 What is solved

- The loop is mechanically sound.
- The gate is real and effective.
- The Docker integration surface is fully covered.
- Results are inspectable enough to diagnose optimizer weakness precisely.

### 9.2 What is not solved

- No analyzer has yet found a promotable edit.
- Proposal diversity remains poor.
- The search neighborhood is too local.
- Once proposal quality improves, confidence / power becomes the next bottleneck.

### 9.3 The most important current interpretation

v0.3.0 is no longer a story about hidden system bugs. It is a story about an honest optimizer ceiling:

- weak analyzers produce null edits
- stronger analyzers produce weak positive signal
- neither yet produces an edit strong enough for promotion

That is a much healthier place for the project to be.

It is also a better place to make design decisions from. The project no longer needs broad “fix everything” motions. The next changes can be sharply targeted at:

- analyzer model strength
- analyzer search diversity
- promotion-set calibration
- confidence / power reporting

### 9.4 Cross-run inference: the system now fails honestly

Across all executed runs, the strongest shared learning is not that the optimizer failed. It is that the optimizer now fails in a way that can be trusted and explained.

Evidence across run families:

- hermetic suite: 807 tests pass, including rollback, adversarial, rejection-aware, seeded-prompts, and role-routing coverage
- Docker suite: 16/16 pass, including classification, extraction, generation, staged analyzer, mixed-domain, adversarial, A/B cache, and materialize guard
- local 4B synthetic run: complete artifacts, stable gate behavior, no hidden execution anomaly
- cloud Mistral synthetic run: complete artifacts, small positive signal appears, still no promotion
- cheap-smoke runs: same broad failure pattern appears in extraction, generation, and mixed-domain

That combination means we have crossed an important threshold as a project. The framework is no longer the dominant source of uncertainty. The optimizer is.

### 9.5 Cross-run inference: analyzer weakness generalizes across domains

The classification runs could have been dismissed as a domain-specific problem. The cheap-smoke runs make that explanation much less plausible.

Cross-domain evidence:

- classification: repeated urgency-rule tightening, mostly null or cancelling edits
- extraction: repeated field-name / formatting clarifications, mostly tiny gains or regressions
- generation: repeated format-adherence tightening, often actively harmful
- mixed-domain: repeated high-level formatting/conciseness advice, only one late small positive pocket

This is a consistent behavioral signature, not random noise:

- the analyzer sees plausible failure patterns
- it responds with local wording adjustments
- it rarely changes prompt structure, examples, or broader task decomposition
- it does not escape the same narrow edit neighborhood

That means the current optimizer limitation is not tied to one corpus. It is a cross-domain search problem.

### 9.6 Cross-run inference: generation is the most regression-prone corpus

Generation behaved differently from classification and extraction in an important way.

Evidence:

- generation iteration 1: `1` task improved, `7` regressed
- generation iteration 3: `1` task improved, `2` regressed
- both generation proposals focused on stricter format adherence and avoiding generic content

Interpretation:

- generation tasks are more sensitive to over-constraining edits
- a prompt change that sounds directionally correct can still reduce quality on most tasks
- this makes generation the best corpus for detecting harmful “tighten the wording” edits

So generation is not just another domain. It is the sharpest corpus for exposing when the analyzer confuses stricter instructions with better behavior.

### 9.7 Cross-run inference: mixed-domain is the first sign of broader upside

Mixed-domain produced the most interesting non-classification cheap-smoke result.

Evidence:

- mixed-domain iteration 3 achieved `2` improvements and `0` regressions
- effect size was reported as `inf`
- confidence still failed at `p = 0.46`

Interpretation:

- the mixed-domain corpus can surface meaningful local gains
- broader task diversity may help the analyzer escape the weakest formatting-only edits
- but even there, the gain is still too small or too unstable for promotion

This is not success, but it is useful signal. Mixed-domain looks like the most promising non-classification place to continue experiments once role-separated runs are available.

### 9.8 Cross-run inference: the gate is separating three different failure classes

The gate is not merely saying “no.” It is separating qualitatively different kinds of bad candidates.

Those classes are now visible in the data:

1. **Null edits**
   - no task movement
   - typical in the local 4B run
2. **Locally plausible but net-zero edits**
   - one task up, one task down
   - also present in the local 4B run
3. **Weak positive but underpowered edits**
   - small clean gains, but confidence failure
   - visible in the Mistral run and mixed-domain cheap-smoke run

This matters because future reporting should not lump all gate rejections together. A rejected null edit and a rejected weak-positive candidate are different product signals.

### 9.9 Cross-run inference: reported final accuracy must be treated differently in no-promotion runs

The cloud Mistral classification run reported `64.0% -> 68.0%`, but no prompt was promoted.

That creates an important reporting rule:

- if `prompt-after.md == prompt-a.md`, then held-out “final” accuracy is not a deployed-improvement claim
- it is part of candidate evaluation context only

This distinction should become a permanent reporting convention because otherwise future readers will overread no-promotion runs as actual shipped prompt improvements.

### 9.10 Cross-run inference: the next high-value experiment is role separation, not more same-model reruns

The runs now point clearly to the best next experiment.

Evidence:

- local 4B model is cheap and mechanically useful, but weak as analyzer
- cloud Mistral is stronger as analyzer, but still expensive and still trapped in local search
- generation and mixed-domain both show that the analyzer weakness is not classification-only

Interpretation:

- repeating more single-model runs is unlikely to change the conclusion much
- the best next experiment is a role-separated run with:
  - cheaper executor
  - stronger analyzer
  - possibly stronger judge for generation

That is now the cleanest way to test whether analyzer quality is still the dominant bottleneck before making gate-calibration changes.

---

## 10. Remaining Execution Gaps

Not every planned field-test run has been executed yet.

Still pending:

| Run | Status | Why it matters |
|-----|--------|----------------|
| extraction multi-iteration loop | pending | checks whether the analyzer weakness is classification-specific |
| generation multi-iteration loop | pending | tests judge-role path under repeated optimization |
| mixed-domain multi-iteration loop | pending | tests whether broader corpora change proposal behavior |
| seeded-prompts execution run | pending | validates known-failure prompt behavior under live loop conditions |
| separated-role run | pending | tests small executor + stronger analyzer strategy directly |
| model-vs-model A/B | pending | isolates model quality from prompt quality |

### 10.1 Cheap-smoke corpus runs completed

After the main classification runs, three reduced-cost `cheap-smoke` runs were executed with:

- `--iterations 3`
- `--held-out-sample 5`
- `--promotion-sample 10`
- `--run-label cheap-smoke`

These runs were designed to answer a narrower question than the main classification field tests: not “can the optimizer succeed end-to-end?” but “does the same local-search weakness generalize across other corpora when run cheaply?”

The answer is yes.

#### Cheap-smoke run summary

| Corpus | Baseline held-out | Final held-out | Promotions | Strongest iteration | Main observed pattern |
|--------|-------------------|----------------|------------|---------------------|-----------------------|
| extraction | 80.0% (4/5) | 20.0% (1/5) | 0 | iter 2 (`+1`, `0` down on 10-task A/B) | formatting / field-name micro-edits |
| generation | 80.0% (4/5) | 20.0% (1/5) | 0 | iter 1 (`+1`, `7` down) | format-adherence wording causes broader regressions |
| mixed-domain | 0.0% (0/5) | 0.0% (0/5) | 0 | iter 3 (`+2`, `0` down, `effect_size = inf`) | small classification-format gain, still no confidence |

#### Evidence caveat: top-level report overwrite

The per-run artifact layout under:

- `field-test/v0.3.0/results/openai/mistralai-mistral-small-3.2-24b-instruct/cheap-smoke/`

contains the authoritative per-corpus iteration directories (`extraction/`, `generation/`, `mixed-domain/`). However, the single top-level `improvement-loop-report.json` under `cheap-smoke/` is not a reliable combined summary for all three domains. It appears to reflect the most recent run written to that label rather than a merged report.

For that reason, the analysis below uses the per-corpus directories and their `analysis.json`, `ab-comparison.json`, and `accuracy.json` files as the source of truth.

### 10.2 Extraction cheap-smoke run

Artifact root:

- `field-test/v0.3.0/results/openai/mistralai-mistral-small-3.2-24b-instruct/cheap-smoke/extraction/`

Observed metrics:

| Iteration | Proposals | A/B winner | p-value | Effect size | Delta summary | Held-out |
|-----------|-----------|------------|---------|-------------|---------------|----------|
| 1 | 1 | tie | 1.0 | 0.0 | `0` up / `0` down / `10` unchanged | 20.0% |
| 2 | 1 | inconclusive | 0.93 | 0.0455 | `1` up / `0` down / `9` unchanged | 20.0% |
| 3 | 1 | inconclusive | 0.92 | -0.0645 | `1` up / `2` down / `7` unchanged | 20.0% |

Proposal pattern:

- all three proposals targeted the extraction formatting line
- all three hypotheses focused on:
  - exact field naming
  - concise formatting
  - lowercase / no-space conventions

This is a useful result because it shows the analyzer is not making nonsense edits. It is spotting a plausible failure family. But it is still trapped in micro-formatting interventions.

Interpretation:

- iteration 2 showed the best extraction candidate, with a small clean positive move (`1` improved, `0` regressed)
- that still failed effect-size with `0.0455`, just below the 5% threshold
- iteration 3 over-corrected and regressed more tasks than it helped

This is consistent with the broader classification finding: the analyzer can find plausible local edits, but they are too weak and too narrow to become promotable.

### 10.3 Generation cheap-smoke run

Artifact root:

- `field-test/v0.3.0/results/openai/mistralai-mistral-small-3.2-24b-instruct/cheap-smoke/generation/`

Observed metrics:

| Iteration | Proposals | A/B winner | p-value | Effect size | Delta summary | Held-out |
|-----------|-----------|------------|---------|-------------|---------------|----------|
| 1 | 1 | inconclusive | 0.81 | -0.0459 | `1` up / `7` down / `2` unchanged | 80.0% |
| 2 | 0 | — | — | — | no proposal | 80.0% |
| 3 | 1 | inconclusive | 0.85 | -0.0629 | `1` up / `2` down / `7` unchanged | 20.0% |

Proposal pattern:

- both generated proposals targeted the top-level instruction line
- both hypotheses emphasized:
  - format adherence
  - avoiding generic content
  - following structure and constraints strictly

Interpretation:

- the analyzer correctly identifies that generation failures are often about structure and constraint-following
- but the proposed fix is too blunt
- in iteration 1 it helped `1` task and harmed `7`
- in iteration 3 it helped `1` and harmed `2`

This is stronger evidence than the classification run that local prompt tightening can actively degrade behavior. The generation corpus is more sensitive to over-constraining language than classification is.

The `0` proposals result in iteration 2 is also important. It suggests the analyzer is not robustly productive even with a stronger model. Sometimes it finds a weak local edit; sometimes it finds nothing.

### 10.4 Mixed-domain cheap-smoke run

Artifact root:

- `field-test/v0.3.0/results/openai/mistralai-mistral-small-3.2-24b-instruct/cheap-smoke/mixed-domain/`

Observed metrics:

| Iteration | Proposals | A/B winner | p-value | Effect size | Delta summary | Held-out |
|-----------|-----------|------------|---------|-------------|---------------|----------|
| 1 | 1 | tie | 1.0 | 0.0 | `0` up / `0` down / `10` unchanged | 0.0% |
| 2 | 1 | tie | 1.0 | 0.0 | `0` up / `0` down / `10` unchanged | 0.0% |
| 3 | 1 | inconclusive | 0.46 | `inf` | `2` up / `0` down / `8` unchanged | 0.0% |

Proposal pattern:

- iterations 1 and 2 proposed generic formatting / conciseness standardization at the top-level instruction line
- iteration 3 finally proposed a more domain-specific clarification for classification behavior inside the multi-domain prompt

Interpretation:

- the first two iterations are classic null-edit outcomes in a broader corpus
- the third iteration is more interesting:
  - `2` tasks improved
  - `0` regressed
  - `effect_size = inf`

That `inf` effect size means the sampled baseline slice for those tasks was effectively zero while the candidate achieved some positive score. This is a mathematically real output from the current effect-size implementation, but it still was not enough for promotion because confidence remained weak (`p = 0.46`).

This is the strongest cheap-smoke evidence that the mixed-domain corpus is at least capable of surfacing non-trivial candidate gains. But even here, the analyzer still needed three iterations to move out of generic formatting advice and into something domain-specific.

### 10.5 What the cheap-smoke runs add to the overall conclusion

These reduced-cost runs matter because they show the classification result is not just a classification artifact.

Across extraction, generation, and mixed-domain:

- the analyzer still prefers narrow wording changes
- proposals cluster around formatting, clarity, or local rule tightening
- the gate still rejects everything
- when positive movement appears, it is small
- when the corpus is more open-ended, overly strict prompt wording can cause regressions

That means the v0.3.0 conclusion becomes stronger, not weaker:

- the optimizer weakness generalizes across corpora
- a stronger model improves signal quality but does not fix search breadth
- the gate remains conservative, and sometimes the next limiting factor is confidence rather than effect size

### 10.6 Evidence pointers for cheap-smoke runs

| Corpus | Artifact root |
|--------|---------------|
| extraction | `field-test/v0.3.0/results/openai/mistralai-mistral-small-3.2-24b-instruct/cheap-smoke/extraction/` |
| generation | `field-test/v0.3.0/results/openai/mistralai-mistral-small-3.2-24b-instruct/cheap-smoke/generation/` |
| mixed-domain | `field-test/v0.3.0/results/openai/mistralai-mistral-small-3.2-24b-instruct/cheap-smoke/mixed-domain/` |

### 10.7 Separated-role classification run

Artifact root:

- `field-test/v0.3.0/results/openai/qwen-qwen3-30b-a3b-instruct-2507+analyzer-mistralai-mistral-small-3.2-24b-instruct/separated-role/`

Run configuration:

- executor: `qwen/qwen3-30b-a3b-instruct-2507`
- analyzer: `mistralai/mistral-small-3.2-24b-instruct`
- iterations: `3`
- held-out sample: `5`
- promotion sample: `10`

Top-line metrics:

| Metric | Value |
|--------|-------|
| Baseline held-out | `60.0%` (`3/5`) |
| Final held-out | `60.0%` (`3/5`) |
| Improvement | `0.0%` |
| Promotions | `0` |

Per-iteration evidence:

| Iteration | Proposals | Analysis cost | A/B artifacts | Accuracy |
|-----------|-----------|---------------|----------------|----------|
| 1 | `0` | `0.0` | none | `60.0%` (`3/5`) |
| 2 | `0` | `0.0` | none | `60.0%` (`3/5`) |
| 3 | `0` | `0.0` | none | `60.0%` (`3/5`) |

Artifact inspection showed:

- `analysis.json` exists in every iteration
- each `analysis.json` records `0` proposals and `0.0` cost
- `prompt-a.md` exists in every iteration
- `prompt-b.md` does **not** exist in any iteration
- `ab-comparison.json` does **not** exist in any iteration
- `prompt-after.md` does **not** exist in any iteration
- no `error.txt` files were written

Interpretation:

- the separated-role runner itself worked
- the unique output directory logic worked
- the executor model produced a plausible baseline (`60%`), so this was not the broken `0% baseline` failure seen with the wrong OpenRouter Qwen model
- but the analyzer produced **no proposals at all**

This is a useful result because it rules out one hypothesis. The problem is not simply “the analyzer needs to be stronger than the executor.” Here the analyzer *was* stronger, yet the analyzer path still produced no proposed edit in 3 iterations.

What this likely means:

- either the analyzer prompt is poorly matched to this role-separated setup
- or the smaller held-out/promotion smoke configuration reduced the visible failure structure too far
- or the analyzer is highly sensitive to the specific executor outputs it sees, and the Qwen 30B executor changed those failures enough that the staged analyzer no longer found a stable edit candidate

Cross-run implication:

- local 4B single-model: weak local edits
- cloud Mistral single-model: weak positive edits
- separated-role Qwen 30B + Mistral: no proposals at all

That means role separation is **not** an automatic fix. It may still be valuable, but the first separated-role result does not show an immediate improvement over the single-model Mistral run.

This is also the strongest evidence yet that the optimizer problem is not reducible to “just use a better analyzer.” The interaction between executor outputs, analyzer prompts, and proposal generation behavior appears to matter more than simple model ranking.

#### Why the artifact shape matters

This run is especially informative because of what is **missing** from the iteration directories, not just what is present.

For all 3 iterations:

- `analysis.json` exists
- `prompt-a.md` exists
- `accuracy.json` exists
- `prompt-b.md` does not exist
- `ab-comparison.json` does not exist
- `prompt-after.md` does not exist
- `error.txt` does not exist

That pattern narrows the failure point very precisely.

It means:

1. the iteration started normally
2. failed traces were collected successfully
3. the analyzer pipeline returned a result object
4. but that result contained zero proposals
5. so the run exited before candidate prompt materialization or A/B testing

This is a materially different failure class from the local 4B and single-model Mistral runs, where proposals existed but were too weak to promote.

#### Why `analysis_cost = 0.0` matters

Every `analysis.json` reported:

- `n_proposals = 0`
- `cost_usd = 0.0`

That combination is a strong clue.

If the analyzer had run a normal paid model pass and simply failed to parse output into proposals, we would typically expect non-zero token or cost evidence. Instead, the zero-cost result suggests one of two things:

1. the analyzer path short-circuited before real proposal generation, or
2. the analyzer returned an empty result extremely early in the staged flow

That makes this run different from a plain “weak proposal” case. The analyzer is not merely proposing bad edits here. It is not proposing **anything**.

#### Comparison to the single-model Mistral run

This separated-role result should be read against the earlier cloud single-model Mistral classification run.

| Dimension | Single-model Mistral | Separated-role Qwen 30B + Mistral |
|-----------|----------------------|------------------------------------|
| Baseline held-out | `64.0%` | `60.0%` |
| Iterations | 8 | 3 |
| Proposals produced | yes, 1 per iter | no, 0 in all iterations |
| Positive task movement | yes, small | none observed |
| Promotions | 0 | 0 |
| Main failure mode | weak, local proposals | no proposals |

This comparison is important because it shows that role separation did **not** simply preserve the analyzer behavior and improve executor behavior independently. Instead, changing the executor also changed the failure surface seen by the analyzer enough that proposal generation collapsed entirely.

#### What this implies about analyzer dependence on executor outputs

The analyzer does not reason over abstract task labels. It reasons over concrete failed traces.

That means the executor model indirectly shapes the analyzer search space:

- different executor outputs create different failure reasons
- different failure reasons produce different analyzer prompts
- different analyzer prompts may surface or suppress different edit families

The separated-role run is the first strong evidence that the optimizer is sensitive to this interaction.

The implication is significant:

- upgrading the analyzer alone is not enough as a mental model
- the quality and structure of executor failures matter just as much
- role separation changes the optimization landscape, not just model quality per role

#### Why this is still a successful experiment

Even though the run produced no proposals, it is not a wasted experiment.

It rules out a very plausible simplifying story:

- “just keep the executor cheap and swap in a stronger analyzer”

The result says that story is incomplete.

What we learned instead is more valuable:

- executor/analyzer interaction matters
- proposal generation is not purely a function of analyzer model strength
- a stronger analyzer can still produce no output if the incoming failure surface is not fertile for proposal extraction

That is exactly the kind of interaction effect the runner did not allow us to measure before #315.

#### Most likely explanations for the zero-proposal outcome

The run does not by itself prove which explanation is correct, but the evidence makes some hypotheses more plausible than others.

Most plausible:

1. **Executor-output shift**
   - Qwen 30B produced different failures than the single-model Mistral run
   - those failures may have been less clustered or less actionable from the analyzer’s perspective

2. **Smoke-size underexposure**
   - `--held-out-sample 5` and `--promotion-sample 10` reduce cost, but they may also reduce failure diversity too far
   - with only 3 seeded failures in an iteration, the analyzer may not see enough recurring structure to propose an edit

3. **Staged analyzer brittleness**
   - the staged analyzer may be more sensitive than expected to the exact phrasing of failures coming from a different executor model

Less plausible:

4. **Framework bug**
   - the iteration artifacts are structurally consistent
   - no crash files were produced
   - the runner completed normally
   - that makes a hidden execution bug less likely than a real model/interaction limitation

#### What this run does and does not prove

What it proves:

- #315 works mechanically
- separated-role flags parse and run
- unique output dirs prevent collisions
- a role-separated run completes without crashing
- executor/analyzer interaction can materially change proposal generation behavior

What it does not prove:

- that role separation is useless
- that Qwen 30B is a bad executor in general
- that Mistral is a bad analyzer in general

It only proves that this specific role-separated pairing, at this sample size, on this corpus, did not produce actionable proposals.

#### Best next follow-up from this result

If we ever continue this line of testing, the highest-value follow-up is not “rerun the same thing longer.” It is:

1. increase sample richness slightly while preserving separate roles
2. inspect the actual failed traces the analyzer saw under the Qwen executor
3. compare those failure clusters against the single-model Mistral run

That would tell us whether the no-proposal outcome came from:

- weaker failure clustering
- less interpretable error surfaces
- or a brittle analyzer prompt pipeline

## 11. Open Questions and Next Steps

1. Inspect the exact task deltas from the strongest Mistral iteration (`iteration-03`).
2. Run separated-role experiments:
   - smaller executor
   - stronger analyzer
3. Run extraction, generation, and mixed-domain multi-iteration loops with the stronger analyzer.
4. Evaluate whether promotion gating should explicitly distinguish:
   - no-signal candidates
   - weak positive but statistically underpowered candidates
   - guardrail-blocked candidates
5. Normalize `accuracy.json` so per-iteration percentage fields are always populated consistently.

---

## 12. Evidence Index

| Evidence | Path |
|----------|------|
| Local synthetic loop | `field-test/v0.3.0/results/omlx/qwen3-4b-instruct-2507-4bit/` |
| Cloud synthetic loop | `field-test/v0.3.0/results/openai/mistralai-mistral-small-3.2-24b-instruct/` |
| Docker integration results | `field-test/v0.3.0/results/docker/omlx/qwen3-4b-instruct-2507-4bit/` |
| Gold analyzer sample | `field-test/v0.3.0/results/gold-corpus-analyzer.json` |
| Docker detailed report | `docs/field-test/v0.3.0/docker-test-run-report.md` |
| Learnings log | `docs/field-test/v0.3.0/learnings.md` |

---

## 13. References

- [WBS Part 6](../wbs/v0.3.0/wbs-v0.3.0-part6-field-test.md)
- [Field Test Plan](field-test-plan.md)
- [Docker Test Plan](docker-test-plan.md)
- [Docker Test Run Report](docker-test-run-report.md)
- [Learnings](learnings.md)
