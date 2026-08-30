# WBS — AgentSelfEdit v0.1.0 Part 4: Intelligence

> Part of the v0.1.0 release. See [index](wbs-v0.1.0-index.md) for milestone overview.
>
> **Milestones:** M7 (Feedback Analyzer) · M8 (Diff Visualization)
> **Dependency:** M7 → M8 (diff shows analyzer output)
> **Issue Range:** #44–#54

## M7 — Feedback Analyzer (#44–#50)

**Goal:** The LLM that reviews traces and proposes edits. All proposals go through A/B test and promotion gate.

### Design

| Task | Description | Deliverable |
|---|---|---|
| D7 | Design feedback analyzer | `docs/design/feedback-analyzer-design.md` — analyzer system prompt, proposal format, validation rules, deduplication strategy, batch analysis logic, cost tracking |

### Build

| Task | Description | Deliverable |
|---|---|---|
| M7.1 | Edit proposal dataclass | `EditProposal` dataclass: section, old_text, new_text, hypothesis, evidence_traces: list[str], expected_improvement: str. Add to `types.py`. |
| M7.2 | Analyzer system prompt | Prompt template: current prompt with frozen annotations, batch of failed traces, instructions for proposal format. Frozen sections clearly marked. |
| M7.3 | Analyzer runner | `analyze(traces, current_prompt, frozen_sections, llm_provider) -> list[EditProposal]` — calls LLM, parses response, validates format. |
| M7.4 | Proposal validation | `validate_proposal(proposal, current_prompt, frozen_sections) -> list[str]` — verify: section exists in prompt, old_text matches current prompt, new_text is non-empty, hypothesis is non-empty, section is not frozen. |
| M7.5 | Proposal deduplication | `deduplicate_proposals(proposals, near_misses, threshold=0.85) -> list[EditProposal]` — compare new proposals against recent near-misses using embedding similarity. Skip if similar. |
| M7.6 | Batch analysis | `analyze_batch(traces, current_prompt, frozen_sections, llm_provider, max_proposals=3) -> list[EditProposal]` — group failures by pattern, generate 1-3 proposals per batch. |
| M7.7 | Failure pattern clustering | Group traces by failure_reason similarity. Cluster similar failures. Generate proposals for the most common cluster first. |
| M7.8 | Analyzer cost tracking | Token count and estimated cost per analysis run. Configurable cost ceiling. Abort if ceiling exceeded. |
| M7.9 | Mock analyzer | `MockAnalyzer` — returns predetermined proposals. Used for testing and in CI (no LLM calls). |

### Tests

| Task | Description | Files |
|---|---|---|
| T7.1 | Test edit proposal validation | `tests/test_analyzer.py` — valid proposal, missing section, old_text doesn't match, new_text empty, hypothesis empty, frozen section targeted |
| T7.2 | Test analyzer prompt | `tests/test_analyzer.py` — prompt includes current prompt, prompt includes frozen markers, prompt includes traces, prompt includes output format instructions |
| T7.3 | Test analyzer runner | `tests/test_analyzer.py` — mock LLM returns valid proposals, malformed response handled, empty response handled, multiple proposals parsed |
| T7.4 | Test proposal deduplication | `tests/test_analyzer.py` — identical proposals deduplicated, similar proposals deduplicated, different proposals kept, near-miss comparison |
| T7.5 | Test batch analysis | `tests/test_analyzer.py` — single failure pattern, multiple failure patterns, no failures, max_proposals limit enforced |
| T7.6 | Test failure pattern clustering | `tests/test_analyzer.py` — identical failures clustered, similar failures clustered, unrelated failures separate, empty trace list |
| T7.7 | Test mock analyzer | `tests/test_analyzer.py` — returns predetermined proposals, doesn't call LLM, used in CI tests |
| T7.8 | Test analyzer cost tracking | `tests/test_analyzer.py` — token count tracked, cost ceiling enforced, abort on ceiling exceeded |

### Documentation

| Task | Description | Deliverable |
|---|---|---|
| M7.DOC1 | Analyzer reference | Create `docs/reference/analyzer.md` — analyzer prompt structure, proposal format, configuration, cost settings |
| M7.DOC2 | Integration guide | Create `docs/explanation/integration.md` — how to integrate AgentSelfEdit with an existing agent, trace format, adapter setup |
| M7.DOC3 | Update WBS index | Update `docs/wbs/v0.1.0/wbs-v0.1.0-index.md` with M7 status, issue links, exit gate results |

### M7 Exit Gate

- [ ] Design docs reviewed and committed
- [ ] EditProposal dataclass is complete
- [ ] Analyzer produces valid proposals from traces
- [ ] Proposals are validated and deduplicated
- [ ] Batch analysis groups failures and generates proposals
- [ ] Mock analyzer works without LLM calls
- [ ] Cost tracking enforces ceiling
- [ ] Ruff clean, mypy strict clean
- [ ] All tests pass: `pytest` → 0 failures
- [ ] Coverage > 92%: `pytest --cov=agent_self_edit --cov-fail-under=92`

---

## M8 — Diff Visualization (#51–#54)

**Goal:** Show the user exactly what changed, what stayed the same, and why.

### Design

| Task | Description | Deliverable |
|---|---|---|
| D8 | Design diff visualization | `docs/design/prompt-diff-design.md` — inline diff format, side-by-side diff format, color coding, frozen section annotations, edit density computation, guardrail report formatting |

### Build

| Task | Description | Deliverable |
|---|---|---|
| M8.1 | Inline diff output | `format_diff_inline(diff_result) -> str` — removed lines with `- ` prefix, added lines with `+ ` prefix, frozen sections with `(frozen)` annotation. Color-coded if terminal supports. |
| M8.2 | Side-by-side diff output | `format_diff_side_by_side(diff_result) -> str` — two-column format. Left column: before, right column: after. Frozen sections grayed out. |
| M8.3 | Guardrail report output | `format_guardrail_report(gate_result) -> str` — table: check name, passed/failed, value, threshold. Summary line. |
| M8.4 | Edit summary line | `format_edit_summary(edit_id, gate_result, ab_result) -> str` — one-line: "Edit #{N} — {Promoted|Rejected} — {+X%} accuracy (p<{val}, n={trials}) — {lines changed} lines" |
| M8.5 | Edit density (CLI) | `format_edit_density(registry, window=20) -> str` — text-based bar chart. Per-section edit frequency over last N cycles. |
| M8.6 | Color output | Support `--color` flag (auto, always, never). Auto: detect terminal color support. Always: force color. Never: plain text. |
| M8.7 | Markdown output | Support `--format markdown` for all visualization commands. Enables sharing diffs in PRs, docs, and articles. |

### Tests

| Task | Description | Files |
|---|---|---|
| T8.1 | Test inline diff | `tests/test_diff.py` — identical prompts, added lines, removed lines, modified lines, frozen sections, empty diff |
| T8.2 | Test side-by-side diff | `tests/test_diff.py` — two-column alignment, frozen sections, added/removed/modified, long lines |
| T8.3 | Test guardrail report | `tests/test_diff.py` — all passed, some failed, all failed, empty checks |
| T8.4 | Test edit summary | `tests/test_diff.py` — promoted, rejected, near-miss, with ab_result, without ab_result |
| T8.5 | Test edit density | `tests/test_diff.py` — single section, multiple sections, no edits, window size, empty history |
| T8.6 | Test color output | `tests/test_diff.py` — auto detects terminal, always forces color, never suppresses color |
| T8.7 | Test markdown output | `tests/test_diff.py` — markdown format is valid, code blocks for diffs, tables for guardrail reports |

### Documentation

| Task | Description | Deliverable |
|---|---|---|
| M8.DOC1 | Diff reference | Create `docs/reference/diff.md` — diff output formats, color support, markdown export, examples |
| M8.DOC2 | Update WBS index | Update `docs/wbs/v0.1.0/wbs-v0.1.0-index.md` with M8 status, issue links, exit gate results |

### M8 Exit Gate

- [ ] Design docs reviewed and committed
- [ ] Inline and side-by-side diff work correctly
- [ ] Guardrail report is clear and readable
- [ ] Edit summary is one line
- [ ] Edit density chart renders correctly
- [ ] Color output works in all modes
- [ ] Markdown output is valid
- [ ] Ruff clean, mypy strict clean
- [ ] All tests pass: `pytest` → 0 failures
- [ ] Coverage > 92%: `pytest --cov=agent_self_edit --cov-fail-under=92`