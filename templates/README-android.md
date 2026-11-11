# __REPOSITORY_NAME__

> An Android project bootstrapped with GitHub Actions, Release Please, and
> Dependabot. Replace this sentence with the project's purpose and intended users.

| Detail | Value |
|---|---|
| Status | Initial setup |
| Toolchain | Android SDK (API 37 compile/target, API 35 min), JDK 17, Gradle 9.6.0 |

## Start here

The bootstrapper supplies repository infrastructure, but deliberately leaves
application source, Gradle build files, and wrapper files under application ownership.
Add the Android application scaffold and Gradle wrapper before shipping:

1. Initialise the application scaffold with a compatible Gradle wrapper (`gradlew`).
2. Add your application build configuration (`settings.gradle.kts`, `build.gradle.kts`).
3. Ensure JDK 17 is configured for Gradle builds and local verification.
4. When Jetpack Compose is enabled, apply the AGP Compose Preview configuration:
   set `android.onlyEnableUnitTestForTheTestedBuildType=false` in `gradle.properties`
   and `testOptions.unitTests.isIncludeAndroidResources = true` in `app/build.gradle.kts`.

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

CI runs these checks on every pull request:

```sh
./gradlew check
```

## Project guide

- `AGENTS.md`: branch, commit, pull-request, and validation workflow.
- `docs/branch-protection-runbook.md`: how to unblock required GitHub checks.
