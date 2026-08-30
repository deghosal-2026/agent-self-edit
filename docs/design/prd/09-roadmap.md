# 09 — Roadmap

> Sub-document of the [Design overview](../README.md). Milestone roadmap from v0.1.0 through v1.0.0.

## 9.1 Release Overview

| Version | Target | Focus | Status |
|---|---|---|---|
| v0.1.0 | Sep 2026 | Prove the loop | Core self-improvement loop with statistical promotion gate, CLI, guardrails. Prove one prompt is better than another, safely. |
| v0.2.0 | Oct 2026 | Trust + visibility | Web dashboard, drift detection, near-miss feedback, REST API, shadow mode. Make the loop trustworthy enough to run unattended. |
| v0.3.0 | Nov 2026 | Scale + adapters | Framework adapters, multi-failure clustering, adaptive sample floors, evals integration. Make the loop work with real agents. |
| v0.4.0 | Dec 2026 | Fleet | Fleet-wide shared-rules learning, cost-aware improvement, promotion analytics. Make the loop work across many agents. |
| v0.5.0 | Jan 2027 | Hardening | Production hardening, OpenSSF Silver, performance optimization, documentation. |
| v0.6.0 | Feb 2027 | Extensibility | Plugin system, custom guardrails, custom analyzers, webhook integration. |
| v0.7.0 | Mar 2027 | Enterprise | SSO, RBAC, audit export, SOC 2 mapping, multi-tenant support. |
| v0.8.0 | Apr 2027 | Observability | OTel export, Prometheus metrics, alerting, SLO tracking. |
| v0.9.0 | May 2027 | Release candidate | Final feature freeze, bug fixes, documentation, community feedback. |
| v1.0.0 | Jun 2027 | General availability | Stable API, long-term support, production deployment guide. |

---

## 9.2 v0.1.0 — Prove the Loop

**Goal:** A working self-improvement loop that can prove one prompt is better than another, safely, with full lineage and rollback.

**Success bar:** An agent fails a task, the analyzer proposes a concrete edit, the A/B test proves it's better, the promotion gate checks all guardrails, the edit is promoted, and the improvement is measurable. Rollback works. The user can see the diff. Zero bad edits ship.

### M1 — Scaffold + Config

**Scope:** Repo structure, package, CI, config system, held-out task set management.

| Task | Description | Deliverable |
|---|---|---|
| M1.1 | Package scaffold | `pyproject.toml`, `src/agent_self_edit/`, `tests/`, package name `agent-self-edit` |
| M1.2 | Config file format | YAML config with: guardrail thresholds, sample floor, trigger mode, held-out task set path, LLM provider config, frozen section annotations |
| M1.3 | Config validation | Schema validation on load. Errors on missing required fields, invalid thresholds, contradictory settings |
| M1.4 | Held-out task set loader | Load task set from YAML/JSON. Each task: input, expected output, scoring function reference. Validate on load. |
| M1.5 | Task set management API | `add_task()`, `remove_task()`, `list_tasks()`, `validate_set()`. Tasks can be added/removed without restarting the loop |
| M1.6 | CI pipeline | GitHub Actions: ruff, mypy strict, pytest, coverage >90%. Dependabot. PR template. |
| M1.7 | OSS community files | CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md, SUPPORT.md, issue templates |

**Exit gate:** Config loads and validates. Task set loads and validates. CI green. `agent-self-edit init` creates a valid config file.

**Config schema (example):**
```yaml
# agent-self-edit.yaml
agent:
  prompt_file: ./prompts/system.md
  frozen_sections: ["role", "safety"]
  
analyzer:
  model: gpt-4o-mini
  batch_size: 50          # analyze after N traces
  trigger: batch          # batch | time | manual
  
ab_test:
  held_out_tasks: ./tasks/held-out.yaml
  sample_floor: 30        # min trials before promotion
  effect_size_min: 0.05   # min improvement (5%)
  confidence_level: 0.95  # p < 0.05
  bootstrap_trials: 10000
  
guardrails:
  max_edit_distance: 5    # max lines changed per cycle
  drift_threshold: 0.30   # max semantic drift from original
  drift_method: cosine    # cosine | jaccard | embedding
  
storage:
  registry_path: ./prompts/registry/
  trace_db: ./data/traces.sqlite3
  
logging:
  level: INFO
  near_miss_log: ./logs/near-misses.jsonl
```

### M2 — Execution Trace Ingestion

**Scope:** Accept execution traces from the agent, store them, batch them for analysis.

| Task | Description | Deliverable |
|---|---|---|
| M2.1 | Trace schema | JSON schema: task_id, task_input, steps[], final_output, success (bool), failure_reason (optional), timestamp, prompt_version |
| M2.2 | Trace store | SQLite table with trace schema. Indexes on task_id, prompt_version, success. Auto-migration on schema change. |
| M2.3 | Trace ingestion API | `ingest_trace(trace: dict)` — validates, stores, increments batch counter |
| M2.4 | Trace batching | When batch_size reached, trigger analyzer. Buffer in memory if analyzer is busy. Configurable batch_size. |
| M2.5 | Trace adapter interface | Abstract `TraceAdapter` class. Implement `StdinAdapter` (JSON via stdin) and `FileAdapter` (watch directory for trace files). Future: framework-specific adapters. |
| M2.6 | Trace cleanup | Configurable retention. Old traces archived or deleted after N days. Default: 90 days. |

**Exit gate:** Traces ingest correctly. Batch triggers fire. SQLite store is queryable. Adapter loads traces from file and stdin.

**Trace schema:**
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

### M3 — A/B Test Engine

**Scope:** The core measurement capability. Compare two prompt versions on the held-out task set and produce statistically valid results.

| Task | Description | Deliverable |
|---|---|---|
| M3.1 | Task runner | Run a task against a prompt version. Return: output, success, latency, token count. Uses the configured LLM provider. |
| M3.2 | Scoring interface | Abstract `Scorer` class. Implement `ExactMatchScorer`, `ContainsScorer`, `LLMJudgeScorer` (uses a separate LLM call to judge output quality). |
| M3.3 | A/B test runner | Run N trials: each trial runs the same task against both prompt versions (paired design). Collect win/loss/tie per task. |
| M3.4 | Statistical analysis | Bootstrap resampling (10,000 resamples) for confidence intervals. Effect size (Cohen's d or relative improvement). P-value via permutation test. |
| M3.5 | Per-task breakdown | Report per-task performance: which tasks improved, which degraded, which unchanged. Segment analysis if task tags exist. |
| M3.6 | Results object | Structured result: `{ winner, win_rate, ci_low, ci_high, effect_size, p_value, n_trials, per_task: [...] }` |
| M3.7 | Cost tracking | Token count and estimated cost per A/B test run. Configurable cost ceiling. Abort if ceiling exceeded. |

**Exit gate:** A/B test runs two prompt versions against a held-out set. Produces valid confidence intervals and effect sizes. Per-task breakdown works. Cost is tracked.

**Statistical methodology:**
- **Design:** Paired comparison (same task against both versions). More powerful than unpaired.
- **Bootstrap:** 10,000 resamples of the paired differences. 95% CI from the 2.5th and 97.5th percentiles.
- **Effect size:** Relative improvement = (new_score - old_score) / old_score. Minimum threshold configurable (default 5%).
- **P-value:** Permutation test — shuffle the paired labels 1,000 times, count how often the shuffled difference exceeds the observed. P-value = fraction of shuffles that exceed.
- **Sample floor:** Minimum number of paired trials before any promotion decision. Default 30. Configurable.

### M4 — Promotion Gate

**Scope:** The safety-critical component. Deterministic checks that must all pass before an edit is promoted.

| Task | Description | Deliverable |
|---|---|---|
| M4.1 | Gate interface | `PromotionGate.check(edit, ab_result, current_prompt, original_prompt) -> GateResult` |
| M4.2 | Sample floor check | Verify n_trials >= configured minimum. Fail if below. |
| M4.3 | Effect size check | Verify relative improvement >= configured minimum. Fail if below. |
| M4.4 | Confidence check | Verify p-value < configured threshold. Fail if above. |
| M4.5 | Frozen section check | Diff the prompt. Verify no lines changed in frozen sections. Fail if any frozen line modified. |
| M4.6 | Edit-distance check | Count changed lines. Verify <= configured max. Fail if exceeded. |
| M4.7 | Drift check | Compute semantic similarity between new prompt and original. Verify drift <= threshold. Fail if exceeded. (v0.1.0: cosine similarity on TF-IDF vectors. v0.2.0: embedding-based.) |
| M4.8 | Gate result | Structured: `{ decision: promote|reject|near_miss, checks: [{name, passed, value, threshold}], reasoning: str }` |
| M4.9 | Near-miss classification | If rejected but >= 50% of checks passed, classify as near-miss. Log to near-miss file. |
| M4.10 | Gate audit log | Every gate decision logged with timestamp, edit ID, all check results, and final decision. Immutable append-only log. |

**Exit gate:** Gate runs all 6 checks in order. Produces structured result. Near-miss classification works. Audit log is append-only and queryable.

**Gate evaluation order (fail-fast):**
```
1. Sample floor     → if fail, REJECT (not enough data)
2. Effect size      → if fail, REJECT (not better enough)
3. Confidence       → if fail, REJECT (could be noise)
4. Frozen sections  → if fail, REJECT (guardrail violation)
5. Edit distance    → if fail, REJECT (too much changed)
6. Drift            → if fail, REJECT (too far from original)
→ all pass: PROMOTE
```

### M5 — Prompt Registry

**Scope:** Versioned store of every prompt with full lineage, diff, and rollback.

| Task | Description | Deliverable |
|---|---|---|
| M5.1 | Registry store | File-based: each version is `prompts/registry/v{N}.md`. Metadata in `prompts/registry/v{N}.meta.json`. |
| M5.2 | Version metadata | Per version: version number, timestamp, prompt text, diff from previous, analyzer hypothesis, A/B results, gate result, trigger trace IDs, model version, token cost |
| M5.3 | Diff computation | Line-level diff between any two versions. Output: added[], removed[], modified[], unchanged_count, frozen_unchanged_count |
| M5.4 | Rollback | `rollback(version)` — promotes a previous version to current. Creates a new version that is a copy of the target. Logs the rollback reason. |
| M5.5 | Lineage query | `lineage()` — returns full history: list of versions with metadata. `lineage(version)` — returns lineage from that version to current. |
| M5.6 | Integrity check | SHA-256 hash of each version's prompt text stored in metadata. Verify on load. Detect corruption. |
| M5.7 | Registry locking | File lock during write operations. Prevents concurrent writes from corrupting the registry. |

**Exit gate:** Registry stores versions with metadata. Diff works between any two versions. Rollback creates a new version. Lineage is queryable. Integrity check passes.

### M6 — Guardrail Module

**Scope:** Constraint enforcement. The guardrails are deterministic code, not LLM-judged.

| Task | Description | Deliverable |
|---|---|---|
| M6.1 | Frozen section parser | Parse prompt file. Identify sections marked with `<!-- frozen -->` or YAML frontmatter annotations. Return list of frozen line ranges. |
| M6.2 | Edit-distance calculator | Diff two prompt versions. Count: lines added, lines removed, lines modified. Return total edit distance. |
| M6.3 | Drift calculator (v0.1.0) | TF-IDF vectorization of both prompts. Cosine similarity. Drift = 1 - similarity. Range: 0 (identical) to 1 (completely different). |
| M6.4 | Guardrail config | Load guardrail thresholds from config. Validate: max_edit_distance > 0, drift_threshold in [0, 1], frozen_sections list is valid. |
| M6.5 | Guardrail report | Structured output per check: `{ name, passed, value, threshold, details }`. Human-readable summary. |
| M6.6 | Near-miss logger | Append-only JSONL file. Each entry: timestamp, edit_id, edit_summary, failed_checks[], passed_checks[], rejection_reason. |

**Exit gate:** Frozen sections are parsed correctly. Edit distance is accurate. Drift is computed. Guardrail report is structured. Near-miss logger appends correctly.

### M7 — Feedback Analyzer

**Scope:** The LLM that reviews traces and proposes edits. This is the creative engine — but it has no authority. All proposals go through A/B test and promotion gate.

| Task | Description | Deliverable |
|---|---|---|
| M7.1 | Analyzer prompt | System prompt for the analyzer LLM. Inputs: current prompt with frozen annotations, batch of failed traces. Output: structured edit proposals. |
| M7.2 | Edit proposal format | JSON: `{ section, old_text, new_text, hypothesis, evidence_traces: [], expected_improvement: str }` |
| M7.3 | Analyzer runner | `analyze(traces, current_prompt) -> list[EditProposal]`. Calls LLM, parses response, validates format. |
| M7.4 | Proposal validation | Verify: proposal targets a non-frozen section, old_text matches current prompt, new_text is non-empty, hypothesis is non-empty. Reject invalid proposals. |
| M7.5 | Proposal deduplication | Compare new proposals against recent near-misses. If a proposal is semantically similar to a recently rejected edit, skip it and log. |
| M7.6 | Batch analysis | Process a batch of traces. Group failures by pattern. Generate 1-3 proposals per batch (not one per trace). Prioritize proposals that address the most common failure pattern. |
| M7.7 | Cost tracking | Token count and estimated cost per analysis run. Configurable cost ceiling. Abort if ceiling exceeded. |

**Exit gate:** Analyzer produces valid edit proposals from traces. Proposals are validated and deduplicated. Cost is tracked.

**Analyzer system prompt (structure):**
```
You are a prompt optimization analyst. You review execution traces 
where an agent failed and propose minimal, concrete edits to the 
agent's system prompt.

Current prompt (frozen sections marked with [FROZEN]):
{current_prompt}

Failed traces (batch of {N}):
{traces}

For each failure pattern you identify, propose ONE edit:
- Which section of the prompt to change
- The exact old text (must match current prompt)
- The exact new text (minimal change)
- Why this change should help (hypothesis grounded in trace evidence)
- Which traces support this hypothesis

Do NOT propose changes to [FROZEN] sections.
Do NOT propose more than 3 edits per batch.
Each edit must be minimal — change the fewest lines possible.
```

### M8 — Diff Visualization

**Scope:** Show the user exactly what changed, what stayed the same, and why. See [prompt-diff-design.md](../prompt-diff-design.md) for full design.

| Task | Description | Deliverable |
|---|---|---|
| M8.1 | CLI diff output | Inline diff format: `-` removed lines, `+` added lines, `(frozen)` annotations. Color-coded if terminal supports it. |
| M8.2 | Guardrail report output | CLI table: check name, passed/failed, value, threshold. Summary line: "All passed" or "N failed". |
| M8.3 | Edit summary | One-line summary per edit: "Edit #{N} — {Promoted|Rejected} — {+X%} accuracy (p<{val}, n={trials}) — {lines changed} lines" |
| M8.4 | Edit density (CLI) | Text-based bar chart showing per-section edit frequency over last N cycles |

**Exit gate:** CLI diff is readable. Guardrail report is clear. Edit summary is one line. Density chart renders.

### M9 — CLI

**Scope:** The user-facing interface for v0.1.0. All operations accessible via CLI.

| Command | Description | Flags |
|---|---|---|
| `agent-self-edit init` | Scaffold config file, create registry directory, load held-out task set | `--prompt <path>`, `--tasks <path>`, `--model <name>` |
| `agent-self-edit run` | Start the self-improvement loop. Watches for traces, batches, analyzes, tests, promotes. | `--batch-size <N>`, `--shadow` (v0.2.0), `--dry-run` (analyze only, no promote) |
| `agent-self-edit status` | Show current state: prompt version, last edit, guardrail pass rate, improvement trend | `--json` for machine-readable output |
| `agent-self-edit diff <v1> <v2>` | Show diff between two prompt versions | `--inline`, `--side-by-side` (default) |
| `agent-self-edit rollback <version>` | Roll back to a previous prompt version | `--reason <text>` |
| `agent-self-edit guardrails` | Show guardrail history | `--last <N>`, `--edit <id>` |
| `agent-self-edit lineage` | Show full prompt version history | `--from <version>`, `--format table|json` |
| `agent-self-edit propose` | Manually trigger analysis on current traces | `--dry-run` (propose only, no A/B test) |
| `agent-self-edit ingest <file>` | Ingest a trace file | `--format json` |

**Exit gate:** All commands work. `init` creates valid config. `run` starts the loop. `status` shows current state. `diff` shows readable output. `rollback` works. `guardrails` shows history. `lineage` shows full history.

### M10 — Field Test

**Scope:** Validate the loop end-to-end on a synthetic task suite. Prove improvement is measurable and guardrails work.

| Task | Description | Deliverable |
|---|---|---|
| M10.1 | Synthetic task suite | 50 tasks across 3 domains (classification, extraction, generation). Each task has input, expected output, scorer. 30 in held-out set, 20 in training set. |
| M10.2 | Baseline measurement | Run baseline prompt against held-out set. Record accuracy, latency, cost. |
| M10.3 | Improvement measurement | Run 10 self-improvement iterations. Measure: accuracy improvement, guardrail pass rate, rejection rate, near-miss rate, cost per improvement. |
| M10.4 | Guardrail validation | Inject 5 intentionally bad edits. Verify all 5 are caught by guardrails. Verify none are promoted. |
| M10.5 | Rollback validation | Promote an edit, then roll back. Verify prompt reverts correctly. Verify lineage is preserved. |
| M10.6 | Field test report | Markdown report: baseline, per-iteration results, guardrail validation, rollback validation, cost analysis, recommendations. |

**Exit gate:** Field test shows measurable improvement. Guardrails catch all injected bad edits. Rollback works. Report is comprehensive.

### M11 — Release

**Scope:** Package, document, publish.

| Task | Description | Deliverable |
|---|---|---|
| M11.1 | PyPI package | `pyproject.toml`, build, twine, upload. Package: `agent-self-edit` |
| M11.2 | Docker image | Dockerfile, multi-stage build. Image runs the loop as a sidecar. |
| M11.3 | Documentation | Quickstart, API reference, config reference, CLI reference, architecture overview |
| M11.4 | GitHub release | Release notes, tagged release, changelog |
| M11.5 | Repo public | Make repo public, main branch protected, CI required |
| M11.6 | OpenSSF badge | Register, complete checklist, embed badge in README |

**Exit gate:** PyPI published. Docker image works. Docs complete. Repo public. OpenSSF badge earned.

### v0.1.0 Exit Criteria

- [ ] Self-improvement loop runs end-to-end: trace → analyze → A/B test → gate → promote
- [ ] Guardrails catch 100% of injected bad edits
- [ ] Rollback works in one command
- [ ] Prompt lineage is fully queryable
- [ ] CLI covers all operations
- [ ] Diff visualization is readable
- [ ] Field test shows measurable improvement (target: 10%+ over 10 iterations)
- [ ] PyPI published, Docker image works, repo public
- [ ] OpenSSF Best Practices Passing badge
- [ ] Coverage > 90%, ruff clean, mypy strict clean

---

## 9.3 v0.2.0 — Trust + Visibility

**Goal:** Make the loop trustworthy enough to run unattended in production. Add the visibility layer that lets operators monitor, audit, and intervene.

**Success bar:** An operator deploys AgentSelfEdit in shadow mode, reviews 20 proposed edits over a week, gains confidence, switches to live mode, and the agent improves without intervention. Drift detection alerts fire when needed. The dashboard shows the full picture.

### M1 — Shadow Mode

**Scope:** Run the full loop without modifying the prompt. The operator reviews before enabling.

| Task | Description | Deliverable |
|---|---|---|
| M1.1 | Shadow mode flag | `--shadow` flag on `run`. Loop runs analyzer, A/B test, gate — but never writes to the prompt file. All results stored in shadow log. |
| M1.2 | Shadow log | JSONL log: timestamp, edit proposal, A/B results, gate decision. Queryable. |
| M1.3 | Shadow-to-live transition | `agent-self-edit promote --from-shadow <edit_id>` — promotes a shadow edit to live. Runs gate again. Creates new prompt version. |
| M1.4 | Shadow dashboard (CLI) | `agent-self-edit shadow --list` — shows all shadow edits with their gate decisions. `--review <id>` — shows full detail. |

**Exit gate:** Shadow mode runs without modifying the prompt. Shadow log is queryable. Shadow-to-live promotion works.

### M2 — Drift Detection (Production-Grade)

**Scope:** Replace v0.1.0's TF-IDF drift with embedding-based semantic similarity. Add alerts and dashboards.

| Task | Description | Deliverable |
|---|---|---|
| M2.1 | Embedding-based drift | Compute sentence embeddings (sentence-transformers or OpenAI embeddings) for original and current prompt. Cosine similarity. Drift = 1 - similarity. |
| M2.2 | Per-section drift | Compute drift per prompt section. Identify which sections have drifted most. Report section-level drift scores. |
| M2.3 | Drift threshold config | Configurable per-deployment. Default: 0.30. Alert when exceeded. |
| M2.4 | Drift alert | When drift exceeds threshold: log alert, send webhook (if configured), show in dashboard, block further promotions until reviewed. |
| M2.5 | Drift history | Track drift score over time. Show trend on dashboard. Detect accelerating drift. |
| M2.6 | Drift reset | `agent-self-edit drift --reset` — sets the current prompt as the new "original" for drift comparison. Used after intentional manual edits. |

**Exit gate:** Embedding-based drift works. Per-section drift is accurate. Alerts fire at threshold. Drift history is tracked. Reset works.

### M3 — Web Dashboard

**Scope:** React-based dashboard for monitoring the self-improvement loop.

| Task | Description | Deliverable |
|---|---|---|
| M3.1 | Dashboard server | FastAPI serves the dashboard at `localhost:8080`. Serves React build from `dashboard/`. |
| M3.2 | Timeline view | Scrollable timeline of every edit cycle. Color-coded: green (promoted), red (rejected), yellow (near-miss). Click to see detail. |
| M3.3 | Prompt diff view | Side-by-side diff for any two versions. Inline toggle. Frozen sections grayed out. Color-coded changes. |
| M3.4 | Guardrail report view | Per-edit guardrail check results. Pass/fail per check. Value vs threshold. Summary line. |
| M3.5 | Edit density heatmap | Per-section bar chart. Configurable time window (last 10, 20, 50 cycles). Color intensity by edit frequency. |
| M3.6 | Drift chart | Line chart of drift score over time. Threshold line. Alert markers. |
| M3.7 | Rollback control | Button on each promoted edit. Confirmation dialog. Logs rollback reason. |
| M3.8 | Status overview | Current prompt version, total edits, promotion rate, rejection rate, near-miss rate, improvement trend, cost summary. |

**Exit gate:** Dashboard loads. Timeline renders. Diff view works. Guardrail report displays. Density heatmap renders. Drift chart shows trend. Rollback button works. Status overview is accurate.

### M4 — REST API

**Scope:** Programmatic access to all registry, diff, and gate operations.

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/status` | GET | Current state: prompt version, last edit, improvement trend |
| `/api/v1/edits` | GET | List all edits with filters (promoted, rejected, near-miss, date range) |
| `/api/v1/edits/{id}` | GET | Full detail: proposal, A/B results, gate result, diff |
| `/api/v1/diff` | GET | Diff between two versions. Params: `v1`, `v2`, `format` (inline, side-by-side) |
| `/api/v1/lineage` | GET | Full prompt version history |
| `/api/v1/rollback` | POST | Rollback to a version. Body: `{ version, reason }` |
| `/api/v1/guardrails` | GET | Guardrail history with filters |
| `/api/v1/drift` | GET | Drift history and current score |
| `/api/v1/density` | GET | Edit density per section |
| `/api/v1/shadow` | GET | Shadow mode edits |
| `/api/v1/shadow/promote` | POST | Promote a shadow edit to live |

**Exit gate:** All endpoints return correct data. Error handling for invalid inputs. OpenAPI/Swagger docs auto-generated.

### M5 — Near-Miss Feedback Loop

**Scope:** The analyzer learns from rejected edits to avoid re-proposing similar changes.

| Task | Description | Deliverable |
|---|---|---|
| M5.1 | Near-miss similarity | When a new proposal is generated, compare it against the near-miss log using embedding similarity. If similarity > threshold (default 0.85), skip the proposal. |
| M5.2 | Near-miss clustering | Cluster near-misses by failure pattern. Report: "5 near-misses in 'classification rule' section — consider manual review." |
| M5.3 | Analyzer context injection | Inject the last 10 near-misses into the analyzer's context as "avoid these patterns." |
| M5.4 | Rejection rate tracking | Track rejection rate over time. Report trend. Alert if rejection rate increases (analyzer not learning). |

**Exit gate:** Near-miss similarity prevents re-proposal. Clustering works. Analyzer context includes near-misses. Rejection rate is tracked.

### M6 — Audit Export

**Scope:** Export the full audit trail for compliance.

| Task | Description | Deliverable |
|---|---|---|
| M6.1 | Export format | JSON and CSV export of: all edits, all gate decisions, all near-misses, all rollbacks, with timestamps and metadata |
| M6.2 | SOC 2 mapping | Map each audit event to SOC 2 control objectives (CC1, CC2, CC6, CC7) |
| M6.3 | Tamper-evident log | Hash chain: each log entry includes the hash of the previous entry. Detect tampering. |
| M6.4 | Export command | `agent-self-edit export --format json|csv --from <date> --to <date>` |

**Exit gate:** Export produces valid JSON and CSV. SOC 2 mapping is documented. Hash chain detects tampering.

### v0.2.0 Exit Criteria

- [ ] Shadow mode runs without modifying the prompt
- [ ] Embedding-based drift detection works with per-section breakdown
- [ ] Drift alerts fire at threshold and block promotions
- [ ] Web dashboard shows timeline, diffs, guardrails, density, drift, status
- [ ] REST API covers all operations with OpenAPI docs
- [ ] Near-miss feedback reduces rejection rate over time
- [ ] Audit export produces compliance-ready output
- [ ] Tamper-evident log detects tampering
- [ ] Coverage > 90%, ruff clean, mypy strict clean

---

## 9.4 v0.3.0 — Scale + Adapters

**Goal:** Make the loop work with real agents, not just synthetic tasks.

| Milestone | Focus | Key Deliverables |
|---|---|---|
| M1 | Framework adapters | LangGraph adapter, PydanticAI adapter, CrewAI adapter, raw Python adapter. Each: trace ingestion + prompt injection. |
| M2 | Multi-failure clustering | Analyzer groups failures by pattern (embedding clustering). Proposes edits targeting skill gaps, not one-off mistakes. |
| M3 | Adaptive sample floors | Sample floor adjusts based on observed variance. High-variance tasks need more trials. Low-variance tasks need fewer. |
| M4 | Evals integration | Integration with EvalForge for held-out task evaluation. EvalForge provides scorers and task sets. |
| M5 | Guardrail history dashboard | Timeline of guardrail pass/fail rates, near-miss trends, drift scores over time. |
| M6 | Per-segment performance | A/B test results broken down by task segment (domain, difficulty, input type). Detect segment-specific regressions. |
| M7 | Cost optimization | Token budget per cycle. Cache analyzer responses for similar traces. Skip A/B test if effect size is obviously zero. |

## 9.5 v0.4.0 — Fleet

**Goal:** Make the loop work across many agents.

| Milestone | Focus | Key Deliverables |
|---|---|---|
| M1 | Fleet-wide shared-rules | Aggregate near-miss patterns across multiple agents. Identify shared prompt improvements. Propose fleet-wide edits. |
| M2 | Cost-aware improvement | Track cost per improvement. Optimize for quality-per-dollar. Budget enforcement per agent and per fleet. |
| M3 | Promotion analytics | Regression reports, per-agent improvement trends, cross-agent comparison, A/B test archive. |
| M4 | Fleet dashboard | Per-agent cards, fleet overview, cross-agent pattern detection, fleet-wide edit proposals. |

## 9.6 v0.5.0 — Hardening

| Milestone | Focus |
|---|---|
| M1 | OpenSSF Silver badge |
| M2 | Performance optimization (analyzer caching, parallel A/B trials) |
| M3 | Comprehensive documentation (user guide, admin guide, integration guide) |
| M4 | Load testing (1000+ traces, 100+ edit cycles) |
| M5 | Security audit (OWASP Agentic Top 10 full assessment) |

## 9.7 v0.6.0 — Extensibility

| Milestone | Focus |
|---|---|
| M1 | Plugin system (custom guardrails, custom scorers, custom analyzers) |
| M2 | Webhook integration (Slack, Discord, email alerts on promotion/rejection/drift) |
| M3 | Custom drift detection strategies (pluggable drift calculators) |
| M4 | Prompt template system (variables, conditionals, includes) |

## 9.8 v0.7.0 — Enterprise

| Milestone | Focus |
|---|---|
| M1 | SSO authentication (OIDC, SAML) |
| M2 | Role-based access control (admin, operator, viewer) |
| M3 | Multi-tenant support (multiple agents, isolated registries) |
| M4 | SOC 2 Type II readiness documentation |

## 9.9 v0.8.0 — Observability

| Milestone | Focus |
|---|---|
| M1 | OpenTelemetry export (traces, metrics, logs) |
| M2 | Prometheus metrics endpoint |
| M3 | Alerting (PagerDuty, Slack, email) |
| M4 | SLO tracking (promotion rate, rejection rate, improvement rate, cost) |

## 9.10 v0.9.0 — Release Candidate

| Milestone | Focus |
|---|---|
| M1 | Feature freeze |
| M2 | Bug fixes from community feedback |
| M3 | Documentation finalization |
| M4 | Migration guide from v0.x to v1.0 |
| M5 | Backward compatibility guarantees |

## 9.11 v1.0.0 — General Availability

| Milestone | Focus |
|---|---|
| M1 | Stable API (semver guarantees) |
| M2 | Long-term support policy |
| M3 | Production deployment guide (Docker, Kubernetes, bare metal) |
| M4 | Case studies (3+ real-world deployments) |
| M5 | Community governance (CONTRIBUTING, GOVERNANCE, ROADMAP) |

---

## 9.12 Build Sequence (v0.1.0)

The v0.1.0 build sequence is engine-first: the promotion gate and A/B test engine are built first, because everything else is downstream of the one question that matters: can you prove one prompt is better than another, safely?

**Build order:**
1. M1 — Config scaffold + held-out task set management
2. M3 — A/B test engine (the core measurement capability)
3. M4 — Promotion gate (the safety-critical component)
4. M5 — Prompt registry (versioned storage)
5. M6 — Guardrail module (constraint enforcement)
6. M2 — Execution trace ingestion (trace store + batching)
7. M7 — Feedback analyzer (edit proposal generation)
8. M8 — Diff visualization (user-facing output)
9. M9 — CLI (user-facing interface)
10. M10 — Field test (validation)
11. M11 — Release (ship)

**Rationale:** The A/B test engine and promotion gate are the hardest parts and the core value proposition. Build them first, prove they work, then wrap the analyzer and CLI around them. If the gate doesn't work, nothing else matters.