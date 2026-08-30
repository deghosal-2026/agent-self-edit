# WBS — AgentSelfEdit v0.1.0 Part 4: Intelligence

> **Milestones covered:** M7 (Feedback Analyzer) · M8 (Diff Visualization)
> **PRD coverage:** [F-02](../../design/prd/05-features.md) (analyzer), [F-08](../../design/prd/05-features.md) (diff visualization)
> **CUJs covered:** CUJ 1 (deploy, observe, improve — analyzer proposes), CUJ 2 (catch bad edit — analyzer proposes), CUJ 3 (trace lineage — diff)
> **Dependency:** M7 (depends on M2 + M6) → M8 (depends on M5)
> **Issue Range:** #44–#54

---

## Milestone 7: Feedback Analyzer (#44–#50)

**Objective:** The LLM that reviews traces and proposes edits. The creative engine — but it has no authority. All proposals go through A/B test and promotion gate.

### M7 Design Documents

- **D7 — Feedback analyzer design** (`docs/design/feedback-analyzer-design.md`): analyzer system prompt, proposal format, validation rules, deduplication strategy, batch analysis logic, cost tracking.
- **D13 — Design decisions:** DD-14 (analyzer prompt includes frozen annotations), DD-15 (max 3 proposals per batch).

### M7 Task Checklist

| # | Task | Build (files) | Behavior + edge cases | Feature | Design Ref | Verify | Status |
|---|------|---------------|----------------------|---------|------------|--------|--------|
| 1 | Edit proposal dataclass | `src/agent_self_edit/types.py`: `EditProposal` | Fields: section, old_text, new_text, hypothesis, evidence_traces: list[str], expected_improvement: str; all fields required except evidence_traces | F-02 | [D7](../../design/feedback-analyzer-design.md) | valid/invalid proposals; missing fields | [#44](https://github.com/deghosal-2026/agent-self-edit/issues/44) · ⬜ |
| 2 | Analyzer system prompt | Prompt template in `src/agent_self_edit/analyzer.py` | Includes: current prompt with frozen annotations, batch of failed traces, output format instructions; frozen sections clearly marked; max 3 proposals per batch | F-02 | [D7](../../design/feedback-analyzer-design.md) | prompt includes all sections; correct format instructions | [#45](https://github.com/deghosal-2026/agent-self-edit/issues/45) · ⬜ |
| 3 | Analyzer runner | `analyze(traces, current_prompt, frozen_sections, llm_provider) -> list[EditProposal]` | Calls LLM; parses structured response; validates format; returns proposals; empty traces → empty list; LLM failure → `AnalyzerError` | F-02 | [D7](../../design/feedback-analyzer-design.md) | valid traces; empty traces; LLM failure | [#46](https://github.com/deghosal-2026/agent-self-edit/issues/46) · ⬜ |
| 4 | Proposal validation | `validate_proposal(proposal, current_prompt, frozen_sections) -> list[str]` | Checks: section exists, old_text matches prompt, new_text non-empty, hypothesis non-empty, section not frozen; returns list of error messages | F-02 | [D7](../../design/feedback-analyzer-design.md) | all valid; each invalid case; frozen section targeted | [#47](https://github.com/deghosal-2026/agent-self-edit/issues/47) · ⬜ |
| 5 | Proposal deduplication | `deduplicate_proposals(proposals, near_misses, threshold=0.85) -> list[EditProposal]` | Embedding similarity; skip if similarity > threshold; identical proposals deduplicated; similar near-misses skipped; no near-misses → all proposals kept | F-02 | [D7](../../design/feedback-analyzer-design.md) | identical/similar/different; near-miss list empty | [#48](https://github.com/deghosal-2026/agent-self-edit/issues/48) · ⬜ |
| 6 | Batch analysis | `analyze_batch(traces, current_prompt, frozen_sections, llm_provider, max_proposals=3) -> list[EditProposal]` | Group failures by pattern; generate proposals for most common pattern first; max_proposals limit enforced; single failure pattern → 1-3 proposals | F-02 | [D7](../../design/feedback-analyzer-design.md) | single/multiple patterns; max limit; no failures | [#49](https://github.com/deghosal-2026/agent-self-edit/issues/49) · ⬜ |
| 7 | Mock analyzer + cost tracking | `MockAnalyzer` class; token cost tracking in `analyze()` | `MockAnalyzer` returns predetermined proposals, no LLM calls; cost ceiling: abort if exceeded | F-02 | [D7](../../design/feedback-analyzer-design.md) | mock used in CI; cost ceiling enforced | [#50](https://github.com/deghosal-2026/agent-self-edit/issues/50) · ⬜ |

### M7 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Proposal validity | 100% of valid proposals accepted, 100% invalid rejected | validation test suite |
| Deduplication | identical proposals skipped, different proposals kept | dedup test suite |
| Batch analysis | groups failures by pattern, respects max_proposals | batch test suite |
| Mock analyzer | returns predetermined proposals, zero LLM calls | mock test suite |
| Coverage | > 92% | `--cov-fail-under=92` |

### M7 Out of Scope

- Diff visualization (M8), CLI (M9), web dashboard (v0.2.0), drift detection (v0.2.0)

### M7 Exit Gate

- [ ] `EditProposal` dataclass is complete
- [ ] Analyzer produces valid proposals from traces
- [ ] Proposals are validated and deduplicated
- [ ] Batch analysis groups failures and generates proposals
- [ ] Mock analyzer works without LLM calls
- [ ] Cost tracking enforces ceiling
- [ ] Ruff clean, mypy strict clean, all tests pass, coverage > 92%
- [ ] **Design docs authored:** D7 (feedback-analyzer), D13 (DD-14/15)

**Dependency:** M2 (traces) + M6 (guardrails). **Produces for M9+:** `EditProposal`, `analyze()`, `validate_proposal()`, `deduplicate_proposals()`, `MockAnalyzer`.

---

## Milestone 8: Diff Visualization (#51–#54)

**Objective:** Show the user exactly what changed, what stayed the same, and why. The transparency layer that makes the system trustworthy.

### M8 Design Documents

- **D8 — Diff visualization design** (`docs/design/prompt-diff-design.md`): inline diff format, side-by-side diff format, color coding, frozen section annotations, edit density computation, guardrail report formatting, markdown export.

### M8 Task Checklist

| # | Task | Build (files) | Behavior + edge cases | Feature | Design Ref | Verify | Status |
|---|------|---------------|----------------------|---------|------------|--------|--------|
| 1 | Inline diff output | `format_diff_inline(diff_result) -> str` | Removed lines `- `, added lines `+ `; frozen sections `(frozen)`; color-coded if terminal supports; identical prompts → single line "no changes" | F-08 | [D8](../../design/prompt-diff-design.md) | identical/different/frozen; color auto/always/never | [#51](https://github.com/deghosal-2026/agent-self-edit/issues/51) · ⬜ |
| 2 | Side-by-side diff + guardrail report | `format_diff_side_by_side(diff_result) -> str`; `format_guardrail_report(gate_result) -> str` | Two-column alignment; frozen sections grayed out; guardrail report: table with check name, passed/failed, value, threshold; summary line | F-08 | [D8 §2.1](../../design/prompt-diff-design.md#21-prompt-diff--before-vs-after) | side-by-side alignment; guardrail all/some/none passed | [#52](https://github.com/deghosal-2026/agent-self-edit/issues/52) · ⬜ |
| 3 | Edit summary + density | `format_edit_summary(edit_id, gate_result, ab_result) -> str`; `format_edit_density(registry, window=20) -> str` | Summary: "Edit #N — Promoted — +12.4% accuracy (p<0.01, n=78) — 3 lines"; density: text-based bar chart per-section; empty history → empty chart | F-08 | [D8 §2.2-2.3](../../design/prompt-diff-design.md#22-edit-density-over-time) | promoted/rejected/near-miss; empty/full history | [#53](https://github.com/deghosal-2026/agent-self-edit/issues/53) · ⬜ |
| 4 | Markdown output + color support | `--format markdown` flag; `--color auto|always|never` | Markdown: code blocks for diffs, tables for reports; color: auto detects terminal, always forces color, never suppresses | F-08 | [D8 §3.1](../../design/prompt-diff-design.md#31-cli) | markdown valid; all 3 color modes | [#54](https://github.com/deghosal-2026/agent-self-edit/issues/54) · ⬜ |

### M8 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Diff output readability | inline and side-by-side produce correct output | diff format test suite |
| Guardrail report | table format correct for all pass/fail combinations | report test suite |
| Edit summary | one-line summary correct for all decision types | summary test suite |
| Markdown output | valid markdown, renders correctly | markdown test suite |
| Coverage | > 92% | `--cov-fail-under=92` |

### M8 Out of Scope

- CLI (M9), web dashboard (v0.2.0), drift detection (v0.2.0)

### M8 Exit Gate

- [ ] Inline and side-by-side diff work correctly
- [ ] Guardrail report is clear and readable
- [ ] Edit summary is one line
- [ ] Edit density chart renders correctly
- [ ] Color output works in all modes
- [ ] Markdown output is valid
- [ ] Ruff clean, mypy strict clean, all tests pass, coverage > 92%
- [ ] **Design docs authored:** D8 (prompt-diff-design)

**Dependency:** M5 (registry). **Produces for M9+:** `format_diff_inline()`, `format_diff_side_by_side()`, `format_guardrail_report()`, `format_edit_summary()`, `format_edit_density()`.