"""Guardrail module: deterministic constraint primitives (F-06, F-07).

Frozen-section parsing, edit-distance calculation, and TF-IDF drift are the
deterministic primitives the promotion gate, analyzer, and diff visualization
rely on. Extracted into a standalone module per PRD 02-architecture §2.2.5 so
they are reusable independently of the promotion gate.
"""

from __future__ import annotations

import difflib
import math
import re
from typing import Any


class GuardrailError(Exception):
    """Raised on malformed guardrail annotations."""


_FROZEN_RE = re.compile(r"<!--\s*frozen:*\s*(.*?)-->\s*", re.IGNORECASE | re.DOTALL)


def parse_frozen_sections(prompt_text: str) -> list[dict[str, Any]]:
    """Split a prompt into sections by ``<!-- frozen: name -->`` markers.

    Returns ``[{"name": str|None, "lines": list[str], "start": int, "end": int}]``.
    A named marker freezes the span between it and the next marker or EOF.
    """
    lines = prompt_text.splitlines()
    sections: list[dict[str, Any]] = []
    current_name: str | None = None
    current_start = 0
    current_lines: list[str] = []
    for idx, line in enumerate(lines):
        m = _FROZEN_RE.search(line)
        if m:
            if current_name is not None:
                sections.append(
                    {
                        "name": current_name,
                        "lines": current_lines,
                        "start": current_start,
                        "end": idx - 1,
                    }
                )
            current_name = (m.group(1) or "core").strip() or None
            current_start = idx
            current_lines = []
        else:
            current_lines.append(line)
    if current_name is not None:
        sections.append(
            {
                "name": current_name,
                "lines": current_lines,
                "start": current_start,
                "end": len(lines) - 1,
            }
        )
    return sections


def frozen_line_indexes(prompt_text: str) -> set[int]:
    sections = parse_frozen_sections(prompt_text)
    indexes: set[int] = set()
    for sec in sections:
        if sec["name"] is not None:
            indexes.update(range(sec["start"], sec["end"] + 1))
    return indexes


def compute_edit_distance(old_prompt: str, new_prompt: str) -> int:
    old_lines = old_prompt.splitlines()
    new_lines = new_prompt.splitlines()
    sm = difflib.SequenceMatcher(None, old_lines, new_lines)
    changed = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            changed += (i2 - i1) + (j2 - j1)
    return changed


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
    """Drift = 1 - cosine similarity between two prompts' TF-IDF vectors."""
    if prompt_a.strip() == prompt_b.strip():
        return 0.0
    vecs = _tfidf_vectors([prompt_a, prompt_b])
    return 1.0 - _cosine_similarity(vecs[0], vecs[1])
