
## Tooling

Run all checks before pushing:

```sh
ruff format .   # format (CI runs ruff format --check .)
ruff check .    # lint (matches CI)
mypy .          # type check
pytest          # tests
```

Install dependencies first, the way CI does: `uv sync` when `uv.lock` exists
(with `--extra dev` if the project declares a `dev` extra); otherwise
`pip install -r requirements-dev.txt`, `pip install -r requirements.txt`, or
`pip install -e ".[dev]"` as appropriate, adding `--group dev` (pip 25.1 or
later) for a `[dependency-groups]` dev group.
