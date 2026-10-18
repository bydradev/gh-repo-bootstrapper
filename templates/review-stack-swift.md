### Swift

- **Concurrency.** UI state is `@MainActor`. `@unchecked Sendable` has a
  stated reason. State read before an `await` may have changed after it
  (actor reentrancy). Tasks check cancellation, and stale results are
  discarded.
- **Memory.** No retain cycles: a closure stored by, or retained through, the
  object it captures holds it weakly. Delegates are weak.
- **Permissions and privacy.** Each protected resource is requested in
  context, and the denied and restricted states are handled. Info.plist usage
  strings and the privacy manifest cover new APIs. Secrets live in the
  Keychain, not `UserDefaults`.
- **Time.** Date maths uses `Calendar` and `TimeZone`, not fixed offsets or
  86,400-second days, and survives time zone and daylight-saving changes.
- **Purchases**, where the app has them. Entitlements come from verified
  transactions, restore works, and paid features fail closed.
- **CI.** `local-validation-swift` says which suites run where; as generated,
  pull requests run only `swift-format` lint, not `xcodegen generate` or
  tests, so behaviour changes need local `xcodebuild test` evidence. Formatter
  rules change in `.swift-format`, never through ignore comments. With
  XcodeGen, `project.yml` is the source and the generated project is not
  committed.
