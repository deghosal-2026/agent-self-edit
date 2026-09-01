# The Edit That Fixed 4 and Broke 1

## Hook

The analyzer proposed a prompt edit that fixed 4 classification tasks and broke 1. The A/B test showed a real improvement. The gate rejected it. Here's what the edit did, task by task.

## Summary

This article does a deep dive into a single prompt edit — the one the analyzer proposed 15 times in a row. We inspect every task that changed: what the model said with Prompt A, what it said with Prompt B, what the expected answer was, and why the edit helped some tasks while hurting others. The edit added "Priority Rules" to a classification prompt, teaching the model to prioritize urgent over security and to handle multi-label cases. It fixed 4 tasks but broke 1 (classify-014: search bug went from "technical" to "feature"). Net +3 on 26 tasks, p=0.23, gate=reject.

## Key Points

- The edit: adding priority rules for urgent/security/billing classification and multi-label handling
- 4 tasks fixed: classify-015 (maintenance→urgent), 023 (stolen card→urgent,security), 024 (feature+billing), 029 (feedback→other)
- 1 task broken: classify-014 (search bug: technical→feature — the edit's rule #3 misclassified it)
- 5 tasks changed but both wrong: the edit over-added "urgent" to multi-label tasks (021, 022, 025)
- The ExactMatch scorer requires exact label match — extra labels score 0
- The pattern: Prompt B over-corrects by adding "urgent" everywhere
- Why this is a great teaching example: the edit is smart but not smart enough

## Learnings

- A good edit can still be a bad edit if it breaks something
- Over-correction is a real failure mode for LLM-proposed edits
- ExactMatch scoring is strict — "security, urgent" ≠ "urgent" (order matters, extra labels fail)
- The analyzer's priority rules were too broad — they fired on tasks that didn't need "urgent"
- Multi-label classification is hard: the model needs to know when to stop adding labels

## Experience

- Inspected all 11 changed tasks by reading results-a.json and results-b.json
- Found that the edit's rule #3 ("classify as 'technical' if it blocks functionality, otherwise 'feature'") caused classify-014 to be classified as "feature" instead of "technical"
- Found that rule #1 ("prioritize 'urgent'") fired on classify-021, 022, 025 — adding "urgent" where it didn't belong
- The edit is a good example of why human review of LLM-proposed edits matters

## What Went Well

- The per-iteration artifacts (results-a.json, results-b.json, ab-comparison.json) made it possible to inspect every task
- The failure pattern (over-adding "urgent") was visible in the data — no guessing needed
- The gate correctly rejected despite the edit being "mostly right"

## What Could Have Gone Better

- The analyzer should propose smaller, more targeted edits — not rewrite the entire prompt
- The priority rules were too broad — they needed per-task exceptions
- The ExactMatch scorer could be relaxed to order-independent matching for multi-label tasks

## Data

- 11 tasks changed (4 fixed, 1 broken, 6 changed-but-both-wrong)
- classify-014: A="technical" (correct), B="feature" (wrong) — BROKEN
- classify-015: A="technical" (wrong), B="urgent" (correct) — FIXED
- classify-023: A="security" (wrong), B="urgent, security" (correct) — FIXED
- classify-024: A="feature" (wrong), B="feature, billing" (correct) — FIXED
- classify-029: A="feature" (wrong), B="other" (correct) — FIXED

## Audience

Prompt engineers, AI engineers debugging LLM behavior, anyone interested in why LLM edits fail.
