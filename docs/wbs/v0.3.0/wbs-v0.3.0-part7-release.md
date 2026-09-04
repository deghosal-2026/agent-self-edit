# WBS — AgentSelfEdit v0.3.0 Part 7: Release Readiness

> **Milestone covered:** M13 (Release Readiness)
> **Source:** v0.2.0 release process (#180–#185) with v0.3.0 updates — mirrors v0.2.0-M9 for 0.3.0
> **Dependency:** M13 depends on M12 (field-test evidence) and all M1–M12 — needs coverage 91%, field-test report, Docker evidence, security scan
> **Issue Range:** #309–#314 — [M13 milestone](https://github.com/deghosal-2026/agent-self-edit/milestone/35)

---

## Milestone 13: Release Readiness (#309–#314)

**Objective:** Package, document, publish, and release v0.3.0. Update PyPI, Docker image, documentation, coverage, security audit, and GitHub release — directly mirroring v0.2.0-M9 (#180–#185) but at 0.3.0 with 91% coverage gate and M1–M12 field-test evidence.

### M13 Task Checklist

#### PyPI

| # | Issue | Deliverable | Acceptance |
|---|-------|-------------|------------|
| 1 | PyPI packaging and release | Update version to 0.3.0 in `pyproject.toml`; verify openai optional dep (`agent-self-edit[llm]`), no dead numpy/scipy, no pytest-cov in addopts; `python -m build` + `twine check` + `twine upload`; test clean install | [#309](https://github.com/deghosal-2026/agent-self-edit/issues/309) — `python -m build` succeeds; `twine check` passes; published to https://pypi.org/project/agent-self-edit/0.3.0/ |

#### Docker

| # | Issue | Deliverable | Acceptance |
|---|-------|-------------|------------|
| 2 | Docker image build and publish | Verify no extra `COPY docs/ field-test/` and `.dockerignore` excludes dev artifacts (as fixed per #167/#168); ensure `Dockerfile` installs via `agent-self-edit[llm]`; verify size; `docker build` passes in CI; publish to GHCR/Docker Hub on tag `v0.3.0` | [#310](https://github.com/deghosal-2026/agent-self-edit/issues/310) — Image builds as `agent-self-edit:0.3.0`; CI Docker build passes; GHCR push on release |

#### Documentation

| # | Issue | Deliverable | Acceptance |
|---|-------|-------------|------------|
| 3 | Documentation and release notes | Update README with v0.3.0 features and field test results (link `docs/field-test/v0.3.0/FIELD_TEST_REPORT.md`); write v0.3.0 release notes; update CHANGELOG.md; tighten claims per #135; document known limitations | [#311](https://github.com/deghosal-2026/agent-self-edit/issues/311) — README/CHANGELOG/release notes updated; claims tightened to evidence |

#### Coverage

| # | Issue | Deliverable | Acceptance |
|---|-------|-------------|------------|
| 4 | Coverage target: 91%+ | Measure baseline; close gaps in CLI error paths, adapters, gate/analyzer/A/B edge cases, config validation, registry ops + new M1–M12 paths; enforce `pytest --cov --cov-fail-under=91` in CI; re-measure and report | [#312](https://github.com/deghosal-2026/agent-self-edit/issues/312) — `pytest --cov=agent_self_edit --cov-fail-under=91` passes; CI enforces 91% |

#### Security

| # | Issue | Deliverable | Acceptance |
|---|-------|-------------|------------|
| 5 | Security audit and OpenSSF badge | `bandit -r src/` (document B608 FPs), gitleaks/trufflehog 0 findings, `pip audit`, OpenSSF badge current, document security-relevant changes (file lock, WAL timeout) | [#313](https://github.com/deghosal-2026/agent-self-edit/issues/313) — Bandit clean (documented FPs); gitleaks 0; OpenSSF badge current |

#### GitHub Release

| # | Issue | Deliverable | Acceptance |
|---|-------|-------------|------------|
| 6 | GitHub release and repo publication | Create `v0.3.0` git tag; write GitHub release notes (CHANGELOG + FIELD_TEST_REPORT summary); verify all CI checks pass (ruff, mypy, pytest, coverage 91%, bandit, Docker); close all v0.3.0 milestones (M1–M13, 23–35) | [#314](https://github.com/deghosal-2026/agent-self-edit/issues/314) — Tag `v0.3.0` at https://github.com/deghosal-2026/agent-self-edit/releases/tag/v0.3.0; CI green; milestones closed |

### M13 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| PyPI | 0.3.0 published, clean install works | `pip install` test |
| Docker | Image builds, CI passes, size reasonable | `docker build` + CI |
| Docs | README/CHANGELOG/release notes updated, claims tightened | Manual review |
| Coverage | 91% enforced in CI | `pytest --cov-fail-under=91` |
| Security | Bandit clean, OpenSSF current | Scan reports |
| GitHub release | Tag + release, milestones closed | Release URL + milestone state |
| Exit gates | M1–M13 each: ruff 0, mypy 0, tests 0 failures, coverage 91%, docs | Per-milestone checklist |

### M13 Exit Gate

- [x] v0.3.0 released on PyPI (`pip install agent-self-edit==0.3.0`) — #309
- [x] Docker image built and published (`agent-self-edit:0.3.0`, GHCR on tag) — #310
- [x] README, release notes, CHANGELOG updated; claims tightened — #311
- [x] Coverage ≥ 91% enforced in CI — #312
- [x] Security audit clean; OpenSSF badge current; gitleaks 0 — #313
- [x] GitHub release `v0.3.0` created; milestones M1–M13 closed — #314
- [x] Ruff clean: `ruff check .` → 0 errors
- [x] Mypy strict clean: `mypy --strict src/agent_self_edit` → 0 errors
- [x] All tests pass: `python3 -m pytest --ignore=tests/test_docker.py -x -q` → 809 passed
- [x] Coverage > 91%: `pytest --cov=agent_self_edit --cov-fail-under=91` → 94.75%
- [x] Documentation updated for the milestone's scope
- [x] WBS index updated with M13 status

**Dependency:** M12 (field-test evidence) + all M1–M12. **Produces:** v0.3.0 release.

---

## v0.2.0 → v0.3.0 Release Mapping

| v0.2.0 (M9 #180–#185) | v0.3.0 (M13 #309–#314) | Delta |
|---|---|---|
| #180 PyPI 0.2.0 | #309 PyPI 0.3.0 | Version bump 0.3.0, same optional dep fix |
| #181 Docker 0.2.0 | #310 Docker 0.3.0 | Same Dockerfile/.dockerignore, verify `[llm]` install |
| #182 Docs 0.2.0 | #311 Docs 0.3.0 | Updated for M1–M12 + `FIELD_TEST_REPORT.md` |
| #183 Coverage 92% (accepted 81%) | #312 Coverage 91% | Gate 91% per updated WBS exit gates |
| #184 Security + OpenSSF | #313 Security + OpenSSF | Same scans, document M1–M12 changes |
| #185 GitHub release 0.2.0 | #314 GitHub release 0.3.0 | Tag `v0.3.0`, close 13 milestones (23–35) |

## Release Checklist (M13)

```
M11 (91% measured) ──► M12 (corpora + field-test) ──► M13 (release)
                              │                              │
                              ├──► 306 corpus gen            ├──► 309 PyPI
                              ├──► 307 field test exec       ├──► 310 Docker
                              ├──► 308 plan docs             ├──► 311 docs
                              ├──► 302–305 Docker/plan       ├──► 312 coverage 91%
                                                             ├──► 313 security
                                                             └──► 314 GitHub release
```
