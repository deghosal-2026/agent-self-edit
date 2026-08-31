# Design Decisions — AgentSelfEdit v0.1.0

> Record of design decisions (DD-01 through DD-17) made during v0.1.0 development.

## DD-01 — Package / CLI naming
**Date:** 2026-08-30 · **Milestone:** M1
**Decision:** Package name `agent_self_edit`, PyPI name `agent-self-edit`, CLI entry `agent-self-edit`.
**Rationale:** Consistent, discoverable naming across import, distribution, and command-line surfaces.

## DD-02 — Config format YAML (primary) + TOML (supported)
**Date:** 2026-08-30 · **Milestone:** M1 (updated M5)
**Decision:** Configuration is stored as YAML by default, with TOML also supported (PRD F-13 "YAML/TOML"). Enabled by file extension (`.yaml`/`.yml` → YAML, `.toml` → TOML).
**Rationale:** YAML supports comments and round-trips cleanly; TOML satisfies PRD F-13 for teams that standardize on it. Auto-detection keeps a single `load_config()` entry point.

## DD-03 — Task set format
**Date:** 2026-08-30 · **Milestone:** M1
**Decision:** Held-out task sets are YAML or JSON lists with `id`, `input`, `expected_output`, optional `metadata`.
**Rationale:** Both formats supported for flexibility; structure is minimal and scorer-agnostic.

## DD-04 — Trace store SQLite
**Date:** M2
**Decision:** Execution traces are stored in a local SQLite database.
**Rationale:** Zero external services, ACID guarantees, indexed querying, file-based portability.

## DD-05 — Adapter pattern
**Date:** M2
**Decision:** Trace ingestion uses an adapter pattern (stdin, file watch) behind a common interface.
**Rationale:** Agent transport is deployment-specific; adapters isolate it.

## DD-06 — Paired A/B design
**Date:** M3
**Decision:** Each task runs against both prompts (paired design) rather than independent samples.
**Rationale:** Same held-out task set, same task → controls task variance, higher statistical power.

## DD-07 — Bootstrap 10K resamples
**Date:** M3
**Decision:** Confidence intervals are computed via bootstrap with 10,000 resamples.
**Rationale:** Distribution-free, consistent with the CI calibration target, cheap enough to run in CI.

## DD-08 — Scorer interface
**Date:** M3
**Decision:** Scoring is pluggable: ExactMatch, Contains, LLMJudge behind a common `Scorer` interface.
**Rationale:** Task domains differ; a single scoring rule cannot cover classification, extraction, and generation.

## DD-09 — Fail-fast gate order
**Date:** M4
**Decision:** The promotion gate runs its checks in fail-fast order and stops at the first failure.
**Rationale:** Saves compute, gives a single clear rejection reason, simplifies near-miss classification.

## DD-10 — Near-miss threshold 50%
**Date:** M4
**Decision:** A gate is classified near-miss when ≥ 50% of checks pass.
**Rationale:** Threshold is conservative: a mostly-passing gate is not silently rejected and logs for review.

## DD-11 — Git-backed file registry (PRD §2.5)
**Date:** M5 (updated to git-backed per discrepancy audit)
**Decision:** The prompt registry is a file-based store (`v{N}.md` + `v{N}.meta.json`) that also commits every created version to git when the registry path is inside a git work tree (PRD §2.5). Falls back to file-only when git is unavailable or the path is outside a repo.
**Rationale:** Files keep prompts human-readable and make integrity trivial (DD-12); git commits give tree-wide diff, rollback, branching, and merge through standard tooling, and each version records its `commit_sha` in metadata.

## DD-12 — SHA-256 integrity
**Date:** M5
**Decision:** Each prompt version carries a SHA-256 hash; hashes are recomputed and verified on read.
**Rationale:** Tamper-evidence without external key infrastructure.

## DD-13 — TF-IDF drift for v0.1.0
**Date:** M6
**Decision:** Drift uses TF-IDF cosine similarity in v0.1.0; embedding-based drift comes in v0.2.0.
**Rationale:** TF-IDF is deterministic, zero-cost, and CI-friendly; embeddings add cost and provider coupling.

## DD-14 — Analyzer prompt includes frozen annotations
**Date:** M7
**Decision:** The analyzer receives the current prompt with frozen sections annotated so it never proposes edits there.
**Rationale:** Prevents wasted A/B runs on frozen content; guardrail is the backstop.

## DD-15 — Max 3 proposals per batch
**Date:** M7
**Decision:** The analyzer outputs at most 3 proposals per analysis batch.
**Rationale:** Bounds A/B cost per cycle; forces prioritizing the most common failure patterns.

## DD-16 — Click framework
**Date:** M9
**Decision:** CLI is built on Click.
**Rationale:** Modern, well-established, supports shell completion out of the box.

## DD-17 — Exit codes
**Date:** M9
**Decision:** CLI exit codes: 0 success, 1 error, 2 validation failure.
**Rationale:** Simple, scriptable, distinguishes operational failures from invalid input.

## DD-18 — Standalone guardrail module (PRD §2.2.5)
**Date:** M5 (discrepancy audit fix)
**Decision:** Frozen-section parsing, edit-distance calculation, and TF-IDF drift primitives live in `src/agent_self_edit/guardrails.py` as a standalone module, independent of the promotion gate.
**Rationale:** PRD 02-architecture §2.2.5 specifies a separate Guardrail Module (F-06/F-07). The promotion gate (M4) re-imports the primitives; the analyzer (M7) and diff visualization (M8) can reuse them without depending on the gate.

## DD-19 — Dedup uses TF-IDF similarity, not embedding
**Date:** M7
**Decision:** Proposal deduplication (#49) uses TF-IDF cosine similarity via `compute_drift_tfidf()` (skip if `1 - drift > threshold`, default 0.85), not embedding similarity as the M7 ticket wording states.
**Rationale:** The `LLMProvider` interface has only `complete()` — there is no embedding endpoint in v0.1.0. Consistent with DD-13 (TF-IDF for all similarity in v0.1.0; embeddings deferred to v0.2.0). Hermetic, deterministic, zero extra dependencies.