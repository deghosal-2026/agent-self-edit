# Contributing to AgentSelfEdit

## Reporting Bugs
Open an issue with the bug report template. Include:
- Full command and config
- Python version and OS
- Full error output (no screenshots — paste text)

## Feature Requests
Open an issue with the feature request template. Include a clear description of the problem and your proposed solution.

## Pull Requests
1. Fork the repo and create a branch from `main`
2. Run `ruff check .` and `mypy --strict src/` — both must pass
3. Write tests for any new functionality
4. Ensure coverage stays above 92%
5. Open a PR with a clear description

## Coding Standards
- Python 3.10+, type-annotated, mypy strict clean
- Line length: 100
- No paid LLM calls in CI — mock providers for all tests
- Deterministic guardrails — no LLM-judged safety checks