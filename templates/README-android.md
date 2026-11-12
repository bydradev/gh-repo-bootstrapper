# __REPOSITORY_NAME__

> An Android project bootstrapped with GitHub Actions, Release Please, and
> Dependabot. Replace this sentence with the project's purpose and intended users.

| Detail | Value |
|---|---|
| Status | Initial setup |
| Toolchain | Android SDK (the app's own `compileSdk`, `targetSdk` and `minSdk`), JDK 17, the Gradle version the app's AGP needs |

The templates were checked on 2026-11-07 against the
[Android Gradle Plugin 9.5 release notes](https://developer.android.com/build/releases/agp-9-5-0-release-notes)
(Gradle 9.6.0 or later and JDK 17 for AGP 9.5), the
[Android 17 SDK setup guide](https://developer.android.com/about/versions/17/setup-sdk)
and [Gradle releases](https://services.gradle.org/versions/all).

## Start here

The bootstrapper supplies repository infrastructure, but deliberately leaves
application source, Gradle build files, and wrapper files under application ownership.
Add the Android application scaffold and Gradle wrapper before shipping:

1. Initialise the application scaffold with a compatible Gradle wrapper (`gradlew`).
2. Add your application build configuration (`settings.gradle.kts`, `build.gradle.kts`).
3. Ensure JDK 17 is configured for Gradle builds and local verification.
4. Apply the [Spotless](https://plugins.gradle.org/plugin/com.diffplug.spotless)
   Gradle plugin (`com.diffplug.spotless`) with a Kotlin formatter such as
   ktfmt. CI runs `./gradlew spotlessCheck` on every pull request and stops
   with an error until the task exists.
5. When Jetpack Compose is enabled under Android Gradle Plugin (AGP) 9.5.1,
   local testing found that Compose Preview task realization
   requires setting `android.onlyEnableUnitTestForTheTestedBuildType=false` in
   `gradle.properties` and `testOptions.unitTests.isIncludeAndroidResources = true`
   in `app/build.gradle.kts`. (This pair is an isolated workaround finding from
   local testing rather than official guidance.) Projects adopting other AGP
   versions should verify whether their toolchain requires these settings.

## Local development

Configure your Android SDK location in `local.properties` (kept uncommitted):

```properties
sdk.dir=/path/to/android/sdk
```

Run Gradle tasks through the wrapper:

```sh
./gradlew spotlessCheck
./gradlew lintDebug
./gradlew test
```

## Verification

CI runs fast checks on every pull request:

```sh
./gradlew spotlessCheck lintDebug testDebugUnitTest
```

Full validation (`./gradlew check`) runs before releases.

## Project guide

- `AGENTS.md`: branch, commit, pull-request, and validation workflow.
- `docs/branch-protection-runbook.md`: how to unblock required GitHub checks.
