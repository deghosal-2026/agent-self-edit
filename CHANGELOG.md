# Changelog

All notable changes to AgentSelfEdit are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] — 2026-09-04

### Added

- **Hermetic non-LLM CI suite** (#263): 15 tests, zero LLM calls, all passing — 807 total
- **Oracle Drift Guard** (#226): detects shared wrong success definition across optimizer/scorer/golden
- **Mixed-domain corpus** (#259): expanded to 100 tasks across 5 domain sets
- **Sentinel regression benchmark** (#261): 20 tasks validated end-to-end
- **Adversarial edit injection** (#260): 8/8 bad edits blocked, FN=0
- **Rollback validation** (#262): real promoted version reverted, lineage preserved
- **Real-trace gold corpus** (#268): 30 traces, 7 failure clusters, 7 ideal interventions, operationalized for analyzer quality evaluation
- **Seeded-prompts corpus** (#271): 15 prompts with known failure modes
- **Separated-role runner** (#315): executor/analyzer/judge can be different models with fallback
- **Real-trace ingestion fix** (#264): correct A/B corpus (gold-corpus.jsonl) and result paths
- **Rejection-aware behavioral diff** (#270): measures novelty/repeat/fixed/broken per iteration
- **Cost-per-iteration breakdown** (#269): tokens, $, wall-clock per proposal in field test report
- **Docker multi-domain tests** (#303): 16 tests covering classification, extraction, generation, staged analyzer, mixed-domain, adversarial, A/B cache, materialize guard
- **Materialize guard** (#303): `materialize_candidate_prompt()` loudly rejects missing `old_text`
- **`materialize_candidate_prompt()`**: replaces raw `str.replace()`, full prompt materialization
- **`PromotionGate.check()` wired into propose path**: gate now runs in real proposal flow
- **Drift measured against original prompt**: not current prompt
- **Coverage**: 94.86% (exceeds 91% gate)
- **Ruff + mypy strict**: 0 errors both

### Fixed

- **Confidence fix** (#107): gate checked `p < 0.95` instead of `p < 0.05` — promoted edits were noise (fixed in v0.1.0, confirmed v0.3.0)
- **Stage 4 fuzzy-match propagation** (#285): corrected proposals now flow through to A/B and gate
- **Rejection context threading** (#205): rejection_context threaded into Stage 1/2/3 prompts
- **A/B task set wiring** (#274): runner uses classification-promotion.yaml directly
- **Staged analyzer default wiring** (#275): staged analyzer is now the default path
- **Model role wiring** (#275): executor, analyzer, and judge routes through separate provider configs
- **`materialize_candidate_prompt()`**: old_text not found errors fixed with multi-strategy fuzzy matching
- **CI coverage threshold** (#312): `--cov-fail-under=91` enforced in CI
- **`validate` checks runnability** (#275): validates end-to-end runnability, not just parseability
- **CLI exit code determinism** (#275): all fatal CLI errors produce deterministic non-zero exit codes
- **`init` writes runnable config** (#275): starter config persisted to disk

### Changed

- **Field-test corpora**: consolidated under field-test/corpus/ with versioned paths
- **Dockerfile**: multi-stage build, reduced image size, pinned dependencies
- **Scorer contract**: scorer consistency enforced across task sets; mixed scorer sets fail fast
- **Analyzer architecture**: staged pipeline replaces monolithic analyzer as default
- **CI**: Python 3.10–3.12 matrix, ruff covers full repo, coverage enforced at 91%
- **Field test runner and docs**: moved fully to `v0.3.0` result paths

### Known Issues

- **Analyzer search quality**: no analyzer has yet produced a promotable edit — local 4B gives null edits, Mistral 24B gives weak positive signal (+0.0625 effect size, p=0.79)
- **Proposal diversity**: analyzer stuck in narrow local search neighborhood (urgency rule rewrites)
- **Statistical power**: once proposal quality improves, confidence/p-value becomes the next bottleneck
- **Separated-role runner**: first separated-role run produced zero proposals (analyzer sensitivity to executor outputs)
- **Generation regressions**: overly strict format-adherence edits cause broader regressions in generation corpus

## [0.2.0] — 2026-09-02

### Added

- **Runtime scorer selection** (M2): Scorers auto-selected based on task type — exact match, structural extraction, LLM judge — instead of hardcoded to exact match
- **Classification subsets** (M2): Subset-aware scoring for multi-label, ambiguous, boundary, and legacy classification traces
- **Label-set-aware scorers** (M2): Scorers that compare sets of labels rather than exact strings, capturing partial credit
- **Staged analyzer pipeline** (M3): Four-stage analyzer — summarize, select, synthesize, score — with failure summarization and proposal diversification
- **Regression sentinel** (M3): Held-out corpus scored at each iteration to detect regressions before promotion
- **Multi-suite runner** (M3): Per-suite runner modes (classification, extraction, generation, mixed-domain)
- **Extraction scorer** (M3): StructuredExtractionScorer for nested fields, null handling, and conflicting-source precedence
- **Model role separation** (M4): executor, analyzer, and judge roles with per-role provider config
- **Benchmark manifests** (M4): Benchmark-role manifests with disjointness validation and scorer compatibility
- **Local-model comparison** (M4): 4B + 4B and 4B + 9B model role configurations with cost/latency comparison
- **Optimizer-effectiveness metrics** (M4): Per-iteration improvement tracking, cost-per-iteration breakdown
- **Larger A/B task sets** (M5): 40-task promotion corpus replacing the fragile 5-task set
- **Prompt style for small models** (M5): Simplified prompt templates optimized for sub-9B models
- **Canonical classification examples** (M5): Gold-labeled classification examples in corpus
- **Missing corpus types** (M5): Extraction, generation, and mixed-domain corpus types
- **Rejection-aware analyzer** (M5): Structured rejection feedback feeding into subsequent analyzer calls
- **Row-identity trace acknowledgement** (M6): Immutable row-ID based ack, retry-safe batch processing
- **In-flight reservation state** (M6): Atomic row reservation prevents concurrent duplicate fetch
- **Benchmark validation** (M6): Validates benchmark-role compatibility, scorer selection
- **CI/CD pipeline** (M7): GitHub Actions CI across Python 3.10–3.12 with ruff, mypy, coverage
- **Hermetic test suite** (M7): Zero LLM call CI tests — mock providers used throughout
- **Conftest fixture deduplication** (M7): Shared fixtures in conftest.py, reduced boilerplate
- **Docker multi-domain tests** (M8): Classification, extraction, generation, staged analyzer Docker tests
- **Adversarial edit field test** (M8): 5+ intentionally bad edits injected and rejected; 100+ random edit stress test
- **Real-trace ingestion** (M8): Real-trace corpus with analyzer quality measurement
- **LLM integration tests** (M8): 4B+4B and 4B+9B model role configurations tested

### Fixed

- **Gate edit-distance** (M1): #117 — measured against full candidate prompt instead of fragment
- **Gate drift detection** (M1): #118 — measured against original prompt baseline, not current prompt
- **A/B alpha semantics** (M1): #119 — `p < (1 - confidence_level)` instead of `p < confidence_level`
- **Promotion persistence** (M1): #116 — candidate prompt materialized using full prompt, not just edited fragment
- **Runtime scorer selection** (M2): Scorer resolved from benchmark manifest instead of hardcoded
- **Hermetic bad-edit rejection** (M3): Gate correctly rejects intentionally bad edits in hermetic tests
- **Per-suite runner modes** (M3): Suite selection driven by manifest/benchmark-role, no hardcoded task IDs
- **Staged analyzer default wiring** (M7.5): Staged analyzer is now the default path
- **Rejection context threading** (M7.5): rejection_context threaded into Stage 1/2/3 prompts
- **Model role wiring** (M7.5): Executor, analyzer, and judge routes through separate provider configs
- **CLI exit code determinism** (M7.5): All fatal CLI errors produce deterministic non-zero exit codes
- **`init` writes runnable config** (M7.5): Starter config persisted to disk
- **`validate` checks runnability** (M7.5): Validates end-to-end runnability, not just parseability
- **CI coverage threshold** (M7.5): --cov-fail-under raised, lint scope covers whole repo
- **Coverage**: 81% (v0.2.0 target 92% accepted at 81%; tracked for v0.2.1)

### Changed

- **Field-test corpora**: Consolidated under field-test/corpus/ with versioned paths
- **Dockerfile**: Multi-stage build, reduced image size, pinned dependencies
- **Scorer contract**: Scorer consistency enforced across task sets; mixed scorer sets fail fast
- **Analyzer architecture**: Staged pipeline replaces monolithic analyzer as default
- **CI**: Python 3.10–3.12 matrix, ruff covers full repo, coverage enforced

### Known Issues

- **Rejection context threading**: #205 — staged analyzer acceptance_context was not populated in all paths during field test; proposal-diversification conclusions are stale
- **Coverage**: 81% (target: 92%) — gaps in analyzer, CLI propose/run, scorers, trace
- **Improvement**: 0% over all v0.2.0 runs — the strongest analyzer (Mistral Small 24B) produced directional gains but no promotable edit
- **GHCR Docker push**: Blocked by token permissions (write:packages scope needed)
- **Verification coverage**: Acceptance criteria tests for M7.5 adjustments remain partially covered

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