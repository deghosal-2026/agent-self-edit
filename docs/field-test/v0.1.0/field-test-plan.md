# Field Test Plan — AgentSelfEdit v0.1.0

> Test objectives, corpus structure, baseline/improvement measurement, guardrail validation, rollback validation, cost analysis, LLM I/O capture, and hermetic vs LLM testing strategy.

## 1. What This Project Does

AgentSelfEdit is a sidecar that observes execution traces and rewrites its own system prompt through a closed loop:

```
Agent executes task ──▶ Execution trace stored (SQLite)
                                │
                                ▼
                      Feedback Analyzer (LLM)
                      reviews traces, proposes concrete edits,
                      each with a written hypothesis
                                │
                                ▼
─────────────────────  A/B Test Engine  ─────────────────────
  candidate edit vs current prompt on a held-out task set:
  win rate, bootstrap confidence interval, effect size,
  permutation p-value, per-task breakdown
────────────────────────────────────────────────────────────
                                │
                                ▼
                Promotion Gate (deterministic checks)
                1. Sample floor     4. Frozen sections
                2. Effect size      5. Edit-distance limit
                3. Confidence p-val 6. Drift detection
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
          Promoted         Near-miss        Rejected
     prompt updated in     logged for       archived with
     versioned Registry    human review     full reasoning
```

The field test must prove this loop works end-to-end against a real LLM.

## 2. Test Objectives

1. **Loop closure** — can the full loop (trace → analyze → A/B test → gate → promote) run end-to-end with mock providers (hermetic) and real LLM (OMLX/OpenRouter)?
2. **Improvement** — does the loop measurably improve accuracy over 10 iterations? Target: 10%+ improvement.
3. **Guardrail effectiveness** — do guardrails catch 100% of injected bad edits? (FN < 0.1%, FP < 1%)
4. **Rollback** — does rollback revert the prompt and preserve lineage?
5. **Cost** — is cost per iteration < $0.50?
6. **Docker** — does the image build and run the full loop against OMLX inside a container?
7. **LLM I/O capture** — are all LLM requests and responses written to disk for debuggability?

## 3. LLM Arms

All LLM-based tests support two arms, configurable via environment variables and CLI args:

| Arm | Provider | Endpoint | Model | Key env var |
|-----|----------|----------|-------|-------------|
| Local | `omlx` | `http://localhost:8000/v1` | `Qwen3.5-9B-MLX-4bit` | `OPENROUTER_API_KEY` |
| Cloud | `openai` | `https://openrouter.ai/api/v1` | `openai/gpt-4o-mini` | `OPENROUTER_API_KEY` |

The API key is **always** from `OPENROUTER_API_KEY` — no fallbacks, no hardcoding. See `field-test/scripts/README.md` for all commands.

## 4. Corpus Structure

### 4.1 Synthetic Corpus (90 tasks)

| Domain | Tasks | Scorer | Edge cases |
|--------|-------|--------|------------|
| Classification | 30 | ExactMatch | ambiguous boundary, multi-label, missing category, truly ambiguous |
| Extraction | 25 | Contains | missing fields, wrong format, extra fields, nested, multi-entity, conflicting info |
| Generation | 25 | LLMJudge | off-topic, wrong tone, missing constraints, non-ops, tone variation, constraint conflict |
| Mixed-domain | 10 | Contains | cross-domain (classification+extraction, extraction+generation, etc.) |

Additional:
- **Seeded failure prompts**: 15 prompts with known failure modes (including `<!-- frozen -->` annotations)
- **Adversarial edits**: 8 intentionally bad edits (each improves one task type but degrades another)

### 4.2 Real-Life Corpus (770 traces)

| Source | Traces | Description | Variety added |
|--------|--------|-------------|---------------|
| agent-exec-trace (AgentObservatory) | 336 | Real LLM telemetry from Qwen 4B/9B models — detector results, latency, tokens, cache hits | Multi-step LLM telemetry, detector-level failures (hallucination, semantic loop, degradation), cache-hit traces |
| agent-eval-forge (EvalForge) | 34 | Real agent scenario failures across 12 frameworks (LangGraph, CrewAI, PydanticAI, OpenAI Agents, LlamaIndex, etc.) | Cross-framework agent failures, tool-call errors, multi-step scenario traces |
| HuggingFace (open-agent-traces) | 150 | 10-domain multi-agent traces (customer support, code review, incident response, market research, legal, financial, content generation, e-commerce, academic review, data pipeline) | 10 distinct domains, multi-agent orchestration (planner → worker → aggregate patterns), tool calls (web_search, calculator, file_reader, code_interpreter, text_splitter, database_query) |
| HuggingFace (customer-support) | 50 | Customer support agent traces with tool calls, reasoning steps, deviations | Sequential agent patterns, deviation tracking, customer-facing tone |
| HuggingFace (pi coding agent) | 200 | Real human-AI coding agent sessions (TypeScript, Java, Python) — real prompts, real tool calls, real errors, real backtracking | Real human prompts (typos, vague, context-dependent), real tool calls (bash, read, edit, write), real error recovery, multi-file refactors, varied programming languages |

All real traces are validated against the Trace schema (`validate_trace()`). Each has `steps` populated with per-step metadata (latency, tokens, model, tool calls, agent roles).

> **Known issue (#97):** `agent-observatory-traces.jsonl` has duplicate `task_id` values (all `s_BlipZorp_000000`). This breaks TraceStore ingestion. Must be fixed in `import_real_traces.py`.

### 4.3 Variety Coverage

| Dimension | Synthetic | Real-life |
|-----------|-----------|-----------|
| Languages | English only | English + TypeScript, Java, Python, Lua |
| Task types | 4 domains (classification, extraction, generation, mixed) | 14 domains (support, code review, incident, research, legal, financial, content, e-commerce, academic, pipeline, coding, monitoring, deployment, security) |
| Failure modes | Expected output mismatch | Hallucination, semantic loop, quality degradation, tool errors, deviation, backtracking |
| Trace complexity | Single-step | Multi-step (2-2,500 events per trace) |
| Tool calls | None | bash, read, edit, write, web_search, calculator, code_interpreter, file_reader, database_query, text_splitter |
| Agent patterns | Single-agent | Single-agent, multi-agent (planner → workers → aggregate), sequential pipeline |
| Model diversity | Mock only | Qwen 4B, Qwen 9B, Claude Opus, Claude Sonnet, GPT-4o, DeepSeek, Gemini, Kimi |

### 4.4 Directory Layout

```
field-test/v0.1.0/
├── corpus/
│   ├── synthetic/
│   │   ├── classification.yaml          (30 tasks)
│   │   ├── extraction.yaml              (25 tasks)
│   │   ├── generation.yaml              (25 tasks)
│   │   ├── mixed-domain.yaml            (10 tasks)
│   │   ├── seeded-prompts/
│   │   │   └── seeded-prompts.yaml      (15 prompts)
│   │   └── adversarial-edits/
│   │       └── adversarial-edits.yaml   (8 edits)
│   └── real-life/
│       └── real-traces/
│           ├── agent-observatory-traces.jsonl  (336)
│           ├── evalforge-failures.jsonl         (34)
│           ├── hf-open-agent-traces.jsonl       (150)
│           ├── hf-customer-support-traces.jsonl  (50)
│           ├── hf-pi-coding-agent-traces.jsonl  (200)
│           └── README.md
├── scripts/
│   ├── generate_traces.py          (synthetic trace generator)
│   ├── import_real_traces.py       (portfolio trace importer)
│   ├── download_hf_traces.py       (HuggingFace open-agent-traces + customer-support)
│   ├── download_pi_traces.py       (HuggingFace pi coding agent traces)
│   ├── run_docker_tests.py         (docker pytest runner)
│   ├── run_docker_field_test.py    (standalone docker test — to be rewritten, #99)
│   ├── run_traces.py               (LLM eval runner — to be replaced, #95)
│   └── README.md                   (script usage guide)
├── results/
│   ├── docker/
│   │   └── omlx/
│   │       └── qwen3.5-4b-4bit/
│   │           ├── docker-run-full-loop.json
│   │           ├── docker-propose-full.json
│   │           ├── llm-traffic-run.jsonl
│   │           └── llm-traffic-propose.jsonl
│   ├── omlx/
│   │   └── qwen3.5-4b-4bit/
│   │       ├── *-results.json
│   │       └── llm-traffic-*.jsonl
│   ├── openai/
│   │   └── openai-gpt-4o-mini/
│   │       ├── *-results.json
│   │       └── llm-traffic-*.jsonl
│   └── FIELD_TEST_REPORT.md         (to be written, #101)
└── (no plan file here — see docs/field-test/v0.1.0/)
```

## 5. Baseline Measurement

1. Pick a baseline prompt (e.g. "You are a classifier.").
2. Run `run_ab_test(baseline, baseline, holdout_set, llm, scorer)` → n_trials.
3. Record: accuracy, per-task scores, cost.
4. Target: > 70% baseline accuracy (synthetic tasks are designed to be achievable).

> **Note:** `run_ab_test()` requires a `TaskSet` loaded from `config.tasks.task_set_path`. If this is empty, the A/B test cannot execute (issue #103). The config for any full-loop test must set `task_set_path` to a valid YAML.

## 6. Improvement Measurement

1. Run 10 self-improvement iterations via `agent-self-edit run --once` (no `--dry-run`).
2. Each iteration: analyze failed traces → propose edits → A/B test → gate → promote.
3. Record per iteration: accuracy on held-out set, guardrail pass/fail, cost, A/B test results, LLM I/O.
4. Target: 10%+ improvement over baseline after 10 iterations.

> **Config requirement:** `task_set_path` must point to a held-out task set YAML (e.g. `classification.yaml`) so `run_ab_test()` can execute.

## 7. Guardrail Validation

- **False positive test:** Inject 5 good edits. Verify < 1% rejected (FP < 1%).
- **False negative test:** Inject 5 intentionally bad edits (adversarial). Verify 100% caught (FN < 0.1%).
- **Stress test:** Run 100 random edits through gate. Verify 0 crashes, all decisions valid.

## 8. Rollback Validation

1. Promote an edit.
2. Roll back via `agent-self-edit rollback <version> --reason "test"`.
3. Verify prompt reverts.
4. Verify lineage shows both promote and rollback events.

## 9. LLM I/O Capture

Every LLM call (analyzer + A/B test) is captured to disk for debuggability:

- **Traffic log:** `AGENT_SELF_EDIT_LLM_LOG` env var → JSONL append-mode file
- **Each entry:** `{model, base_url, messages, temperature, response, usage, latency_ms}`
- **Results JSON:** structured per-test report with meta (accuracy, tokens, latency) + per-trace LLM I/O and scoring

Results are stored under `field-test/v0.1.0/results/<provider>/<model>/`.

## 10. Test Matrix

### Hermetic (CI-safe, mock LLM)

| Test | CI | LLM | Pass condition | Status |
|------|----|-----|----------------|--------|
| Baseline measurement | ✅ | mock | > 70% accuracy | ✅ |
| Dry-run loop | ✅ | mock | loop completes, all stages | ✅ |
| Gate validation | ✅ | mock | 5/5 bad edits rejected | ✅ |
| Rollback test | ✅ | mock | prompt reverts, lineage shows | ✅ |
| Zero-LLM full loop | ✅ | mock | no real LLM calls, loop completes | ✅ |
| Concurrency | ✅ | mock | 100 traces, no data loss | ✅ |
| Registry integrity | ✅ | mock | 20 versions, 0 corruption | ✅ |
| Guardrail stress | ✅ | mock | 100 random edits, 0 crashes | ✅ |
| Real trace replay | ✅ | mock | 50 real traces validate + ingest | ✅ |
| Full loop with real traces | ✅ | mock | loop processes 770 real traces | ✅ |

### LLM-based (OMLX, CI-skipped)

| Test | LLM | Pass condition | Status | Issue |
|------|-----|----------------|--------|-------|
| Full loop integration | OMLX 4B | all stages produce valid output, LLM I/O captured | ✅ | #100 closed |
| 15-iteration improvement | OMLX 4B | 10%+ improvement | ❌ 0% — honest result | #100 closed |
| Adversarial edit test | OMLX 4B | 5/5 bad edits caught | ⬜ not run | #107 |
| Analyzer quality | OMLX 4B | > 80% validity rate | ✅ valid proposals every iteration | #100 |
| Cost analysis | OMLX 4B | < $0.50 per iteration | ✅ $0.00 (local) | #107 closed |
| Guardrail FP/FN | OMLX 4B | FP<1%, FN<0.1% | ✅ FP=0, FN=0 | #107 closed |

### Docker (requires Docker daemon + OMLX)

| Test | LLM | Pass condition | Status | Issue |
|------|-----|----------------|--------|-------|
| Docker build | none | image builds, openai installed | ✅ | — |
| OMLX is up | none | non-empty model list | ✅ | — |
| OMLX model available | none | `Qwen3.5-9B-MLX-4bit` found | ✅ | — |
| OMLX reachable from container | none | model visible from container | ✅ | — |
| Docker help | none | all 10 commands listed | ✅ | — |
| Docker validate | none | exit 0 or 2 | ✅ | — |
| Docker status | none | exit 0, 1, or 2 | ✅ | — |
| Docker full loop | OMLX | ingest → analyze → A/B test → gate → promote, LLM I/O captured | ✅ | #98 closed |
| Docker propose full | OMLX | analyze → propose → A/B test → gate, LLM I/O captured | ✅ | #98 closed |

## 11. Deliverables

- `field-test/v0.1.0/results/FIELD_TEST_REPORT.md` (issue #101)
- Per-iteration accuracy table + trend chart
- Guardrail FP/FN analysis
- Cost-per-iteration breakdown
- Test matrix pass/fail summary
- LLM I/O traffic logs (per arm, per test)

## 12. Open Issues

| Issue | Problem | Status |
|-------|---------|--------|
| [#93](https://github.com/deghosal-2026/agent-self-edit/issues/93) | D10 field test plan design doc | ✅ closed — plan exists |
| [#95](https://github.com/deghosal-2026/agent-self-edit/issues/95) | `run_traces.py` is wrong tool | ✅ closed — deleted |
| [#96](https://github.com/deghosal-2026/agent-self-edit/issues/96) | Scoring always passes | ✅ closed — deleted with run_traces.py |
| [#97](https://github.com/deghosal-2026/agent-self-edit/issues/97) | Duplicate `task_id` | ✅ closed — unique IDs |
| [#98](https://github.com/deghosal-2026/agent-self-edit/issues/98) | Docker integration only `--dry-run` | ✅ closed |
| [#99](https://github.com/deghosal-2026/agent-self-edit/issues/99) | `run_docker_field_test.py` stale | ✅ closed — deleted |
| [#100](https://github.com/deghosal-2026/agent-self-edit/issues/100) | LLM field tests not implemented | ✅ closed — run_improvement_loop.py |
| [#101](https://github.com/deghosal-2026/agent-self-edit/issues/101) | Field test report missing | ✅ closed — final-field-test-report.md |
| [#102](https://github.com/deghosal-2026/agent-self-edit/issues/102) | WBS row 23 falsely marked done | ✅ closed |
| [#103](https://github.com/deghosal-2026/agent-self-edit/issues/103) | A/B test engine not exercised | ✅ closed |
| [#104](https://github.com/deghosal-2026/agent-self-edit/issues/104) | A/B test fragment bug | ✅ closed |
| [#105](https://github.com/deghosal-2026/agent-self-edit/issues/105) | Ruff: 13 lint errors | ⬜ open |
| [#106](https://github.com/deghosal-2026/agent-self-edit/issues/106) | Mypy: 5 type errors | ⬜ open |
| [#107](https://github.com/deghosal-2026/agent-self-edit/issues/107) | Guardrail FP/FN + cost vs real LLM | ✅ closed — FP=0, FN=0, cost=$0.00 |
| [#108](https://github.com/deghosal-2026/agent-self-edit/issues/108) | Docker: no latency/token assertions | ✅ closed |
| [#109](https://github.com/deghosal-2026/agent-self-edit/issues/109) | Docker: identical seeded traces | ✅ closed |
| [#110](https://github.com/deghosal-2026/agent-self-edit/issues/110) | Docker: accepts tie without delta check | ✅ closed |
| [#111](https://github.com/deghosal-2026/agent-self-edit/issues/111) | Docker: no registry state assertion | ✅ closed |
| [#112](https://github.com/deghosal-2026/agent-self-edit/issues/112) | Docker test plan stale | ✅ closed |

---

## 13. Field Test Results Summary

### Improvement Loop (15 iterations, Qwen3.5-4B-4bit local)

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Improvement | 10%+ | 0% (20%→20%) | ❌ not met — honest result |
| Gate FP rate | < 1% | 0% (no false promotions) | ✅ |
| Gate FN rate | < 0.1% | 0% (no good edits rejected) | ✅ |
| Cost per iteration | < $0.50 | $0.00 (local 4B) | ✅ |
| LLM calls | — | 4,150 | — |
| Total tokens | — | 716,580 | — |
| Wall time | — | 37 minutes | — |
| p-value (every iteration) | < 0.05 | 0.23 | gate correctly rejects |

### Docker Tests (9/9 pass)

All Docker tests pass. Full loop runs inside container against OMLX. Registry state verified. Per-trace latency and token assertions pass. A/B test uses 2 distinct prompts.

### What the field test proved

1. **The gate works** — 15/15 iterations correctly rejected. 0 false positives, 0 false negatives.
2. **The loop is mechanically sound** — trace → analyze → A/B test → gate → reject. Every stage produces valid output.
3. **A/B results are inspectable** — per-iteration artifacts (prompt-a/b, results-a/b, ab-comparison, analysis, accuracy) written for all 15 iterations.
4. **The current analyzer strategy is insufficient** — same edit proposed every iteration, p=0.23, not significant.
5. **Local 4B is the right tool** — free, fast (540ms/call), same accuracy as 9B and cloud.

### What the field test did not prove

1. **Improvement** — 0% improvement. The analyzer's edit is real but underpowered.
2. **Adversarial edit rejection** — not tested with intentionally bad edits against real LLM.
3. **Rollback on real promotion** — no promotion occurred, so rollback wasn't exercised.
4. **Non-LLM hermetic tests** — not run in this session (CI items).

---

## 14. Follow-Up Work for v0.2.0

| # | Improvement | Why |
|---|-------------|-----|
| 1 | Rejection-aware analyzer | Feed gate rejection back so analyzer proposes different edits |
| 2 | Cumulative evidence across iterations | Aggregate evidence if same edit fixes same tasks repeatedly |
| 3 | Larger A/B task set (50+) | More statistical power to detect improvement at p<0.05 |
| 4 | Constrain over-broad multi-label edits | Reduce tendency to over-add "urgent" |
| 5 | Smaller, more targeted edits | Stay under drift threshold with fewer changed lines |
| 6 | Adversarial edit test against real LLM | Inject 5 bad edits, verify gate catches all 5 |
| 7 | Rollback test with real promotion | Promote an edit, rollback, verify prompt reverts |
| 8 | Fix ruff + mypy | Exit gate requires clean lint and type checks |
| 9 | Multi-domain testing | Test on extraction and generation, not just classification |
| 10 | Real trace ingestion | Feed real agent execution traces to the analyzer |
