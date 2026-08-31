# Trace Schema Design

> Trace JSON schema, SQLite store schema, indexes, adapter interface design, and cleanup strategy for AgentSelfEdit v0.1.0.

## 1. Trace JSON Schema

An execution trace captures one agent task run — the input, the agent's steps, its final output, and whether it succeeded. Traces are the raw material the feedback analyzer learns from.

```json
{
  "task_id": "classify-ticket-001",
  "task_input": "Ticket: 'My billing page shows wrong amount'",
  "steps": [
    {"action": "classify", "result": "billing", "confidence": 0.72}
  ],
  "final_output": "billing",
  "expected_output": "technical",
  "success": false,
  "failure_reason": "misclassified — user's issue is technical, not billing",
  "timestamp": "2026-09-01T10:00:00Z",
  "prompt_version": 3
}
```

### 1.1 Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `task_id` | string | Yes | Unique identifier for the task |
| `task_input` | string | Yes | The input text given to the agent |
| `steps` | list | No | Ordered list of agent actions; each item is a free-form object |
| `final_output` | string | Yes | The agent's final output |
| `expected_output` | string | Yes | The ground-truth / expected output |
| `success` | bool | Yes | Whether the task succeeded |
| `failure_reason` | string | No | Optional reason for failure |
| `timestamp` | string (ISO 8601) | Yes | When the task ran |
| `prompt_version` | int | No | Prompt registry version the agent used |

**Validation semantics:**
- Missing required fields → `ValueError`
- Extra fields → ignored (schema-forward compatible)
- `timestamp` must parse as ISO 8601
- `steps` and `failure_reason` are optional and may be absent
- `prompt_version` optional; absent → `None`

## 2. SQLite Store Schema

```sql
CREATE TABLE IF NOT EXISTS traces (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id       TEXT    NOT NULL,
    task_input    TEXT,
    steps         TEXT,                  -- JSON-encoded list
    final_output  TEXT,
    expected_output TEXT,
    success       INTEGER NOT NULL,      -- 0/1
    failure_reason TEXT,
    timestamp     TEXT    NOT NULL,      -- ISO 8601, lexicographically sortable
    prompt_version INTEGER,
    ingested_at   TEXT    NOT NULL,      -- ISO 8601
    processed     INTEGER NOT NULL DEFAULT 0,
    batch_id      INTEGER NULL
);

CREATE INDEX IF NOT EXISTS idx_traces_task_id        ON traces(task_id);
CREATE INDEX IF NOT EXISTS idx_traces_prompt_version ON traces(prompt_version);
CREATE INDEX IF NOT EXISTS idx_traces_success        ON traces(success);
CREATE INDEX IF NOT EXISTS idx_traces_timestamp      ON traces(timestamp);
CREATE INDEX IF NOT EXISTS idx_traces_processed      ON traces(processed);
```

### 2.1 Schema Migration

`user_version` pragma tracks the schema version. On open:
- If `PRAGMA user_version` is older than current → run ALTERs/creates to migrate
- If newer → raise error (downgrade not supported)

### 2.2 Concurrency

SQLite connections run in `WAL` mode and use `get_db()` returning a thread-safe connection per call. Writes are serialized by a single process-level write lock.

## 3. Batching

- `batch_ready()` → `True` when count of `processed = 0` traces (> whatever is pending) reaches `batch_size`
- `get_batch(size)` → oldest `size` unprocessed traces ordered by `ingested_at`
- `acknowledge(task_ids)` → marks given traces `processed = 1`
- Batch counter increments on each `ingest()`

## 4. Cleaning

- `cleanup(retention_days=90)` deletes rows where `timestamp < now - retention_days`
- `retention_days = 0` deletes everything
- Called on store open and every 24h by the loop

## 5. Adapter Interface

```python
class TraceAdapter(ABC):
    def __init__(self, store: TraceStore): ...
    @abstractmethod
    def run(self) -> None: ...     # blocking; calls store.ingest() per trace
    @abstractmethod
    def stop(self) -> None: ...
```

- **StdinAdapter** — reads JSON-lines from stdin, one trace per line, ingests each
- **FileAdapter** — watches a directory for new `.json` files, ingests each, moves to `.done` after

## 6. Design Decisions

See DD-04 (SQLite) and DD-05 (adapter pattern) in `design-decisions.md`.