---
name: local-validation-android
description: Use before Android Gradle validation, emulator or device checks, or setting up an Android worktree.
---

# Local validation for Android

If `## Project specifics` in `AGENTS.md` names a repository-owned validation
skill, load it first; where it is narrower, it governs.

For pre-push tasks, see `## Tooling` in `AGENTS.md`. Use the Gradle wrapper.
Fix formatting with `./gradlew spotlessApply`. Never bypass the formatter.
Fix lint findings at the source and review any lint suppression.

## CI validation tiers and local device checks

The generated `.github/workflows/test.yml` uses Ubuntu, JDK 17 and the Gradle
cache. Both tiers require an executable wrapper, a verified wrapper JAR and
the app's Spotless task.

| When | Validation |
| --- | --- |
| PRs and ordinary pushes to `main` | fast checks (`full: false`) run `./gradlew spotlessCheck lintDebug testDebugUnitTest` |
| Push of the release PR merge to `main` or manual dispatch of `release-please.yml` | full validation (`full: true`) runs `./gradlew check` before the release job |

CI runs host tests. For changes to UI, lifecycle, persistence, permissions or
API behaviour, run the app's instrumentation tests on a booted emulator or
attached device before landing: `./gradlew connectedCheck` or
`./gradlew connectedDebugAndroidTest`. Use the API levels the change affects.

## Android safeguards and review focus

# <<ANDROID_SAFEGUARDS>>

## Compose Preview under AGP 9.5.1

When Compose Preview is used under Android Gradle Plugin (AGP) 9.5.1, local
testing found that task realization requires setting:

- `android.onlyEnableUnitTestForTheTestedBuildType=false` in `gradle.properties`
- `testOptions.unitTests.isIncludeAndroidResources = true` in `app/build.gradle.kts`

This pair is an isolated workaround finding from local testing rather than official
guidance. Other AGP versions should verify their own task realization behavior.

## Worktrees and Gradle daemon

Share Gradle's user cache (`GRADLE_USER_HOME`). Do not copy `.gradle/` or
`app/build/` into a new worktree. Ensure `local.properties` exists in each
worktree pointing to the local `sdk.dir` and keep it uncommitted, including
during parallel builds.

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
