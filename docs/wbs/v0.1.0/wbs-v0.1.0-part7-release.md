# WBS — AgentSelfEdit v0.1.0 Part 7: Release

> Part of the v0.1.0 release. See [index](wbs-v0.1.0-index.md) for milestone overview.
>
> **Milestone:** M11 (Release)
> **Dependency:** M11 depends on M10 (field test validation)
> **Issue Range:** #69–#74

## M11 — Release (#69–#74)

**Goal:** Package, document, publish, and make the repo public.

### Design

| Task | Description | Deliverable |
|---|---|---|
| D11.1 | Release plan | `docs/release/v0.1.0/release-plan.md` — packaging checklist, documentation checklist, security checklist, PyPI release checklist, GitHub release checklist, announcement plan |

### Build — Packaging

| Task | Description | Deliverable |
|---|---|---|
| M11.1 | pyproject.toml | Complete pyproject.toml with: package name `agent-self-edit`, version, description, author, license, Python version, dependencies, optional dependencies, entry points, build system. |
| M11.2 | Build verification | `python -m build` succeeds. `twine check dist/*` passes. |
| M11.3 | Clean venv install test | Create clean virtualenv, `pip install agent-self-edit`, verify CLI commands work. |
| M11.4 | PyPI publish | `twine upload dist/*` — publish to PyPI. Package: `agent-self-edit`. |
| M11.5 | PyPI metadata | PyPI project page: README rendered as description, links to GitHub, docs, changelog. |

### Build — Docker

| Task | Description | Deliverable |
|---|---|---|
| M11.6 | Docker image | Multi-stage Dockerfile: build stage (pip install), runtime stage (python -m). Docker image published to GitHub Container Registry. |
| M11.7 | Docker smoke test | `docker build . && docker run agent-self-edit --help` — verify image works. |
| M11.8 | Docker compose | `docker-compose.yml` — agent-self-edit service with volume mounts. |

### Build — Documentation

| Task | Description | Deliverable |
|---|---|---|
| M11.9 | README.md | Complete README: what, why, how it works, quickstart, CLI reference, architecture, configuration, field test results, status, license, links. |
| M11.10 | Documentation index | `docs/README.md` — update with all documentation links. |
| M11.11 | CHANGELOG.md | Keep a Changelog format. v0.1.0 entry: all features, fixes, known issues. |
| M11.12 | Release notes | `docs/release/v0.1.0/release-notes.md` — what's new, field test results, known issues, upgrade guide, credits. |

### Build — Security

| Task | Description | Deliverable |
|---|---|---|
| M11.13 | Security audit | Run `bandit -r src/`. Fix all findings. Run `trufflehog` on repo. Fix any secrets. |
| M11.14 | Dependency audit | `pip audit` or `safety check` — verify no vulnerable dependencies. |
| M11.15 | OpenSSF badge | Register at bestpractices.dev. Complete all passing criteria. Embed badge in README. |
| M11.16 | Security policy | Update SECURITY.md with vulnerability reporting process. |

### Build — GitHub

| Task | Description | Deliverable |
|---|---|---|
| M11.17 | GitHub release | Create GitHub Release v0.1.0. Tag from main. Include release notes, artifacts. |
| M11.18 | Main branch protection | Require CI passing, require 1 review, require signed commits. |
| M11.19 | Update about | Repo description, website (docs/README.md), topics. |

### Tests

| Task | Description | Files |
|---|---|---|
| T11.1 | Test package install | `tests/test_release.py` — `pip install agent-self-edit` works, `pip install -e .` works, all CLI commands accessible |
| T11.2 | Test Docker build | `tests/test_docker.py` — image builds, container runs, CLI commands work in container |
| T11.3 | Test security audit | `manual` — bandit passes, trufflehog passes, safety check passes |
| T11.4 | Test full test suite | `pytest --cov=agent_self_edit --cov-fail-under=92` — all tests pass, coverage meets target |

### Documentation

| Task | Description | Deliverable |
|---|---|---|
| M11.DOC1 | Release summary | Update `docs/release/v0.1.0/release-notes.md` with final release notes |
| M11.DOC2 | Update WBS index | Update `docs/wbs/v0.1.0/wbs-v0.1.0-index.md` with M11 status, issue links, exit gate results |

### M11 Exit Gate

- [ ] Release plan reviewed and committed
- [ ] PyPI package published: `pip install agent-self-edit` works
- [ ] Docker image published: `docker run agent-self-edit` works
- [ ] README complete with quickstart, CLI reference, architecture
- [ ] CHANGELOG.md complete
- [ ] Release notes written
- [ ] Security audit clean (bandit, trufflehog, safety check)
- [ ] OpenSSF Best Practices Passing badge earned
- [ ] GitHub Release v0.1.0 created
- [ ] Main branch protected (CI required, 1 review, signed commits)
- [ ] Repo public and discoverable
- [ ] Ruff clean, mypy strict clean
- [ ] All tests pass: `pytest` → 0 failures
- [ ] Coverage > 92%: `pytest --cov=agent_self_edit --cov-fail-under=92`