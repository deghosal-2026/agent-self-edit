import json
import tempfile
from pathlib import Path

import yaml

from agent_self_edit.tasks import Task, TaskSet, TaskSetError, load_task_set

_VALID_TASKS = [
    {"id": "t1", "input": "classify this", "expected_output": "cat_a"},
    {
        "id": "t2",
        "input": "classify that",
        "expected_output": "cat_b",
        "metadata": {"difficulty": "hard"},
    },
]


def _write_yaml(data) -> Path:
    tmp = Path(tempfile.mktemp(suffix=".yaml"))
    with open(tmp, "w") as f:
        yaml.dump(data, f)
    return tmp


def _write_json(data) -> Path:
    tmp = Path(tempfile.mktemp(suffix=".json"))
    with open(tmp, "w") as f:
        json.dump(data, f)
    return tmp


def test_load_yaml():
    path = _write_yaml(_VALID_TASKS)
    ts = load_task_set(path)
    assert len(ts) == 2
    assert ts.get_task("t1") is not None
    assert ts.get_task("t2") is not None


def test_load_json():
    path = _write_json(_VALID_TASKS)
    ts = load_task_set(path)
    assert len(ts) == 2


def test_empty_task_set():
    path = _write_yaml([])
    try:
        load_task_set(path)
        assert False, "expected TaskSetError for empty task set"
    except TaskSetError as e:
        assert "empty" in str(e).lower()


def test_missing_file():
    try:
        load_task_set("/nonexistent/tasks.yaml")
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass


def test_invalid_yaml():
    path = Path(tempfile.mktemp(suffix=".yaml"))
    path.write_text("not: valid: yaml: [")
    try:
        load_task_set(path)
        assert False, "expected TaskSetError"
    except TaskSetError as e:
        assert "Invalid YAML" in str(e)


def test_invalid_json():
    path = Path(tempfile.mktemp(suffix=".json"))
    path.write_text("{invalid json")
    try:
        load_task_set(path)
        assert False, "expected TaskSetError"
    except TaskSetError as e:
        assert "Invalid JSON" in str(e)


def test_non_mapping_task_item():
    path = _write_yaml([{"id": "t1", "input": "x", "expected_output": "y"}, 42])
    try:
        load_task_set(path)
        assert False, "expected TaskSetError"
    except TaskSetError as e:
        assert "must be a mapping" in str(e)


def test_non_string_id():
    path = _write_yaml([{"id": 42, "input": "x", "expected_output": "y"}])
    try:
        load_task_set(path)
        assert False, "expected TaskSetError"
    except TaskSetError as e:
        assert "'id' must be a string" in str(e)


def test_missing_id():
    path = _write_yaml([{"input": "x", "expected_output": "y"}])
    try:
        load_task_set(path)
        assert False, "expected TaskSetError"
    except TaskSetError as e:
        assert "missing required field 'id'" in str(e)


def test_missing_input():
    path = _write_yaml([{"id": "t1", "expected_output": "y"}])
    try:
        load_task_set(path)
        assert False, "expected TaskSetError"
    except TaskSetError as e:
        assert "missing required field 'input'" in str(e)


def test_missing_expected_output():
    path = _write_yaml([{"id": "t1", "input": "x"}])
    try:
        load_task_set(path)
        assert False, "expected TaskSetError"
    except TaskSetError as e:
        assert "missing required field 'expected_output'" in str(e)


def test_duplicate_ids():
    data = [
        {"id": "t1", "input": "x", "expected_output": "y"},
        {"id": "t1", "input": "z", "expected_output": "w"},
    ]
    path = _write_yaml(data)
    try:
        load_task_set(path)
        assert False, "expected TaskSetError"
    except TaskSetError as e:
        assert "duplicate id" in str(e)


def test_non_list_data():
    path = _write_yaml({"id": "t1", "input": "x"})
    try:
        load_task_set(path)
        assert False, "expected TaskSetError"
    except TaskSetError as e:
        assert "must be a list" in str(e)


def test_add_task():
    ts = TaskSet()
    task = Task(id="t1", input="x", expected_output="y")
    ts.add_task(task)
    assert len(ts) == 1
    assert ts.get_task("t1") == task


def test_remove_task():
    ts = TaskSet()
    ts.add_task(Task(id="t1", input="x", expected_output="y"))
    ts.remove_task("t1")
    assert len(ts) == 0
    assert ts.get_task("t1") is None


def test_list_tasks():
    ts = TaskSet()
    ts.add_task(Task(id="t1", input="x", expected_output="y"))
    ts.add_task(Task(id="t2", input="z", expected_output="w"))
    tasks = ts.list_tasks()
    assert len(tasks) == 2
    assert tasks[0].id in ("t1", "t2")
    assert tasks[1].id in ("t1", "t2")
    assert tasks[0].id != tasks[1].id


def test_remove_nonexistent():
    ts = TaskSet()
    ts.remove_task("nonexistent")
    assert len(ts) == 0


def test_unsupported_format():
    path = Path(tempfile.mktemp(suffix=".toml"))
    path.write_text("[task]\nid = 't1'")
    try:
        load_task_set(str(path))
        assert False, "expected TaskSetError"
    except TaskSetError as e:
        assert "Unsupported format" in str(e)


def test_concurrent_add_remove():
    import threading
    ts = TaskSet()
    errors = []

    def worker(n):
        try:
            for i in range(20):
                ts.add_task(Task(id=f"t{n}-{i}", input=str(i), expected_output=str(i)))
                if i % 2 == 0:
                    ts.remove_task(f"t{n}-{i}")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(ts) > 0
