---
name: local-validation-python
description: "Use before running local validation in this Python repository: `ruff`, `mypy`, `pytest`, or installing dependencies in a worktree. Covers how CI picks which dependency set to install, projects whose dev dependencies CI cannot detect, and the per-worktree virtual environment rule."
---

# Local validation for Python

The commands to run before pushing are in the `## Tooling` section of `AGENTS.md`. This skill covers the detail behind them.

## Dependencies

CI picks the same order automatically. When `uv.lock` exists it runs
`uv sync --locked`, which installs exactly the locked versions and fails if
`uv.lock` is out of date with `pyproject.toml`; run `uv lock` and commit the
result when it does. CI names a declared `dev` group and `dev` extra
explicitly, so a `[tool.uv] default-groups` setting cannot leave them out. Without
`uv.lock`, a `requirements-dev.txt` or `requirements.txt` comes first. For the
`pyproject.toml` case CI installs `.[dev]` when a PEP 621
`[project.optional-dependencies] dev = [...]` extra is declared, and adds
`--group dev` when a PEP 735 `[dependency-groups] dev` group is declared (what
`uv add --dev` writes), falling back to a plain `pip install -e .`. Projects
that declare dev dependencies through tool-specific metadata instead (e.g.
Poetry's `[tool.poetry.group.dev.dependencies]`) aren't detected — add a
`requirements-dev.txt` to have CI install that dependency set explicitly.

## Worktrees

A worktree needs its own virtual environment: create it inside that worktree
and remove it with the worktree. Never copy `.venv/` or tool caches
(`.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`) into a verification copy.
