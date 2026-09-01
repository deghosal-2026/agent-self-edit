# Your A/B Test Is Lying to You

## Hook

Our self-edit loop showed 0% improvement for days. The root cause: the failure traces were completely fabricated.

## Summary

We spent days wondering why the self-edit loop produced 0% improvement. The script hardcoded `final_output: "other"` for every trace, but the model actually outputs `"billing"`, `"security"`, `"technical"`. The analyzer was optimizing against a failure pattern that didn't exist. After fixing to seed real model outputs, non-zero deltas appeared immediately — 5 tasks changed, 4 fixed, 1 broken.

## Key Points

- How synthetic test data can silently diverge from real model behavior
- Why you must run the current prompt against the task set and capture real failures
- The closed loop: `prompt → LLM → real output → score → real failures → analyzer → edit`
- How to debug a stuck loop: inspect the traces, not the prompts
- The A/B artifacts that made the bug visible (results-a.json, results-b.json, ab-comparison.json)

## Learnings

- The feedback loop is only as good as the data you feed it
- Fabricated failure traces caused the analyzer to optimize against a failure pattern that didn't exist
- A closed loop with fake data produces real-looking but meaningless results
- The fix: run the current prompt against the task set, capture real model outputs, seed only real failures

## Experience

- Spent multiple iterations debugging why A and B produced identical outputs
- Discovered the traces were fake by inspecting the A/B artifacts (results-a.json, results-b.json)
- After fixing, the analyzer immediately proposed a more relevant edit
- Non-zero deltas appeared for the first time — 5 tasks changed, 4 fixed, 1 broken

## What Went Well

- The fix was simple: call the LLM, score the output, seed only real failures
- After the fix, the A/B test immediately showed real signal (5 non-zero deltas)
- The inspectable per-iteration artifacts made the bug obvious

## What Could Have Gone Better

- Should have inspected the seeded traces before running the loop
- The fabrication was a shortcut that looked reasonable in code review ("mark all as failed")
- Should have had a trace validation step that checks `final_output` against actual model behavior

## Data

- Before fix: 0 non-zero deltas, p=1.0, gate=reject (1/6 checks)
- After fix: 5 non-zero deltas, p=0.23, gate=reject (2/6, confidence only)

## Audience

ML engineers, prompt engineers, anyone building feedback loops.
