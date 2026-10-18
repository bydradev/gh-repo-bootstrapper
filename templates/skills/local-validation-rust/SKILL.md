---
name: local-validation-rust
description: "Use before running local validation in this Rust repository: `cargo fmt`, `cargo clippy`, `cargo test`, or any Cargo build in a worktree. Covers allowing a lint deliberately, when to add the `cargo` Dependabot entry, the shared `CARGO_TARGET_DIR` for worktrees and who deletes it, and switching Release Please to the `rust` release type."
---

# Local validation for Rust

If `## Project specifics` in `AGENTS.md` names a repository-owned validation
skill, load it first; where it is narrower, it governs.

The commands to run before pushing are in the `## Tooling` section of `AGENTS.md`. This skill covers the detail behind them.

## Lints

As generated, CI runs Clippy with `-D warnings`, so every warning fails it;
check `.github/workflows/test.yml`, which this repository owns.
If a lint is wrong for this codebase, allow it deliberately (in the `[lints]`
table of `Cargo.toml`, or on the narrowest item with a stated reason) and say
why in the commit or PR; never silence it just to pass CI.

## Dependabot

As generated, `.github/dependabot.yml` covers GitHub Actions only: a new
repository has no `Cargo.toml`, and a `cargo` entry would fail on every run
until one exists. Once the manifest is committed, add a `cargo` ecosystem
entry if the file has none.

## Worktrees

Cargo writes build output to `target/` in each checkout, and a workspace build
can reach gigabytes. In a worktree, set `CARGO_TARGET_DIR` to one fixed
directory for this repository, outside the source tree: `target` inside the
directory that holds this repository's worktrees, for example
`../.worktrees/<repo>/target` from the main checkout. Use it for every Cargo
command in those worktrees. Cargo locks the build directory, so a second build
waits for the first rather than corrupting it. Never copy `target/` into a
verification copy.

That shared directory belongs to the repository's worktrees as a group, not to
any one task. Leave it while any of those worktrees exists; the task that
removes the last one deletes it too. It holds only rebuildable output, so when
disk space is short, deleting it costs a rebuild and nothing else; never
create a per-worktree `target/` instead.

## Versioning

As generated, `release-please-config.json` uses the `simple` release type:
Release Please maintains the changelog, tag, and GitHub release, but does not
edit versions in `Cargo.toml`. For a single published crate, switch it to the
`rust` release type; a multi-crate workspace also needs Release Please's
`cargo-workspace` plugin. Make that change deliberately, once the manifest
exists.

## Sources

- Cargo's build-directory lock (its "waiting for file lock" message): cargo
  1.97.1, checked 2026-09-29.
