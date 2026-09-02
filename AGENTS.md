# AGENTS.md — AgentSelfEdit

## Working Rules

1. **Check first** — Before moving, renaming, or deleting any file or directory, verify nothing is actively using it. Never move a results directory while a run is in progress.

2. **Read before write** — Before writing a command to README or docs, run it and inspect the output. Never document a command you haven't tested. Never add a path to docs without confirming the file exists at that path.

3. **Say what you don't know** — Instead of fabricating data, guessing, or assuming, say "I don't know, let me check." Never generate fake model outputs and present them as real traces.

4. **Stop and think** — When asked to fix something, understand the root cause before touching code. Read the actual error, trace the actual execution path, identify the actual problem. Don't patch symptoms.

5. **One thing at a time** — Don't batch unrelated changes that can interfere with each other. Make one change, verify it, then make the next.

## Project Context

- **Branch:** `feat-v0.2.0`
- **Package:** `agent-self-edit` (Python, src/ layout)
- **Test command:** `python3 -m pytest --ignore=tests/test_docker.py -x -q`
- **Lint:** `ruff check .`
- **Type check:** `mypy --strict src/agent_self_edit/`
- **Coverage gate:** 92%
- **Corpus location:** `field-test/corpus/synthetic/` (synthetic) and `field-test/corpus/real-traces/` (real)
- **Results location:** `field-test/v0.2.0/results/`
- **Field test runner:** `field-test/scripts/run_improvement_loop.py`

## Key Conventions

- Never commit unless explicitly asked
- Never move/rename result directories while runs are in progress
- Real traces in `usable/` have real outputs but vague expected values — not suitable for A/B scoring
- Real traces in `telemetry/` have placeholder outputs — analyzer produces 0 proposals
- Gold corpus in `labeled/` is for analyzer quality evaluation, not for the improvement loop
- Only synthetic classification traces work end-to-end with the improvement loop