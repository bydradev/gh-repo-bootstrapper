---
name: local-validation-python
description: "Use before running local validation in this Python repository: `ruff`, `mypy`, `pytest`, or installing dependencies in a worktree. Covers the dependency manifest CI requires, how CI picks which dependency set to install, projects whose dev dependencies CI cannot detect, when to add the Dependabot `pip` entry, and the per-worktree virtual environment rule."
---

# Local validation for Python

If `## Project specifics` in `AGENTS.md` names a repository-owned validation
skill, load it first; where it is narrower, it governs.

The commands to run before pushing are in the `## Tooling` section of `AGENTS.md`. This skill covers the detail behind them.

## Dependencies

As generated, `.github/workflows/test.yml` fails with a clear error unless the
repository has a dependency manifest: a `pyproject.toml` or a
`requirements*.txt` anywhere in it, or a `uv.lock`. Those are the files its pip
cache hashes, and `actions/setup-python` stops with `No file ... matched`
without one; a `setup.py` alone does not count. An empty `requirements-dev.txt`
is enough for a project with no dependencies. The install step below reads only
the root `pyproject.toml`, `requirements-dev.txt` and `requirements.txt`, so a
manifest only in a subdirectory, or in a root file with another name such as
`requirements-test.txt`, passes this check but installs nothing: keep the
project's dependencies in one of those three root files.

It then installs dependencies in this order; check that repository-owned file
for the current steps.

- **`uv.lock` exists:** `uv sync --locked`, which installs exactly the locked
  versions and fails if `uv.lock` is out of date with `pyproject.toml`; run
  `uv lock` and commit the result when it does. CI names a declared `dev` group
  and `dev` extra explicitly, so a `[tool.uv] default-groups` setting cannot
  leave them out.
- **Otherwise:** `requirements-dev.txt` if present, otherwise
  `requirements.txt`.
- **Otherwise, `pyproject.toml`:** like uv, CI builds the project only when it
  declares a `[build-system]` (or has a `setup.py`, or a `setup.cfg` with
  `[metadata]` or `[options]`), and `[tool.uv] package` overrides that. A
  package installs as `-e .`, or `-e ".[dev]"` when a PEP 621
  `[project.optional-dependencies] dev = [...]` extra is declared, adding
  `--group dev` when a PEP 735 `[dependency-groups] dev` group is declared
  (what `uv add --dev` writes). A project that is not built, as
  `uv init --no-package` writes (and `uv init` did before uv 0.12), gets its
  `[project]` dependencies, the dev extra's and the dev group, after a
  `requires-python` check. A package, such as a `src/` layout, therefore needs
  a `[build-system]` table.

CI does not detect dev dependencies declared through tool-specific metadata,
such as Poetry's `[tool.poetry.group.dev.dependencies]`; add a
`requirements-dev.txt` to have CI install that set.

## Dependabot

As generated, `.github/dependabot.yml` covers GitHub Actions only: a new
repository has no manifest, and a `pip` entry would fail on every run until one
exists. Once the manifest is committed, add this entry under `updates:` if the
file has none. It holds the core tools at their current major, since a major
bump needs deliberate adoption, and groups their updates. Use
`package-ecosystem: uv` rather than `pip` once `uv.lock` is committed, so
Dependabot updates the lockfile too.

```yaml
  - package-ecosystem: pip
    directory: "/"
    schedule:
      interval: weekly
    cooldown:
      default-days: 7
    open-pull-requests-limit: 10
    ignore:
      - dependency-name: ruff
        update-types: ["version-update:semver-major"]
      - dependency-name: mypy
        update-types: ["version-update:semver-major"]
      - dependency-name: pytest
        update-types: ["version-update:semver-major"]
    groups:
      dev-dependencies:
        patterns:
          - ruff
          - mypy
          - pytest
          - pytest-*
```

## Worktrees

A worktree needs its own virtual environment: create it inside that worktree
and remove it with the worktree. Never copy `.venv/` or tool caches
(`.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`) into a verification copy.

## Sources

- When uv builds a project: uv's "Configuring projects" docs, checked
  2026-10-15.
- What `uv init` writes: uv's "Creating projects" docs, checked 2026-10-15.
- Which files the pip cache hashes, and that it stops when none exists:
  `actions/setup-python` v7.0.0, `src/cache-distributions/pip-cache.ts`,
  `cache-distributor.ts` and `constants.ts`, checked 2026-10-21.
- Why a `pip` entry fails without a manifest: GitHub's Dependabot options
  reference (`package-ecosystem`) and dependabot-core's
  `python/lib/dependabot/python/file_fetcher.rb`, checked 2026-10-21.
