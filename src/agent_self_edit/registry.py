"""File-based prompt registry with versioning, diff, rollback, and integrity."""

from __future__ import annotations

import difflib
import hashlib
import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .types import utc_now_iso

logger = logging.getLogger("agent_self_edit.registry")


class RegistryError(Exception):
    """Raised on invalid registry operations (missing version, corruption)."""


@dataclass(frozen=True)
class DiffResult:
    """Line-level diff between two prompt versions."""

    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    unchanged_count: int = 0
    frozen_unchanged_count: int = 0


@dataclass(frozen=True)
class Meta:
    """Metadata for a single prompt version."""

    version: int
    timestamp: str
    sha256_hash: str
    diff_from_previous: dict[str, Any] | None = None
    hypothesis: str | None = None
    ab_results: dict[str, Any] | None = None
    gate_result: dict[str, Any] | None = None
    trigger_trace_ids: list[str] | None = None
    model_version: str | None = None
    token_cost: float | None = None
    rollback_reason: str | None = None
    rollback_target: int | None = None


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_meta(
    version: int,
    prompt_text: str,
    diff_from_previous: dict[str, Any] | None = None,
    hypothesis: str | None = None,
    ab_results: dict[str, Any] | None = None,
    gate_result: dict[str, Any] | None = None,
    trigger_trace_ids: list[str] | None = None,
    model_version: str | None = None,
    token_cost: float | None = None,
    rollback_reason: str | None = None,
    rollback_target: int | None = None,
) -> Meta:
    return Meta(
        version=version,
        timestamp=utc_now_iso(),
        sha256_hash=_sha256(prompt_text),
        diff_from_previous=diff_from_previous,
        hypothesis=hypothesis,
        ab_results=ab_results,
        gate_result=gate_result,
        trigger_trace_ids=trigger_trace_ids,
        model_version=model_version,
        token_cost=token_cost,
        rollback_reason=rollback_reason,
        rollback_target=rollback_target,
    )


class Registry:
    """File-based versioned prompt store."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._current = self._resolve_current()

    @property
    def current_version(self) -> int:
        return self._current

    @property
    def current_prompt(self) -> str:
        if self._current == 0:
            return ""
        prompt_data, _ = self._read(self._current)
        return prompt_data

    def _resolve_current(self) -> int:
        max_v = 0
        for f in self._path.iterdir():
            if f.suffix == ".md" and f.stem.startswith("v"):
                try:
                    v = int(f.stem[1:])
                    if v > max_v:
                        max_v = v
                except ValueError:
                    continue
        return max_v

    def _version_path(self, version: int) -> tuple[Path, Path]:
        base = self._path / f"v{version}"
        return (base.with_suffix(".md"), base.with_suffix(".meta.json"))

    def _read(self, version: int) -> tuple[str, Meta]:
        md_path, meta_path = self._version_path(version)
        if not md_path.exists():
            raise RegistryError(f"version {version} not found")
        prompt_text = md_path.read_text(encoding="utf-8")
        if meta_path.exists():
            meta_data = json.loads(meta_path.read_text(encoding="utf-8"))
            meta = Meta(**meta_data)
        else:
            meta = Meta(
                version=version,
                timestamp="",
                sha256_hash=_sha256(prompt_text),
            )
        return prompt_text, meta

    def _write(self, version: int, prompt_text: str, meta: Meta) -> None:
        md_path, meta_path = self._version_path(version)
        md_path.write_text(prompt_text, encoding="utf-8")
        meta_dict = {
            "version": meta.version,
            "timestamp": meta.timestamp,
            "sha256_hash": meta.sha256_hash,
        }
        for key in (
            "diff_from_previous",
            "hypothesis",
            "ab_results",
            "gate_result",
            "trigger_trace_ids",
            "model_version",
            "token_cost",
            "rollback_reason",
            "rollback_target",
        ):
            val = getattr(meta, key, None)
            if val is not None:
                meta_dict[key] = val
        meta_path.write_text(
            json.dumps(meta_dict, indent=2, sort_keys=True), encoding="utf-8"
        )

    def create(
        self, prompt_text: str, **metadata: Any
    ) -> int:
        """Create a new prompt version. Returns the version number."""
        with self._lock:
            version = self._current + 1
            diff = self._compute_diff(self._current, prompt_text)
            meta = _build_meta(
                version,
                prompt_text,
                hypothesis=metadata.get("hypothesis"),
                ab_results=metadata.get("ab_results"),
                gate_result=metadata.get("gate_result"),
                trigger_trace_ids=metadata.get("trigger_trace_ids"),
                model_version=metadata.get("model_version"),
                token_cost=metadata.get("token_cost"),
                rollback_reason=metadata.get("rollback_reason"),
                rollback_target=metadata.get("rollback_target"),
            )
            if diff is not None:
                meta = Meta(
                    version=meta.version,
                    timestamp=meta.timestamp,
                    sha256_hash=meta.sha256_hash,
                    diff_from_previous={
                        "lines_added": len(diff.added),
                        "lines_removed": len(diff.removed),
                        "lines_modified": len(diff.modified),
                        "total": len(diff.added)
                        + len(diff.removed)
                        + len(diff.modified),
                    },
                    hypothesis=meta.hypothesis,
                    ab_results=meta.ab_results,
                    gate_result=meta.gate_result,
                    trigger_trace_ids=meta.trigger_trace_ids,
                    model_version=meta.model_version,
                    token_cost=meta.token_cost,
                    rollback_reason=meta.rollback_reason,
                    rollback_target=meta.rollback_target,
                )
            self._write(version, prompt_text, meta)
            self._current = version
            logger.info("Registry: created version %d", version)
            return version

    def get(self, version: int) -> tuple[str, Meta]:
        if version <= 0 or version > self._current:
            raise RegistryError(
                f"version {version} not in range [1, {self._current}]"
            )
        return self._read(version)

    def diff(self, v1: int, v2: int) -> DiffResult:
        text1, _ = self.get(v1)
        text2, _ = self.get(v2)
        return self._compute_diff(v1, text2, v1_text=text1) or DiffResult()

    def _compute_diff(
        self, old_version: int, new_text: str, v1_text: str | None = None
    ) -> DiffResult | None:
        if old_version == 0:
            return None
        old_text = v1_text if v1_text is not None else self._read(old_version)[0]
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()
        sm = difflib.SequenceMatcher(None, old_lines, new_lines)
        added: list[str] = []
        removed: list[str] = []
        modified: list[str] = []
        unchanged = 0
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                unchanged += i2 - i1
            elif tag == "replace":
                modified.extend(old_lines[i1:i2])
            elif tag == "delete":
                removed.extend(old_lines[i1:i2])
            elif tag == "insert":
                added.extend(new_lines[j1:j2])
        return DiffResult(
            added=added,
            removed=removed,
            modified=modified,
            unchanged_count=unchanged,
        )

    def rollback(self, version: int, reason: str) -> int:
        if version <= 0 or version > self._current:
            raise RegistryError(
                f"version {version} not in range [1, {self._current}]"
            )
        text, _ = self._read(version)
        return self.create(
            text,
            rollback_reason=reason,
            rollback_target=version,
        )

    def lineage(
        self, from_version: int | None = None
    ) -> list[Meta]:
        start = from_version if from_version is not None else 1
        if start < 1:
            start = 1
        result: list[Meta] = []
        for v in range(start, self._current + 1):
            _, meta = self.get(v)
            result.append(meta)
        return result

    def verify_integrity(self) -> list[str]:
        corrupted: list[str] = []
        for v in range(1, self._current + 1):
            md_path, meta_path = self._version_path(v)
            if not md_path.exists():
                corrupted.append(f"v{v}: missing prompt file")
                continue
            prompt_text = md_path.read_text(encoding="utf-8")
            actual_hash = _sha256(prompt_text)
            if meta_path.exists():
                meta_data = json.loads(meta_path.read_text(encoding="utf-8"))
                expected_hash = meta_data.get("sha256_hash", "")
                if actual_hash != expected_hash:
                    corrupted.append(
                        f"v{v}: hash mismatch (expected {expected_hash}, got {actual_hash})"
                    )
            else:
                corrupted.append(f"v{v}: missing meta file")
        return corrupted
