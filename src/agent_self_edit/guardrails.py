"""Guardrail module: deterministic constraint primitives and report (F-06, F-07).

Frozen-section parsing, edit-distance calculation, TF-IDF drift, and the
guardrail report are the deterministic primitives the promotion gate, analyzer,
and diff visualization rely on. This is a standalone module per PRD
02-architecture §2.2.5 — never LLM-judged.
"""

from __future__ import annotations

import difflib
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Sequence

from .types import CheckResult


class GuardrailError(Exception):
    """Raised on malformed guardrail annotations."""


@dataclass(frozen=True)
class FrozenSection:
    """One frozen span within a prompt."""

    start_line: int
    end_line: int
    section_name: str | None = None
    lines: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EditDistance:
    """Line-level edit distance between two prompts, including frozen span counts."""

    lines_added: int = 0
    lines_removed: int = 0
    lines_modified: int = 0
    total: int = 0
    frozen_lines_changed: int = 0


_FROZEN_RE = re.compile(r"<!--\s*frozen(:|\s+)(.*?)-->\s*", re.IGNORECASE | re.DOTALL)
_MALFORMED_RE = re.compile(r"<!--.*", re.IGNORECASE)


def _marker_name(m: re.Match[str]) -> tuple[str | None, bool]:
    """Return ``(name, is_named)`` for a frozen marker.

    ``<!-- frozen: x -->`` → name ``x`` (named). ``<!-- frozen -->`` →
    anonymous: opens the ``core`` section if none is open, else closes the
    current open section.
    """
    has_colon, raw = m.group(1), m.group(2)
    if has_colon == ":" and raw.strip():
        return (raw.strip(), True)
    return (None, False)


def parse_frozen_sections(prompt_text: str) -> list[FrozenSection]:
    """Split a prompt into frozen sections by ``<!-- frozen: name -->`` markers.

    Returns ``list[FrozenSection]`` with ``start_line``/``end_line`` (0-based
    line indexes of the marker span) and ``section_name``.

    - ``<!-- frozen: name -->`` opens a named section.
    - ``<!-- frozen -->`` with an open named section closes it; with no open
      section it opens the default ``core`` section.

    Raises :class:`GuardrailError` on malformed (unclosed) markers.
    """
    lines = prompt_text.splitlines()
    sections: list[FrozenSection] = []
    current_name: str | None = None
    current_start = 0
    current_lines: list[str] = []
    for idx, line in enumerate(lines):
        m = _FROZEN_RE.search(line)
        if m:
            name, is_named = _marker_name(m)
            if current_name is not None and (not is_named):
                # anonymous marker closes the open named section
                sections.append(
                    FrozenSection(
                        start_line=current_start,
                        end_line=idx - 1,
                        section_name=current_name,
                        lines=list(current_lines),
                    )
                )
                current_name = None
                current_lines = []
            else:
                if current_name is not None:
                    sections.append(
                        FrozenSection(
                            start_line=current_start,
                            end_line=idx - 1,
                            section_name=current_name,
                            lines=list(current_lines),
                        )
                    )
                current_name = name if is_named else "core"
                current_start = idx
                current_lines = []
        else:
            if _MALFORMED_RE.match(line):
                raise GuardrailError(
                    f"malformed frozen annotation at line {idx}: {line!r}"
                )
            current_lines.append(line)
    if current_name is not None:
        sections.append(
            FrozenSection(
                start_line=current_start,
                end_line=len(lines) - 1,
                section_name=current_name,
                lines=list(current_lines),
            )
        )
    return sections


def frozen_line_indexes(prompt_text: str) -> set[int]:
    sections = parse_frozen_sections(prompt_text)
    indexes: set[int] = set()
    for sec in sections:
        if sec.section_name is not None:
            indexes.update(range(sec.start_line, sec.end_line + 1))
    return indexes


def validate_frozen_sections(prompt_text: str, frozen_sections: Sequence[str]) -> bool:
    """Verify frozen section names exist in ``prompt_text`` in order.

    - All requested names must be present in the prompt.
    - The requested names must appear in the prompt in the same relative order
      (so a renumbered/reordered edit fails).
    """
    present = parse_frozen_sections(prompt_text)
    names = [s.section_name for s in present if s.section_name is not None]
    requested = [n for n in frozen_sections if n]
    if len(set(requested)) != len(requested):
        return False
    pos = 0
    for name in requested:
        try:
            found = names.index(name, pos)
        except ValueError:
            return False
        pos = found + 1
    return True


def compute_edit_distance(old_prompt: str, new_prompt: str) -> EditDistance:
    old_lines = old_prompt.splitlines()
    new_lines = new_prompt.splitlines()
    sm = difflib.SequenceMatcher(None, old_lines, new_lines)
    added = 0
    removed = 0
    modified = 0
    changed_old_idx: set[int] = set()
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag == "insert":
            added += j2 - j1
        elif tag == "delete":
            removed += i2 - i1
            changed_old_idx.update(range(i1, i2))
        elif tag == "replace":
            modified += max(i2 - i1, j2 - j1)
            changed_old_idx.update(range(i1, i2))
    frozen_idx = frozen_line_indexes(old_prompt)
    frozen_changed = sum(1 for i in changed_old_idx if i in frozen_idx)
    return EditDistance(
        lines_added=added,
        lines_removed=removed,
        lines_modified=modified,
        total=added + removed + modified,
        frozen_lines_changed=frozen_changed,
    )


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


def _tfidf_vectors(prompts: list[str], smooth_idf: bool = True) -> list[dict[str, float]]:
    docs = [_tokenize(p) for p in prompts]
    vocab: set[str] = set()
    for doc in docs:
        vocab.update(doc)
    vocab_sorted = sorted(vocab)
    n_docs = len(docs)
    df = {term: 0 for term in vocab_sorted}
    idf: dict[str, float] = {}
    for doc in docs:
        for term in set(doc):
            df[term] += 1
    for term in vocab_sorted:
        if smooth_idf:
            idf[term] = 1.0 + (n_docs / (df[term] + 1) if n_docs else 0.0)
        else:
            idf[term] = n_docs / (df[term] or n_docs)
    vectors: list[dict[str, float]] = []
    for doc in docs:
        counts = {term: doc.count(term) for term in vocab_sorted if doc.count(term) > 0}
        vec = {term: counts[term] * idf[term] for term in counts}
        vectors.append(vec)
    return vectors


def _cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0
    for t in set(a).union(set(b)):
        dot += a.get(t, 0.0) * b.get(t, 0.0)
    norm_a = 0.0
    norm_b = 0.0
    for v in a.values():
        norm_a += v * v
    for v in b.values():
        norm_b += v * v
    norm_a = math.sqrt(norm_a)
    norm_b = math.sqrt(norm_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def compute_drift_tfidf(prompt_a: str, prompt_b: str) -> float:
    """Drift = 1 - cosine similarity between two prompts' TF-IDF vectors.

    Range [0, 1]; identical prompts → 0; symmetric.
    """
    if prompt_a.strip() == prompt_b.strip():
        return 0.0
    vecs = _tfidf_vectors([prompt_a, prompt_b])
    return 1.0 - _cosine_similarity(vecs[0], vecs[1])


def _embedding_cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += float(x) * float(y)
        norm_a += float(x) * float(x)
        norm_b += float(y) * float(y)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def compute_drift_embedding(prompt_a: str, prompt_b: str, llm_provider: Any) -> float:
    """Sentence-embedding drift via an LLM provider, falling back to TF-IDF.

    If the provider has no ``embed`` method (interface), or embedding fails,
    return :func:`compute_drift_tfidf`.
    """
    embed = getattr(llm_provider, "embed", None)
    if embed is None:
        return compute_drift_tfidf(prompt_a, prompt_b)
    try:
        emb_a = embed(prompt_a)
        emb_b = embed(prompt_b)
    except (TypeError, ValueError, RuntimeError):
        return compute_drift_tfidf(prompt_a, prompt_b)
    if not emb_a or not emb_b or len(emb_a) != len(emb_b):
        return compute_drift_tfidf(prompt_a, prompt_b)
    sim = _embedding_cosine(list(emb_a), list(emb_b))
    return max(0.0, min(1.0, 1.0 - sim))


def compute_per_section_drift(
    prompt_a: str, prompt_b: str, sections: Sequence[FrozenSection]
) -> dict[str, float]:
    """Drift per named section, keyed by section name."""
    result: dict[str, float] = {}
    lines_a = prompt_a.splitlines()
    lines_b = prompt_b.splitlines()
    for sec in sections:
        name = sec.section_name
        if name is None:
            continue
        text_a = "\n".join(lines_a[sec.start_line : sec.end_line + 1])
        text_b = "\n".join(lines_b[sec.start_line : sec.end_line + 1])
        result[name] = compute_drift_tfidf(text_a, text_b)
    return result


@dataclass
class GuardrailReport:
    """Structured output of one guardrail assessment."""

    checks: list[CheckResult] = field(default_factory=list)
    overall: bool = True

    def __str__(self) -> str:
        lines = ["Guardrail report:", "----------------"]
        for c in self.checks:
            status = "PASS" if c.passed else "FAIL"
            lines.append(
                f"  [{status}] {c.name:<16} value={c.value:<8.4f} "
                f"threshold={c.threshold:<8.4f} {c.details}"
            )
        lines.append("----------------")
        lines.append(f"Overall: {'PASS' if self.overall else 'FAIL'}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return json.dumps(
            {
                "overall": self.overall,
                "checks": [
                    {
                        "name": c.name,
                        "passed": c.passed,
                        "value": c.value,
                        "threshold": c.threshold,
                        "details": c.details,
                    }
                    for c in self.checks
                ],
            },
            indent=2,
        )
