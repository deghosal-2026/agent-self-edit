# WBS — AgentSelfEdit v0.1.0 Part 3: Storage & Guardrails

> Part of the v0.1.0 release. See [index](wbs-v0.1.0-index.md) for milestone overview.
>
> **Milestones:** M5 (Prompt Registry) · M6 (Guardrail Module)
> **Dependency:** M5 → M6 (guardrails diff against registry)
> **Issue Range:** #31–#43

## M5 — Prompt Registry (#31–#37)

**Goal:** Versioned store of every prompt with full lineage, diff, rollback, and integrity.

### Design

| Task | Description | Deliverable |
|---|---|---|
| D5 | Design prompt registry | `docs/design/prompt-registry-design.md` — file-based registry format, version metadata schema, diff computation, rollback semantics, integrity checks, registry locking |

### Build

| Task | Description | Deliverable |
|---|---|---|
| M5.1 | Registry store | File-based registry at `registry_path/`. Each version: `v{N}.md` (prompt text), `v{N}.meta.json` (metadata). `Registry.__init__(path)`, `Registry.current_version -> int`, `Registry.current_prompt -> str` |
| M5.2 | Version metadata | `Meta` dataclass: version, timestamp, diff_from_previous, hypothesis, ab_results, gate_result, trigger_trace_ids, model_version, token_cost, sha256_hash |
| M5.3 | Create version | `Registry.create(prompt_text, hypothesis, ab_results, gate_result, trigger_trace_ids, model_version, token_cost) -> int` — writes prompt file, computes metadata, writes meta file, returns version number |
| M5.4 | Diff computation | `Registry.diff(v1, v2) -> DiffResult` — line-level diff. Output: added[], removed[], modified[], unchanged_count, frozen_unchanged_count |
| M5.5 | Rollback | `Registry.rollback(version, reason) -> int` — promotes a previous version to current. Creates a new version that is a copy of the target. Logs rollback reason and version. |
| M5.6 | Lineage query | `Registry.lineage(from_version=None) -> list[Meta]` — returns full history. `Registry.get(version) -> (str, Meta)` — returns prompt text and metadata. |
| M5.7 | Integrity check | `Registry.verify_integrity() -> list[str]` — verifies SHA-256 hash of each version. Returns list of corrupted versions. |
| M5.8 | Registry locking | File lock (`fcntl` or `portalocker`) during write operations. Prevents concurrent writes. Read operations are not locked. |

### Tests

| Task | Description | Files |
|---|---|---|
| T5.1 | Test registry CRUD | `tests/test_registry.py` — create version, read version, list versions, current_version returns correct value |
| T5.2 | Test version metadata | `tests/test_registry.py` — metadata fields are populated correctly, sha256 hash is computed correctly, hash changes when prompt changes |
| T5.3 | Test diff computation | `tests/test_registry.py` — diff identical prompts, diff completely different prompts, diff with one-line change, diff with frozen sections, diff with added/removed/modified lines |
| T5.4 | Test rollback | `tests/test_registry.py` — rollback creates new version, rollback returns correct prompt, lineage shows rollback, rollback with invalid version raises error |
| T5.5 | Test lineage query | `tests/test_registry.py` — full lineage, lineage from version, lineage with rollback, empty registry |
| T5.6 | Test integrity check | `tests/test_registry.py` — all versions valid, one version corrupted, corrupted version detected, multiple corrupted versions |
| T5.7 | Test registry locking | `tests/test_registry.py` — concurrent writes are serialized, concurrent reads are allowed, lock timeout raises error |

### Documentation

| Task | Description | Deliverable |
|---|---|---|
| M5.DOC1 | Registry reference | Create `docs/reference/registry.md` — registry format, version metadata, CLI commands for registry operations |
| M5.DOC2 | Update WBS index | Update `docs/wbs/v0.1.0/wbs-v0.1.0-index.md` with M5 status, issue links, exit gate results |

### M5 Exit Gate

- [ ] Design docs reviewed and committed
- [ ] Registry stores versions with metadata
- [ ] Diff works between any two versions
- [ ] Rollback creates a new version with rollback reason in lineage
- [ ] Lineage is fully queryable
- [ ] Integrity check detects corrupted versions
- [ ] Registry locking prevents concurrent write corruption
- [ ] Ruff clean, mypy strict clean
- [ ] All tests pass: `pytest` → 0 failures
- [ ] Coverage > 92%: `pytest --cov=agent_self_edit --cov-fail-under=92`

---

## M6 — Guardrail Module (#38–#43)

**Goal:** Constraint enforcement. The guardrails are deterministic code, not LLM-judged.

### Design

| Task | Description | Deliverable |
|---|---|---|
| D6 | Design guardrail module | `docs/design/guardrail-module-design.md` — frozen section annotation format, edit-distance calculation, TF-IDF drift calculation, per-section drift, guardrail report format, near-miss log format |

### Build

| Task | Description | Deliverable |
|---|---|---|
| M6.1 | Frozen section parser | `parse_frozen_sections(prompt_text) -> list[FrozenSection]` — parse `<!-- frozen -->` annotations. `FrozenSection`: start_line, end_line, section_name. |
| M6.2 | Frozen section validator | `validate_frozen_sections(prompt_text, frozen_sections) -> bool` — verify frozen sections exist in current prompt. |
| M6.3 | Edit-distance calculator | `compute_edit_distance(old_prompt, new_prompt) -> EditDistance` — diff, count: lines_added, lines_removed, lines_modified, total, frozen_lines_changed. |
| M6.4 | Drift calculator (TF-IDF) | `compute_drift_tfidf(prompt_a, prompt_b) -> float` — TF-IDF vectorization, cosine similarity. Drift = 1 - similarity. Range [0, 1]. |
| M6.5 | Drift calculator (embedding) | `compute_drift_embedding(prompt_a, prompt_b, llm_provider) -> float` — sentence embedding, cosine similarity. Falls back to TF-IDF if embedding unavailable. |
| M6.6 | Per-section drift | `compute_per_section_drift(prompt_a, prompt_b, sections: list[str]) -> dict[str, float]` — drift per named section. |
| M6.7 | Guardrail report | `GuardrailReport` dataclass: checks: list[CheckResult], summary: str, decision: str. Human-readable `__str__` and `__repr__`. |
| M6.8 | Near-miss logger | `NearMissLogger(path)` — append-only JSONL. `log(edit_id, edit_summary, failed_checks, passed_checks, rejection_reason)`. `query(edit_id)`, `list(limit=100)`. |

### Tests

| Task | Description | Files |
|---|---|---|
| T6.1 | Test frozen section parser | `tests/test_guardrails.py` — single frozen section, multiple sections, no frozen sections, malformed annotations, nested annotations |
| T6.2 | Test frozen section validator | `tests/test_guardrails.py` — sections exist in prompt, section missing from prompt, empty sections list |
| T6.3 | Test edit-distance calculator | `tests/test_guardrails.py` — identical prompts (0 distance), completely different prompts, one-line change, multi-line change, frozen section changes |
| T6.4 | Test TF-IDF drift | `tests/test_guardrails.py` — identical prompts (drift = 0), completely different prompts (drift ≈ 1), similar prompts, drift is symmetric |
| T6.5 | Test embedding drift | `tests/test_guardrails.py` — uses mock embedding provider, identical prompts (drift = 0), different prompts, fallback to TF-IDF |
| T6.6 | Test per-section drift | `tests/test_guardrails.py` — drift per section, sections with no changes, sections with changes, missing sections |
| T6.7 | Test guardrail report | `tests/test_guardrails.py` — all checks pass, some checks fail, all checks fail, report string formatting |
| T6.8 | Test near-miss logger | `tests/test_guardrails.py` — log entry, query by edit_id, list recent, append-only enforced, file rotation, concurrent writes |

### Documentation

| Task | Description | Deliverable |
|---|---|---|
| M6.DOC1 | Guardrails reference | Create `docs/reference/guardrails.md` — frozen section annotation format, guardrail configuration, drift calculation, near-miss log format |
| M6.DOC2 | Update WBS index | Update `docs/wbs/v0.1.0/wbs-v0.1.0-index.md` with M6 status, issue links, exit gate results |

### M6 Exit Gate

- [ ] Design docs reviewed and committed
- [ ] Frozen sections are parsed and validated correctly
- [ ] Edit distance is accurate for all cases
- [ ] TF-IDF drift is computed correctly
- [ ] Embedding drift works with fallback
- [ ] Per-section drift is accurate
- [ ] Guardrail report is human-readable
- [ ] Near-miss logger is append-only and queryable
- [ ] Ruff clean, mypy strict clean
- [ ] All tests pass: `pytest` → 0 failures
- [ ] Coverage > 92%: `pytest --cov=agent_self_edit --cov-fail-under=92`