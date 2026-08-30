# WBS — AgentSelfEdit v0.1.0 Part 5: CLI

> Part of the v0.1.0 release. See [index](wbs-v0.1.0-index.md) for milestone overview.
>
> **Milestone:** M9 (CLI)
> **Dependency:** M9 depends on M7 (analyzer) and M8 (diff)
> **Issue Range:** #55–#62

## M9 — CLI (#55–#62)

**Goal:** The user-facing interface for v0.1.0. All operations accessible via CLI.

### Design

| Task | Description | Deliverable |
|---|---|---|
| D9 | Design CLI | `docs/design/cli-surface-design.md` — all commands, flags, output formats, exit codes, error handling, help text, examples |

### Build

| Task | Description | Deliverable |
|---|---|---|
| M9.1 | `init` command | `agent-self-edit init --prompt <path> --tasks <path> --model <name>` — scaffold config file, create registry directory, load held-out task set, create initial prompt version |
| M9.2 | `init` prompt template | Generate a default system prompt template. User fills in the blanks. Include frozen section annotations. |
| M9.3 | `run` command | `agent-self-edit run` — start the self-improvement loop. Watch for traces, batch, analyze, A/B test, promote/reject. Options: `--batch-size <N>`, `--dry-run` (analyze only, no promote), `--once` (run one cycle and exit). |
| M9.4 | `run` loop daemon | Continuous loop: batch → analyze → A/B test → gate → promote → sleep → repeat. Graceful shutdown on SIGINT/SIGTERM. |
| M9.5 | `status` command | `agent-self-edit status` — show current state: prompt version (N), last edit (promoted/rejected/near-miss), guardrail pass rate (X%), improvement trend (+X%), total edits, total cost. `--json` for machine-readable. |
| M9.6 | `diff` command | `agent-self-edit diff <v1> <v2>` — show diff between two prompt versions. Options: `--inline`, `--side-by-side` (default), `--format markdown`, `--color` (auto/always/never). |
| M9.7 | `rollback` command | `agent-self-edit rollback <version> --reason <text>` — roll back to a previous prompt version. Creates new version. Logs reason. |
| M9.8 | `guardrails` command | `agent-self-edit guardrails` — show guardrail history. Options: `--last <N>`, `--edit <id>`, `--json`. |
| M9.9 | `lineage` command | `agent-self-edit lineage` — show full prompt version history. Options: `--from <version>`, `--format table|json`. |
| M9.10 | `propose` command | `agent-self-edit propose` — manually trigger analysis on current traces. Options: `--dry-run` (propose only, no A/B test). |
| M9.11 | `ingest` command | `agent-self-edit ingest <file>` — ingest a trace file. Options: `--format json`. |
| M9.12 | `validate` command | `agent-self-edit validate` — validate config, task set, and registry integrity. Returns pass/fail per check. |
| M9.13 | Error handling | All commands produce non-zero exit codes on failure. Meaningful error messages. Help text for every command. |
| M9.14 | Shell completion | `agent-self-edit --install-completion` — install shell completion for bash, zsh, fish. |

### Tests

| Task | Description | Files |
|---|---|---|
| T9.1 | Test `init` command | `tests/test_cli.py` — init creates config, init creates registry, init with missing path, init with invalid config |
| T9.2 | Test `run` command | `tests/test_cli.py` — run starts loop, run with dry-run, run with once, run with batch-size, run handles shutdown |
| T9.3 | Test `status` command | `tests/test_cli.py` — status shows correct state, status with --json, status with empty state |
| T9.4 | Test `diff` command | `tests/test_cli.py` — diff between versions, diff with inline, diff with side-by-side, diff with markdown, diff with invalid versions |
| T9.5 | Test `rollback` command | `tests/test_cli.py` — rollback to valid version, rollback with reason, rollback to invalid version, rollback creates new version |
| T9.6 | Test `guardrails` command | `tests/test_cli.py` — guardrails history, guardrails by edit, guardrails with --json |
| T9.7 | Test `lineage` command | `tests/test_cli.py` — lineage table, lineage json, lineage from version |
| T9.8 | Test `propose` command | `tests/test_cli.py` — propose with traces, propose dry-run, propose with no traces |
| T9.9 | Test `ingest` command | `tests/test_cli.py` — ingest valid trace, ingest invalid trace, ingest from file |
| T9.10 | Test error handling | `tests/test_cli.py` — all commands handle missing config, missing registry, invalid args, non-zero exit codes |
| T9.11 | Test CLI help text | `tests/test_cli.py` — all commands have help text, help text is non-empty, help text includes examples |

### Documentation

| Task | Description | Deliverable |
|---|---|---|
| M9.DOC1 | CLI reference | Create `docs/reference/cli.md` — all commands, flags, exit codes, examples, shell completion |
| M9.DOC2 | Quickstart guide | Create `docs/explanation/quickstart.md` — step-by-step: install, init, integrate agent, run, review results |
| M9.DOC3 | Update WBS index | Update `docs/wbs/v0.1.0/wbs-v0.1.0-index.md` with M9 status, issue links, exit gate results |

### M9 Exit Gate

- [ ] Design docs reviewed and committed
- [ ] All 8 core commands work (init, run, status, diff, rollback, guardrails, lineage, propose, ingest, validate)
- [ ] `init` creates valid config and registry
- [ ] `run` starts the loop with graceful shutdown
- [ ] `status` shows correct state including JSON output
- [ ] `diff` shows readable output in all formats
- [ ] `rollback` works with reason logging
- [ ] All commands produce non-zero exit codes on failure
- [ ] Error messages are meaningful
- [ ] Shortest path from `pip install` to working loop is < 5 minutes
- [ ] Ruff clean, mypy strict clean
- [ ] All tests pass: `pytest` → 0 failures
- [ ] Coverage > 92%: `pytest --cov=agent_self_edit --cov-fail-under=92`