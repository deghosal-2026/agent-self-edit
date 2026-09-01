# Changelog

All notable changes to AgentSelfEdit are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-08-31

### Added

- **Execution trace ingestion** (F-01): Agent traces stored in SQLite with validation, batching, and cleanup
- **Feedback analyzer** (F-02): LLM-powered analysis of failed traces with structured prompt-edit proposals
- **A/B test engine** (F-03): Paired comparison of prompt variants with bootstrap CI, permutation test, effect size
- **Promotion gate** (F-04): 6 deterministic checks (sample floor, effect size, confidence, frozen sections, edit distance, drift)
- **Prompt registry** (F-05): Versioned prompt storage with full lineage, diff, rollback
- **Frozen core sections** (F-06): User-annotated sections the analyzer cannot modify
- **Edit-distance limit** (F-07): Configurable max lines changed per edit
- **Prompt diff visualization** (F-08): Side-by-side and inline diff between prompt versions
- **CLI** (F-09): 10 commands — init, run, status, diff, rollback, guardrails, lineage, propose, ingest, validate
- **Held-out task set management** (F-10): YAML-based task sets for A/B evaluation
- **Near-miss logging** (F-11): Rejected edits logged with guardrail reasoning
- **Rollback** (F-12): One-command rollback to any previous prompt version
- **Config file** (F-13): YAML/TOML configuration for all thresholds and paths
- **Docker support** (F-14): Multi-stage Dockerfile and docker-compose

### Fixed

- **A/B test fragment bug** (#104): A/B test was comparing a prompt against itself (passed fragment instead of full candidate)
- **Confidence check inverted** (#107): Gate checked `p < 0.95` instead of `p < 0.05` — promoted edits were noise
- **Gate argument order** (#108): `check_all` received `prompt_b` instead of `prompt_a` — frozen_sections check failed
- **Docker test used `--dry-run`** (#98): Integration test skipped A/B test and gate entirely
- **Failure traces were fabricated** (#96): `final_output` hardcoded to `"other"` — analyzer optimized against fake data
- **A/B task set too easy** (#109): First 5 tasks scored 80% — edits showed no improvement
- **Duplicate task\_ids** (#97): 336 observatory traces all had the same ID
- **`run_traces.py` wrong tool** (#95): Generic eval runner, not the self-edit loop (deleted)
- **`run_docker_field_test.py` stale** (#99): Duplicated test code with worse config (deleted)
- **`run.py` hardcoded MockProvider**: Never made real LLM calls
- **`base_url` missing from LLMConfig**: OMLX endpoint silently ignored
- **Docker: no latency/token assertions** (#108): Silent failures not caught
- **Docker: identical seeded traces** (#109): All 10 traces used same input
- **Docker: no registry state assertion** (#111): Registry not inspected after full loop
- **Pytest UnknownMarkWarning**: `docker` mark not registered in pyproject.toml

### Changed

- **Field test script**: `run_improvement_loop.py` calls internal API directly, writes per-iteration A/B artifacts
- **Gate confidence semantics**: `p < (1 - confidence_level)` instead of `p < confidence_level`
- **Drift threshold**: Default 0.3 → 0.5 to allow meaningful edits
- **A/B task set**: From 5 easy tasks to 26 hard tasks
- **Failure trace seeding**: From fabricated `"other"` to real model outputs
- **Model selection**: 4B local only (dropped 9B and cloud — same accuracy, 9x slower)

### Known Issues

- **Coverage**: 89% (target: 92%) — CLI modules tested via Docker not unit tests (#113)
- **Improvement**: 0% over 15 iterations — analyzer proposes same edit every time, needs rejection feedback
- **Non-LLM hermetic tests**: CI-safe hermetic tests not yet run in CI