---
name: local-validation-android
description: "Use before running local validation in this Android repository: `./gradlew spotlessCheck`, `./gradlew lintDebug`, `./gradlew test`, `./gradlew connectedCheck`, `./gradlew check`, or worktrees and emulator runs. Covers CI validation tiers (fast PR checks vs full release validation), local device verification, safeguards for lifecycle, cancellation, state, persistence, permissions, and API-level compatibility, worktree Gradle locks, and versioning."
---

# Local validation for Android

If `## Project specifics` in `AGENTS.md` names a repository-owned validation
skill, load it first; where it is narrower, it governs.

The commands to run before pushing are in the `## Tooling` section of
`AGENTS.md`. This skill covers the details behind them, local emulator and
device constraints, and CI validation tiers.

## Gradle tasks and tooling commands

The standard repository checks execute through the Gradle wrapper (`./gradlew`):

- **Format check:** `./gradlew spotlessCheck` checks Kotlin formatting (configured
  via Spotless and ktfmt). The task exists only when the application's build
  applies the Spotless Gradle plugin; CI stops with an error until it does. Run `./gradlew spotlessApply` to automatically format
  source files. Never circumvent formatter checks with manual escapes or
  suppression comments.
- **Lint:** `./gradlew lintDebug` performs static analysis of Android resources,
  manifests, and Kotlin code. Treat lint warnings as errors where configured;
  address the root issue rather than silencing lints without review.
- **Host unit tests:** `./gradlew test` (or `./gradlew testDebugUnitTest`) runs
  JVM-based unit tests. This includes unit tests using MockK or Robolectric,
  independent of an emulator.
- **Build compilation:** `./gradlew assembleDebug` compiles the debug APK.
- **Full validation:** `./gradlew check` executes format checks, lint analysis,
  and unit tests across the project.
- **Connected device checks:** `./gradlew connectedCheck` (or
  `./gradlew connectedDebugAndroidTest`) executes instrumentation tests against a
  booted emulator or attached physical device.

## CI validation tiers and local device checks

As generated, CI validates in tiers via `.github/workflows/test.yml` (called by
`ci.yml` and `release-please.yml`):

- **Pull requests (`ci.yml`) and ordinary pushes to `main`:** run fast checks
  (`full: false`): wrapper checks (an executable `gradlew`, and
  `gradle-wrapper.jar` validated against Gradle's published checksums),
  JDK 17 setup with the Gradle cache, a check that the
  `spotlessCheck` task exists, and
  `./gradlew spotlessCheck lintDebug testDebugUnitTest` on `ubuntu-latest`.
- **Release Please merge (`chore(main): release`) and manual dispatch of
  `release-please.yml`:** run full validation (`full: true`): the same
  wrapper checks and JDK 17 setup, the same `spotlessCheck` task check, and
  `./gradlew check`. The release PR merges and
  tags only after full validation passes.
- **Connected device checks:** `./gradlew connectedCheck` (or
  `./gradlew connectedDebugAndroidTest`) is repository-owned and executed
  as an explicit local verification lane against a booted emulator or attached
  device. Standard CI runners do not provide a running emulator or connected
  device; verify device contracts locally before landing changes that touch
  UI, lifecycle, persistence, permissions, or API-level behaviour.

## Android safeguards and review focus

When developing or modifying Android application code, verify these core
engineering safeguards:

- **Lifecycle and state:** UI components observe observable state flows and emit
  unidirectional events. ViewModels manage state transitions and survive
  configuration changes (screen rotation, light/dark mode changes). Process
  death and restoration must be verified with `SavedStateHandle` or persistent
  state; never assume ViewModel memory state survives OS process termination.
  Compose composables must be restartable and skippable where intended.
- **Structured concurrency and cancellation:** Coroutine operations must adhere
  to structured concurrency with explicit scopes (`viewModelScope`,
  `lifecycleScope`). UI updates belong on `Dispatchers.Main`; disk and network
  I/O belong on `Dispatchers.IO`. Long-running tasks and asynchronous flows must
  cooperate with cancellation (checking `isActive` or calling `ensureActive()`).
  Discard stale asynchronous results when user context changes or navigation
  occurs.
- **Persistence and storage:** Database queries and file system access must run
  off the main thread. Database schema migrations must be tested and
  transactional. Credentials, session tokens, and cryptographic keys must be
  secured with keys held in the Android Keystore system, never in plain
  preferences, unencrypted local files, or logs. Do not add Jetpack Security's
  `EncryptedSharedPreferences` or other `security-crypto` APIs to new code:
  AndroidX deprecated them in favour of platform APIs and direct use of the
  Android Keystore.
- **Runtime permissions and privacy:** Request runtime permissions in context
  with clear rationale, never eagerly on launch. Handle both one-time denial and
  permanent denial ("Don't ask again") states gracefully by disabling dependent
  features or guiding users to system settings. Do not log personal data,
  user content, or tokens.
- **API-level compatibility:** Verify behavior across the app's supported
  range, from its `minSdk` to its `targetSdk` (both in the app's Gradle build).
  Guard newer APIs with version checks, and test the fallbacks at the lowest
  supported level. Before raising `targetSdk`, read the behaviour changes for
  apps that target the new version, such as edge-to-edge layout and predictive
  Back. Each new Android release also brings changes for all apps, whatever
  they target, such as 16 KB page sizes for native code. Verify on emulators
  or devices at the levels a change touches.

## Compose Preview under AGP 9.5.1

When Compose Preview is used under Android Gradle Plugin (AGP) 9.5.1, local
testing found that task realization requires setting:

- `android.onlyEnableUnitTestForTheTestedBuildType=false` in `gradle.properties`
- `testOptions.unitTests.isIncludeAndroidResources = true` in `app/build.gradle.kts`

This pair is an isolated workaround finding from local testing rather than official
guidance. Other AGP versions should verify their own task realization behavior.

## Worktrees and Gradle daemon

Gradle caches build artifacts and dependencies in `GRADLE_USER_HOME` and the project-local
`.gradle/` and `build/` directories. In git worktrees:

- Do not copy `.gradle/` or `app/build/` into a new worktree; let Gradle build
  cleanly.
- When working concurrently across multiple worktrees, Gradle daemon handles
  file locks, but parallel task execution across worktrees sharing an SDK
  location must preserve `local.properties`.
- Ensure `local.properties` exists in each worktree pointing to the local
  `sdk.dir` (uncommitted, excluded by `.gitignore`).

## Versioning

As generated, `release-please-config.json` uses the `simple` release type:
Release Please maintains `CHANGELOG.md`, git tags, and GitHub releases, but
leaves `versionName` and `versionCode` in `app/build.gradle.kts` under application
ownership. Update `versionName` and increment `versionCode` deliberately when
preparing release candidates, or configure `extra-files` in
`release-please-config.json` to track them.

## Sources

- Gradle wrapper verification: [Gradle wrapper documentation](https://docs.gradle.org/current/userguide/gradle_wrapper.html), checked 2026-11-07.
- Wrapper JAR validation: [`gradle/actions` wrapper-validation](https://github.com/gradle/actions/tree/v6.4.1/wrapper-validation) v6.4.1; Gradle cache: [`actions/setup-java`](https://github.com/actions/setup-java/tree/v6.1.0) v6.1.0 `cache: gradle`; both checked 2026-11-12.
- AGP 9.5.1 and Compose Preview test options: local qualification testing and [AGP 9.5 release notes](https://developer.android.com/build/releases/agp-9-5-0-release-notes), checked 2026-11-07.
- Android SDK setup for the newest platform: [Android 17 SDK setup guide](https://developer.android.com/about/versions/17/setup-sdk), checked 2026-11-07.
- `security-crypto` deprecation (1.1.0-alpha07, 2025-04-09, and 1.1.0-beta01): [AndroidX Security releases](https://developer.android.com/jetpack/androidx/releases/security), checked 2026-11-12.
- Release Please `simple` release type: Google Release Please v17 schema, checked 2026-10-21.
