# How We Chased the Wrong Target for a Day

## Hook

We spent a full session trying to make the self-edit loop "pass" — tweaking thresholds, expanding task sets, adjusting drift limits. We got a promotion. Then we realized it was noise.

## Summary

We spent a full session trying to make the self-edit loop "pass" — tweaking the drift threshold from 0.3 to 0.5, expanding the A/B task set from 5 to 26, adjusting parameters. We got a promotion (20%→40% accuracy) and celebrated. Then critical review revealed the confidence check was inverted — the "promotion" was noise (p=0.1). After fixing to p<0.05, the same edit was correctly rejected (p=0.23). We had been optimizing for a green outcome instead of an honest conclusion.

## Key Points

- The drift from "validate the gate" to "make it pass" happened gradually
- Each tweak was individually reasonable but collectively moved us toward the wrong goal
- The critical review caught the confidence bug before shipping a false positive
- Course-correcting: "the goal is not to make the loop pass; the goal is to see the gate working"
- A field test that ends with "no promotion" is valid if it proves the gate is honest
- The 12-step timeline from fake signal to honest results

## Learnings

- The field test goal is not "achieve promotion" — it's "prove the system behaves honestly"
- We tweaked the drift threshold to get a promotion through — and got one (20%→40%)
- Then we discovered the confidence check was inverted (p < 0.95 instead of p < 0.05)
- With the correct check, the promotion was revealed as noise (p=0.23)
- We had been optimizing for a green outcome instead of an honest conclusion
- Course correcting from "make it pass" to "prove the gate works" was the key insight

## Experience

- Started by fixing real bugs (fake traces, wrong A/B set, gate arg order) — legitimate work
- Then drifted into threshold tuning to force a promotion — chasing the wrong goal
- Got a promotion at drift=0.5, celebrated, then critical review revealed the confidence bug
- Fixed confidence, re-ran, watched the same edit get correctly rejected (p=0.23)
- Realized: the gate rejecting is the success condition, not the failure condition
- Stopped iterating, wrote learnings, planned the wrap-up

## What Went Well

- The critical review caught the confidence bug before shipping a false positive
- Course-correcting quickly — once we saw the gate rejecting honestly, we stopped pushing
- Documenting the wrong-goal chase in learnings so future sessions don't repeat it

## What Could Have Gone Better

- Should have asked "what is the actual goal?" before tweaking thresholds
- The drift threshold tweak was a band-aid — the real issue was the confidence check
- Spent 2+ iterations chasing promotion before course-correcting
- The field test plan should explicitly state: "success = gate behaves honestly, not = promotion achieved"

## Data

- 12-step session timeline
- First "promotion" at p=0.1 (false positive)
- After fix: p=0.23, 15/15 rejections, 0% improvement, gate validated

## Audience

Engineering managers, AI researchers, anyone who's optimized for the wrong metric.
