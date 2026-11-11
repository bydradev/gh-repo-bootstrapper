
## Tooling

Run the checks your change affects before pushing:

```sh
./gradlew spotlessCheck  # format check (./gradlew spotlessApply fixes formatting)
./gradlew lintDebug      # lint check
./gradlew test           # host unit tests
./gradlew assembleDebug  # debug build
```

The application scaffold and wrapper are repository-owned. Keep local SDK
paths in `local.properties` (uncommitted) and run via `./gradlew`.

When Compose Preview is used under AGP 9.5.1, local testing found task
realization requires setting
`android.onlyEnableUnitTestForTheTestedBuildType=false` in `gradle.properties`
and `testOptions.unitTests.isIncludeAndroidResources = true` in
`app/build.gradle.kts` (an isolated local test finding, not official guidance).
Toolchain sources verified 2026-11-07; see README.md.
