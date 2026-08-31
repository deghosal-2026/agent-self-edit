# CLI Surface Design

> All commands, flags, output formats, exit codes, error handling, help text, loop algorithm, and shell completion for AgentSelfEdit v0.1.0. Commands use Click (DD-16); exit codes: 0 success, 1 error, 2 validation failure (DD-17).

## 1. Command Inventory

| # | Command | Description | PRD ref |
|---|---------|-------------|---------|
| 1 | `init` | Scaffold config, registry, task set, initial prompt | F-09, CUJ-5 |
| 2 | `run` | Start the self-improvement loop | F-09, CUJ-1 |
| 3 | `status` | Show current state | F-09 |
| 4 | `diff <v1> <v2>` | Show diff between two prompt versions | F-08, F-09 |
| 5 | `rollback <version>` | Roll back to a previous prompt version | F-12, CUJ-4 |
| 6 | `guardrails` | Show guardrail history | F-09, F-11 |
| 7 | `lineage` | Show full prompt version history | F-05, CUJ-3 |
| 8 | `propose` | Manually trigger analysis on current traces | F-02 |
| 9 | `ingest <file>` | Ingest a trace file | F-01 |
| 10 | `validate` | Check config + task set + registry integrity | additive (WBS #62) |

## 2. Command Specifications

### 2.1 `init`

```
agent-self-edit init [--prompt <path>] [--tasks <path>]
```

- Scaffolds config file at `agent-self-edit.yaml` (if not exists)
- Creates registry directory
- Loads held-out task set from `--tasks`
- Creates initial prompt version from `--prompt` (or a default placeholder)
- Missing path → error message, exit code 1
- Existing config → overwrite prompt only (preserve config)

### 2.2 `run`

```
agent-self-edit run [--batch-size 50] [--once] [--dry-run] [--no-loop]
```

**Loop algorithm (default mode):**
1. Check `TraceStore.batch_ready()` (pending >= batch_size)
2. If not ready, sleep 5s, retry (loop continues)
3. If ready, get batch via `TraceStore.get_batch(batch_size)`
4. Filter to failed traces
5. If no failures, `acknowledge()` all as processed, continue loop
6. Call `analyze_batch(traces, current_prompt, ...)` using MockProvider if `--dry-run`
7. If `--dry-run`: log proposals, skip A/B test and gate, continue loop
8. For each proposal: call `run_ab_test(prompt_a=current, prompt_b=proposal.new_text, ...)`
9. Call `check_all(proposal, ab_result, current, original, config)`
10. If `decision == promote`: `registry.create(proposal.new_text, ...)`, `gate.audit.log()`
11. `acknowledge()` processed traces
12. If `--once`: exit after one cycle
13. Else: loop back to step 1

**Flags:**
- `--batch-size <N>` — override config batch_size
- `--once` — one cycle then exit
- `--dry-run` — analyze only, no A/B test or gate

**Edge cases:**
- No pending traces → sleep 5s, retry
- All traces succeed → acknowledge, skip analysis
- Cost ceiling hit → abort cycle, log warning, continue next cycle
- SIGINT/SIGTERM → graceful shutdown (finish current cycle, exit cleanly)

### 2.3 `status`

```
agent-self-edit status [--json]
```

Shows: prompt version, last edit, guardrail pass rate, improvement trend (dummy/aggregate), total edits, total cost.

**JSON output schema:**

```json
{
  "prompt_version": 7,
  "last_edit": {
    "edit_id": "e7",
    "decision": "promote",
    "timestamp": "2026-09-01T18:00:00Z",
    "hypothesis": "clearer classification rule"
  },
  "guardrail_pass_rate": 0.85,
  "total_edits": 12,
  "total_cost_usd": 0.84
}
```

Empty state: `{"error": "no data", "prompt_version": 0, "total_edits": 0, "total_cost_usd": 0}`.

### 2.4 `diff`

```
agent-self-edit diff <v1> <v2> [--inline] [--format text|markdown] [--color auto|always|never]
```

- Uses `Registry.diff(v1, v2)` → `DiffResult`
- Renders via `format_diff_inline()` (default) or `format_diff_side_by_side()` with `--inline`
- `--format markdown` → `format_markdown_diff()`
- Invalid version → error message, exit 1
- Identical → "no changes"

### 2.5 `rollback`

```
agent-self-edit rollback <version> [--reason <text>]
```

- Calls `Registry.rollback(version, reason)`
- If `PromotionGate` has an audit path, logs the rollback event
- Invalid version → error message, exit 1

### 2.6 `guardrails`

```
agent-self-edit guardrails [--last <N>] [--edit <id>] [--json]
```

- Reads from `GateAuditLog`
- `--last N` → most recent N entries
- `--edit <id>` → entries matching that edit_id
- Empty history → "no data"

### 2.7 `lineage`

```
agent-self-edit lineage [--from <version>] [--format table|json]
```

- Calls `Registry.lineage(from_version)`
- table format: columns (version, timestamp, hash, hypothesis, decision)
- json format: full Meta list

### 2.8 `propose`

```
agent-self-edit propose [--dry-run]
```

- Reads pending traces from TraceStore
- Calls `analyze_batch(traces, current_prompt, ...)` using MockProvider if `--dry-run`
- Proposals output without A/B test or gate in `--dry-run`
- Logs proposals to stdout

### 2.9 `ingest`

```
agent-self-edit ingest <file> [--format json]
```

- Reads trace file (JSON lines or single JSON object)
- Calls `TraceStore.ingest()` for each trace
- Invalid traces → warning on stderr, continue

### 2.10 `validate`

```
agent-self-edit validate [--json]
```

3 checks:
1. **Config** — calls `load_config()`; errors → exit 2
2. **Task set** — calls `load_task_set()` from config path; errors → exit 2
3. **Registry integrity** — calls `Registry.verify_integrity()`; corruption → exit 2

All pass → exit 0. Individual failures printed with check name.

## 3. Loop Wiring Map

Command → what function it calls:

| Command | Consumer function | Dependencies |
|---------|-------------------|--------------|
| `init` | `load_config`, `Registry`, `load_task_set` | M1 config, M5 registry |
| `run` | `TraceStore`, `analyze_batch`, `run_ab_test`, `check_all`, `Registry.create`, `GateAuditLog` | M2 trace, M7 analyzer, M3 AB test, M4 gate, M5 registry, M1 config |
| `status` | `Registry`, `GateAuditLog` | M5 registry, M4 gate |
| `diff` | `Registry.diff`, `diff.format_diff_inline/markdown` | M5 registry, M8 diff |
| `rollback` | `Registry.rollback`, `GateAuditLog` | M5 registry, M4 gate |
| `guardrails` | `GateAuditLog` | M4 gate |
| `lineage` | `Registry.lineage` | M5 registry |
| `propose` | `TraceStore`, `analyze_batch` | M2 trace, M7 analyzer |
| `ingest` | `TraceStore.ingest` | M2 trace |
| `validate` | `load_config`, `load_task_set`, `Registry.verify_integrity` | M1 config, M5 registry |

## 4. Exit Codes (DD-17)

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (operational failure: file not found, LLM error, IO error) |
| 2 | Validation failure (invalid config, invalid task set, corrupted registry) |

## 5. Error Handling

- All commands wrap the main logic in try/except → `click.echo()` with error message → `sys.exit(code)`
- `FileNotFoundError` → exit 1
- `ConfigError`, `RegistryError`, `TaskSetError` → exit 2
- `AnalyzerError`, `ProviderError` → exit 1
- Unhandled exceptions → exit 1 with traceback

## 6. Shell Completion

Click built-in: `agent-self-edit --install-completion [bash|zsh|fish]`.

## 7. Help Text

Every command has a `help=` string on the Click decorator. Top-level help lists all 10 commands with brief descriptions.