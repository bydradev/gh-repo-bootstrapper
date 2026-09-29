
## Tooling

# <<XCODEGEN_PROJECT_NOTE>>

```sh
# <<XCODEGEN_GENERATE_STEP>>
xcodebuild test -scheme __SCHEME__ -destination "__DESTINATION_EXAMPLE__"
```

The CI suite runs this on `macos-26`. For `iphone`/`ipad` destinations it
resolves an available simulator's UDID at run time (via `xcrun simctl`) and
passes `-destination "platform=iOS Simulator,id=<udid>"` — a UDID rather than
a `name=` destination, since simulator names aren't unique across installed
runtimes.

# <<XCODEGEN_DEPENDENCY_NOTE>>

In a worktree, pass one fixed `-derivedDataPath` for that worktree, reuse it
across runs, and delete it when the worktree is removed. Never choose a new
derived-data path per run or per commit. Keep it outside the source tree — for
example next to the worktree — because `swift-format --recursive .` and search
tools would otherwise scan it. Write `-resultBundlePath` bundles to the
session's scratch directory and delete them once read.

## Formatting

Formatting is enforced in CI (`swift-format lint --recursive --strict .`), so
a violation fails the build. Run `swift-format format --recursive --in-place .`
after changing any Swift file, and `swift-format lint --recursive --strict .`
before pushing. Never suppress or manually circumvent a formatter diagnostic
(no per-line `// swift-format-ignore`, no hand-editing around a rule). Rule
configuration lives in `.swift-format` at the repo root; if a rule is wrong
for this codebase, change that file deliberately and say why in the
commit/PR — it's the only sanctioned escape hatch.
