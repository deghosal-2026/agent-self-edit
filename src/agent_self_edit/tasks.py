import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class TaskSetError(Exception):
    """Raised on task set validation failure."""


VALID_BENCHMARK_ROLES = {
    "failure_seeding", "promotion_ab", "held_out",
    "regression_sentinel", "adversarial",
}

VALID_DOMAINS = {"classification", "extraction", "generation", "mixed"}

VALID_SCORERS = {
    "exact", "exactset", "exact_set", "partialset", "partial_set",
    "contains", "structured", "llmjudge", "llm_judge",
}


@dataclass(frozen=True)
class TaskSetManifest:
    """Top-level manifest fields for a task set."""
    domain: str = ""
    scorer: str = ""
    benchmark_role: str = ""
    judge_rubric: str = ""
    normalization: str = ""
    allow_for_analyzer_seed: bool = False
    required_count: int = 0


def validate_manifest(
    data: list[dict[str, Any]],
    top_level: dict[str, Any] | None = None,
) -> list[str]:
    """Validate manifest-level fields and per-task metadata consistency."""
    errors: list[str] = []
    if top_level is None:
        return errors

    domain = top_level.get("domain", "")
    if domain and domain not in VALID_DOMAINS:
        errors.append(f"Invalid domain '{domain}' — must be one of {VALID_DOMAINS}")

    scorer = top_level.get("scorer", "")
    if scorer and scorer not in VALID_SCORERS:
        errors.append(f"Invalid scorer '{scorer}' — must be one of {VALID_SCORERS}")

    role = top_level.get("benchmark_role", "")
    if role and role not in VALID_BENCHMARK_ROLES:
        errors.append(f"Invalid benchmark_role '{role}'")

    required = top_level.get("required_count", 0)
    if required and len(data) < required:
        errors.append(
            f"Task set has {len(data)} tasks, minimum required is {required}"
        )

    return errors


@dataclass(frozen=True)
class Task:
    id: str
    input: str
    expected_output: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskSet:
    tasks: dict[str, Task] = field(default_factory=dict)
    manifest: dict[str, Any] = field(default_factory=dict)
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

    def benchmark_role(self) -> str | None:
        """Return the benchmark role declared in task metadata, or None."""
        for task in self.list_tasks():
            role: str | None = task.metadata.get("benchmark_role")
            if role:
                return role
        return None

    def validate_benchmark_roles(self) -> list[str]:
        """Check that all tasks declare the same benchmark_role and that it's valid."""
        errors: list[str] = []
        roles_seen: set[str] = set()
        for task in self.list_tasks():
            role = task.metadata.get("benchmark_role")
            if role:
                roles_seen.add(role)
                if role not in VALID_BENCHMARK_ROLES:
                    errors.append(f"Task '{task.id}': invalid benchmark_role '{role}'")
        if len(roles_seen) > 1:
            errors.append(f"Mixed benchmark roles in task set: {roles_seen}")
        return errors


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

    if isinstance(data, dict):
        if "tasks" not in data and "task_list" not in data:
            raise TaskSetError("Task set must be a list of tasks or a dict with 'tasks' key")
        manifest = data.get("manifest", {})
        tasks_data = data.get("tasks", data.get("task_list", []))
        if not isinstance(tasks_data, list):
            raise TaskSetError("'tasks' must be a list")
        man_errors = validate_manifest(tasks_data, manifest)
        if man_errors:
            raise TaskSetError("; ".join(man_errors))
    else:
        tasks_data = data
        manifest = {}

    if not isinstance(tasks_data, list):
        raise TaskSetError("Task set must be a list of tasks")

    errors = _validate_task_list(tasks_data)
    if errors:
        raise TaskSetError("; ".join(errors))

    tasks = {}
    for item in tasks_data:
        task = Task(
            id=item["id"],
            input=item["input"],
            expected_output=item["expected_output"],
            metadata=item.get("metadata", {}),
        )
        tasks[task.id] = task

    if not tasks:
        raise TaskSetError(f"Task set is empty in {path} — add at least one task")

    return TaskSet(tasks=tasks, manifest=dict(manifest))


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


@dataclass(frozen=True)
class SeededPrompt:
    """A prompt with known failure modes on specific task IDs."""
    id: str
    prompt: str
    fails_on: list[str]


def load_seeded_prompts(path: str | Path) -> list[SeededPrompt]:
    """Load a list of seeded prompts from a YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, list):
        raise TaskSetError("Seeded prompts must be a list")
    prompts: list[SeededPrompt] = []
    for item in data:
        if not isinstance(item, dict):
            raise TaskSetError(f"Seeded prompt entry must be a mapping, got {type(item).__name__}")
        if "prompt" not in item:
            eid = item.get("id", "?")
            raise TaskSetError(f"Seeded prompt {eid} missing required field 'prompt'")
        prompts.append(SeededPrompt(
            id=item["id"],
            prompt=item["prompt"],
            fails_on=item.get("fails_on", []),
        ))
    return prompts
