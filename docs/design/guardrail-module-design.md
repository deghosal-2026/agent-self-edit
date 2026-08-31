# Guardrail Module Design

> Frozen section annotation format, edit-distance calculation, TF-IDF drift calculation, per-section drift, and guardrail report format for AgentSelfEdit v0.1.0.

## 1. Purpose

The guardrail module is the **deterministic constraint layer** (PRD 02-architecture §2.2.5). It is never LLM-judged. It produces the primitives the promotion gate consumes and the report the analyzer/diff surfaces. It prevents the analyzer from making unsafe edits.

## 2. Frozen Sections (F-06)

### 2.1 Annotation Format

A user marks a section that must never change using HTML-style markers:

```
Role section (FROZEN):
<!-- frozen: role -->
You are a careful, safety-first coding assistant.
Always verify before you modify.
<!-- frozen -->

Editable behavior section:
When explaining code, prefer concise examples.
```

- `<!-- frozen: name -->` opens a frozen span with an optional name.
- `<!-- frozen -->` (no name) defaults to name `core`.
- The span runs from the opening marker to the next marker or EOF.

### 2.2 Parser

```python
@dataclass(frozen=True)
class FrozenSection:
    start_line: int
    end_line: int
    section_name: str | None

parse_frozen_sections(prompt_text: str) -> list[FrozenSection]
```

- No frozen annotations → empty list.
- Malformed annotation (unbalanced marker) → `GuardrailError`.

### 2.3 Validator

```python
validate_frozen_sections(prompt_text: str, frozen_sections: list[str]) -> bool
```

- Pass if every requested section name exists in `prompt_text`.
- Fail if a requested section is missing.
- Fail if a named section's content was renumbered/reordered after an edit (line-span drift detected by comparing the section's content position).

## 3. Edit Distance (F-07)

```python
@dataclass(frozen=True)
class EditDistance:
    lines_added: int
    lines_removed: int
    lines_modified: int
    total: int
    frozen_lines_changed: int

compute_edit_distance(old_prompt: str, new_prompt: str) -> EditDistance
```

- `lines_added/removed/modified` from a line-level diff (SequenceMatcher).
- `total = added + removed + modified`.
- `frozen_lines_changed` counts changed lines that fall inside a frozen section.
- Identical prompts → `total == 0`.
- Completely different → all lines changed.

## 4. TF-IDF Drift (F-04; default v0.1.0)

```python
compute_drift_tfidf(prompt_a: str, prompt_b: str) -> float
```

- Tokenize lowercase `[a-z0-9_]+`.
- TF-IDF vectorization with smoothing (1 + n/d).
- Drift = `1 - cosine_similarity(a, b)`.
- Range `[0, 1]`; identical → 0; completely different → ≈1; symmetric.

## 5. Embedding Drift (v0.2.0; stubbed v0.1.0)

```python
compute_drift_embedding(prompt_a: str, prompt_b: str, llm_provider) -> float
```

- Attempts sentence embedding via the LLM provider.
- Falls back to `compute_drift_tfidf` on any failure or when embeddings are unsupported.

## 6. Per-Section Drift + Report (F-06, F-07)

```python
compute_per_section_drift(prompt_a, prompt_b, sections: list[FrozenSection]) -> dict[str, float]
```

- For each named section, drift between the section in prompt_a and the corresponding section in prompt_b.

```python
@dataclass
class GuardrailReport:
    ...
    __str__()   # human-readable table/summary
    __repr__()  # machine-readable JSON
```

## 7. Design Decisions

See DD-13 (TF-IDF drift for v0.1.0, embedding in v0.2.0) and DD-18 (standalone module) in `design-decisions.md`.