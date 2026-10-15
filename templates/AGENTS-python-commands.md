
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
later) for a `[dependency-groups]` dev group. A project with no `[project]`
table or `[build-system]` isn't a package: install only `pip install --group dev`.
