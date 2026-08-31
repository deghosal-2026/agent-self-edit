"""Tests for the SQLite TraceStore."""

import pytest

from agent_self_edit.trace import TraceStore
from agent_self_edit.types import validate_trace


def _valid(data=None):
    base = {
        "task_id": "t1",
        "task_input": "input",
        "final_output": "out",
        "expected_output": "exp",
        "success": True,
        "timestamp": "2026-09-01T10:00:00Z",
    }
    base.update(data or {})
    return base


@pytest.fixture
def store(tmp_path):
    return TraceStore(str(tmp_path / "traces.db"), batch_size=2)


def test_init_creates_db(store, tmp_path):
    assert (tmp_path / "traces.db").exists()
    assert store.count() == 0


def test_store_and_get(store):
    trace = validate_trace(_valid())
    row_id = store.store(trace)
    assert row_id > 0
    fetched = store.get("t1")
    assert fetched is not None
    assert fetched.task_id == "t1"
    assert fetched.success is True


def test_get_missing(store):
    assert store.get("nope") is None


def test_list_empty(store):
    assert store.list() == []


def test_list_limit(store):
    for i in range(5):
        store.store(validate_trace(_valid({"task_id": f"t{i}"})))
    assert len(store.list()) == 5
    assert len(store.list(limit=2)) == 2


def test_list_filter_success(store):
    store.store(validate_trace(_valid({"task_id": "a", "success": True})))
    store.store(validate_trace(_valid({"task_id": "b", "success": False})))
    ok = store.list(success=True)
    fail = store.list(success=False)
    assert [t.task_id for t in ok] == ["a"]
    assert [t.task_id for t in fail] == ["b"]


def test_list_filter_prompt_version(store):
    store.store(validate_trace(_valid({"task_id": "a", "prompt_version": 1})))
    store.store(validate_trace(_valid({"task_id": "b", "prompt_version": 3})))
    result = store.list(prompt_version=3)
    assert [t.task_id for t in result] == ["b"]


def test_count(store):
    store.store(validate_trace(_valid({"task_id": "a", "success": True})))
    store.store(validate_trace(_valid({"task_id": "b", "success": False})))
    assert store.count() == 2
    assert store.count(success=True) == 1
    assert store.count(success=False) == 1


def test_delete_before(store):
    store.store(validate_trace(_valid({"task_id": "old", "timestamp": "2026-01-01T00:00:00Z"})))
    store.store(validate_trace(_valid({"task_id": "new", "timestamp": "2026-09-01T00:00:00Z"})))
    deleted = store.delete_before("2026-06-01T00:00:00Z")
    assert deleted == 1
    assert store.get("old") is None
    assert store.get("new") is not None


def test_round_trip_steps(store):
    data = _valid({"steps": [{"action": "x"}, {"action": "y"}]})
    store.store(validate_trace(data))
    fetched = store.get("t1")
    assert fetched is not None
    assert len(fetched.steps) == 2


# ingestion (#11)


def test_ingest_valid(store):
    task_id = store.ingest(_valid({"task_id": "abc"}))
    assert task_id == "abc"
    assert store.count() == 1


def test_ingest_invalid_raises(store):
    bad = _valid({"task_id": "bad"})
    bad.pop("expected_output")
    with pytest.raises(ValueError):
        store.ingest(bad)
    assert store.count() == 0


def test_ingest_increment_counter(store):
    store.ingest(_valid({"task_id": "a"}))
    store.ingest(_valid({"task_id": "b"}))
    assert store._batch_counter == 2


def test_ingest_invalid_no_counter(store):
    bad = _valid({"task_id": "bad"})
    bad.pop("success")
    with pytest.raises(ValueError):
        store.ingest(bad)
    assert store._batch_counter == 0


# batching (#12)


def test_batch_ready_false_when_below(store):
    store.ingest(_valid({"task_id": "a"}))
    assert store.batch_ready() is False


def test_batch_ready_true_at_threshold(store):
    store.ingest(_valid({"task_id": "a"}))
    store.ingest(_valid({"task_id": "b"}))
    assert store.batch_ready() is True


def test_get_batch_returns_oldest(store):
    for i in range(4):
        store.ingest(_valid({"task_id": f"t{i}"}))
    batch = store.get_batch(2)
    assert [t.task_id for t in batch] == ["t0", "t1"]


def test_get_batch_no_pending(store):
    store.ingest(_valid({"task_id": "a"}))
    store.acknowledge(["a"])
    assert store.get_batch(10) == []


def test_acknowledge(store):
    for i in range(3):
        store.ingest(_valid({"task_id": f"t{i}"}))
    store.acknowledge(["t0", "t1"])
    remaining = store.get_batch(10)
    assert [t.task_id for t in remaining] == ["t2"]


def test_partial_acknowledge(store):
    for i in range(3):
        store.ingest(_valid({"task_id": f"t{i}"}))
    store.acknowledge(["t0"])
    remaining = store.get_batch(10)
    assert [t.task_id for t in remaining] == ["t1", "t2"]


def test_acknowledge_empty(store):
    store.acknowledge([])  # no-op, no error


# cleanup (#14)


def test_cleanup_deletes_old_keeps_recent(store):
    store.store(validate_trace(_valid({"task_id": "old", "timestamp": "2026-01-01T00:00:00Z"})))
    store.store(validate_trace(_valid({"task_id": "new", "timestamp": "2026-09-01T00:00:00Z"})))
    deleted = store.cleanup(retention_days=30)
    assert deleted == 1
    assert store.get("old") is None
    assert store.get("new") is not None


def test_cleanup_retention_zero(store):
    store.store(validate_trace(_valid({"task_id": "a"})))
    store.store(validate_trace(_valid({"task_id": "b"})))
    deleted = store.cleanup(retention_days=0)
    assert deleted == 2
    assert store.count() == 0


def test_cleanup_negative_days(store):
    with pytest.raises(ValueError):
        store.cleanup(retention_days=-1)


def test_schema_migration_newer_raises(store):
    import sqlite3
    conn = sqlite3.connect(store.path)
    conn.execute("PRAGMA user_version = 99")
    conn.commit()
    conn.close()
    from agent_self_edit.trace import TraceStore

    with pytest.raises(RuntimeError):
        TraceStore(store.path)
