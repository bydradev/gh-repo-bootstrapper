
## Tooling

Run the checks your change affects before pushing:

```sh
./gradlew spotlessCheck  # format check (./gradlew spotlessApply fixes formatting)
./gradlew lintDebug      # lint check
./gradlew test           # host unit tests
./gradlew assembleDebug  # debug build
```

The application scaffold and Gradle wrapper are owned by the repository. Keep
local SDK configuration in `local.properties` (uncommitted) and run Gradle
commands through `./gradlew`.

When Jetpack Compose is enabled, ensure Compose Preview settings are configured
in the application scaffold: set
`android.onlyEnableUnitTestForTheTestedBuildType=false` in `gradle.properties`
and `testOptions.unitTests.isIncludeAndroidResources = true` in
`app/build.gradle.kts`.
