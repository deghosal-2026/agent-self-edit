# Feedback Analyzer Design

> Analyzer system prompt, proposal format, validation rules, deduplication strategy, batch analysis logic, and cost tracking for AgentSelfEdit v0.1.0.

## 1. Purpose

The feedback analyzer is the **creative engine** of the self-improvement loop (PRD 02-architecture §2.2.1, F-02). It reviews execution traces, identifies failure patterns, and proposes concrete, minimal prompt edits — each with a written hypothesis. It has **no authority**: every proposal goes through A/B test + promotion gate before anything is promoted.

## 2. What's Already Built (Reuse)

| Component | Source | Notes |
|---|---|---|
| `EditProposal` dataclass | `types.py` (M4) | Fields: section, old_text, new_text, hypothesis, expected_improvement, evidence_traces, edit_id. **#45 is pre-done.** |
| `AnalyzerConfig` | `config.py` (M1) | `max_proposals_per_batch=3`, `cost_ceiling_usd=0.50` |
| Frozen-section parsing | `parse_frozen_sections()` (M6 guardrails) | Used to mark `[FROZEN]` in analyzer prompt |
| TF-IDF drift | `compute_drift_tfidf()` (M6 guardrails) | Reuse for dedup similarity (#49) |
| Token estimation | `estimate_tokens()` (M3 `ab_test.py`) | Reuse for cost tracking |
| Cost estimation | `estimate_cost()` (M3 `ab_test.py`) | Reuse for ceiling enforcement |
| LLM provider | `LLMProvider` / `MockProvider` (M3) | MockProvider for hermetic tests |
| Near-miss source | `GateAuditLog` (M4) | Query rejected edits for dedup |
| `GuardrailError` | `guardrails.py` (M6) | Raised on malformed proposals |

## 3. Analyzer System Prompt (#46)

### 3.1 Structure (per PRD roadmap §M7)

```
You are a prompt optimization analyst. You review execution traces
where an agent failed and propose minimal, concrete edits to the
agent's system prompt.

Current prompt (frozen sections marked with [FROZEN]):
{current_prompt_with_annotations}

Failed traces (batch of {N}):
{traces}

For each failure pattern you identify, propose ONE edit:
- Which section of the prompt to change
- The exact old text (must match current prompt)
- The exact new text (minimal change)
- Why this change should help (hypothesis grounded in trace evidence)
- Which traces support this hypothesis

Do NOT propose changes to [FROZEN] sections.
Do NOT propose more than {max_proposals} edits per batch.
Each edit must be minimal — change the fewest lines possible.

Respond as a JSON array of objects with keys:
section, old_text, new_text, hypothesis, evidence_traces, expected_improvement
```

### 3.2 Frozen Annotation Injection

Use `frozen_line_indexes()` from the guardrails module to get the set of
frozen line indexes (0-based). Inject `[FROZEN]` at the start of each
frozen line so the LLM sees them clearly:

```python
def annotate_prompt(prompt_text: str) -> str:
    frozen_idx = frozen_line_indexes(prompt_text)
    lines = prompt_text.splitlines()
    annotated = []
    for i, line in enumerate(lines):
        if i in frozen_idx:
            annotated.append(f"[FROZEN] {line}")
        else:
            annotated.append(line)
    return "\n".join(annotated)
```

Edge cases:
- No frozen sections → `frozen_line_indexes` returns empty set → no annotations injected.
- Entire prompt frozen → every line gets `[FROZEN]` prefix.
- The `[FROZEN]` prefix is cosmetic — the gate still enforces frozen sections deterministically.

### 3.3 Trace Formatting

Format failed traces as a compact text block. Only include **failed**
traces (`success=False`). Include `failure_reason` when available:

```python
def format_traces(traces: list[Trace]) -> str:
    lines = []
    for i, t in enumerate(traces, 1):
        reason = t.failure_reason or "unknown"
        lines.append(
            f"Trace {i}: task_id={t.task_id}, "
            f"input=\"{t.task_input}\", "
            f"output=\"{t.final_output}\", "
            f"expected=\"{t.expected_output}\", "
            f"failure_reason=\"{reason}\""
        )
    return "\n".join(lines)
```

Concrete output example:

```
Trace 1: task_id=t1, input="classify ticket", output="billing", expected="technical", failure_reason="misclassified — user's issue is technical, not billing"
Trace 2: task_id=t5, input="classify ticket", output="billing", expected="technical", failure_reason="same pattern as trace 1"
```

### 3.4 Prompt Assembly

```python
def build_analyzer_prompt(
    current_prompt: str,
    traces: list[Trace],
    max_proposals: int = 3,
) -> str:
    annotated = annotate_prompt(current_prompt)
    formatted_traces = format_traces(traces)
    return ANALYZER_SYSTEM_PROMPT.format(
        current_prompt_with_annotations=annotated,
        N=len(traces),
        traces=formatted_traces,
        max_proposals=max_proposals,
    )
```

The `system_prompt` argument to `llm.complete()` is empty — the full
context is in the user prompt. This matches the A/B test runner pattern
in `ab_test.py` (system prompt is already in the full prompt).

## 4. Edit Proposal Format (#45)

Already defined in `types.py`:

```python
@dataclass(frozen=True)
class EditProposal:
    section: str
    old_text: str
    new_text: str
    hypothesis: str
    expected_improvement: str
    evidence_traces: list[str] = field(default_factory=list)
    edit_id: str | None = None
```

The analyzer returns JSON; each object maps to an `EditProposal`. Fields:
- `section` — a free-form label the analyzer provides (not formally resolved to line ranges)
- `old_text` — must match text in the current prompt (concrete safety check)
- `new_text` — the replacement text (minimal change)
- `hypothesis` — why this change should improve outcomes
- `expected_improvement` — predicted effect (e.g., "+5% accuracy on billing/technical overlap")
- `evidence_traces` — list of trace IDs that support this hypothesis

**#45 is pre-done** — verify fields match and close.

## 5. Analyzer Runner (#47)

```python
class AnalyzerError(Exception):
    """Raised on analyzer LLM failure or malformed response."""

def analyze(
    traces: list[Trace],
    current_prompt: str,
    frozen_sections: list[str] | None,
    llm_provider: LLMProvider,
) -> list[EditProposal]:
```

### 5.1 Flow

1. Empty traces → return `[]` immediately (no LLM call).
2. Build the prompt via `build_analyzer_prompt(current_prompt, traces)`.
3. Call `llm_provider.complete(prompt=..., system_prompt="", temperature=0.0)`.
4. Parse the response as JSON (`json.loads`).
5. Validate each parsed object → `EditProposal` (skip malformed, log).
6. Return `list[EditProposal]`.

### 5.2 JSON Response Parsing

The LLM is instructed to return a JSON array. The response may contain
markdown fences (```` ```json ... ``` ````) or extra prose. Strip those
before parsing:

```python
def _extract_json(response: str) -> list[dict]:
    text = response.strip()
    # strip markdown fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        # drop first and last fence lines
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise AnalyzerError(f"analyzer returned invalid JSON: {e}") from e
    if not isinstance(data, list):
        raise AnalyzerError("analyzer returned non-array JSON")
    return data
```

### 5.3 Proposal Construction

Each parsed dict maps to `EditProposal`. Missing required fields → skip
that proposal (don't raise — partial results are valid). Log a warning:

```python
def _build_proposal(obj: dict) -> EditProposal | None:
    try:
        return EditProposal(
            section=obj["section"],
            old_text=obj["old_text"],
            new_text=obj["new_text"],
            hypothesis=obj["hypothesis"],
            expected_improvement=obj.get("expected_improvement", ""),
            evidence_traces=obj.get("evidence_traces", []),
        )
    except (KeyError, TypeError) as e:
        logger.warning("Skipping malformed proposal: %s", e)
        return None
```

### 5.4 LLM Failure Handling

| Failure | Result |
|---------|--------|
| `ProviderError` from `llm.complete()` | `AnalyzerError("analyzer LLM failed: {e}")` |
| Empty response string | `AnalyzerError("analyzer returned empty response")` |
| Non-JSON after fence stripping | `AnalyzerError("analyzer returned invalid JSON: ...")` |
| JSON but not a list | `AnalyzerError("analyzer returned non-array JSON")` |
| JSON list but object missing keys | Skip that proposal (log warning), keep valid ones |
| JSON list with 0 valid proposals | Return `[]` (not an error — analyzer found nothing actionable) |

### 5.5 MockProvider Usage for Tests

```python
# MockProvider returns a predetermined JSON string
llm = MockProvider(responses=json.dumps([
    {
        "section": "classification",
        "old_text": "When classifying, check the subject line.",
        "new_text": "When classifying, check the subject line and the body.",
        "hypothesis": "Subject-only check misses billing/technical overlap",
        "evidence_traces": ["t1", "t5"],
        "expected_improvement": "+5% accuracy on ambiguous tickets",
    }
]))
proposals = analyze(failed_traces, current_prompt, None, llm)
assert len(proposals) == 1
assert proposals[0].section == "classification"
```

## 6. Proposal Validation (#48)

```python
def validate_proposal(
    proposal: EditProposal,
    current_prompt: str,
    frozen_sections: list[str] | None,
) -> list[str]:
```

Returns a list of error messages (empty = valid).

### 6.1 Checks (in order)

| # | Check | Error message |
|---|---|---|
| 1 | `proposal.section` is non-empty | `"section is required"` |
| 2 | `proposal.old_text` is found in `current_prompt` | `"old_text not found in current prompt"` |
| 3 | `proposal.new_text` is non-empty | `"new_text is required"` |
| 4 | `proposal.hypothesis` is non-empty | `"hypothesis is required"` |
| 5 | `proposal.section` is not a frozen section name | `"section '{section}' is frozen and cannot be modified"` |

All checks run (not fail-fast) — the function returns **all** errors at
once so the caller can log the full picture.

### 6.2 Frozen Section Detection

Two sources of frozen section names:
1. **Parsed from prompt** — `parse_frozen_sections(current_prompt)` →
   extract `.section_name` from each `FrozenSection`.
2. **Explicitly provided** — `frozen_sections` parameter (list of names).

Union both sets. If `proposal.section` is in the union → fail.

```python
def _frozen_names(current_prompt: str, frozen_sections: list[str] | None) -> set[str]:
    names: set[str] = set()
    for sec in parse_frozen_sections(current_prompt):
        if sec.section_name is not None:
            names.add(sec.section_name)
    if frozen_sections:
        names.update(frozen_sections)
    return names
```

### 6.3 `old_text` Match Semantics

`old_text in current_prompt` — exact substring match. The LLM is
instructed to copy the exact text from the prompt. If it paraphrases or
truncates, the match fails and the proposal is rejected. This is the
**concrete safety check** — it proves the analyzer actually read the
prompt, not hallucinated.

Edge cases:
- `old_text` is empty → fails check 2 (not found).
- `old_text` spans multiple lines → works (Python `in` on multi-line strings).
- `old_text` has trailing whitespace → fails. The LLM should be
  instructed to copy verbatim. If this is too strict, consider
  `.strip()` normalization in a future version.

### 6.4 Section Semantics

The `section` field is a **free-form label** the analyzer provides. The
PRD doesn't formally define section boundaries. The concrete safety
check is `old_text in current_prompt` — that's what matters. Don't
over-engineer section resolution. The `section` field is for human
readability and for the frozen-section check (does the name match a
frozen section?).

## 7. Proposal Deduplication (#49)

```python
def deduplicate_proposals(
    proposals: list[EditProposal],
    near_misses: list[EditProposal],
    threshold: float = 0.85,
) -> list[EditProposal]:
```

### 7.1 Strategy: TF-IDF Similarity (not embedding)

The ticket says "embedding similarity" but we have no embedding provider
interface (`LLMProvider` only has `complete()`). Per DD-13, v0.1.0 uses
TF-IDF for all similarity tasks.

**Approach:** For each new proposal, compute TF-IDF drift against each
near-miss's `new_text`. If `1 - drift > threshold` → skip (too similar
to a previously rejected edit).

```python
def deduplicate_proposals(proposals, near_misses, threshold=0.85):
    result = []
    for proposal in proposals:
        is_dup = False
        for nm in near_misses:
            drift = compute_drift_tfidf(proposal.new_text, nm.new_text)
            similarity = 1.0 - drift
            if similarity > threshold:
                is_dup = True
                logger.info(
                    "Dedup: skipping proposal (similarity=%.2f vs near-miss)",
                    similarity,
                )
                break
        if not is_dup:
            result.append(proposal)
    # also deduplicate within proposals themselves
    seen: list[str] = []
    final = []
    for p in result:
        if p.new_text not in seen:
            seen.append(p.new_text)
            final.append(p)
    return final
```

### 7.2 Where Near-Misses Come From

Near-misses are previously **rejected** or **near-miss** proposals from
the promotion gate. The `GateAuditLog` (M4) stores audit entries as
JSONL. Each entry has `decision` (`promote`/`reject`/`near_miss`).

The caller (CLI/loop) queries the audit log for recent near-miss/reject
entries, reconstructs `EditProposal` objects from the stored data, and
passes them to `deduplicate_proposals()`.

For v0.1.0, the audit log entry does not store the full `EditProposal`
— it stores `edit_id`, `decision`, `reason`. To support dedup, the
caller should also store the proposal's `new_text` in the audit entry
when logging. **This is a small enhancement to `GateAuditLog.log()`
in M4 — add a `proposal_text` field to the audit entry.**

Alternatively, for v0.1.0, the caller passes an empty near-miss list
(first run has no history). Dedup against near-misses is a Phase 2
optimization. The function handles empty near-misses gracefully (all
proposals kept).

### 7.3 Edge Cases

| Case | Result |
|------|--------|
| No near-misses | All proposals kept |
| Identical proposals (same `new_text`) | First kept, rest skipped (intra-dedup) |
| Proposal similar to near-miss (sim > 0.85) | Skipped |
| Proposal dissimilar to all near-misses | Kept |
| Empty proposals list | Return `[]` |

### 7.4 Deviation Note

The ticket says "embedding similarity" but we use TF-IDF (DD-13). This
is a documented deviation consistent with the v0.1.0 design decision.
Document as DD-19.

## 8. Batch Analysis (#50)

```python
def analyze_batch(
    traces: list[Trace],
    current_prompt: str,
    frozen_sections: list[str] | None,
    llm_provider: LLMProvider,
    max_proposals: int = 3,
) -> list[EditProposal]:
```

### 8.1 Flow

1. Filter to **failed** traces only (`trace.success is False`).
2. No failures → return `[]` (no LLM call, no cost).
3. Build the prompt via `build_analyzer_prompt(current_prompt, failed, max_proposals)`.
4. Call `analyze()` → get raw proposals.
5. Truncate to `max_proposals` (don't re-call the LLM).
6. Validate each proposal via `validate_proposal()` → drop invalid ones.
7. Deduplicate against near-misses (if available) via `deduplicate_proposals()`.
8. Return the final list.

### 8.2 Pattern Grouping

The LLM itself does pattern grouping — the prompt instructs it to
"identify failure patterns" and "propose ONE edit per pattern." The
code doesn't implement explicit clustering; it relies on the LLM's
reasoning. This is the PRD's intent (DD-14, DD-15).

Why not cluster in code?
- The LLM sees the traces and can identify semantic patterns
  ("all 5 traces misclassify billing/technical overlap") that
  rule-based clustering would miss.
- Clustering adds complexity and its own failure modes.
- The max-3-proposals constraint bounds cost regardless.

### 8.3 Cost Tracking Integration

`analyze_batch()` tracks token cost:

```python
prompt_text = build_analyzer_prompt(current_prompt, failed, max_proposals)
prompt_tokens = estimate_tokens(prompt_text)

# pre-call ceiling check
pre_cost = estimate_cost(prompt_tokens)
if pre_cost > config.analyzer.cost_ceiling_usd:
    logger.warning("Analyzer: pre-call cost %.4f exceeds ceiling %.4f", pre_cost, ceiling)
    return []  # abort before spending

proposals = analyze(failed, current_prompt, frozen_sections, llm_provider)
response_tokens = estimate_tokens(json_response)
total_cost = estimate_cost(prompt_tokens + response_tokens)

if total_cost > ceiling:
    logger.warning("Analyzer: post-call cost %.4f exceeds ceiling %.4f", total_cost, ceiling)
    # return partial results (don't discard work already done)

return proposals[:max_proposals]
```

### 8.4 Relationship to `analyze()`

`analyze_batch()` is a thin wrapper around `analyze()`:

| `analyze()` | `analyze_batch()` |
|---|---|
| Raw: LLM call + parse | Orchestration: filter, call `analyze()`, validate, dedup, truncate |
| No cost tracking | Cost tracking + ceiling |
| No validation | Runs `validate_proposal()` on each |
| No dedup | Runs `deduplicate_proposals()` |
| No max limit | Enforces `max_proposals` |

The CLI loop (M9) calls `analyze_batch()`, not `analyze()` directly.

## 9. MockAnalyzer + Cost Tracking (#51)

### 9.1 MockAnalyzer

```python
class MockAnalyzer:
    """Returns predetermined proposals; never calls an LLM.

    Used in hermetic CI tests. Zero LLM calls → zero cost.
    """

    def __init__(self, proposals: list[EditProposal] | None = None):
        self._proposals = proposals or []
        self.calls = 0
        self.total_tokens = 0
        self.total_cost = 0.0

    def analyze(
        self,
        traces: list[Trace],
        current_prompt: str,
        frozen_sections: list[str] | None,
        llm_provider: LLMProvider,
    ) -> list[EditProposal]:
        self.calls += 1
        return list(self._proposals)

    def analyze_batch(
        self,
        traces: list[Trace],
        current_prompt: str,
        frozen_sections: list[str] | None,
        llm_provider: LLMProvider,
        max_proposals: int = 3,
    ) -> list[EditProposal]:
        self.calls += 1
        return list(self._proposals)[:max_proposals]
```

Design notes:
- `MockAnalyzer` does **not** extend `LLMProvider` — it replaces the
  whole analysis pipeline, not just the LLM call.
- The `llm_provider` parameter is accepted but **ignored** — the mock
  returns predetermined proposals regardless.
- `calls` counter verifies the analyzer was invoked (test assertions).
- `total_tokens` and `total_cost` stay at 0 (no LLM call) — the cost
  ceiling never trips for the mock.

### 9.2 Cost Tracking in `analyze_batch()`

Reuse `estimate_tokens()` and `estimate_cost()` from `ab_test.py`:

```python
from .ab_test import estimate_tokens, estimate_cost

# in analyze_batch():
prompt_text = build_analyzer_prompt(current_prompt, failed, max_proposals)
prompt_tokens = estimate_tokens(prompt_text)
prompt_cost = estimate_cost(prompt_tokens)

if prompt_cost > ceiling:
    logger.warning("Analyzer cost ceiling exceeded before LLM call")
    return []

# ... LLM call ...
response_tokens = estimate_tokens(response)
total_cost = estimate_cost(prompt_tokens + response_tokens)

if total_cost > ceiling:
    logger.warning(
        "Analyzer cost %.4f exceeds ceiling %.4f — returning partial results",
        total_cost, ceiling,
    )
```

- Check **before** the LLM call (prompt tokens are known).
- Check **after** the LLM call (response tokens added).
- If ceiling exceeded post-call → log warning, return partial results
  (don't discard work already done).
- `MockAnalyzer` → cost is always 0 (no LLM call) → ceiling never trips.

### 9.3 Cost Ceiling Location

`AnalyzerConfig.cost_ceiling_usd` (default 0.50) is **per-analysis-run**.
This is separate from `ABTestConfig.cost_ceiling_usd` (default 0.10)
which is **per-A/B-test**. Keep them separate — the analyzer cost is
the LLM call to review traces; the A/B test cost is the LLM calls to
run tasks against both prompts.

### 9.4 Cost Data in Config

```yaml
analyzer:
  max_proposals_per_batch: 3
  cost_ceiling_usd: 0.50   # per analysis run
```

Validation (already implemented in M1):
- `cost_ceiling_usd > 0`
- `max_proposals_per_batch >= 1`

## 10. Test Strategy

### 11.1 Hermetic Tests (CI-safe, no LLM calls)

All tests use `MockProvider` with predetermined JSON responses.

| Test | What it covers |
|------|----------------|
| `test_edit_proposal_fields` | #45 — verify `EditProposal` dataclass exists with all fields |
| `test_analyze_empty_traces` | #47 — empty traces → `[]`, no LLM call |
| `test_analyze_valid_json` | #47 — MockProvider returns JSON array → parses to `EditProposal` list |
| `test_analyze_invalid_json` | #47 — MockProvider returns non-JSON → `AnalyzerError` |
| `test_analyze_malformed_proposal` | #47 — JSON object missing `hypothesis` → skipped, rest kept |
| `test_analyze_markdown_fences` | #47 — response wrapped in ```` ```json ``` ```` → stripped, parsed |
| `test_analyze_llm_failure` | #47 — `ProviderError` → `AnalyzerError` |
| `test_annotate_prompt_no_frozen` | #46 — no frozen sections → no `[FROZEN]` markers |
| `test_annotate_prompt_with_frozen` | #46 — frozen lines get `[FROZEN]` prefix |
| `test_build_analyzer_prompt` | #46 — assembled prompt contains annotated prompt + traces + format instructions |
| `test_validate_proposal_all_valid` | #48 — valid proposal → empty error list |
| `test_validate_proposal_section_empty` | #48 — empty section → error |
| `test_validate_proposal_old_text_not_found` | #48 — old_text not in prompt → error |
| `test_validate_proposal_frozen_section` | #48 — section is frozen → error |
| `test_validate_proposal_all_errors` | #48 — multiple errors returned at once |
| `test_dedup_no_near_misses` | #49 — empty near-misses → all kept |
| `test_dedup_identical_proposals` | #49 — same new_text → intra-dedup |
| `test_dedup_similar_to_near_miss` | #49 — similarity > 0.85 → skipped |
| `test_dedup_different_kept` | #49 — low similarity → kept |
| `test_analyze_batch_no_failures` | #50 — all traces succeed → `[]` |
| `test_analyze_batch_max_proposals` | #50 — 5 proposals returned, max 3 → truncated to 3 |
| `test_analyze_batch_validates` | #50 — invalid proposals dropped after analysis |
| `test_mock_analyzer_no_llm` | #51 — MockAnalyzer.calls == 1, no LLM provider used |
| `test_mock_analyzer_returns_predetermined` | #51 — returns the proposals it was given |
| `test_cost_tracking_ceiling` | #51 — cost ceiling exceeded → abort / partial results |

### 11.2 LLM Tests (manual, CI-skipped)

Not in scope for v0.1.0 hermetic CI. The field test (M10) covers real
LLM analyzer quality.

## 11. Architecture Diagram

```
Failed Traces (from TraceStore)
        │
        ▼
┌───────────────────────┐
│  analyze_batch()      │
│  1. filter failed     │
│  2. build prompt      │── annotate_prompt() ── frozen_line_indexes()
│  3. cost pre-check    │── estimate_tokens() / estimate_cost()
│  4. call analyze()    │
│  5. truncate max      │
│  6. validate each     │── validate_proposal() ── parse_frozen_sections()
│  7. deduplicate       │── deduplicate_proposals() ── compute_drift_tfidf()
│  8. return            │
└───────────┬───────────┘
            │
            ▼
     list[EditProposal]
            │
            ▼
   (A/B Test Engine → Promotion Gate → Registry)
```

## 12. Design Decisions

- **DD-14** — Analyzer prompt includes frozen annotations (prevents wasted A/B runs on frozen content)
- **DD-15** — Max 3 proposals per batch (bounds A/B cost per cycle)
- **DD-13** — TF-IDF for similarity (applies to dedup as well as drift)
- **DD-19** — Dedup uses TF-IDF similarity, not embedding (ticket says "embedding" but v0.1.0 uses TF-IDF per DD-13; no embedding provider interface exists)

## 13. Build Order

1. D7 design doc (this file) → anchor decisions
2. #45 → verify `EditProposal` exists, close as pre-done
3. #46 → analyzer prompt template + `annotate_prompt()` + `format_traces()` + `build_analyzer_prompt()`
4. #47 → `analyze()` runner (LLM call + JSON parse + `_extract_json` + `_build_proposal`)
5. #48 → `validate_proposal()` (5 checks, all errors at once)
6. #49 → `deduplicate_proposals()` (TF-IDF similarity + intra-dedup)
7. #50 → `analyze_batch()` (filter, call analyze, truncate, validate, dedup, cost)
8. #51 → `MockAnalyzer` + cost tracking in `analyze_batch()`
9. Tests → `test_analyzer.py` (all hermetic via MockProvider)
10. Exit gate + WBS + close tickets