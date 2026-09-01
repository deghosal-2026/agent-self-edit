# Why 3 Out of 26 Isn't Enough

## Hook

The analyzer fixed 4 tasks and broke 1. That's a net +3 on 26 tasks — 11.5% improvement. The gate said no. And it was right.

## Summary

The analyzer proposed an edit that fixed 4 tasks and broke 1 (net +3) on 26 hard classification tasks. That's an 11.5% improvement. But the permutation test returned p=0.23 — there's a 23% chance this improvement is random noise. The gate requires p<0.05. Over 15 iterations, the result was identical every time: the edit fixes the same 3 tasks, p stays at 0.23, the gate rejects. The improvement is real but underpowered.

## Key Points

- How permutation testing works for prompt comparison (with actual p-value computation)
- Why n=26 tasks can't distinguish an 11.5% improvement from noise (p=0.23)
- The trade-off between task set size and iteration speed (4B at 540ms/call made n=26 feasible)
- Bootstrap confidence intervals, effect size, and what "inconclusive" actually means
- Why the gate's `confidence_level = 0.95` should mean `p < 0.05`, not `p < 0.95`
- The edit that over-corrected: adding "urgent" to multi-label tasks where it didn't belong
- The analyzer proposes the same edit every iteration because it has no rejection feedback

## Learnings

- Statistical power depends on both effect size and sample size
- 3 net improvements on 26 tasks (11.5%) is not enough for p<0.05
- The permutation test asks: "could this happen by chance?" — with 3/26, there's a 23% chance
- The confidence check semantics matter: `p < 0.95` is not `p < 0.05`
- The gate's job is to be conservative — rejecting real-but-weak improvements is correct

## Experience

- Watched the gate reject the same edit 15 times in a row
- The edit genuinely fixed classify-015, 023, 024, 029 every single iteration — no variance
- But it also broke classify-014 every iteration (A correct, B wrong)
- Net +3 on 26, p=0.23, gate=reject. Consistent, real, but not significant.

## What Went Well

- The permutation test correctly identified the improvement as underpowered
- The gate's conservatism prevented a false positive promotion
- The A/B artifacts (per-task deltas, p-value, CI) made the statistical analysis transparent

## What Could Have Gone Better

- Should have started with 50+ hard tasks instead of 26
- The analyzer needs rejection awareness — it shouldn't propose the same edit repeatedly
- Cumulative evidence across iterations would strengthen the case (same 3 tasks fixed every time)

## Data

- 15 iterations, identical results every time
- 4 fixed (classify-015, 023, 024, 029), 1 broken (classify-014)
- Mean delta=0.115, p=0.23, effect size=25%

## Audience

Data scientists, ML researchers, A/B testing practitioners.
