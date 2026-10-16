
## Tooling

Run the checks your change affects before pushing:

```sh
ruff format .     # format (CI runs ruff format --check .)
ruff check .      # lint (matches CI)
mypy .            # type check
python -m pytest  # tests
```

Install dependencies the way CI does (`uv sync --locked` with the dev group or
extra when `uv.lock` exists); `local-validation-python` gives the full order.
