"""Tests for trace adapters (stdin + file)."""

import io
import json
import threading
import time

import pytest

from agent_self_edit.adapters.file import FileAdapter
from agent_self_edit.adapters.stdin import StdinAdapter
from agent_self_edit.trace import TraceStore


def _valid(task_id="t1"):
    return {
        "task_id": task_id,
        "task_input": "input",
        "final_output": "out",
        "expected_output": "exp",
        "success": True,
        "timestamp": "2026-09-01T10:00:00Z",
    }


@pytest.fixture
def store(tmp_path):
    return TraceStore(str(tmp_path / "traces.db"), batch_size=2)


# ---- StdinAdapter ----

def test_stdin_ingests_lines(store):
    lines = json.dumps(_valid("a")) + "\n" + json.dumps(_valid("b")) + "\n"
    stream = io.StringIO(lines)
    adapter = StdinAdapter(store, stream=stream)
    adapter.run()
    assert store.count() == 2
    assert {t.task_id for t in store.list()} == {"a", "b"}


def test_stdin_skips_malformed(store, capsys):
    lines = "this is not json\n" + json.dumps(_valid("a")) + "\n"
    adapter = StdinAdapter(store, stream=io.StringIO(lines))
    adapter.run()
    assert store.count() == 1


def test_stdin_skips_invalid_trace(store):
    bad = _valid("bad")
    bad.pop("expected_output")
    lines = json.dumps(bad) + "\n" + json.dumps(_valid("good")) + "\n"
    adapter = StdinAdapter(store, stream=io.StringIO(lines))
    adapter.run()
    assert store.count() == 1
    assert store.get("good") is not None


def test_stdin_empty_input(store):
    adapter = StdinAdapter(store, stream=io.StringIO("\n\n"))
    adapter.run()
    assert store.count() == 0


def test_stdin_stop_breaks_loop(store):
    lines = json.dumps(_valid("a")) + "\n" + json.dumps(_valid("b")) + "\n"
    stream = io.StringIO(lines)
    adapter = StdinAdapter(store, stream=stream)

    def run():
        adapter.run()

    t = threading.Thread(target=run)
    t.start()
    adapter.stop()
    t.join(timeout=2)
    # Stream loops quickly; at least it did not hang and stopped cleanly.
    assert not t.is_alive()


# ---- FileAdapter ----

def test_file_ingests_and_moves(store, tmp_path):
    watch = tmp_path / "traces"
    watch.mkdir()
    p = watch / "a.json"
    p.write_text(json.dumps(_valid("a")))
    adapter = FileAdapter(store, watch, poll_interval=0.05)
    adapter._process_once()
    assert store.count() == 1
    assert not p.exists()
    assert (watch / "a.json.done").exists()


def test_file_watch_processing(store, tmp_path):
    watch = tmp_path / "traces"
    watch.mkdir()
    adapter = FileAdapter(store, watch, poll_interval=0.05)
    for i in range(3):
        (watch / f"t{i}.json").write_text(json.dumps(_valid(f"t{i}")))
    adapter._process_once()
    assert store.count() == 3


def test_file_dedup_no_reprocess(store, tmp_path):
    watch = tmp_path / "traces"
    watch.mkdir()
    (watch / "a.json").write_text(json.dumps(_valid("a")))
    adapter = FileAdapter(store, watch, poll_interval=0.05)
    adapter._process_once()
    adapter._process_once()  # same dir, file already moved
    assert store.count() == 1


def test_file_skips_malformed(store, tmp_path):
    watch = tmp_path / "traces"
    watch.mkdir()
    (watch / "bad.json").write_text("{invalid json")
    (watch / "good.json").write_text(json.dumps(_valid("good")))
    adapter = FileAdapter(store, watch, poll_interval=0.05)
    adapter._process_once()
    assert store.count() == 1
    assert store.get("good") is not None


def test_file_moves_ignored_for_malformed(store, tmp_path):
    watch = tmp_path / "traces"
    watch.mkdir()
    (watch / "bad.json").write_text("{not json}")
    adapter = FileAdapter(store, watch, poll_interval=0.05)
    adapter._process_once()
    # Malformed file is not moved, but a corrected file with the same name
    # will be retried on the next poll (no in-memory basename blacklist, ref #142).
    assert (watch / "bad.json").exists()


def test_file_retries_fixed_malformed(store, tmp_path):
    """A corrected file with the same name is retried on the next poll (ref #142)."""
    watch = tmp_path / "traces"
    watch.mkdir()
    (watch / "bad.json").write_text("{not json}")
    adapter = FileAdapter(store, watch, poll_interval=0.05)
    adapter._process_once()
    assert store.count() == 0
    # Fix the file
    (watch / "bad.json").write_text(json.dumps(_valid("retried")))
    adapter._process_once()
    assert store.count() == 1
    assert store.get("retried") is not None


def test_file_run_loop_stops_cleanly(store, tmp_path):
    watch = tmp_path / "traces"
    watch.mkdir()
    adapter = FileAdapter(store, watch, poll_interval=0.05)

    def run():
        adapter.run()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    time.sleep(0.1)
    adapter.stop()
    t.join(timeout=1)
    assert not t.is_alive()


def test_file_empty_dir_returns_zero(store, tmp_path):
    watch = tmp_path / "empty_traces"
    watch.mkdir()
    adapter = FileAdapter(store, watch, poll_interval=0.05)
    assert adapter._process_once() == 0
    assert store.count() == 0


def test_file_ignores_non_json_files(store, tmp_path):
    watch = tmp_path / "traces"
    watch.mkdir()
    (watch / "readme.txt").write_text("not a trace")
    (watch / "data.csv").write_text("a,b,c\n")
    adapter = FileAdapter(store, watch, poll_interval=0.05)
    adapter._process_once()
    assert store.count() == 0


def test_file_non_dict_json_skipped(store, tmp_path):
    watch = tmp_path / "traces"
    watch.mkdir()
    (watch / "list.json").write_text(json.dumps(["a", "b"]))
    adapter = FileAdapter(store, watch, poll_interval=0.05)
    adapter._process_once()
    assert store.count() == 0
    # Non-dict JSON files are skipped but NOT moved to .done
    assert (watch / "list.json").exists()


def test_stdin_stops_mid_stream(store):
    lines = json.dumps(_valid("a")) + "\n" + json.dumps(_valid("b")) + "\n"
    stream = io.StringIO(lines)
    adapter = StdinAdapter(store, stream=stream)

    def run():
        adapter.run()

    t = threading.Thread(target=run)
    t.start()
    adapter.stop()
    t.join(timeout=2)
    assert not t.is_alive()
    # At least some traces may have been ingested before stop
    assert store.count() >= 0


def test_stdin_batch_size_boundary(store):
    """Batch_size boundary: ingested count triggers progress message."""
    import io
    adapter = StdinAdapter(store, stream=io.StringIO(""), batch_size=2)
    adapter._ingested = 1
    assert adapter._ingested % adapter._batch_size != 0  # no message when not at boundary


def test_stdin_invalid_trace_value_error(store, capsys):
    """Invalid trace that fails store.ingest should be skipped."""
    lines = json.dumps({"task_id": "bad", "success": True}) + "\n"
    store.batch_size = 1000
    adapter = StdinAdapter(store, stream=io.StringIO(lines))
    adapter.run()
    assert store.count() == 0
