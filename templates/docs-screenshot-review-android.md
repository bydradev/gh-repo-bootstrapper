## Android projects

When the repository already has an Android capture capability (such as Compose
preview tests, layout snapshot tests, or connected device captures via `adb
shell screencap -p` or Gradle connected tasks), use that capability against
local or fictional fixture data and follow its existing setup instructions.
Do not assume a particular native capture tool, command, device, or dependency:
this template does not create any of them.

Review the rendered result for layout, content, and sensitive-data boundaries
before adding an image to version control:

- **Formatter:** Source code formatters (such as Spotless `ktfmt`, run via
  `./gradlew spotlessCheck` or `./gradlew spotlessApply`) format Kotlin and
  Gradle files, not image assets or capture outputs. Formatter checks must pass
  cleanly without corrupting test data fixtures or baseline manifests.
- **Emulator selection:** When connected captures run against a virtual
  device, select a pinned, deterministic AVD (a named device profile and system
  image API level, run headless) with known screen dimensions, density, and
  system settings (theme, font scale). Avoid testing against unpinned or ad-hoc
  physical devices whose system state differs.
- **Fixture isolation:** Drive captures from reproducible, synthetic
  in-memory or sandbox fixture data. Never run captures against live user
  accounts or data, production credentials, or real personal information.
- **Artifact-review boundaries:** Screenshot generation and visual approval are
  separate gates. A passing capture command or `./gradlew connectedCheck` proves
  only that artifacts were produced; it is not visual or privacy approval. Keep
  temporary captures outside version control until visual and privacy review is
  complete. Keep accepted workflow commands and repository-specific launch
  details in the application repository.
