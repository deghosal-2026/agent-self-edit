import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class TaskSetError(Exception):
    """Raised on task set validation failure."""


@dataclass(frozen=True)
class Task:
    id: str
    input: str
    expected_output: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskSet:
    tasks: dict[str, Task] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add_task(self, task: Task) -> None:
        with self._lock:
            self.tasks[task.id] = task

    def remove_task(self, task_id: str) -> None:
        with self._lock:
            self.tasks.pop(task_id, None)

    def list_tasks(self) -> list[Task]:
        with self._lock:
            return list(self.tasks.values())

    def get_task(self, task_id: str) -> Task | None:
        with self._lock:
            return self.tasks.get(task_id)

    def __len__(self) -> int:
        with self._lock:
            return len(self.tasks)


def load_task_set(path: str | Path) -> TaskSet:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Task set file not found: {path}")
    raw_text = path.read_text()
    if path.suffix in (".yaml", ".yml"):
        try:
            data = yaml.safe_load(raw_text)
        except yaml.YAMLError as e:
            raise TaskSetError(f"Invalid YAML in task set: {e}") from e
    elif path.suffix == ".json":
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise TaskSetError(f"Invalid JSON in task set: {e}") from e
    else:
        raise TaskSetError(f"Unsupported format: {path.suffix} (use .yaml, .yml, or .json)")

    if not isinstance(data, list):
        raise TaskSetError("Task set must be a list of tasks")

    errors = _validate_task_list(data)
    if errors:
        raise TaskSetError("; ".join(errors))

    tasks = {}
    for item in data:
        task = Task(
            id=item["id"],
            input=item["input"],
            expected_output=item["expected_output"],
            metadata=item.get("metadata", {}),
        )
        tasks[task.id] = task

    return TaskSet(tasks=tasks)


def _validate_task_list(data: list[Any]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            errors.append(f"Task #{i}: must be a mapping, got {type(item).__name__}")
            continue
        task_id = item.get("id")
        if not task_id:
            errors.append(f"Task #{i}: missing required field 'id'")
        elif not isinstance(task_id, str):
            errors.append(f"Task #{i}: 'id' must be a string, got {type(task_id).__name__}")
        elif task_id in seen_ids:
            errors.append(f"Task #{i}: duplicate id '{task_id}'")
        else:
            seen_ids.add(task_id)

        if "input" not in item:
            errors.append(f"Task #{i}: missing required field 'input'")
        if "expected_output" not in item:
            errors.append(f"Task #{i}: missing required field 'expected_output'")
    return errors
