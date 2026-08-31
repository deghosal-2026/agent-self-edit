# Prompt Diff Visualization — Design

> How the user sees what changed, what stayed the same, and why.

## 1. Why This Matters

Self-edit is invisible by default. The prompt changes, but the user has no way to see what happened unless we show them. Without a diff visualization, the system is a black box — the user doesn't know if the edit was a one-word tweak or a complete rewrite, whether the guardrails held, or whether the change was justified.

The diff visualization is how the user trusts the system. It answers three questions on every edit cycle:

1. **What changed?** — The exact before/after of the prompt, line by line.
2. **What stayed the same?** — Frozen core sections, guardrails, and unchanged instructions.
3. **Why was it promoted or rejected?** — The evidence that justified or blocked the change.

## 2. The Three Visual Signals

### 2.1 Prompt Diff — Before vs. After

Every edit cycle produces a side-by-side or inline diff of the prompt. The user sees exactly which lines were added, removed, or modified.

**Side-by-side view (default):**

```
┌──────────────────────────────────────────────────────────────────┐
│  Edit #7 — Promoted  ⭐  (+12.4% accuracy, p<0.01, n=78)      │
├──────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────┐  ┌────────────────────────────────┐  │
│  │ BEFORE (v6)            │  │ AFTER (v7)                     │  │
│  │                        │  │                                │  │
│  │ You are a classifier   │  │ You are a classifier           │  │
│  │ assistant.             │  │ assistant.                     │  │
│  │                        │  │                                │  │
│  │ When classifying       │  │ When classifying               │  │
│  │ tickets, check the     │  │ tickets, check the subject     │  │
│  │ subject line first.    │  │ line + body first.             │  │
│  │                        │  │                                │  │
│  │▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐│  │▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐│  │
│  │▐▐ FROZEN CORE ▐▐▐▐▐▐▐▐▐▐▐▐▐▐│  │▐▐ FROZEN CORE ▐▐▐▐▐▐▐▐▐▐▐▐▐▐│  │
│  │▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐│  │▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐▐│  │
│  │                        │  │                                │  │
│  │ For ambiguous cases,   │  │▐ For ambiguous cases, check    │  │
│  │ flag for human review. │  │▐ the user's history before     │  │
│  │                        │  │▐ flagging for review.          │  │
│  │                        │  │                                │  │
│  └────────────────────────┘  └────────────────────────────────┘  │
│                                                                │
│  🟢 +1 line added    🔴 -1 line removed    🟡 1 line modified  │
│  ⚪ 12 lines unchanged (frozen core preserved)                  │
│                                                                │
│  Diff: agent-self-edit diff v6..v7                             │
│  Rollback: agent-self-edit rollback --version 6                 │
└──────────────────────────────────────────────────────────────────┘
```

**Inline view (toggle):**

```
--- v6    2026-09-01 10:00:00
+++ v7    2026-09-01 18:00:00
@@ -1,5 +1,6 @@
 You are a classifier assistant.
 
-When classifying tickets, check the subject line first.
+When classifying tickets, check the subject line + body first.
 
 (frozen core — 12 lines unchanged)
 
-For ambiguous cases, flag for human review.
+For ambiguous cases, check the user's history before flagging for review.
```

**Color coding:**
- 🟢 **Green** — Lines added
- 🔴 **Red** — Lines removed
- 🟡 **Yellow** — Lines modified (changed but not wholly new)
- ⚪ **White** — Lines unchanged
- 🔲 **Gray** — Frozen core sections (never change)

### 2.2 Edit Density Over Time

A heatmap next to the prompt shows which sections change most over time. If the same section keeps getting edited, that is a signal the instruction is unstable — the analyzer hasn't found the right wording yet.

```
Section edit frequency (last 20 cycles):
┌──────────────────────────────────────────────────┐
│  Role definition      ████░░░░░░░░░░  4 edits    │
│  Classification rule  ████████████░░  12 edits   │
│  Ambiguity handling   ████████████░░  11 edits   │
│  Output format        ██░░░░░░░░░░░░  2 edits    │
│  Frozen core          ░░░░░░░░░░░░░░  0 edits    │
└──────────────────────────────────────────────────┘
```

**Interpretation:**
- High-frequency sections (many edits) suggest the instruction is unstable or the task is hard to specify. The user may want to rewrite the section from scratch.
- Low-frequency sections (few edits) suggest the instruction is stable and working well.
- Frozen core sections should always show 0 edits. Any non-zero is a guardrail failure.

### 2.3 No-Change Evidence — Guardrails Checked and Passed

Every edit cycle produces a guardrail report showing what was checked and what passed. This proves the system didn't change randomly — it changed within constraints.

The CLI render is an **aligned text table** (PRD M8.2, ticket #53) — not a
box-draw card. Columns: check name, passed/failed, value, threshold. Summary
line "All passed" or "N failed".

```
Guardrail check — Edit #7:
  Check                 Result   Value       Threshold
  --------------------  -------  ----------  ----------
  Frozen core sections  ✅ pass  12 lines    0 (must not change)
  Edit-distance limit   ✅ pass  3 lines     5 lines
  Drift threshold       ✅ pass  0.12        0.30
  Sample floor          ✅ pass  78 trials   50 trials
  Effect size           ✅ pass  +12.4%      +5%
  Confidence interval   ✅ pass  p<0.01      p<0.05
  All guardrails passed. Edit promoted to v7.
```

**Rejected edit guardrail report:**

```
Guardrail check — Edit #8 (REJECTED):
  Check                 Result   Value       Threshold
  --------------------  -------  ----------  ----------
  Frozen core sections  ✅ pass  12 lines    0 (must not change)
  Edit-distance limit   ✅ pass  2 lines     5 lines
  Drift threshold       ❌ fail  0.35        0.30
  Sample floor          ✅ pass  60 trials   50 trials
  Effect size           ❌ fail  +2.1%       +5%
  Confidence interval   ❌ fail  p<0.15      p<0.05
  3 guardrails failed. Edit archived.
  Near-miss: similar edit proposed 2 times before.
```

Table rules:
- Value/threshold formatting is function-selected (ints shown as ints, floats to 3 dp, p-values to 2 dp, effect size as %).
- The exact column widths are computed from content (left-aligned name, centered Result, right-aligned Value/Threshold).
- Color: pass rows green, fail rows red (see §3.1 color modes).

## 3. Output Surfaces

### 3.1 CLI

**Edit summary is a single line** (PRD M8.3, ticket #54):

```
Edit #7 — Promoted — +12.4% accuracy (p<0.01, n=78) — 3 lines
```

Template: `Edit #{N} — {decision} — {±X.X%} accuracy (p<{val}, n={trials}) — {N} line(s)`

| Decision | Line renders |
|----------|--------------|
| `promote` | `Edit #7 — Promoted — +12.4% accuracy (p<0.01, n=78) — 3 lines` |
| `reject` | `Edit #8 — Rejected — (drift, effect, CI) — 2 lines` |
| `near_miss` | `Edit #9 — Near-miss — (drift) — 1 line` |
| rollback event | `Edit #10 — Rollback — reverted to v6 — 0 lines` |

- Promoted line includes the A/B result (`effect_size` %, `p_value`, `n_trials`).
- Rejected/near-miss include the failed check names (from `GateResult.checks`).
- Singular/plural handled (`1 line` vs `3 lines`).

```
$ agent-self-edit diff v6 v7

Edit #7 — Promoted — +12.4% accuracy (p<0.01, n=78) — 3 lines
  diff: -When classifying tickets, check the subject line first.
        +When classifying tickets, check the subject line + body first.
  Frozen core: 12 lines unchanged.
  Rollback: agent-self-edit rollback --version 6
```

```
$ agent-self-edit guardrails --history

Edit #7  ✅ All passed    Promoted   3 lines changed
Edit #8  ❌ 3 failed     Rejected   2 lines changed (drift, effect, CI)
Edit #9  ✅ All passed    Promoted   1 line changed
```

### 3.1.1 Color Modes (`--color auto|always|never`)

| Mode | Behavior |
|------|----------|
| `auto` | Detect TTY (e.g. `click` context; if stdout is a TTY) → color, else plain |
| `always` | Force color (ANSI codes) even when piped |
| `never` | Plain text — **no ANSI characters emitted at all** |

- Colors (per DD-02): added lines green, removed lines red, modified yellow,
  unchanged white, **frozen sections gray**.
- Use a small internal helper that wraps a string in ANSI only when the
  active mode allows it. `click.style(text, fg=...)` is the renderer; the
  mode gate decides whether to pass the color through or return plain text.

### 3.1.2 Markdown Output (`--format markdown`)

| Surface | Markdown form |
|---------|---------------|
| Inline diff | fenced code block ```` ```diff ````  with `-`/`+` lines |
| Side-by-side | two-col table? — no; keep inline fenced block (side-by-side not representable cleanly) |
| Guardrail report | markdown table (`\| Check \| Result \| Value \| Threshold \|`) |
| Edit summary | plain line (no special markdown) |
| Edit density | fenced code block with the bar chart |

Edge cases:
- Identical prompts → single line `no changes` (both plain + markdown).
- Empty registry / no history → density chart is empty (zero-height bar block).

### 3.2 Dashboard (Web UI)

The dashboard shows:
- **Timeline view** — scrollable history of every edit, color-coded by promoted/rejected
- **Prompt diff view** — side-by-side or inline diff for any two versions
- **Edit density heatmap** — per-section edit frequency over configurable time windows
- **Guardrail pass/fail chart** — stacked bar chart of guardrail results per edit cycle
- **Rollback button** — one-click rollback to any previous version with confirmation dialog

### 3.3 API

```
GET /api/v1/edits?version_from=6&version_to=7
→ { diff: { added: [...], removed: [...], modified: [...] },
    guardrails: { passed: [...], failed: [] },
    evidence: { improvement: 0.124, p_value: 0.008, n_trials: 78 },
    rollback: "agent-self-edit rollback --version 6" }

GET /api/v1/edits/density?window=20
→ { sections: [
    { name: "Role definition", edit_count: 4 },
    { name: "Classification rule", edit_count: 12 },
    ... ] }

GET /api/v1/guardrails?edit_id=8
→ { 
    frozen_core: { passed: true, untouched_lines: 12 },
    edit_distance: { passed: true, changed: 2, max: 5 },
    drift: { passed: false, score: 0.35, threshold: 0.30 },
    sample_floor: { passed: true, trials: 60, min: 50 },
    effect_size: { passed: false, improvement: 0.021, min: 0.05 },
    confidence: { passed: false, p_value: 0.15, threshold: 0.05 }
  }
```

## 4. Design Decisions

### DD-01: Diff granularity is line-level, not token-level

Token-level diffs are noisy and hard to read when the prompt changes meaningfully. Line-level diffs show the user exactly which instruction changed, which is what they need to evaluate the edit.

### DD-02: Frozen sections are visually distinct

Frozen core sections are always grayed out in the diff view. This makes it immediately obvious that the guardrails held — the user doesn't need to cross-reference against a config file.

### DD-03: Edit density is per-section, not per-character

Sections are delimited by the prompt's structure (paragraphs, bullet points, instruction blocks). Per-character density would be meaningless noise. Per-section density tells the user which parts of the prompt are stable and which are still being tuned.

### DD-04: Guardrail failures are shown alongside the diff, not in a separate report

The user should see the edit and the evidence for its promotion or rejection in the same view. Separating them would make it harder to understand why an edit was accepted or rejected.

## 5. Related

- [PRD 05 — Features](../prd/05-features.md) — Feature set including F-08 (diff view), F-09 (edit density), F-10 (guardrail report)
- [PRD 04 — Users and CUJs](../prd/04-users-and-cujs.md) — CUJ-01 (deploy, observe, improve), CUJ-04 (rollback), CUJ-08 (drift detection)

## 6. M8 Implementation Contract

> Signatures, consumed types, and test matrix for M8 (#52–#55). Mirrors the
> D7 pattern so the build is unambiguous.

### 6.1 Function Signatures

```python
# Module: src/agent_self_edit/diff.py

def format_diff_inline(diff_result: DiffResult, color: str = "never") -> str: ...
def format_diff_side_by_side(diff_result: DiffResult, color: str = "never") -> str: ...
def format_guardrail_report(gate_result: GateResult, color: str = "never") -> str: ...
def format_edit_summary(
    edit_id: str | int,
    gate_result: GateResult | None,
    ab_result: ABResult | None,
) -> str: ...
def format_edit_density(registry: Registry, window: int = 20) -> str: ...
def render_inline(diff_result: DiffResult, color: str = "never") -> str: ...
def render_guardrail_table(gate_result: GateResult, color: str = "never") -> str: ...
def render_density_bars(per_section: dict[str, int]) -> str: ...
def _color(text: str, mode: str, fg: str | None) -> str: ...
```

### 6.2 Consumed Types

| Type | Source | Used by |
|------|--------|---------|
| `DiffResult` (added/removed/modified/unchanged_count/frozen_unchanged_count) | `registry.py` (M5) | `format_diff_inline`, `format_diff_side_by_side` |
| `GateResult` (decision, checks: tuple[CheckResult]) | `types.py` (M4) | `format_guardrail_report`, `format_edit_summary` |
| `CheckResult` (name, passed, value, threshold, details) | `types.py` (M4) | `format_guardrail_report` |
| `ABResult` (effect_size, p_value, n_trials) | `ab_test.py` (M3) | `format_edit_summary` |
| `Registry.current_prompt` / `lineage()` for edit density | `registry.py` (M5) | `format_edit_density` |

### 6.3 Edge Cases

| Edge case | Output |
|-----------|--------|
| Identical prompts (`DiffResult` empty) | single line `no changes` (plain + markdown) |
| Empty registry / no history | density chart empty (zero bars) |
| `GateResult` with all pass | summary "All passed" |
| `GateResult` with some fail | summary "N failed" + failed check names |
| `decision == near_miss` | summary includes "(frozen/...) failed names" |
| p_value / effect formatting | p to 2 dp, effect as signed % to 1 dp |

### 6.4 Color Helper

```python
def _color(text: str, mode: str, fg: str | None) -> str:
    if mode == "never" or fg is None:
        return text
    if mode == "auto" and not sys.stdout.isatty():
        return text
    return click.style(text, fg=fg)
```

### 6.5 Test Matrix

| # | Test | Coverage |
|---|------|----------|
| T1 | `test_inline_identical_no_changes` | identical → `no changes` |
| T2 | `test_inline_added_removed_prefixes` | `- ` / `+ ` lines |
| T3 | `test_inline_frozen_annotation` | frozen → `(frozen)` / gray |
| T4 | `test_inline_color_modes` | auto/always/never ANSI presence |
| T5 | `test_side_by_side_two_column` | aligned columns |
| T6 | `test_side_by_side_frozen_grayed` | frozen grayed in both cols |
| T7 | `test_guardrail_table_format` | name/passed/value/threshold columns |
| T8 | `test_guardrail_all_passed_summary` | "All passed" |
| T9 | `test_guardrail_some_failed_summary` | "N failed" |
| T10 | `test_edit_summary_promoted_one_line` | one-line promoted template |
| T11 | `test_edit_summary_rejected_names` | rejected includes failed names |
| T12 | `test_edit_summary_near_miss` | near-miss render |
| T13 | `test_edit_density_empty` | empty registry → empty chart |
| T14 | `test_edit_density_bars` | bar chart width from counts |
| T15 | `test_markdown_diff_code_block` | `` ```diff `` block |
| T16 | `test_markdown_guardrail_table` | markdown table |
| T17 | `test_markdown_density_code_block` | fenced density |