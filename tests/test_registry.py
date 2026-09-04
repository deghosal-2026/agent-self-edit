"""Tests for the prompt registry."""

import json
import subprocess

import pytest

from agent_self_edit.registry import DiffResult, Meta, Registry, RegistryError


@pytest.fixture
def reg(tmp_path):
    return Registry(tmp_path / "registry")


def _git_init(tmp_path):
    """Initialize a git repo in tmp_path and mark it a git-backed registry dir."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"], check=True
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True
    )
    return tmp_path


def test_init_empty(reg):
    assert reg.current_version == 0
    assert reg.current_prompt == ""


def test_create_first_version(reg):
    v = reg.create("You are a classifier.")
    assert v == 1
    assert reg.current_version == 1
    assert reg.current_prompt == "You are a classifier."


def test_create_increments(reg):
    v1 = reg.create("first")
    v2 = reg.create("second")
    assert v1 == 1
    assert v2 == 2
    assert reg.current_version == 2
    assert reg.current_prompt == "second"


def test_get_version(reg):
    reg.create("prompt text")
    text, meta = reg.get(1)
    assert text == "prompt text"
    assert meta.version == 1
    assert meta.sha256_hash


def test_get_invalid_version(reg):
    with pytest.raises(RegistryError):
        reg.get(99)


def test_get_zero_version(reg):
    with pytest.raises(RegistryError):
        reg.get(0)


def test_meta_has_timestamp(reg):
    reg.create("hello")
    _, meta = reg.get(1)
    assert meta.timestamp


def test_meta_has_hash(reg):
    reg.create("content")
    _, meta = reg.get(1)
    assert len(meta.sha256_hash) == 64


def test_create_with_metadata(reg):
    reg.create("text", hypothesis="test hypothesis", model_version="gpt-4o-mini")
    _, meta = reg.get(1)
    assert meta.hypothesis == "test hypothesis"
    assert meta.model_version == "gpt-4o-mini"


def test_create_with_ab_results(reg):
    reg.create("text", ab_results={"winner": "b", "n_trials": 30})
    _, meta = reg.get(1)
    assert meta.ab_results is not None
    assert meta.ab_results["winner"] == "b"


def test_meta_optional_fields(reg):
    reg.create("text")
    _, meta = reg.get(1)
    assert meta.hypothesis is None
    assert meta.ab_results is None
    assert meta.gate_result is None
    assert meta.trigger_trace_ids is None
    assert meta.model_version is None
    assert meta.token_cost is None


def test_create_empty_prompt(reg):
    v = reg.create("")
    assert v == 1
    assert reg.current_prompt == ""


def test_diff_identical_versions(reg):
    reg.create("same content")
    reg.create("same content")
    d = reg.diff(1, 2)
    assert d.unchanged_count > 0


def test_diff_different_versions(reg):
    reg.create("line one\nline two\nline three")
    reg.create("line one\nline two modified\nline three\nline four")
    d = reg.diff(1, 2)
    assert len(d.modified) > 0 or len(d.added) > 0


def test_diff_invalid_version(reg):
    reg.create("text")
    with pytest.raises(RegistryError):
        reg.diff(1, 99)


def test_rollback_creates_new_version(reg):
    reg.create("alpha")
    reg.create("beta")
    assert reg.current_prompt == "beta"
    v3 = reg.rollback(1, "reverting to alpha")
    assert v3 == 3
    assert reg.current_prompt == "alpha"
    _, meta = reg.get(3)
    assert meta.rollback_reason == "reverting to alpha"
    assert meta.rollback_target == 1


def test_rollback_invalid_version(reg):
    with pytest.raises(RegistryError):
        reg.rollback(99, "nope")


def test_rollback_to_current(reg):
    reg.create("text")
    v2 = reg.rollback(1, "same thing")
    assert v2 == 2
    assert reg.current_prompt == "text"


def test_rollback_preserves_lineage_after_real_promotion(reg):
    """Rollback to a real promoted version preserves full lineage."""
    reg.create("You are a classifier.")
    reg.create(
        "You are a better classifier.",
        hypothesis="improved classification",
        ab_results={"effect_size": 0.15, "p_value": 0.03},
        gate_result={"decision": "promote", "reason": "all checks passed"},
        trigger_trace_ids=["t1", "t2"],
        model_version="gpt-4",
        token_cost=0.05,
        changed_section="role",
    )
    assert reg.current_version == 2
    assert reg.current_prompt == "You are a better classifier."

    v3 = reg.rollback(1, "reverting to original classifier")
    assert v3 == 3
    assert reg.current_prompt == "You are a classifier."
    assert reg.current_version == 3

    _, meta = reg.get(3)
    assert meta.rollback_reason == "reverting to original classifier"
    assert meta.rollback_target == 1
    assert meta.version == 3

    lineage = reg.lineage()
    assert len(lineage) == 3
    assert [m.version for m in lineage] == [1, 2, 3]
    assert lineage[0].rollback_target is None
    assert lineage[1].hypothesis == "improved classification"
    assert lineage[2].rollback_target == 1
    assert lineage[2].rollback_reason == "reverting to original classifier"


def test_lineage_all(reg):
    reg.create("a")
    reg.create("b")
    reg.create("c")
    lineage = reg.lineage()
    assert len(lineage) == 3
    assert [m.version for m in lineage] == [1, 2, 3]


def test_lineage_from_version(reg):
    reg.create("a")
    reg.create("b")
    reg.create("c")
    partial = reg.lineage(from_version=2)
    assert len(partial) == 2
    assert [m.version for m in partial] == [2, 3]


def test_lineage_empty(reg):
    assert reg.lineage() == []


def test_integrity_all_intact(reg):
    reg.create("a")
    reg.create("b")
    reg.create("c")
    assert reg.verify_integrity() == []


def test_integrity_tampered(reg):
    reg.create("original")
    v1_path, _ = reg._version_path(1)
    v1_path.write_text("tampered content")
    corrupted = reg.verify_integrity()
    assert len(corrupted) == 1
    assert "v1" in corrupted[0]


def test_integrity_missing_meta(reg):
    reg.create("text")
    _, meta_path = reg._version_path(1)
    meta_path.unlink()
    corrupted = reg.verify_integrity()
    assert any("missing meta" in c for c in corrupted)


def test_integrity_empty_registry(reg):
    assert reg.verify_integrity() == []


def test_version_metadata_json_round_trip(reg):
    reg.create("text", token_cost=0.042)
    _, meta = reg.get(1)
    _, meta_path = reg._version_path(1)
    raw = json.loads(meta_path.read_text())
    assert raw["token_cost"] == 0.042
    assert raw["version"] == 1


def test_diff_result_dataclass():
    d = DiffResult(added=["a"], removed=["b"], modified=["c"], unchanged_count=5)
    assert d.unchanged_count == 5
    assert len(d.added) == 1


def test_meta_dataclass():
    m = Meta(version=1, timestamp="now", sha256_hash="abc")
    assert m.version == 1
    assert m.hypothesis is None


def test_concurrent_create(reg):
    import threading

    errors = []

    def worker(n):
        try:
            for i in range(5):
                reg.create(f"text from {n}-{i}")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert reg.current_version == 15


def test_diff_after_rollback(reg):
    reg.create("original prompt")
    reg.create("modified prompt")
    reg.rollback(1, "revert")
    d = reg.diff(3, 1)
    assert d.unchanged_count > 0


def test_missing_md_file_raises(reg):
    reg.create("text")
    # delete the md file, then create a new Registry instance that resolves
    # current via filesystem and fails to read the missing prompt
    md_path, _ = reg._version_path(1)
    md_path.unlink()
    with pytest.raises(RegistryError, match="not found"):
        reg._read(1)


def test_missing_meta_creates_fallback(reg):
    reg.create("text")
    _, meta_path = reg._version_path(1)
    meta_path.unlink()
    text, meta = reg._read(1)
    assert text == "text"
    assert meta.version == 1
    assert meta.sha256_hash  # recomputed from prompt


def test_lineage_from_version_below_one_clamps(reg):
    reg.create("a")
    reg.create("b")
    lineage = reg.lineage(from_version=0)
    assert [m.version for m in lineage] == [1, 2]


def test_integrity_missing_prompt_file(reg):
    reg.create("text")
    md_path, _ = reg._version_path(1)
    md_path.unlink()
    corrupted = reg.verify_integrity()
    assert any("missing prompt" in c for c in corrupted)


def test_resolve_current_ignores_non_numeric(tmp_path):
    # create a junk file with v-prefix that is not numeric

    r = Registry(tmp_path / "registry")
    r.create("text")
    (r._path / "vnotanumber.md").write_text("junk")
    r2 = Registry(tmp_path / "registry")
    assert r2.current_version == 1


def test_exists_in_list():
    from agent_self_edit.registry import Registry

    assert hasattr(Registry, "verify_integrity")


# ---- D-1: git-backed registry (PRD §2.5) ----


@pytest.fixture
def git_reg(tmp_path):
    _git_init(tmp_path)
    return Registry(tmp_path / "registry")


def test_git_backed_detected(tmp_path):
    _git_init(tmp_path)
    r = Registry(tmp_path / "registry", git_backed=True)
    assert r.git_backed is True


def test_file_only_when_not_in_repo(reg):
    assert reg.git_backed is False


def test_git_disabled_flag(reg):
    r = Registry(reg._path, git_backed=False)
    assert r.git_backed is False


def test_git_commit_on_create(tmp_path):
    _git_init(tmp_path)
    r = Registry(tmp_path / "registry", git_backed=True)
    r.create("prompt v1 content")
    # the registry directory must contain committed prompt file
    result = subprocess.run(
        ["git", "-C", str(tmp_path), "log", "--oneline"],
        capture_output=True, text=True,
    )
    assert "prompt v1" in result.stdout
    _, meta = r.get(1)
    assert meta.commit_sha is not None


def test_git_commit_each_version(tmp_path):
    _git_init(tmp_path)
    r = Registry(tmp_path / "registry", git_backed=True)
    r.create("one")
    r.create("two")
    r.create("three")
    result = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-list", "--count", "HEAD"],
        capture_output=True, text=True,
    )
    assert int(result.stdout.strip()) >= 3
    _, meta3 = r.get(3)
    assert meta3.commit_sha is not None


def test_git_meta_commit_sha_stored(tmp_path):
    _git_init(tmp_path)
    r = Registry(tmp_path / "registry", git_backed=True)
    r.create("content", hypothesis="h1")
    _, meta = r.get(1)
    assert meta.commit_sha
    assert meta.hypothesis == "h1"


def test_git_integrity_still_works(tmp_path):
    _git_init(tmp_path)
    r = Registry(tmp_path / "registry", git_backed=True)
    r.create("a")
    r.create("b")
    assert r.verify_integrity() == []


def test_git_rollback_commit(tmp_path):
    _git_init(tmp_path)
    r = Registry(tmp_path / "registry", git_backed=True)
    r.create("alpha")
    r.create("beta")
    v3 = r.rollback(1, "revert to alpha")
    assert v3 == 3
    _, meta = r.get(3)
    assert meta.rollback_reason == "revert to alpha"
    assert meta.commit_sha is not None
    result = subprocess.run(
        ["git", "-C", str(tmp_path), "log", "--oneline"],
        capture_output=True, text=True,
    )
    assert "prompt v3" in result.stdout or "prompt v" in result.stdout


def test_git_missing_commit_meta_still_reads(tmp_path):
    # meta files without commit_sha (pre-git versions) still load
    r = Registry(tmp_path / "registry")
    r.create("legacy")
    _, meta = r.get(1)
    assert meta.commit_sha is None


def test_git_failure_degrades_gracefully(tmp_path, monkeypatch):
    # Simulate git unavailability: monkeypatch _git_available to False
    import agent_self_edit.registry as reg_mod

    monkeypatch.setattr(reg_mod, "_git_available", lambda: False)
    r = Registry(tmp_path / "registry", git_backed=True)
    assert r.git_backed is False
    v = r.create("still works")
    assert v == 1
