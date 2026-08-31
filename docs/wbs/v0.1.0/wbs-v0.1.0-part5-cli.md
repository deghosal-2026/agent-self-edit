# WBS — AgentSelfEdit v0.1.0 Part 5: CLI

> **Milestone covered:** M9 (CLI)
> **PRD coverage:** [F-09](../../design/prd/05-features.md) (CLI), [F-12](../../design/prd/05-features.md) (rollback)
> **CUJs covered:** CUJ 5 (first-time setup — init), CUJ 4 (rollback), CUJ 1 (status/diff/propose)
> **Dependency:** M9 depends on M7 (analyzer) + M8 (diff) + M5 (registry) + M4 (gate) + M3 (A/B test) + M2 (trace) + M1 (config)
> **Issue Range:** #56–#63 (+ #89–#91 M9 design gaps)
> **Note:** D9 design doc (`docs/design/cli-surface-design.md`) does not exist yet — must be authored before building (#89).

---

## Milestone 9: CLI (#56–#63)

**Objective:** The user-facing interface for v0.1.0. All operations accessible via CLI. Shortest path from `pip install` to working loop is < 5 minutes.

### M9 Design Documents

- **D9 — CLI surface design** (`docs/design/cli-surface-design.md`): all commands, flags, output formats, exit codes, error handling, help text, examples, shell completion.
- **D13 — Design decisions:** DD-16 (Click framework), DD-17 (exit codes: 0 success, 1 error, 2 validation failure).

### M9 Task Checklist

| # | Task | Build (files) | Behavior + edge cases | Feature | Design Ref | Verify | Status |
|---|------|---------------|----------------------|---------|------------|--------|--------|
| 1 | `init` command | `src/agent_self_edit/cli/init.py` | `agent-self-edit init --prompt <path> --tasks <path>`; scaffolds config, creates registry, loads task set, creates initial prompt version; missing path → error message; existing config → overwrite prompt | F-09 | [D9](../../design/cli-surface-design.md) | init with/without existing config; missing paths | [#56](https://github.com/deghosal-2026/agent-self-edit/issues/56) · ⬜ |
| 2 | `run` command | `src/agent_self_edit/cli/run.py` | `agent-self-edit run --batch-size 50 --once --dry-run`; starts loop; graceful shutdown on SIGINT/SIGTERM; `--dry-run` (analyze only, no A/B test); `--once` (one cycle and exit) | F-09 | [D9](../../design/cli-surface-design.md) | run + once + dry-run; shutdown; no traces | [#57](https://github.com/deghosal-2026/agent-self-edit/issues/57) · ⬜ |
| 3 | `status` command | `src/agent_self_edit/cli/status.py` | `agent-self-edit status --json`; shows: prompt version, last edit, guardrail pass rate, improvement trend, total edits, total cost; `--json` for machine-readable; empty state → "no data" | F-09 | [D9](../../design/cli-surface-design.md) | status with/without data; JSON output | [#58](https://github.com/deghosal-2026/agent-self-edit/issues/58) · ⬜ |
| 4 | `diff` command | `src/agent_self_edit/cli/diff.py` | `agent-self-edit diff <v1> <v2> --inline --format markdown --color`; shows diff between versions; invalid versions → error; identical versions → "no changes" | F-08, F-09 | [D9](../../design/cli-surface-design.md) | valid/invalid versions; all format modes | [#59](https://github.com/deghosal-2026/agent-self-edit/issues/59) · ⬜ |
| 5 | `rollback` command | `src/agent_self_edit/cli/rollback.py` | `agent-self-edit rollback <version> --reason <text>`; creates new version; logs reason; invalid version → error; rollback to current → creates identical copy | F-12 | [D9](../../design/cli-surface-design.md) | valid/invalid version; rollback reason | [#60](https://github.com/deghosal-2026/agent-self-edit/issues/60) · ⬜ |
| 6 | `guardrails` + `lineage` commands | `src/agent_self_edit/cli/guardrails.py`, `src/agent_self_edit/cli/lineage.py` | `guardrails --last 10 --edit <id> --json`; `lineage --from <version> --format table|json`; empty history → "no data" | F-09 | [D9](../../design/cli-surface-design.md) | guardrails with/without data; lineage all formats | [#61](https://github.com/deghosal-2026/agent-self-edit/issues/61) · ⬜ |
| 7 | `propose` + `ingest` + `validate` commands | `src/agent_self_edit/cli/propose.py`, `src/agent_self_edit/cli/ingest.py`, `src/agent_self_edit/cli/validate.py` | `propose --dry-run`; `ingest <file>`; `validate` (config + task set + registry integrity); missing config → error on validate | F-09 | [D9](../../design/cli-surface-design.md) | propose dry-run; ingest valid/invalid; validate all pass/fail | [#62](https://github.com/deghosal-2026/agent-self-edit/issues/62) · ⬜ |
| 8 | Error handling + shell completion | Update `src/agent_self_edit/cli.py` | All commands: non-zero exit codes on failure; meaningful error messages; help text for every command; `--install-completion` for bash/zsh/fish | F-09 | [D9](../../design/cli-surface-design.md) | exit codes; help text; completion installs | [#63](https://github.com/deghosal-2026/agent-self-edit/issues/63) · ⬜ |

### M9 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| Command coverage | all 10 commands work (init, run, status, diff, rollback, guardrails, lineage, propose, ingest, validate) | CLI test suite |
| Error handling | all commands produce non-zero exit code on failure | error test suite |
| Help text | every command has non-empty help text | help test suite |
| Setup time | `pip install` → `init` → first run < 5 minutes | manual timing test |
| Coverage | > 92% | `--cov-fail-under=92` |

### M9 Out of Scope

- Web dashboard (v0.2.0), REST API (v0.2.0), shadow mode (v0.2.0), drift detection (v0.2.0)

### M9 Exit Gate

- [ ] All 10 commands work (init, run, status, diff, rollback, guardrails, lineage, propose, ingest, validate)
- [ ] `init` creates valid config and registry
- [ ] `run` starts the loop with graceful shutdown
- [ ] `status` shows correct state including JSON output
- [ ] `diff` shows readable output in all formats
- [ ] `rollback` works with reason logging
- [ ] All commands produce non-zero exit codes on failure
- [ ] Error messages are meaningful
- [ ] Ruff clean, mypy strict clean, all tests pass, coverage > 92%
- [ ] **Design docs authored:** D9 (cli-surface-design), D13 (DD-16/17)

**Dependency:** M7 (analyzer) + M8 (diff) + M5 (registry) + M4 (gate) + M3 (A/B test) + M2 (trace) + M1 (config). **Produces for M10+:** complete CLI with all commands.

### M9 Design Gaps Found (PRD vs WBS Audit, 2026-08-30)

> D9 design doc (`docs/design/cli-surface-design.md`) does not exist and is referenced by all 8 tickets. Three additional gaps found. **Author D9 first, then build.**

| # | Gap | PRD requirement | Current state | Ticket | Fix |
|---|-----|----------------|---------------|--------|-----|
| G-1 | D9 design doc missing | All 8 tickets reference D9 | File does not exist | [#89](https://github.com/deghosal-2026/agent-self-edit/issues/89) · ⬜ | Author D9 with all commands, flags, wiring, loop, errors |
| G-2 | `run` loop algorithm | PRD says "starts the loop" | No concrete algorithm | [#89](https://github.com/deghosal-2026/agent-self-edit/issues/89) · ⬜ | Specify poll→batch→analyze→test→gate→log→repeat; `--once`/`--dry-run` semantics |
| G-3 | `status --json` schema | PRD: "prompt version, last edit, guardrail pass rate, improvement trend, total edits, total cost" | No JSON shape pinned | [#90](https://github.com/deghosal-2026/agent-self-edit/issues/90) · ⬜ | Add JSON schema to D9; empty state: "no data" |
| G-4 | `validate` command spec | Not in PRD roadmap (additive) | WBS #62 adds it without spec | [#91](https://github.com/deghosal-2026/agent-self-edit/issues/91) · ⬜ | Add 3-check spec (config, task set, registry) to D9 |