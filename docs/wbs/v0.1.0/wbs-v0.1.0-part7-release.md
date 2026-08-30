# WBS — AgentSelfEdit v0.1.0 Part 7: Release

> **Milestone covered:** M11 (Release)
> **PRD coverage:** [06-security-baseline](../../design/prd/06-security-baseline.md) (OpenSSF, OWASP)
> **CUJs covered:** all P0
> **Dependency:** M11 depends on M10 (field test validation)
> **Issue Range:** #69–#74

---

## Milestone 11: Release (#69–#74)

**Objective:** Package, document, publish, and make the repo public. OpenSSF Best Practices Passing badge earned.

### M11 Design Documents

- **D11 — Release plan** (`docs/release/v0.1.0/release-plan.md`): packaging checklist, documentation checklist, security checklist, PyPI release checklist, GitHub release checklist, announcement plan.

### M11 Task Checklist

#### Packaging

| # | Task | Build (files) | Behavior + edge cases | Feature | Design Ref | Verify | Status |
|---|------|---------------|----------------------|---------|------------|--------|--------|
| 1 | pyproject.toml | `pyproject.toml` | Package name `agent-self-edit`; version, description, author, license, Python version, dependencies, optional dependencies, entry points, build system | — | [D11](../../design/promotion-gate-design.md) | `python -m build` succeeds; `twine check` passes | [#69](https://github.com/deghosal-2026/agent-self-edit/issues/69) · ⬜ |
| 2 | PyPI publish | — | `twine upload dist/*`; PyPI project page with README, links to GitHub, docs, changelog | — | [D11](../../design/release-plan.md) | `pip install agent-self-edit` works from PyPI | [#69](https://github.com/deghosal-2026/agent-self-edit/issues/69) · ⬜ |
| 3 | Clean venv install test | `tests/test_release.py` | Clean virtualenv, `pip install agent-self-edit`, verify CLI commands work | — | [D11](../../design/release-plan.md) | install succeeds; CLI accessible | [#69](https://github.com/deghosal-2026/agent-self-edit/issues/69) · ⬜ |

#### Docker

| # | Task | Build (files) | Behavior + edge cases | Feature | Verify | Status |
|---|------|---------------|----------------------|---------|--------|--------|
| 4 | Docker image | `Dockerfile` (multi-stage), publish to GitHub Container Registry | Build stage: pip install; runtime stage: `python -m agent_self_edit` | F-14 | `docker build .` succeeds; `docker run` works | [#70](https://github.com/deghosal-2026/agent-self-edit/issues/70) · ⬜ |
| 5 | Docker compose | `docker-compose.yml` | agent-self-edit service with volume mounts for config, registry, traces | F-14 | `docker compose up` works | [#70](https://github.com/deghosal-2026/agent-self-edit/issues/70) · ⬜ |

#### Documentation

| # | Task | Deliverable | Acceptance |
|---|-------|-------------|------------|
| 6 | README.md | `README.md` | Complete: what, why, how it works, quickstart, CLI reference, architecture, configuration, field test results, status, license, links |
| 7 | CHANGELOG.md | `CHANGELOG.md` | Keep a Changelog format; v0.1.0 entry: all features, fixes, known issues |
| 8 | Release notes | `docs/release/v0.1.0/release-notes.md` | What's new, field test results, known issues, upgrade guide, credits |
| 9 | All reference docs | `docs/reference/*.md` | Config, trace schema, registry, guardrails, analyzer, diff, CLI — all complete |

#### Security

| # | Task | Build (files) | Behavior + edge cases | Feature | Verify | Status |
|---|------|---------------|----------------------|---------|--------|--------|
| 10 | Security audit | — | `bandit -r src/` — fix all findings; `trufflehog` — fix any secrets; `pip audit` or `safety check` — no vulnerable dependencies | — | all security tools pass clean | [#71](https://github.com/deghosal-2026/agent-self-edit/issues/71) · ⬜ |
| 11 | OpenSSF badge | Register at bestpractices.dev | Complete all passing criteria; embed badge in README | — | badge earned and embedded | [#71](https://github.com/deghosal-2026/agent-self-edit/issues/71) · ⬜ |
| 12 | Update SECURITY.md | `SECURITY.md` | Vulnerability reporting process, PGP key, response SLA | — | meaningful content | [#71](https://github.com/deghosal-2026/agent-self-edit/issues/71) · ⬜ |

#### GitHub

| # | Task | Behavior + edge cases | Feature | Verify | Status |
|---|-------|----------------------|---------|--------|--------|
| 13 | GitHub Release v0.1.0 | Tag from main; release notes; artifacts | — | release created with correct tag | [#72](https://github.com/deghosal-2026/agent-self-edit/issues/72) · ⬜ |
| 14 | Main branch protection | Require CI passing, require 1 review, require signed commits | — | protection rules active | [#72](https://github.com/deghosal-2026/agent-self-edit/issues/72) · ⬜ |
| 15 | Repo public + about | Make repo public; add description, website, topics | — | repo discoverable | [#72](https://github.com/deghosal-2026/agent-self-edit/issues/72) · ⬜ |

### M11 Success Metrics

| Metric | Target | Verification |
|--------|--------|-------------|
| PyPI publish | `pip install agent-self-edit` works | clean venv install |
| Docker publish | `docker run agent-self-edit --help` works | docker build + run |
| OpenSSF badge | Passing | badge.openssf.org |
| Security audit | 0 bandit findings, 0 vulnerable deps | bandit + safety check |
| GitHub release | tag v0.1.0, release notes, artifacts | github.com/releases |
| Coverage | > 92% | `--cov-fail-under=92` |

### M11 Out of Scope

- OpenSSF Silver badge (v0.5.0), SSO/RBAC (v0.7.0), OTel export (v0.8.0)

### M11 Exit Gate

- [ ] PyPI package published: `pip install agent-self-edit` works
- [ ] Docker image published: `docker run agent-self-edit --help` works
- [ ] README complete with quickstart, CLI reference, architecture
- [ ] CHANGELOG.md complete
- [ ] Release notes written
- [ ] Security audit clean (bandit, trufflehog, safety check)
- [ ] OpenSSF Best Practices Passing badge earned
- [ ] GitHub Release v0.1.0 created
- [ ] Main branch protected (CI required, 1 review, signed commits)
- [ ] Repo public and discoverable
- [ ] Ruff clean, mypy strict clean, all tests pass, coverage > 92%
- [ ] **Design docs authored:** D11 (release-plan)

**Dependency:** M10 (field test). **Produces:** v0.1.0 release on PyPI, Docker Hub, GitHub.