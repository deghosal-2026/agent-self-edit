"""Shared fixtures for all tests."""

import pytest

from agent_self_edit.config import (
    Config,
    ProjectConfig,
)
from agent_self_edit.llm import MockProvider
from agent_self_edit.scorers import ExactMatchScorer
from agent_self_edit.tasks import Task, TaskSet
from agent_self_edit.trace import TraceStore


@pytest.fixture
def mock_llm():
    return MockProvider(responses="mock output")


@pytest.fixture
def scorer():
    return ExactMatchScorer()


@pytest.fixture
def config():
    return Config(project=ProjectConfig(name="x"))


@pytest.fixture
def task_set():
    tasks = {f"t{i}": Task(id=f"t{i}", input="x", expected_output="y") for i in range(5)}
    return TaskSet(tasks=tasks)


@pytest.fixture
def trace_store(tmp_path):
    return TraceStore(str(tmp_path / "traces.db"), batch_size=10)


@pytest.fixture
def registry(tmp_path):
    from agent_self_edit.registry import Registry
    return Registry(tmp_path / "registry")
