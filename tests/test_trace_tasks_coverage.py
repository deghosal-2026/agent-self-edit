"""Coverage补 for trace.py and tasks.py to reach 90%+ (M5 fixes).

Targets missing lines:
- trace.py: persistent WAL connection, metadata column, delete_before,
  _row_to_trace metadata, cleanup processed!=-1, count_pending, get_batch,
  release_in_flight, acknowledge, acknowledge_batch
- tasks.py: validate_manifest domain/scorer/role, required_count,
  benchmark_role, load_task_set empty check
Hermetic: tmp_path only, no real LLM.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from agent_self_edit.tasks import (
    Task,
    TaskSet,
    TaskSetError,
    load_task_set,
    validate_manifest,
)
from agent_self_edit.trace import TraceStore
from agent_self_edit.types import validate_trace


def _valid_trace(task_id: str = "t1", **overrides) -> dict:
    base = {
        "task_id": task_id,
        "task_input": "input",
        "final_output": "out",
        "expected_output": "exp",
        "success": True,
        "timestamp": "2026-09-01T10:00:00Z",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# TraceStore: persistent connection
# ---------------------------------------------------------------------------


def test_trace_persistent_single_connect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Only one sqlite3.connect call; subsequent ops reuse persistent _db."""
    calls: list[int] = []
    orig = sqlite3.connect

    def counting(*a, **kw):  # type: ignore[no-untyped-def]
        calls.append(1)
        return orig(*a, **kw)

    monkeypatch.setattr(sqlite3, "connect", counting)
    store = TraceStore(str(tmp_path / "t.db"), batch_size=5)
    before = len(calls)
    # these should reuse the persistent connection
    store.ingest(_valid_trace("a"))
    store.count()
    store.count_pending()
    store.list()
    store.get("a")
    assert len(calls) == before
    store.close()


def test_trace_connect_fallback_when_db_none(tmp_path: Path) -> None:
    """_connect creates new connection when _db is None (covers 74-78)."""
    store = TraceStore(str(tmp_path / "t.db"), batch_size=5)
    store.ingest(_valid_trace("x"))
    # force fallback path
    assert store._db is not None
    store._db.close()  # close underlying so we can set to None
    store._db = None
    # should create a new connection and close it after use
    assert store.count() == 1
    assert store.count(success=True) == 1
    # get and list also use fallback path with _close_if_needed
    assert store.get("x") is not None
    assert len(store.list()) == 1
    # get_batch fallback not yet tested — ingest another then get
    # need to recreate persistent for cleanup; but test fallback once more
    conn = store._connect()
    assert conn is not None
    # _is_persistent should be False when _db is None
    assert store._is_persistent(conn) is False
    store._close_if_needed(conn)
    # restore persistent connection for close()
    store._db = sqlite3.connect(str(tmp_path / "t.db"), check_same_thread=False)
    store._db.row_factory = sqlite3.Row
    store.close()


def test_trace_close_and_del(tmp_path: Path) -> None:
    """close() and __del__ handle persistent connection (88-93, 99-100)."""
    store = TraceStore(str(tmp_path / "t.db"))
    store.ingest(_valid_trace("a"))
    # _close_if_needed on persistent should not close
    assert store._db is not None
    persistent = store._db
    store._close_if_needed(persistent)
    # still usable
    assert store.count() == 1
    # close() with exception swallowed (cover except branch)
    store.close()
    assert store._db is None
    # second close is no-op
    store.close()
    # __del__ should not raise when _db is None
    store.__del__()
    # __del__ when _db still present
    store2 = TraceStore(str(tmp_path / "t2.db"))
    store2.ingest(_valid_trace("b"))
    # manually trigger del path that closes
    store2.__del__()
    # also test close when close raises
    store3 = TraceStore(str(tmp_path / "t3.db"))

    class BadConn:
        def close(self) -> None:  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

    store3._db = BadConn()  # type: ignore[assignment]
    store3.close()  # should swallow exception
    assert store3._db is None
    # __del__ with bad close also swallowed
    store4 = TraceStore(str(tmp_path / "t4.db"))
    store4._db = BadConn()  # type: ignore[assignment]
    store4.__del__()


def test_trace_close_if_needed_non_persistent(tmp_path: Path) -> None:
    """_close_if_needed closes non-persistent connections (84-85)."""
    store = TraceStore(str(tmp_path / "t.db"))
    conn = sqlite3.connect(str(tmp_path / "t.db"))
    # non-persistent should be closed
    store._close_if_needed(conn)
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


# ---------------------------------------------------------------------------
# TraceStore: metadata round-trip, empty, migration, invalid json
# ---------------------------------------------------------------------------


def test_trace_metadata_roundtrip(tmp_path: Path) -> None:
    store = TraceStore(str(tmp_path / "t.db"))
    meta = {"source": "prod", "user_id": "abc"}
    store.ingest({**_valid_trace("m1"), "metadata": meta, "prompt_version": 1})
    got = store.get("m1")
    assert got is not None
    assert got.metadata == meta
    assert got.prompt_version == 1


def test_trace_metadata_empty(tmp_path: Path) -> None:
    store = TraceStore(str(tmp_path / "t.db"))
    store.ingest(_valid_trace("m2"))
    got = store.get("m2")
    assert got is not None
    assert got.metadata == {}


def test_trace_metadata_invalid_json(tmp_path: Path) -> None:
    """_row_to_trace handles invalid metadata JSON (263-264)."""
    store = TraceStore(str(tmp_path / "t.db"))
    store.ingest(_valid_trace("a"))
    # corrupt metadata to invalid JSON
    assert store._db is not None
    store._db.execute("UPDATE traces SET metadata = 'not-json' WHERE task_id='a'")
    store._db.commit()
    got = store.get("a")
    assert got is not None
    assert got.metadata == {}


def test_trace_metadata_none_handling(tmp_path: Path) -> None:
    """_row_to_trace handles NULL metadata (meta_raw is None)."""
    store = TraceStore(str(tmp_path / "t.db"))
    store.ingest(_valid_trace("a"))
    assert store._db is not None
    store._db.execute("UPDATE traces SET metadata = NULL WHERE task_id='a'")
    store._db.commit()
    got = store.get("a")
    assert got is not None
    assert got.metadata == {}


def test_trace_row_to_trace_missing_metadata_column(tmp_path: Path) -> None:
    """_row_to_trace tolerates missing metadata column (257-258)."""
    store = TraceStore(str(tmp_path / "t.db"))

    class FakeRow(dict):  # type: ignore[type-arg]
        def __getitem__(self, key):  # type: ignore[no-untyped-def]
            if key == "metadata":
                raise KeyError("metadata")
            return super().__getitem__(key)

    row = FakeRow(
        {
            "id": 1,
            "task_id": "t1",
            "task_input": "in",
            "steps": None,
            "final_output": "out",
            "expected_output": "exp",
            "success": 1,
            "failure_reason": None,
            "timestamp": "2026-09-01T10:00:00Z",
            "prompt_version": None,
        }
    )
    trace = store._row_to_trace(row)  # type: ignore[arg-type]
    assert trace.metadata == {}
    # also test IndexError path
    row2 = FakeRow(
        {
            "id": 1,
            "task_id": "t1",
            "task_input": "in",
            "steps": None,
            "final_output": "out",
            "expected_output": "exp",
            "success": 1,
            "failure_reason": None,
            "timestamp": "2026-09-01T10:00:00Z",
            "prompt_version": None,
        }
    )

    def raise_index(key):  # type: ignore[no-untyped-def]
        if key == "metadata":
            raise IndexError("metadata")
        return dict.__getitem__(row2, key)

    row2.__getitem__ = raise_index  # type: ignore[method-assign]
    trace2 = store._row_to_trace(row2)  # type: ignore[arg-type]
    assert trace2.metadata == {}


def test_trace_migration_adds_metadata(tmp_path: Path) -> None:
    """Migration v2 adds metadata column to old DB without it."""
    db = tmp_path / "old.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE traces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            task_input TEXT NOT NULL,
            steps TEXT,
            final_output TEXT NOT NULL,
            expected_output TEXT NOT NULL,
            success INTEGER NOT NULL,
            failure_reason TEXT,
            timestamp TEXT NOT NULL,
            prompt_version INTEGER,
            processed INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()
    store = TraceStore(str(db), batch_size=5)
    store.ingest({**_valid_trace("mig"), "metadata": {"x": 1}})
    got = store.get("mig")
    assert got is not None
    assert got.metadata == {"x": 1}


def test_trace_migration_duplicate_column_swallowed(tmp_path: Path) -> None:
    """Line 124: duplicate column error is swallowed."""
    db = tmp_path / "dup.db"
    # create DB already at version 2 schema (has metadata)
    store = TraceStore(str(db))
    store.close()
    # downgrade user_version to 1 so migration tries to add metadata again
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()
    # reopen should attempt ALTER and swallow duplicate column error
    store2 = TraceStore(str(db))
    assert store2.count() == 0
    store2.close()


def test_trace_migration_other_operational_error_reraises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Line 124: non-duplicate OperationalError is re-raised."""
    import agent_self_edit.trace as trace_mod

    db = tmp_path / "err.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE traces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            task_input TEXT NOT NULL,
            steps TEXT,
            final_output TEXT NOT NULL,
            expected_output TEXT NOT NULL,
            success INTEGER NOT NULL,
            failure_reason TEXT,
            timestamp TEXT NOT NULL,
            prompt_version INTEGER,
            processed INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()
    # inject an invalid migration that raises OperationalError without "duplicate column"
    monkeypatch.setitem(trace_mod._MIGRATIONS, 2, "INVALID SQL SYNTAX;")
    with pytest.raises(sqlite3.OperationalError):
        TraceStore(str(db))


# ---------------------------------------------------------------------------
# TraceStore: count_pending, list filtering, delete_before, get_batch, etc.
# ---------------------------------------------------------------------------


def test_trace_count_pending(tmp_path: Path) -> None:
    store = TraceStore(str(tmp_path / "t.db"), batch_size=5)
    for i in range(3):
        store.ingest(_valid_trace(f"p{i}"))
    assert store.count_pending() == 3
    batch = store.get_batch(2)
    assert store.count_pending() == 1
    store.acknowledge_rows(batch)
    assert store.count_pending() == 1


def test_trace_count_pending_fallback(tmp_path: Path) -> None:
    """count_pending fallback path closes non-persistent (295)."""
    store = TraceStore(str(tmp_path / "t.db"))
    store.ingest(_valid_trace("a"))
    assert store._db is not None
    store._db.close()
    store._db = None
    assert store.count_pending() == 1
    # restore for cleanup
    store._db = sqlite3.connect(str(tmp_path / "t.db"), check_same_thread=False)
    store._db.row_factory = sqlite3.Row
    store.close()


def test_trace_list_filtering(tmp_path: Path) -> None:
    store = TraceStore(str(tmp_path / "t.db"))
    store.store(validate_trace(_valid_trace("a", success=True, prompt_version=1)))
    store.store(validate_trace(_valid_trace("b", success=False, prompt_version=2)))
    store.store(validate_trace(_valid_trace("c", success=True, prompt_version=2)))
    assert len(store.list(success=True)) == 2
    assert len(store.list(success=False)) == 1
    assert len(store.list(prompt_version=2)) == 2
    assert len(store.list(success=True, prompt_version=1)) == 1
    assert len(store.list(limit=1)) == 1
    # non-persistent list path (214)
    assert store._db is not None
    store._db.close()
    store._db = None
    assert len(store.list(success=True)) == 2
    store._db = sqlite3.connect(str(tmp_path / "t.db"), check_same_thread=False)
    store._db.row_factory = sqlite3.Row
    store.close()


def test_trace_delete_before(tmp_path: Path) -> None:
    store = TraceStore(str(tmp_path / "t.db"))
    store.store(validate_trace(_valid_trace("old", timestamp="2026-01-01T00:00:00Z")))
    store.store(validate_trace(_valid_trace("new", timestamp="2026-09-01T00:00:00Z")))
    deleted = store.delete_before("2026-06-01T00:00:00Z")
    assert deleted == 1
    assert store.get("old") is None
    assert store.get("new") is not None
    # fallback path (249)
    assert store._db is not None
    store._db.close()
    store._db = None
    store.store(validate_trace(_valid_trace("old2", timestamp="2026-01-02T00:00:00Z")))
    deleted2 = store.delete_before("2026-06-01T00:00:00Z")
    assert deleted2 == 1
    store._db = sqlite3.connect(str(tmp_path / "t.db"), check_same_thread=False)
    store._db.row_factory = sqlite3.Row
    store.close()


def test_trace_cleanup_skips_in_flight(tmp_path: Path) -> None:
    """cleanup with retention 0 skips in-flight (processed=-1), deletes after ack."""
    store = TraceStore(str(tmp_path / "t.db"), batch_size=10)
    for i in range(5):
        store.ingest(_valid_trace(f"c{i}", timestamp="2026-01-01T00:00:00Z"))
    batch = store.get_batch(3)
    assert len(batch) == 3
    # all are old but in-flight rows protected
    deleted = store.cleanup(retention_days=0)
    # in-flight protected, remaining 2 pending are deleted (processed != -1)
    assert deleted == 2
    assert store.count() == 3  # in-flight still there
    # acknowledge then cleanup deletes in-flight
    store.acknowledge_rows(batch)
    deleted2 = store.cleanup(retention_days=0)
    assert deleted2 == 3
    assert store.count() == 0
    # fallback cleanup close path (449)
    store.ingest(_valid_trace("z", timestamp="2026-01-01T00:00:00Z"))
    assert store._db is not None
    store._db.close()
    store._db = None
    deleted3 = store.cleanup(retention_days=0)
    assert deleted3 == 1
    store._db = sqlite3.connect(str(tmp_path / "t.db"), check_same_thread=False)
    store._db.row_factory = sqlite3.Row
    store.close()


def test_trace_get_batch_and_acknowledge(tmp_path: Path) -> None:
    store = TraceStore(str(tmp_path / "t.db"), batch_size=10)
    for i in range(4):
        store.ingest(_valid_trace(f"t{i}"))
    batch = store.get_batch(2)
    assert [t.task_id for t in batch] == ["t0", "t1"]
    # get_batch with no pending returns []
    store.acknowledge_rows(batch)
    store.acknowledge_rows(store.get_batch(10))
    assert store.get_batch(10) == []
    # get_batch fallback non-persistent (330)
    assert store._db is not None
    store._db.close()
    store._db = None
    store.ingest(_valid_trace("new1"))
    store.ingest(_valid_trace("new2"))
    # need to re-create persistent? fallback get_batch should still work
    b2 = store.get_batch(1)
    assert len(b2) == 1
    store._db = sqlite3.connect(str(tmp_path / "t.db"), check_same_thread=False)
    store._db.row_factory = sqlite3.Row
    store.close()


def test_trace_acknowledge_rows_edge_cases(tmp_path: Path) -> None:
    store = TraceStore(str(tmp_path / "t.db"))
    # empty list no-op (334-335)
    store.acknowledge_rows([])
    # traces with no row_id no-op (337-338)
    t = validate_trace(_valid_trace("a"))
    # t.row_id is None by default
    assert t.row_id is None
    store.ingest(_valid_trace("b"))
    store.acknowledge_rows([t])
    # normal acknowledge
    batch = store.get_batch(1)
    store.acknowledge_rows(batch)
    assert store.count_pending() == 0
    # fallback non-persistent acknowledge_rows
    store.ingest(_valid_trace("c"))
    batch2 = store.get_batch(1)
    assert store._db is not None
    store._db.close()
    store._db = None
    store.acknowledge_rows(batch2)
    store._db = sqlite3.connect(str(tmp_path / "t.db"), check_same_thread=False)
    store._db.row_factory = sqlite3.Row
    store.close()


def test_trace_release_in_flight(tmp_path: Path) -> None:
    store = TraceStore(str(tmp_path / "t.db"), batch_size=10)
    for i in range(3):
        store.ingest(_valid_trace(f"r{i}"))
    batch = store.get_batch(2)
    assert store.count_pending() == 1
    # release_in_flight puts them back to pending
    store.release_in_flight(batch)
    assert store.count_pending() == 3
    # empty no-op (355-356)
    store.release_in_flight([])
    # no row_id no-op (357-359)
    t = validate_trace(_valid_trace("x"))
    store.release_in_flight([t])
    # fallback non-persistent (372)
    batch2 = store.get_batch(2)
    assert store._db is not None
    store._db.close()
    store._db = None
    store.release_in_flight(batch2)
    assert store.count_pending() == 3
    store._db = sqlite3.connect(str(tmp_path / "t.db"), check_same_thread=False)
    store._db.row_factory = sqlite3.Row
    store.close()


def test_trace_release_in_flight_after_exception(tmp_path: Path) -> None:
    """_run_once releases in-flight on analyzer exception (covers release_in_flight)."""
    from agent_self_edit.cli.run import _run_once
    from agent_self_edit.registry import Registry

    reg_path = tmp_path / "reg"
    db_path = tmp_path / "db.sqlite"
    reg = Registry(str(reg_path))
    reg.create("hello world prompt for testing drift and frozen")
    task_path = tmp_path / "tasks.yaml"
    task_path.write_text(
        yaml.dump([{"id": "t1", "input": "hi", "expected_output": "hello"}])
    )
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(
        yaml.dump(
            {
                "project": {"name": "test", "registry_path": str(reg_path), "trace_path": str(db_path)},
                "tasks": {"task_set_path": str(task_path), "batch_size": 2, "sample_floor": 1},
                "llm": {"provider": "mock"},
                "ab_test": {"n_resamples": 10, "n_permutations": 10},
                "gate": {"max_edit_distance": 100, "drift_threshold": 1.0},
            }
        )
    )
    # use same store instance passed in so we can check pending after
    store = TraceStore(str(db_path), batch_size=2)
    for i in range(2):
        store.ingest(
            {
                "task_id": f"ex{i}",
                "task_input": "hi",
                "final_output": "bad",
                "expected_output": "good",
                "success": False,
                "timestamp": "2026-09-01T10:00:00Z",
            }
        )
    with patch("agent_self_edit.analyzer._llm_call", side_effect=Exception("boom")):
        try:
            _run_once(str(cfg_path), batch_size=2, dry_run=False, rejection_context="old", store=store)
        except Exception:
            pass
    assert store.count_pending() == 2


def test_trace_acknowledge_and_acknowledge_batch(tmp_path: Path) -> None:
    store = TraceStore(str(tmp_path / "t.db"), batch_size=10)
    for i in range(3):
        store.ingest(_valid_trace(f"a{i}"))
    # acknowledge legacy by task_id (covers 390)
    store.acknowledge(["a0"])
    assert store.count_pending() == 2
    store.acknowledge([])  # no-op 376-377
    # fallback acknowledge non-persistent (390)
    assert store._db is not None
    store._db.close()
    store._db = None
    store.acknowledge(["a1"])
    assert store.count_pending() == 1
    store._db = sqlite3.connect(str(tmp_path / "t.db"), check_same_thread=False)
    store._db.row_factory = sqlite3.Row
    # need fresh traces for acknowledge_batch
    for i in range(2):
        store.ingest(_valid_trace(f"b{i}"))
    batch = store.get_batch(2)
    # acknowledge_batch edge: empty and no row_id
    store.acknowledge_batch([])
    t_noid = validate_trace(_valid_trace("noid"))
    store.acknowledge_batch([t_noid])
    # normal acknowledge_batch (398-415)
    store.acknowledge_batch(batch)
    assert store.count_pending() == 1  # a2 still pending
    # fallback acknowledge_batch (415)
    batch2 = store.get_batch(1)
    assert len(batch2) == 1
    assert store._db is not None
    store._db.close()
    store._db = None
    store.acknowledge_batch(batch2)
    store._db = sqlite3.connect(str(tmp_path / "t.db"), check_same_thread=False)
    store._db.row_factory = sqlite3.Row
    assert store.count_pending() == 0
    store.close()


def test_trace_store_returns_row_id_and_batched(tmp_path: Path) -> None:
    """Covers 157/161 via store fallback when _db is None."""
    store = TraceStore(str(tmp_path / "t.db"))
    assert store._db is not None
    store._db.close()
    store._db = None
    trace = validate_trace(_valid_trace("fallback"))
    row_id = store.store(trace)
    assert row_id > 0
    store._db = sqlite3.connect(str(tmp_path / "t.db"), check_same_thread=False)
    store._db.row_factory = sqlite3.Row
    # also cover count fallback for success filter (236)
    assert store.count(success=True) == 1
    # get fallback (186)
    assert store.get("fallback") is not None
    store.close()


# ---------------------------------------------------------------------------
# TaskSet / load_task_set
# ---------------------------------------------------------------------------


def test_validate_manifest_invalid_domain() -> None:
    errs = validate_manifest([], {"domain": "bad_domain"})
    assert any("Invalid domain" in e for e in errs)


def test_validate_manifest_invalid_scorer() -> None:
    errs = validate_manifest([], {"scorer": "bad_scorer"})
    assert any("Invalid scorer" in e for e in errs)


def test_validate_manifest_invalid_role() -> None:
    errs = validate_manifest([], {"benchmark_role": "bad_role"})
    assert any("Invalid benchmark_role" in e for e in errs)


def test_validate_manifest_required_count_insufficient() -> None:
    errs = validate_manifest([{"id": "t1"}], {"required_count": 5})
    assert any("minimum required" in e for e in errs)


def test_validate_manifest_valid_and_none() -> None:
    assert validate_manifest([], None) == []
    assert validate_manifest([{"id": "t1"}], {"domain": "classification"}) == []
    assert validate_manifest([{"id": "t1"}], {"scorer": "exact"}) == []
    assert validate_manifest([{"id": "t1"}], {"benchmark_role": "held_out"}) == []
    # required_count satisfied
    assert validate_manifest([{"id": "t1"}, {"id": "t2"}], {"required_count": 2}) == []


def test_taskset_benchmark_role() -> None:
    ts = TaskSet()
    assert ts.benchmark_role() is None
    ts.add_task(Task(id="t1", input="x", expected_output="y", metadata={"benchmark_role": "held_out"}))
    assert ts.benchmark_role() == "held_out"


def test_taskset_validate_benchmark_roles_mixed_and_invalid() -> None:
    ts = TaskSet()
    ts.add_task(Task(id="t1", input="x", expected_output="y", metadata={"benchmark_role": "held_out"}))
    ts.add_task(Task(id="t2", input="x", expected_output="y", metadata={"benchmark_role": "adversarial"}))
    errs = ts.validate_benchmark_roles()
    assert any("Mixed benchmark roles" in e for e in errs)
    ts2 = TaskSet()
    ts2.add_task(Task(id="t1", input="x", expected_output="y", metadata={"benchmark_role": "bad_role"}))
    errs2 = ts2.validate_benchmark_roles()
    assert any("invalid benchmark_role" in e.lower() for e in errs2)
    # valid single role produces no errors
    ts3 = TaskSet()
    ts3.add_task(Task(id="t1", input="x", expected_output="y", metadata={"benchmark_role": "held_out"}))
    assert ts3.validate_benchmark_roles() == []


def test_load_task_set_empty_list_yaml(tmp_path: Path) -> None:
    p = tmp_path / "empty.yaml"
    p.write_text("[]\n")
    with pytest.raises(TaskSetError, match="empty"):
        load_task_set(p)


def test_load_task_set_empty_tasks_key_yaml(tmp_path: Path) -> None:
    p = tmp_path / "empty2.yaml"
    p.write_text(yaml.dump({"tasks": []}))
    with pytest.raises(TaskSetError, match="empty"):
        load_task_set(p)


def test_load_task_set_empty_tasks_key_json(tmp_path: Path) -> None:
    p = tmp_path / "empty.json"
    p.write_text(json.dumps({"tasks": []}))
    with pytest.raises(TaskSetError, match="empty"):
        load_task_set(p)


def test_load_task_set_empty_task_list_key_yaml(tmp_path: Path) -> None:
    p = tmp_path / "empty3.yaml"
    p.write_text(yaml.dump({"task_list": []}))
    with pytest.raises(TaskSetError, match="empty"):
        load_task_set(p)


def test_load_task_set_empty_dict_tasks_via_json(tmp_path: Path) -> None:
    p = tmp_path / "empty4.json"
    p.write_text(json.dumps({"manifest": {}, "tasks": []}))
    with pytest.raises(TaskSetError, match="empty"):
        load_task_set(p)


def test_load_task_set_with_tasks_key_ok(tmp_path: Path) -> None:
    # dict with tasks key via yaml
    p = tmp_path / "ok.yaml"
    p.write_text(yaml.dump({"tasks": [{"id": "t1", "input": "x", "expected_output": "y"}]}))
    ts = load_task_set(p)
    assert len(ts) == 1
    # dict with tasks via json
    p2 = tmp_path / "ok.json"
    p2.write_text(json.dumps({"tasks": [{"id": "t1", "input": "x", "expected_output": "y"}]}))
    ts2 = load_task_set(p2)
    assert len(ts2) == 1
    # dict with task_list key
    p3 = tmp_path / "ok2.yaml"
    p3.write_text(yaml.dump({"task_list": [{"id": "t1", "input": "x", "expected_output": "y"}]}))
    ts3 = load_task_set(p3)
    assert len(ts3) == 1
    # plain list via yaml
    p4 = tmp_path / "plain.yaml"
    p4.write_text(yaml.dump([{"id": "t1", "input": "x", "expected_output": "y"}]))
    ts4 = load_task_set(p4)
    assert len(ts4) == 1
    # plain list via json
    p5 = tmp_path / "plain.json"
    p5.write_text(json.dumps([{"id": "t1", "input": "x", "expected_output": "y"}]))
    ts5 = load_task_set(p5)
    assert len(ts5) == 1


def test_load_task_set_manifest_invalid_domain(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.dump({"manifest": {"domain": "bad_domain"}, "tasks": [{"id": "t1", "input": "x", "expected_output": "y"}]}))
    with pytest.raises(TaskSetError, match="Invalid domain"):
        load_task_set(p)


def test_load_task_set_manifest_invalid_scorer(tmp_path: Path) -> None:
    p = tmp_path / "bad2.yaml"
    p.write_text(yaml.dump({"manifest": {"scorer": "bad"}, "tasks": [{"id": "t1", "input": "x", "expected_output": "y"}]}))
    with pytest.raises(TaskSetError, match="Invalid scorer"):
        load_task_set(p)


def test_load_task_set_manifest_invalid_role(tmp_path: Path) -> None:
    p = tmp_path / "bad3.yaml"
    p.write_text(yaml.dump({"manifest": {"benchmark_role": "bad"}, "tasks": [{"id": "t1", "input": "x", "expected_output": "y"}]}))
    with pytest.raises(TaskSetError, match="Invalid benchmark_role"):
        load_task_set(p)


def test_load_task_set_manifest_required_count(tmp_path: Path) -> None:
    p = tmp_path / "bad4.yaml"
    p.write_text(yaml.dump({"manifest": {"required_count": 5}, "tasks": [{"id": "t1", "input": "x", "expected_output": "y"}]}))
    with pytest.raises(TaskSetError, match="minimum required"):
        load_task_set(p)


def test_load_task_set_manifest_valid(tmp_path: Path) -> None:
    p = tmp_path / "good.yaml"
    p.write_text(
        yaml.dump(
            {
                "manifest": {"domain": "classification", "scorer": "exact", "benchmark_role": "held_out"},
                "tasks": [{"id": "t1", "input": "x", "expected_output": "y"}],
            }
        )
    )
    ts = load_task_set(p)
    assert ts.manifest["domain"] == "classification"


def test_load_task_set_tasks_not_list(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.dump({"tasks": "not-a-list"}))
    with pytest.raises(TaskSetError, match="'tasks' must be a list"):
        load_task_set(p)
    # also covers isinstance(tasks_data, list) second check (159) when top-level is dict with tasks as list but later data is not list
    # the non-list data path via plain non-dict list is covered below


def test_load_task_set_tasks_data_not_list_second_check(tmp_path: Path) -> None:
    # This hits the second isinstance check at 159 via plain data that is not list/dict
    # But plain string in yaml will be loaded as string, not list, so it hits that branch
    p = tmp_path / "bad2.yaml"
    p.write_text("just: a string dict but tasks key missing\n")
    # This will raise "must be a list of tasks or a dict with 'tasks' key"
    with pytest.raises(TaskSetError):
        load_task_set(p)


def test_load_task_set_non_list_top_level(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"tasks": [{"id": "t1", "input": "x", "expected_output": "y"}]}))
    # force tasks_data to be non-list but via dict path already tested; also test directly _validate
    # cover _validate_task_list via load: use string as data
    p2 = tmp_path / "bad2.json"
    p2.write_text(json.dumps("not a list"))
    with pytest.raises(TaskSetError, match="must be a list"):
        load_task_set(p2)


# Additional coverage for remaining tasks.py branches


def test_taskset_add_remove_list_get_len(tmp_path: Path) -> None:  # noqa: ARG001
    ts = TaskSet()
    t1 = Task(id="t1", input="x", expected_output="y")
    t2 = Task(id="t2", input="x", expected_output="y")
    ts.add_task(t1)
    ts.add_task(t2)
    assert len(ts) == 2
    assert ts.get_task("t1") == t1
    assert len(ts.list_tasks()) == 2
    ts.remove_task("t1")
    assert len(ts) == 1
    assert ts.get_task("t1") is None
    ts.remove_task("nonexistent")


def test_load_task_set_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_task_set(tmp_path / "nope.yaml")


def test_load_task_set_invalid_yaml(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("not: valid: yaml: [")
    with pytest.raises(TaskSetError, match="Invalid YAML"):
        load_task_set(p)


def test_load_task_set_invalid_json(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{invalid json")
    with pytest.raises(TaskSetError, match="Invalid JSON"):
        load_task_set(p)


def test_load_task_set_unsupported_format(tmp_path: Path) -> None:
    p = tmp_path / "bad.toml"
    p.write_text("[task]\nid='t1'")
    with pytest.raises(TaskSetError, match="Unsupported format"):
        load_task_set(p)


def test_load_task_set_dict_missing_tasks_key(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.dump({"id": "t1", "input": "x"}))
    with pytest.raises(TaskSetError, match="must be a list"):
        load_task_set(p)


def test_load_task_set_validation_errors(tmp_path: Path) -> None:
    # non-mapping item
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.dump([{"id": "t1", "input": "x", "expected_output": "y"}, 42]))
    with pytest.raises(TaskSetError, match="must be a mapping"):
        load_task_set(p)
    # non-string id
    p2 = tmp_path / "bad2.yaml"
    p2.write_text(yaml.dump([{"id": 42, "input": "x", "expected_output": "y"}]))
    with pytest.raises(TaskSetError, match="'id' must be a string"):
        load_task_set(p2)
    # missing id
    p3 = tmp_path / "bad3.yaml"
    p3.write_text(yaml.dump([{"input": "x", "expected_output": "y"}]))
    with pytest.raises(TaskSetError, match="missing required field 'id'"):
        load_task_set(p3)
    # missing input / expected_output
    p4 = tmp_path / "bad4.yaml"
    p4.write_text(yaml.dump([{"id": "t1", "expected_output": "y"}]))
    with pytest.raises(TaskSetError, match="missing required field 'input'"):
        load_task_set(p4)
    p5 = tmp_path / "bad5.yaml"
    p5.write_text(yaml.dump([{"id": "t1", "input": "x"}]))
    with pytest.raises(TaskSetError, match="missing required field 'expected_output'"):
        load_task_set(p5)
    # duplicate id
    p6 = tmp_path / "bad6.yaml"
    p6.write_text(yaml.dump([{"id": "t1", "input": "x", "expected_output": "y"}, {"id": "t1", "input": "z", "expected_output": "w"}]))
    with pytest.raises(TaskSetError, match="duplicate id"):
        load_task_set(p6)


def test_trace_batch_ready_and_cleanup_negative(tmp_path: Path) -> None:
    store = TraceStore(str(tmp_path / "t.db"), batch_size=2)
    assert store.batch_ready() is False
    store.ingest(_valid_trace("a"))
    assert store.batch_ready() is False
    store.ingest(_valid_trace("b"))
    assert store.batch_ready() is True
    with pytest.raises(ValueError):
        store.cleanup(retention_days=-1)


def test_trace_schema_newer_raises(tmp_path: Path) -> None:
    db = tmp_path / "newer.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA user_version = 99")
    conn.commit()
    conn.close()
    with pytest.raises(RuntimeError, match="newer than"):
        TraceStore(str(db))


def test_trace_store_row_id_none_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover line 157: lastrowid is None raises RuntimeError."""
    store = TraceStore(str(tmp_path / "t.db"))

    class FakeCursor:
        lastrowid = None

        def __class_getitem__(cls, item):  # noqa: ARG003
            return cls

    class FakeConn:
        row_factory = None

        def execute(self, *a, **kw):  # type: ignore[no-untyped-def]
            return FakeCursor()

        def commit(self):  # type: ignore[no-untyped-def]
            pass

        def close(self):  # type: ignore[no-untyped-def]
            pass

    # monkeypatch _connect to return FakeConn that returns None lastrowid
    monkeypatch.setattr(store, "_connect", lambda: FakeConn())
    monkeypatch.setattr(store, "_is_persistent", lambda c: False)
    trace = validate_trace(_valid_trace("x"))
    with pytest.raises(RuntimeError, match="Failed to retrieve"):
        store.store(trace)
    store.close()
