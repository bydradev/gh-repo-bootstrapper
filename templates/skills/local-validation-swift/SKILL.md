---
name: local-validation-swift
description: "Use before running local validation in this Swift repository: `xcodebuild test`, simulator destinations, `swift-format`, derived data in a worktree, or result bundles. Covers how CI picks a simulator, which CI runs test and which only lint, project and dependency setup, the fixed `-derivedDataPath` rule, what Release Please does and does not version, and the formatter rules."
---

# Local validation for Swift

The commands to run before pushing are in the `## Tooling` section of `AGENTS.md`. This skill covers the detail behind them.

## Simulator destinations

The CI suite runs this on `macos-26`. For `iphone`/`ipad` destinations it
resolves an available simulator's UDID at run time (via `xcrun simctl`) and
passes `-destination "platform=iOS Simulator,id=<udid>"` — a UDID rather than
a `name=` destination, since simulator names aren't unique across installed
runtimes.

## CI validation tiers

- **Pull requests (`ci.yml`) and ordinary pushes to `main`:** run only
  `xcrun swift-format lint --recursive --strict .`. `xcodebuild test` is
  skipped, so a green pull request does not mean the tests passed; run them
  locally first.
- **Release Please merge (`chore(main): release`) and a manual dispatch of
  `release-please.yml`:** run the formatter and `xcodebuild test`. A release
  is tagged only after this passes.

## Dependencies

# <<XCODEGEN_DEPENDENCY_NOTE>>

## Worktrees

In a worktree, pass one fixed `-derivedDataPath` for that worktree, reuse it
across runs, and delete it when the worktree is removed. Never choose a new
derived-data path per run or per commit. Keep it outside the source tree — for
example next to the worktree — because `swift-format --recursive .` and search
tools would otherwise scan it. Write `-resultBundlePath` bundles to the
session's scratch directory and delete them once read. (Both options checked
against `xcodebuild -help` in Xcode 27.0, 2026-09-29.)

## Versioning

Release Please runs with the `simple` release type: it maintains the
changelog, tag, and GitHub release, but does not change the app's
`MARKETING_VERSION` or `CURRENT_PROJECT_VERSION`, wherever they are set. For
`MARKETING_VERSION`, update it deliberately for a build you ship, or point
`extra-files` in `release-please-config.json` at the field that holds it.
`extra-files` only replaces a semantic version, so `CURRENT_PROJECT_VERSION`
needs its own, separately verified build-number step (checked against
release-please v17.11.2's `simple` strategy, generic updater, and config
schema, 2026-09-29).

## Formatting

Formatting is enforced in CI (`xcrun swift-format lint --recursive --strict .`),
so a violation fails the build. Run
`xcrun swift-format format --recursive --in-place .` after changing any Swift
file, and `xcrun swift-format lint --recursive --strict .` before pushing.
Never suppress or manually circumvent a formatter diagnostic (no per-line
`// swift-format-ignore`, no hand-editing around a rule). Rule
configuration lives in `.swift-format` at the repo root; if a rule is wrong
for this codebase, change that file deliberately and say why in the
commit/PR — it's the only sanctioned escape hatch.
