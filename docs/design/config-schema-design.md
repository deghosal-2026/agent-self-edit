# Config Schema Design

> Config file format, validation rules, schema versioning, and migration strategy for AgentSelfEdit v0.1.0.

## 1. Format

**YAML** (`.yaml` / `.yml`), single file at project root or specified via `--config`.

## 2. Schema

```yaml
# agent-self-edit configuration — v0.1.0
schema_version: 1

# ── Project identity ──
project:
  name: my-agent                     # short name, used for registry dir naming
  registry_path: ./registry           # prompt registry directory
  trace_path: ./traces.db             # SQLite trace database path

# ── Held-out task set ──
tasks:
  task_set_path: ./tasks.yaml          # path to held-out task set
  batch_size: 50                       # traces per analysis batch
  sample_floor: 10                     # minimum tasks for A/B test (>= 10)

# ── LLM provider ──
llm:
  provider: openai                     # openai | mock
  model: gpt-4o-mini                   # model name
  api_key: ${OPENAI_API_KEY}           # env-var reference
  temperature: 0.0                     # 0.0 = deterministic
  max_tokens: 4096                     # max response tokens
  timeout: 30                          # request timeout in seconds

# ── A/B test engine ──
ab_test:
  n_resamples: 10000                   # bootstrap resamples
  n_permutations: 1000                 # permutation test shuffles
  confidence_level: 0.95               # 0.5 .. 0.999
  min_effect_size: 0.05                # min relative improvement (5%)
  cost_ceiling_usd: 0.10               # abort if per-A/B-test cost exceeds this

# ── Promotion gate ──
gate:
  max_edit_distance: 20                # max changed lines (> 0)
  drift_threshold: 0.3                 # max allowed drift [0, 1]
  near_miss_threshold: 0.5             # fraction of checks that must pass to be near-miss

# ── Analyzer ──
analyzer:
  max_proposals_per_batch: 3           # max edits per analysis cycle
  cost_ceiling_usd: 0.50               # abort if per-cycle cost exceeds this

# ── Trigger ──
trigger: batch                         # batch | time | manual

# ── Trace retention ──
trace_retention_days: 90               # 0 = delete everything
```

## 3. Validation Rules

| Field | Rule | Error message |
|-------|------|---------------|
| `schema_version` | must be `1` | `schema_version must be 1` |
| `project.name` | required, non-empty | `project.name is required` |
| `tasks.sample_floor` | >= 10 | `sample_floor must be >= 10, got {n}` |
| `ab_test.confidence_level` | in [0.5, 0.999] | `confidence_level must be between 0.5 and 0.999` |
| `ab_test.min_effect_size` | in [0, 1] | `min_effect_size must be between 0 and 1` |
| `gate.max_edit_distance` | > 0 | `max_edit_distance must be > 0, got {n}` |
| `ab_test.cost_ceiling_usd` | > 0 | `cost_ceiling_usd must be > 0, got {n}` |
| `gate.drift_threshold` | in [0, 1] | `drift_threshold must be between 0 and 1` |
| `gate.near_miss_threshold` | in [0, 1] | `near_miss_threshold must be between 0 and 1` |
| `llm.provider` | one of `openai`, `mock` | `llm.provider must be 'openai' or 'mock'` |
| `analyzer.max_proposals_per_batch` | >= 1 | `max_proposals_per_batch must be >= 1` |
| `analyzer.cost_ceiling_usd` | > 0 | `cost_ceiling_usd must be > 0` |
| `trigger` | one of `batch`, `time`, `manual` | `trigger must be one of: batch, time, manual` |
| `trace_retention_days` | >= 0 | `trace_retention_days must be >= 0` |

## 4. Default Config

If no config file is provided, `init` command writes a default config with:
- `gpt-4o-mini`, `sample_floor: 10`, `confidence_level: 0.95`, `max_edit_distance: 20`, `drift_threshold: 0.3`, `trigger: batch`, `trace_retention_days: 90`.

## 5. Schema Versioning

`schema_version` is always `1` in v0.1.0. On upgrade:
1. New fields are added with defaults in code
2. Old configs with `schema_version: 1` still load — missing fields get defaults
3. On breaking changes, `schema_version` increments and old versions are rejected with a migration guide URL

## 6. Environment Variable Interpolation

Values prefixed with `${...}` are replaced from environment variables at load time. Missing env vars raise a validation error with the variable name.