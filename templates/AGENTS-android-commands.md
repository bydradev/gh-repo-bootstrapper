
## Tooling

Run the checks your change affects before pushing:

```sh
./gradlew spotlessCheck  # format check (./gradlew spotlessApply fixes formatting)
./gradlew lintDebug      # lint check
./gradlew test           # host unit tests
./gradlew assembleDebug  # debug build
```

The application scaffold and Gradle wrapper are repository-owned. Keep local SDK
configuration in `local.properties` (uncommitted) and run via `./gradlew`.

When Compose Preview is used under AGP 9.5.1, set
`android.onlyEnableUnitTestForTheTestedBuildType=false` in `gradle.properties`
and `testOptions.unitTests.isIncludeAndroidResources = true` in
`app/build.gradle.kts`. Other AGP versions should verify if still required.
