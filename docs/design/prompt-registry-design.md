# Prompt Registry Design

> File-based registry format, version metadata schema, diff computation, rollback semantics, integrity checks, and registry locking for AgentSelfEdit v0.1.0.

## 1. Format

File-based, no external database. Each version is a pair of files:

```
<registry_path>/
├── v1.md              # Prompt text (plain markdown)
├── v1.meta.json       # Version metadata
├── v2.md
├── v2.meta.json
├── ...
└── registry.lock      # File-based lock for concurrent access
```

## 2. Metadata Schema (`v{N}.meta.json`)

```json
{
  "version": 3,
  "timestamp": "2026-09-02T10:00:00Z",
  "sha256_hash": "abc123...",
  "diff_from_previous": {
    "lines_added": 2,
    "lines_removed": 1,
    "lines_modified": 0,
    "total": 3
  },
  "hypothesis": "Clarify the classification instruction for edge cases with ambiguous billing/technical overlap",
  "ab_results": {
    "winner": "b",
    "mean_delta": 0.12,
    "ci_low": 0.05,
    "ci_high": 0.19,
    "p_value": 0.01,
    "effect_size": 0.15,
    "n_trials": 30
  },
  "gate_result": {
    "decision": "promote",
    "reason": "all checks passed"
  },
  "trigger_trace_ids": ["t1", "t2", "t3"],
  "model_version": "gpt-4o-mini-2026-08-01",
  "token_cost": 0.042
}
```

All fields except `version`, `timestamp`, and `sha256_hash` are optional.

## 3. Operations

### Create

`Registry.create(prompt_text, **metadata) -> int`
- Computes SHA-256 hash of `prompt_text`
- Writes `v{N}.md` (prompt) + `v{N}.meta.json` (metadata)
- Increments version number
- Concurrent writes blocked by lock

### Diff

`Registry.diff(v1, v2) -> DiffResult`
- Line-level diff between two stored versions
- Returns: `added[]`, `removed[]`, `modified[]`, `unchanged_count`, `frozen_unchanged_count`
- `v1 == v2` → empty diff
- Invalid versions → `RegistryError`

### Rollback

`Registry.rollback(version, reason) -> int`
- Creates a new version as a copy of the target version's prompt
- `reason` and target version stored in metadata
- Invalid version → `RegistryError`
- Rollback to current version → creates identical copy

### Lineage

`Registry.lineage(from_version=None) -> list[Meta]`
- Returns ordered list of metadata from `from_version` to current
- `get(version) -> (str, Meta)` — returns prompt text + metadata

### Integrity

`Registry.verify_integrity() -> list[str]`
- Recomputes SHA-256 for each version
- Returns list of corrupted version strings
- All intact → empty list

## 4. Locking

A file-based lock (`registry.lock`) serializes write operations. The lock uses a timeout to prevent deadlock and is released on the `__exit__` pattern.

## 5. Design Decisions

See DD-11 (file-based registry) and DD-12 (SHA-256 integrity) in `design-decisions.md`.