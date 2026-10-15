
## Tooling

Run all checks before pushing:

```sh
ruff format .   # format (CI runs ruff format --check .)
ruff check .    # lint (matches CI)
mypy .          # type check
pytest          # tests
```

Install dependencies first, the way CI does: `uv sync` when `uv.lock` exists
(adding `--group dev` and `--extra dev` for whichever the project declares);
otherwise
`pip install -r requirements-dev.txt`, `pip install -r requirements.txt`, or
`pip install -e ".[dev]"` as appropriate, adding `--group dev` (pip 25.1 or
later) for a `[dependency-groups]` dev group. As with uv (uv's "Configuring
projects" docs, checked 2026-10-15), a project with no `[build-system]` (and no
`setup.py`, and no `setup.cfg` with `[metadata]` or `[options]`) isn't built
unless it sets `[tool.uv] package = true`, and `package = false` skips the build
even with them: install an unbuilt project's `[project]` dependencies, the dev
extra's and the dev group without `-e .`. A package needs a `[build-system]`
table (or `[tool.uv] package = true`), or CI will not install it either.
