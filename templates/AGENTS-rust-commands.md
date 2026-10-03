
## Tooling

Run all checks before pushing:

```sh
cargo fmt --all -- --check                             # format (matches CI)
cargo clippy --workspace --all-targets -- -D warnings  # lint (matches CI)
cargo test --workspace                                 # tests (matches CI)
```

`cargo fmt --all` fixes formatting.
