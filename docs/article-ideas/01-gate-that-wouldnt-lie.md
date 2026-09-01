# The Gate That Wouldn't Lie

## Hook

We built a self-improving prompt system. The promotion gate rejected every edit — 15 times in a row. And it was right every time.

## Summary

The most compelling story from this project is that the gate rejected every edit the analyzer proposed — 15 times in a row — and that was the correct outcome every time. The analyzer proposed a real improvement (+4 tasks fixed, -1 broken, net +3 on 26), but at p=0.23 the gate refused to promote because there was a 23% chance the improvement was noise. The gate requires p<0.05. Zero false positives, zero false negatives.

## Key Points

- The 6 deterministic checks (sample floor, effect size, confidence, frozen sections, edit distance, drift) in fail-fast order
- How the confidence check was inverted (p < 0.95 vs p < 0.05) — a "promotion" at p=0.1 was a false positive
- After fixing: 15/15 iterations correctly rejected. The gate works.
- Why a gate that never promotes is still valuable — it proves the safety property works
- The tension between "make the loop pass" and "prove the gate works" — we course-corrected
- The gate rejecting a real-but-weak improvement is the strongest evidence it works

## Learnings

- The gate's 6 deterministic checks are the real product, not the optimizer
- The confidence check was inverted: `p < 0.95` instead of `p < 0.05` — almost everything passed
- After fixing to `alpha = 1 - confidence_level`, a "promotion" at p=0.1 was revealed as noise (p=0.23)
- A gate that never promotes still proves the safety property works
- The goal isn't to make the loop pass; it's to prove the gate is honest

## Experience

- Built the gate, ran 15 iterations, watched it reject every time
- The analyzer proposed a real edit (fixed 4 tasks, broke 1, net +3 on 26) — but p=0.23
- Fixed the confidence bug (2-line change), re-ran, watched the same edit get correctly rejected
- Had to course-correct: stopped chasing a promotion, started validating gate behavior
- 0% false positive rate, 0% false negative rate over 15 iterations

## What Went Well

- The gate caught a real improvement that was too weak (3/26 tasks, p=0.23)
- The 6-check fail-fast architecture made it easy to see exactly which check blocked promotion
- Fixing the confidence check was a 2-line change that changed the entire outcome

## What Could Have Gone Better

- The confidence bug should have been caught in unit tests, not in field testing
- We spent time trying to "make it pass" before realizing the goal was gate validation
- The drift threshold (0.3) blocked a legitimate edit — needed tuning to 0.5

## Data

- 4,150 LLM calls, 15 iterations
- p=0.23 every time, gate=reject every time
- 0% false positive rate, 0% false negative rate
- Checks: sample_floor PASS, effect_size PASS, confidence FAIL (p=0.23 >= 0.05)

## Audience

AI engineers building self-improving systems, platform safety teams.
