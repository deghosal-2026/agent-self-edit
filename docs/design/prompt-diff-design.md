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

```
Guardrail check — Edit #7:
┌──────────────────────────────────────────────────────┐
│  ✅ Frozen core sections   — 12 lines untouched      │
│  ✅ Edit-distance limit    — 3 lines changed (max 5) │
│  ✅ Drift threshold        — 0.12 (max 0.30)         │
│  ✅ Sample floor           — 78 trials (min 50)      │
│  ✅ Effect size            — +12.4% (min 5%)         │
│  ✅ Confidence interval    — p<0.01                  │
│                                                      │
│  All guardrails passed. Edit promoted to v7.         │
└──────────────────────────────────────────────────────┘
```

**Rejected edit guardrail report:**

```
Guardrail check — Edit #8 (REJECTED):
┌──────────────────────────────────────────────────────┐
│  ✅ Frozen core sections   — 12 lines untouched      │
│  ✅ Edit-distance limit    — 2 lines changed (max 5) │
│  ❌ Drift threshold        — 0.35 (max 0.30)         │
│  ✅ Sample floor           — 60 trials (min 50)      │
│  ❌ Effect size            — +2.1% (min 5%)          │
│  ❌ Confidence interval    — p<0.15 (min p<0.05)     │
│                                                      │
│  3 guardrails failed. Edit archived.                 │
│  Near-miss: similar edit proposed 2 times before.    │
└──────────────────────────────────────────────────────┘
```

## 3. Output Surfaces

### 3.1 CLI

```
$ agent-self-edit diff v6 v7

Edit #7 — Promoted ⭐
+12.4% accuracy (p<0.01, n=78)

  -When classifying tickets, check the subject line first.
  +When classifying tickets, check the subject line + body first.

  -For ambiguous cases, flag for human review.
  +For ambiguous cases, check the user's history before flagging.

  Frozen core: 12 lines unchanged.
  Rollback: agent-self-edit rollback --version 6
```

```
$ agent-self-edit guardrails --history

Edit #7  ✅ All passed    Promoted   3 lines changed
Edit #8  ❌ 3 failed     Rejected   2 lines changed (drift, effect, CI)
Edit #9  ✅ All passed    Promoted   1 line changed
```

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