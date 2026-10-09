
## Tooling

Run all checks before pushing:

```sh
ruff format .   # format (CI runs ruff format --check .)
ruff check .    # lint (matches CI)
mypy .          # type check
pytest          # tests
```

Install dependencies first — use `pip install -r requirements-dev.txt`,
`pip install -r requirements.txt`, or `pip install -e ".[dev]"` as appropriate.
