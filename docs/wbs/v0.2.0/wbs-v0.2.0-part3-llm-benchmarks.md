# WBS — AgentSelfEdit v0.2.0 Part 3: Local LLM & Benchmarks

> **Milestones covered:** M4 (Local LLM & Accuracy) · M5 (Benchmark Expansion)
> **Source:** v0.1.0 field test issues-found.md Issues 8–13, 20–25
> **Dependency:** M4 (depends on M3) → M5 (depends on M4)
> **Issue Range:** #129–#141

---

## Milestone 4: Local LLM & Accuracy Improvements (#129–#135)

**Objective:** Add model role separation (executor, analyzer, judge), configurable provider backends, benchmark manifests with disjointness validation, structured local-model comparison, optimizer-effectiveness metrics, and tighten claims to match evidence.

### M4 Design Documents

- **D3 — Model role separation design** (`docs/design/model-role-design.md`): executor/analyzer/judge roles, per-role provider config, per-role generation settings.
- **D4 — Benchmark manifest design** (`docs/design/benchmark-manifest-design.md`): benchmark-role manifests (failure-seeding, promotion A/B, held-out, regression sentinel, adversarial), disjointness validation, scorer compatibility, required counts.

### M4 Task Checklist

| # | Issue | Build (files) | Behavior + edge cases | Issue | Verify |
|---|-------|---------------|----------------------|-------|--------|
| 1 | Rubric-backed generation judge | `src/agent_self_edit/scorers.py`, generation corpus | Define per-benchmark rubrics; add positive and negative anchors; multi-dimension scoring; separate judge model role; judge configuration is benchmark-aware; reproducible results | [#129](https://github.com/deghosal-2026/agent-self-edit/issues/129) | Generation tasks have explicit rubrics; results reproducible |
| 2 | Add separate model roles | `src/agent_self_edit/config.py`, `src/agent_self_edit/cli/run.py`, `src/agent_self_edit/cli/propose.py`, field-test runner | Add config sections for executor, analyzer, judge model roles; each role has its own provider, model, temperature, max_tokens; role configs are individually optional (fall back to default provider) | [#130](https://github.com/deghosal-2026/agent-self-edit/issues/130) | Roles can be configured independently; each role uses correct model |
| 3 | Make provider backend knobs configurable | `src/agent_self_edit/llm/openai.py`, `src/agent_self_edit/config.py` | Add configurable per-role generation settings (temperature, max_tokens); allow backend-specific request extensions to be configured rather than hardcoded; provider works with and without backend-specific extras | [#131](https://github.com/deghosal-2026/agent-self-edit/issues/131) | Provider configurable per role; no hardcoded backend assumptions |
| 4 | Add benchmark-role manifests | `field-test/v0.1.0/corpus/`, `src/agent_self_edit/tasks.py`, field-test runner config | Introduce benchmark-role manifests with role identity, scorer compatibility, required counts, disjointness validation where needed | [#132](https://github.com/deghosal-2026/agent-self-edit/issues/132) | Manifests validate correctly; disjointness enforced |
| 5 | Expand local-model comparison | Field-test docs, benchmark procedures | Run broader matrix comparing 4B and 9B across executor classification, analyzer quality, extraction, generation, mixed-domain; document per-role results | [#133](https://github.com/deghosal-2026/agent-self-edit/issues/133) | Comparison matrix documented; role conclusions are evidence-based |
| 6 | Add optimizer-effectiveness metrics | Field-test runner, report docs | Track proposal validity rate, proposal novelty rate, repeat-proposal rate, tasks fixed per proposal, tasks broken per proposal | [#134](https://github.com/deghosal-2026/agent-self-edit/issues/134) | All metrics tracked in field-test reports |
| 7 | Tighten README and release claims | `README.md`, `docs/release/v0.1.0/release-notes.md`, `docs/field-test/v0.1.0/final-field-test-report.md` | Distinguish mechanical validation, classification-domain field validation, and broader design intent not yet fully validated | [#135](https://github.com/deghosal-2026/agent-self-edit/issues/135) | All claims match demonstrated evidence |

### M4 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Model roles | 3 roles configurable independently; each uses correct provider/model | Config + integration tests |
| Generation judge | Rubric-backed; benchmark-aware; reproducible | Scorer test suite |
| Benchmark manifests | All manifests valid; disjointness enforced | Manifest validation tests |
| Claims accuracy | All documented claims match demonstrated evidence | Manual review |
| Coverage | > 92% | `--cov-fail-under=92` |

### M4 Exit Gate

- [ ] Executor, analyzer, and judge model roles configurable
- [ ] Provider backends configurable per role (no hardcoded assumptions)
- [ ] Rubric-backed generation judge designed and implemented
- [ ] Benchmark-role manifests with disjointness validation
- [ ] Local-model comparison matrix documented
- [ ] Optimizer-effectiveness metrics tracked
- [ ] README and release claims tightened to match evidence
- [ ] Ruff clean, mypy strict clean, all tests pass, coverage > 92%
- [ ] **Design docs authored:** D3 (model-role-design), D4 (benchmark-manifest-design)

**Dependency:** M3. **Produces for M5+:** model role separation, benchmark manifests, generation judge.

---

## Milestone 5: Benchmark Expansion & Prompt Optimization (#136–#141)

**Objective:** Expand evaluation sets for statistical power, optimize prompt style for small local models (examples over rules), add canonical classification examples, add missing critical corpus types, strengthen task-set metadata schema, and make analyzer rejection-aware.

### M5 Design Documents

- **D5 — Rejection-aware analyzer design** (`docs/design/rejection-aware-analyzer-design.md`): structured feedback feeding, proposal memory keyed by normalized edit intent, novelty constraints, per-cluster proposal generation, cheap regression pre-screen.

### M5 Task Checklist

| # | Issue | Build (files) | Behavior + edge cases | Issue | Verify |
|---|-------|---------------|----------------------|-------|--------|
| 1 | Expand held-out and A/B evaluation sets | Field-test corpus, runner config | A/B promotion set: 50+ tasks per domain; high-confidence promotion: 100+ tasks; held-out: 25–50 tasks per domain; split datasets by purpose (analyzer input, A/B promotion, regression sentinel, held-out generalization) | [#136](https://github.com/deghosal-2026/agent-self-edit/issues/136) | Minimum task counts met; sets are disjoint; significance more stable |
| 2 | Optimize prompt style for small local models | Baseline prompt, analyzer prompt templates | Prefer short discriminators and examples over abstract rule blocks; reduce prompt length; avoid interacting exception rules; use example-grounded decision boundaries | [#137](https://github.com/deghosal-2026/agent-self-edit/issues/137) | Small models produce less over-broad edits; lower variance |
| 3 | Add canonical classification examples | Baseline prompt, classification prompt templates | Add 4–5 canonical examples from failure set: technical vs billing boundary, security vs urgent boundary, broken feature vs feature request, ambiguous → other, non-actionable praise → other | [#138](https://github.com/deghosal-2026/agent-self-edit/issues/138) | Examples present in prompt; classification accuracy improves |
| 4 | Add missing critical benchmark types | Field-test corpus | Regression sentinel corpus (15–25 fixed correct tasks); boundary-heavy classification corpus (urgent/security/technical ambiguity); structured extraction normalization corpus; rubric-backed generation corpus; larger mixed-domain corpus; real-trace gold corpus; promotion-seeking corpus | [#139](https://github.com/deghosal-2026/agent-self-edit/issues/139) | All corpus types exist, are operationalized, and enforced |
| 5 | Strengthen task-set metadata schema | `src/agent_self_edit/tasks.py`, all task-set YAML files | Move from loose per-task metadata to structured task-set manifest; add top-level fields: `domain`, `scorer`, `benchmark_role`; validate scorer compatibility, benchmark purpose, domain identity, normalization expectations, judge rubric config | [#140](https://github.com/deghosal-2026/agent-self-edit/issues/140) | Manifests validate at load time; evaluator misconfiguration prevented |
| 6 | Make analyzer rejection-aware | `src/agent_self_edit/analyzer.py`, `src/agent_self_edit/cli/run.py`, `src/agent_self_edit/cli/propose.py`, field-test runner | Feed structured rejection context into analyzer prompting: previous proposal impact (tasks fixed, tasks broken), gate decision reason, observed regression pattern; cluster failed traces by failure mode; proposal memory with novelty constraints | [#141](https://github.com/deghosal-2026/agent-self-edit/issues/141) | Analyzer avoids repeated same-family proposals; proposals improve over iterations |

### M5 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Task set sizes | A/B 50+/domain; held-out 25–50/domain | Count verification |
| Prompt style | Small models produce more minimal, focused edits | Field-test comparison |
| Classification accuracy | Improves with canonical examples | Field-test measurement |
| Corpus completeness | 7 corpus types operationalized and enforced | Corpus validation |
| Metadata schema | Manifests validate scorer compatibility, domain, role | Manifest validation tests |
| Rejection-aware analyzer | Proposals diversify over iterations; novelty constraints work | Analyzer test suite |
| Coverage | > 92% | `--cov-fail-under=92` |

### M5 Exit Gate

- [ ] Held-out and A/B sets expanded to meet minimum task counts
- [ ] Prompt style optimized for local models (examples over rules)
- [ ] Canonical classification examples added
- [ ] 7 critical corpus types operationalized
- [ ] Task-set metadata schema strengthened with domain/scorer/role fields
- [ ] Analyzer feeds on structured rejection context
- [ ] Ruff clean, mypy strict clean, all tests pass, coverage > 92%
- [ ] **Design docs authored:** D5 (rejection-aware-analyzer-design)

**Dependency:** M4. **Produces for M6+:** expanded corpora, optimized prompts, rejection-aware analyzer.