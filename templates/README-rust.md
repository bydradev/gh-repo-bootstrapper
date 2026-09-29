# __REPOSITORY_NAME__

> A Rust project bootstrapped with GitHub Actions, Release Please, and
> Dependabot. Replace this sentence with the project’s purpose and intended users.

| Detail | Value |
|---|---|
| Status | Initial setup |
| Toolchain | Rust stable |

## Start here

The bootstrapper supplies repository automation, but deliberately does not
choose a crate layout. Add a crate or workspace with `cargo init` (or a
workspace `Cargo.toml`) before shipping; CI fails until a root `Cargo.toml`
exists.

## Local development

Install the stable toolchain with [rustup](https://rustup.rs), including the
`rustfmt` and `clippy` components:

```sh
rustup toolchain install stable --component rustfmt,clippy
```

## Verification

CI runs these checks on every pull request:

```sh
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```

## Project guide

- `AGENTS.md` — branch, commit, pull-request, and validation workflow.
- `docs/branch-protection-runbook.md` — how to unblock required GitHub checks.
