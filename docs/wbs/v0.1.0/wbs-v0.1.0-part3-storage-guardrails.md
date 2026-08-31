# WBS — AgentSelfEdit v0.1.0 Part 3: Storage & Guardrails

> **Milestones covered:** M5 (Prompt Registry) · M6 (Guardrail Module)
> **PRD coverage:** [F-05](../../design/prd/05-features.md) (registry), [F-12](../../design/prd/05-features.md) (rollback), [F-06](../../design/prd/05-features.md) (frozen sections), [F-07](../../design/prd/05-features.md) (edit distance)
> **CUJs covered:** CUJ 3 (trace lineage), CUJ 4 (rollback), CUJ 9 (custom guardrails)
> **Dependency:** M5 (depends on M4) → M6 (depends on M5)
> **Issue Range:** #32–#44

---

## Milestone 5: Prompt Registry (#32–#38)

**Objective:** Versioned store of every prompt with full lineage, diff, rollback, and integrity. File-based — no external database.

### M5 Design Documents

- **D5 — Prompt registry design** (`docs/design/prompt-registry-design.md`): file-based registry format, version metadata schema, diff computation, rollback semantics, integrity checks, registry locking.
- **D13 — Design decisions:** DD-11 (file-based registry), DD-12 (SHA-256 integrity).

### M5 Task Checklist

| # | Task | Build (files) | Behavior + edge cases | Feature | Design Ref | Verify | Status |
|---|------|---------------|----------------------|---------|------------|--------|--------|
| 1 | Registry store | `src/agent_self_edit/registry.py`: `Registry.__init__(path)`, `current_version`, `current_prompt` | Version `v{N}.md` + `v{N}.meta.json`; directory created on init; empty registry → version 0, empty prompt; path doesn't exist → created | F-05 | [D5](../../design/prompt-registry-design.md) | init with/without existing path; empty registry | [#32](https://github.com/deghosal-2026/agent-self-edit/issues/32) · ✅ |
| 2 | Version metadata | `Meta` dataclass: version, timestamp, sha256_hash, diff_from_previous, hypothesis, ab_results, gate_result, trigger_trace_ids, model_version, token_cost | SHA-256 computed on write; hash verified on read; all fields optional except version, timestamp, hash; JSON serialization round-trips | F-05 | [D5](../../design/prompt-registry-design.md) | JSON round-trip; hash verification; all fields optional | [#33](https://github.com/deghosal-2026/agent-self-edit/issues/33) · ✅ |
| 3 | Create version | `Registry.create(prompt_text, **metadata) -> int` | Writes prompt file + meta file; increments version; returns version number; concurrent writes blocked by lock; empty prompt text accepted | F-05 | [D5](../../design/prompt-registry-design.md) | create increments version; concurrent writes blocked; empty prompt | [#34](https://github.com/deghosal-2026/agent-self-edit/issues/34) · ✅ |
| 4 | Diff computation | `Registry.diff(v1, v2) -> DiffResult` | Line-level diff; output: added[], removed[], modified[], unchanged_count, frozen_unchanged_count; v1=v2 → empty diff; invalid versions → `RegistryError` | F-05 | [D5](../../design/prompt-registry-design.md) | identical/different; invalid versions; frozen sections | [#35](https://github.com/deghosal-2026/agent-self-edit/issues/35) · ✅ |
| 5 | Rollback | `Registry.rollback(version, reason) -> int` | Creates new version as copy of target; rollback reason + target version stored in metadata; invalid version → `RegistryError`; rollback to current → creates identical copy | F-12 | [D5](../../design/prompt-registry-design.md) | rollback to valid/invalid/current version; metadata preserved | [#36](https://github.com/deghosal-2026/agent-self-edit/issues/36) · ✅ |
| 6 | Lineage query | `Registry.lineage(from_version=None) -> list[Meta]`, `Registry.get(version) -> (str, Meta)` | Lineage returns ordered list; `get()` returns prompt + metadata; invalid version → `RegistryError`; lineage from version N returns N..current | F-05 | [D5](../../design/prompt-registry-design.md) | full lineage; partial lineage; invalid version | [#37](https://github.com/deghosal-2026/agent-self-edit/issues/37) · ✅ |
| 7 | Integrity check | `Registry.verify_integrity() -> list[str]` | Recomputes SHA-256 for each version; returns list of corrupted versions; all intact → empty list; file tampered → detected | F-05 | [D5](../../design/prompt-registry-design.md) | all intact; one corrupted; all corrupted; empty registry | [#38](https://github.com/deghosal-2026/agent-self-edit/issues/38) · ✅ |

### M5 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Registry CRUD | 100% create/read/update operations correct | registry test suite |
| Diff accuracy | line-level diff correct on all known fixtures | diff test suite |
| Rollback integrity | rollback creates correct version; metadata preserved | rollback test suite |
| Integrity detection | 100% of tampered versions detected | integrity test suite |
| Coverage | > 92% | `--cov-fail-under=92` |

### M5 Out of Scope

- Guardrail module (M6), feedback analyzer (M7), diff visualization (M8), CLI (M9)

### M5 Exit Gate

- [x] Registry stores versions with metadata
- [x] Diff works between any two versions
- [x] Rollback creates a new version with rollback reason in lineage
- [x] Lineage is fully queryable
- [x] Integrity check detects corrupted versions
- [x] Ruff clean, mypy strict clean, all tests pass, coverage > 92%
- [x] **Design docs authored:** D5 (prompt-registry), D13 (DD-11/12)

### M5 Discrepancies Found (PRD-vs-Implementation Audit, 2026-08-30)

> During a PRD conformance audit, three discrepancies were found where the implemented M1-M5 code diverged from the PRD's original v0.1.0 intent. These are tracked as M5 milestone tickets and **must be fixed and closed before M6 begins**.

| # | Discrepancy | PRD Intent | Implemented | Ticket | Fix |
|---|-------------|------------|-------------|--------|-----|
| D-1 | Registry is file-based, not git-versioned | PRD §2.5: "Prompt registry is versioned in git. Git provides free diff, rollback, branching, merge. Registry is a thin layer on top" | File-based `v{N}.md` + `v{N}.meta.json` (DD-11), no git backing | [#81](https://github.com/deghosal-2026/agent-self-edit/issues/81) · ✅ | Git-backed: each `create()`/`rollback()` auto-commits when registry is in a git work tree; `commit_sha` stored in metadata; file-only fallback preserved |
| D-2 | Config is YAML-only | PRD F-13: "YAML/TOML configuration for guardrail thresholds, sample floors, trigger modes, held-out task set path" | `load_config` handles YAML only (DD-02) | [#82](https://github.com/deghosal-2026/agent-self-edit/issues/82) · ✅ | TOML support added (`tomllib`), auto-detected by `.toml` extension; YAML stays default |
| D-3 | Guardrail logic lives inside gate.py | PRD 02-architecture §2.2.5: standalone Guardrail Module (M6) enforcing F-06/F-07 | Frozen-section parse, edit-distance, drift embedded in `gate.py` from M4 | [#83](https://github.com/deghosal-2026/agent-self-edit/issues/83) · ✅ | Extracted to `src/agent_self_edit/guardrails.py`; gate re-imports primitives; reusable by M7/M8 |

**Gate:** all three tickets (#81, #82, #83) closed + audit re-run confirms alignment before M6 starts. ✅ Verified 2026-08-30: ruff clean, mypy strict clean, 273 tests, 94.1% coverage.

**Dependency:** M4. **Produces for M6+:** `Registry`, `Meta`, `DiffResult`, `create()`, `diff()`, `rollback()`, `lineage()`, `verify_integrity()`.

---

## Milestone 6: Guardrail Module (#39–#44)

**Objective:** Constraint enforcement. The guardrails are deterministic code, not LLM-judged. They prevent the analyzer from making unsafe edits.

### M6 Design Documents

- **D6 — Guardrail module design** (`docs/design/guardrail-module-design.md`): frozen section annotation format, edit-distance calculation, TF-IDF drift calculation, per-section drift, guardrail report format, near-miss log format.
- **D13 — Design decisions:** DD-13 (TF-IDF drift for v0.1.0, embedding in v0.2.0).

### M6 Task Checklist

| # | Task | Build (files) | Behavior + edge cases | Feature | Design Ref | Verify | Status |
|---|------|---------------|----------------------|---------|------------|--------|--------|
| 1 | Frozen section parser | `parse_frozen_sections(prompt_text) -> list[FrozenSection]` | Parse `<!-- frozen -->` annotations; `FrozenSection`: start_line, end_line, section_name; no frozen sections → empty list; malformed annotation → `GuardrailError` | F-06 | [D6](../../design/guardrail-module-design.md) | single/multiple/no frozen sections; malformed | [#39](https://github.com/deghosal-2026/agent-self-edit/issues/39) · ⬜ |
| 2 | Frozen section validator | `validate_frozen_sections(prompt_text, frozen_sections) -> bool` | Verify frozen sections exist in current prompt; section renumbered after edit → fail; all sections match → pass | F-06 | [D6](../../design/guardrail-module-design.md) | sections exist/don't exist; renumbered after edit | [#40](https://github.com/deghosal-2026/agent-self-edit/issues/40) · ⬜ |
| 3 | Edit-distance calculator | `compute_edit_distance(old_prompt, new_prompt) -> EditDistance` | `EditDistance`: lines_added, lines_removed, lines_modified, total, frozen_lines_changed; identical prompts → 0 total; completely different → all lines changed; frozen section changes counted separately | F-07 | [D6](../../design/guardrail-module-design.md) | identical/different; frozen vs non-frozen changes | [#41](https://github.com/deghosal-2026/agent-self-edit/issues/41) · ⬜ |
| 4 | TF-IDF drift calculator | `compute_drift_tfidf(prompt_a, prompt_b) -> float` | TF-IDF vectorization; cosine similarity; drift = 1 - similarity; range [0, 1]; identical prompts → drift = 0; completely different → drift ≈ 1; symmetric | F-04 | [D6](../../design/guardrail-module-design.md) | identical/different/similar; symmetry verified | [#42](https://github.com/deghosal-2026/agent-self-edit/issues/42) · ⬜ |
| 5 | Drift calculator (embedding) | `compute_drift_embedding(prompt_a, prompt_b, llm_provider) -> float` | Sentence embedding via LLM provider; cosine similarity; falls back to TF-IDF if embedding unavailable | F-04 | [D6](../../design/guardrail-module-design.md) | embedding vs TF-IDF; fallback on failure | [#43](https://github.com/deghosal-2026/agent-self-edit/issues/43) · ⬜ |
| 6 | Per-section drift + guardrail report | `compute_per_section_drift(prompt_a, prompt_b, sections) -> dict[str, float]`; `GuardrailReport` dataclass | Per-section drift computed; `GuardrailReport.__str__()` human-readable; `__repr__()` machine-readable | F-06, F-07 | [D6](../../design/guardrail-module-design.md) | per-section drift; report formatting | [#44](https://github.com/deghosal-2026/agent-self-edit/issues/44) · ⬜ |

### M6 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Frozen section parsing | 100% of valid annotations parsed correctly | parser test suite |
| Edit distance | 100% accurate on known diffs | distance test suite |
| TF-IDF drift | symmetric, range [0,1], identical = 0 | drift test suite |
| Embedding drift | fallback to TF-IDF works | embedding test suite |
| Report formatting | human-readable and machine-readable output | report test suite |
| Coverage | > 92% | `--cov-fail-under=92` |

### M6 Out of Scope

- Feedback analyzer (M7), diff visualization (M8), CLI (M9), near-miss logger (part of M4)

### M6 Exit Gate

- [ ] Frozen sections are parsed and validated correctly
- [ ] Edit distance is accurate for all cases
- [ ] TF-IDF drift is computed correctly (symmetric, range [0,1])
- [ ] Embedding drift works with TF-IDF fallback
- [ ] Per-section drift is accurate
- [ ] Guardrail report is human-readable
- [ ] Ruff clean, mypy strict clean, all tests pass, coverage > 92%
- [ ] **Design docs authored:** D6 (guardrail-module), D13 (DD-13)

**Dependency:** M5. **Produces for M7+:** `parse_frozen_sections()`, `compute_edit_distance()`, `compute_drift_tfidf()`, `compute_drift_embedding()`, `GuardrailReport`.