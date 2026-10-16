---
name: local-validation-python
description: "Use before running local validation in this Python repository: `ruff`, `mypy`, `pytest`, or installing dependencies in a worktree. Covers how CI picks which dependency set to install, projects whose dev dependencies CI cannot detect, and the per-worktree virtual environment rule."
---

# Local validation for Python

If `## Project specifics` in `AGENTS.md` names a repository-owned validation
skill, load it first; where it is narrower, it governs.

The commands to run before pushing are in the `## Tooling` section of `AGENTS.md`. This skill covers the detail behind them.

## Dependencies

As generated, `.github/workflows/test.yml` installs dependencies in this
order; check that repository-owned file for the current steps.

- **`uv.lock` exists:** `uv sync --locked`, which installs exactly the locked
  versions and fails if `uv.lock` is out of date with `pyproject.toml`; run
  `uv lock` and commit the result when it does. CI names a declared `dev` group
  and `dev` extra explicitly, so a `[tool.uv] default-groups` setting cannot
  leave them out.
- **Otherwise:** `requirements-dev.txt`, then `requirements.txt`.
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

## Worktrees

A worktree needs its own virtual environment: create it inside that worktree
and remove it with the worktree. Never copy `.venv/` or tool caches
(`.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`) into a verification copy.

## Sources

- When uv builds a project: uv's "Configuring projects" docs, checked
  2026-10-15.
- What `uv init` writes: uv's "Creating projects" docs, checked 2026-10-15.
