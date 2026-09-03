"""Git-backed file prompt registry with versioning, diff, rollback, integrity.

Per PRD §2.5, the prompt registry is versioned in git: each created version is
auto-committed when the registry lives inside a git work tree, giving tree-wide
diff, rollback, branching, and merge through standard git tooling. When git is
not available (or the path is not inside a repo), the registry degrades
gracefully to plain file-based storage.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import logging
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .types import utc_now_iso

logger = logging.getLogger("agent_self_edit.registry")


class RegistryError(Exception):
    """Raised on invalid registry operations (missing version, corruption)."""


def _git_available() -> bool:
    return shutil.which("git") is not None


def _inside_git_repo(path: Path) -> bool:
    if not _git_available():
        return False
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except (subprocess.SubprocessError, OSError):
        return False


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
    commit_sha: str | None = None
    diff_from_previous: dict[str, Any] | None = None
    hypothesis: str | None = None
    ab_results: dict[str, Any] | None = None
    gate_result: dict[str, Any] | None = None
    trigger_trace_ids: list[str] | None = None
    model_version: str | None = None
    token_cost: float | None = None
    rollback_reason: str | None = None
    rollback_target: int | None = None

    def to_dict(self) -> dict[str, Any]:
        import dataclasses

        return {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_meta(
    version: int,
    prompt_text: str,
    commit_sha: str | None = None,
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
        commit_sha=commit_sha,
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
    """Git-backed versioned prompt store.

    When ``git_backed=True`` is explicitly set and the registry path is inside a
    git work tree, every ``create()``/``rollback()`` also creates a git commit.
    Default is ``False`` (opt-in) to avoid unintended auto-commits into
    enclosing repositories (ref #157).
    """

    def __init__(self, path: str | Path, git_backed: bool = False) -> None:
        self._path = Path(path)
        self._path.mkdir(parents=True, exist_ok=True)
        self._git_enabled = git_backed and _inside_git_repo(self._path)
        self._lock = threading.Lock()
        self._current = self._resolve_current()
        self._cached_prompt: str | None = None
        self._cached_version: int | None = None
        if self._git_enabled:
            logger.info(
                "Registry: git-backed at %s (current version %d)",
                self._path,
                self._current,
            )
        else:
            logger.info(
                "Registry: file-only at %s (git unavailable or path not in a repo)",
                self._path,
            )

    @property
    def git_backed(self) -> bool:
        return self._git_enabled

    def _ensure_git_repo(self) -> None:
        if self._git_enabled:
            return
        # Attempt to (re)detect git at call time so a repo created after
        # construction is picked up lazily.
        if _inside_git_repo(self._path):
            self._git_enabled = True
            logger.info("Registry: git backing enabled at %s", self._path)

    def _git_commit(self, version: int) -> str | None:
        md_path, meta_path = self._version_path(version)
        try:
            subprocess.run(
                ["git", "-C", str(self._path), "add", "--", md_path.name, meta_path.name],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(self._path),
                    "commit",
                    "-m",
                    f"prompt v{version}",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            commit_result = subprocess.run(
                ["git", "-C", str(self._path), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return commit_result.stdout.strip()
        except (subprocess.SubprocessError, OSError) as e:
            logger.error(
                "Registry: git commit failed for v%d: %s",
                version,
                e,
            )
            return None

    @property
    def current_version(self) -> int:
        return self._current

    @property
    def current_prompt(self) -> str:
        if self._current == 0:
            return ""
        if self._cached_prompt is not None and self._cached_version == self._current:
            return self._cached_prompt
        prompt_data, _ = self._read(self._current)
        self._cached_prompt = prompt_data
        self._cached_version = self._current
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
            # Forward-compat: ignore unknown fields from newer versions (fix 291/215)
            known = set(Meta.__dataclass_fields__.keys())
            filtered = {k: v for k, v in meta_data.items() if k in known}
            meta = Meta(**filtered)
        else:
            meta = Meta(
                version=version,
                timestamp="",
                sha256_hash=_sha256(prompt_text),
            )
        return prompt_text, meta

    def _write(self, version: int, prompt_text: str, meta: Meta) -> None:
        md_path, meta_path = self._version_path(version)
        # Atomic write via temp files (fix 222 corruption window)
        md_tmp = md_path.with_suffix(".tmp.md")
        meta_tmp = meta_path.with_suffix(".tmp.json")
        md_tmp.write_text(prompt_text, encoding="utf-8")
        meta_dict = {
            "version": meta.version,
            "timestamp": meta.timestamp,
            "sha256_hash": meta.sha256_hash,
            "commit_sha": meta.commit_sha,
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
        meta_tmp.write_text(
            json.dumps(meta_dict, indent=2, sort_keys=True), encoding="utf-8"
        )
        md_tmp.replace(md_path)
        meta_tmp.replace(meta_path)

    def create(
        self, prompt_text: str, **metadata: Any
    ) -> int:
        """Create a new prompt version (optionally git-committed). Returns the version number."""
        with self._lock:
            self._ensure_git_repo()
            version = self._current + 1
            diff = self._compute_diff(self._current, prompt_text)
            # Write with no SHA first so git has files to add; single logical write
            # but handle corruption window (fix 222): clean up if git fails after write
            meta_tmp = _build_meta(
                version,
                prompt_text,
                commit_sha=None,
                diff_from_previous=(
                    {
                        "lines_added": len(diff.added),
                        "lines_removed": len(diff.removed),
                        "lines_modified": len(diff.modified),
                        "total": len(diff.added)
                        + len(diff.removed)
                        + len(diff.modified),
                    }
                    if diff is not None
                    else None
                ),
                hypothesis=metadata.get("hypothesis"),
                ab_results=metadata.get("ab_results"),
                gate_result=metadata.get("gate_result"),
                trigger_trace_ids=metadata.get("trigger_trace_ids"),
                model_version=metadata.get("model_version"),
                token_cost=metadata.get("token_cost"),
                rollback_reason=metadata.get("rollback_reason"),
                rollback_target=metadata.get("rollback_target"),
            )
            self._write(version, prompt_text, meta_tmp)
            commit_sha: str | None = None
            if self._git_enabled:
                try:
                    commit_sha = self._git_commit(version)
                except Exception as e:
                    md_path, meta_path = self._version_path(version)
                    if md_path.exists():
                        md_path.unlink(missing_ok=True)
                    if meta_path.exists():
                        meta_path.unlink(missing_ok=True)
                    raise RegistryError(f"git commit failed for v{version}: {e}") from e
                if commit_sha:
                    # Second write with SHA (working tree ahead)
                    meta = _build_meta(
                        version,
                        prompt_text,
                        commit_sha=commit_sha,
                        diff_from_previous=meta_tmp.diff_from_previous,
                        hypothesis=meta_tmp.hypothesis,
                        ab_results=meta_tmp.ab_results,
                        gate_result=meta_tmp.gate_result,
                        trigger_trace_ids=meta_tmp.trigger_trace_ids,
                        model_version=meta_tmp.model_version,
                        token_cost=meta_tmp.token_cost,
                        rollback_reason=meta_tmp.rollback_reason,
                        rollback_target=meta_tmp.rollback_target,
                    )
                    self._write(version, prompt_text, meta)
                    self._cached_prompt = prompt_text
                    self._cached_version = version
                    self._current = version
                    logger.info(
                        "Registry: created version %d (git=%s, sha=%s)",
                        version,
                        self._git_enabled,
                        commit_sha,
                    )
                    return version
            # File-only or git without SHA
            self._cached_prompt = prompt_text
            self._cached_version = version
            self._current = version
            logger.info("Registry: created version %d (git=%s)", version, self._git_enabled)
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
