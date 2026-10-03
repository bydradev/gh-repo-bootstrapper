---
name: local-validation-python
description: "Use before running local validation in this Python repository: `ruff`, `mypy`, `pytest`, or installing dependencies in a worktree. Covers how CI picks which dependency set to install, projects whose dev dependencies CI cannot detect, and the per-worktree virtual environment rule."
---

# Local validation for Python

The commands to run before pushing are in the `## Tooling` section of `AGENTS.md`. This skill covers the detail behind them.

## Dependencies

CI picks the same order automatically. For the `pyproject.toml` case it
detects a PEP 621 `[project.optional-dependencies] dev = [...]` extra and
installs `.[dev]` only when that extra is actually declared, falling back to
a plain `pip install -e .` otherwise. Projects that declare dev dependencies
through tool-specific metadata instead (e.g. Poetry's
`[tool.poetry.group.dev.dependencies]`) aren't detected by this check — add a
`requirements-dev.txt` to have CI install that dependency set explicitly.

## Worktrees

A worktree needs its own virtual environment: create it inside that worktree
and remove it with the worktree. Never copy `.venv/` or tool caches
(`.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`) into a verification copy.
