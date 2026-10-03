
## Tooling

Run all checks before pushing:

```sh
cargo fmt --all -- --check                             # format (matches CI)
cargo clippy --workspace --all-targets -- -D warnings  # lint (matches CI)
cargo test --workspace                                 # tests (matches CI)
```

`cargo fmt --all` fixes formatting. CI treats every Clippy warning as an error.
If a lint is wrong for this codebase, allow it deliberately — in the `[lints]`
table of `Cargo.toml`, or on the narrowest item with a stated reason — and say
why in the commit or PR; never silence it just to pass CI.

Dependabot starts with GitHub Actions updates only: a new repository has no
`Cargo.toml`, and a `cargo` entry would fail on every run until one exists.
Once the manifest is committed, add a `cargo` ecosystem entry to
`.github/dependabot.yml`.

Cargo writes build output to `target/` in each checkout, and a workspace build
can reach gigabytes. In a worktree, set `CARGO_TARGET_DIR` to one fixed
directory for this repository, outside the source tree: `target` inside the
directory that holds this repository's worktrees, for example
`../.worktrees/<repo>/target` from the main checkout. Use it for every Cargo
command in those worktrees. Cargo locks the build directory, so a second build
waits for the first rather than corrupting it (its "waiting for file lock"
message, checked against cargo 1.97.1, 2026-09-29). Never copy `target/` into a
verification copy.

That shared directory belongs to the repository's worktrees as a group, not to
any one task. Leave it while any of those worktrees exists; the task that
removes the last one deletes it too. It holds only rebuildable output, so when
disk space is short, deleting it costs a rebuild and nothing else — never
create a per-worktree `target/` instead.

Release Please runs with the `simple` release type: it maintains the changelog,
tag, and GitHub release, but does not edit versions in `Cargo.toml`. For a
single published crate, switch `release-please-config.json` to the `rust`
release type; a multi-crate workspace also needs Release Please's
`cargo-workspace` plugin. Make that change deliberately, once the manifest
exists.
