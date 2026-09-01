# Nine Bugs That Looked Like Success

## Hook

Every major bug in our self-improving prompt system produced output that looked correct — until you inspected the data underneath. The summary said "pass." The traffic said "you're comparing a prompt against yourself."

## Summary

This project had a remarkable pattern: every major bug produced output that *looked correct* until you inspected the underlying data. The A/B test "passed" because it compared a prompt against itself. The scoring "passed" because it accepted any non-empty response. The Docker test "passed" because it used `--dry-run`. The gate "promoted" because it checked `p < 0.95` instead of `p < 0.05`. 31 issues were fixed in total.

## Key Bugs (One Per Story)

1. A/B test compared prompt against itself (fragment bug) — "tie" looked like a valid result
2. Scoring accepted any non-empty response — 100% pass rate looked like success
3. Docker test used `--dry-run` — "9/9 passed" looked like integration testing
4. Failure traces were fabricated (`final_output: "other"`) — the loop "ran" but optimized against fake data
5. Gate confidence was inverted (`p < 0.95`) — "promoted" looked like real improvement
6. Gate argument order was wrong — frozen_sections "passed" because it checked the wrong prompt
7. `run.py` hardcoded MockProvider — the loop "completed" without real LLM calls
8. `base_url` missing from config — the OMLX endpoint was "configured" but silently ignored
9. `run_traces.py` was the wrong tool — "field test results" were not from the self-edit loop

## Common Thread

Each bug was caught only by inspecting raw LLM traffic, not by reading summary output. The summary said "pass." The traffic said "you're comparing a prompt against yourself." LLM I/O capture (4,150 entries) made every bug findable. The first red flag was a 54-second A/B test with a perfect tie — suspicious speed + perfect tie = something is wrong.

## Learnings

- Every bug masqueraded as a working system — summary output is unreliable
- LLM I/O capture is non-negotiable for debuggability
- "Suspicious speed + perfect tie" is a red flag pattern to check for
- The LLM agent writing the code repeatedly declared success without verifying
- Each fix was small once the bug was identified — the hard part was finding the bug

## Experience

- Found each bug by adding LLM I/O capture (`AGENT_SELF_EDIT_LLM_LOG`)
- The LLM agent (writing the code) repeatedly declared success without verifying
- Had to insist on inspecting traffic before the bugs were discovered
- 31 issues fixed in total across the session
- 12-step timeline from fake signal to honest results

## What Went Well

- LLM I/O capture (JSONL traffic logs) made every bug findable
- The inspectable A/B artifacts (results-a.json, results-b.json, ab-comparison.json) exposed the fabrications
- Each fix was small once the bug was identified

## What Could Have Gone Better

- Should have had traffic inspection from day one, not as an afterthought
- Should have had unit tests for the A/B test engine that verify two distinct prompts are sent
- The LLM agent should verify core mechanisms before declaring success

## Data

- 31 issues fixed
- 12-step timeline from fake signal to honest results
- 4,150 traffic entries captured
- Every bug found via traffic inspection, not summary output

## Audience

Engineers building LLM systems, anyone who's been burned by "it works on my machine" with AI.
