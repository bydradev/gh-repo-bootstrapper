<!-- SECTION:PROJECT_NOTE -->
`project.yml` is the source of truth and the generated `.xcodeproj` is ignored.
Never hand-edit or commit generated project output. After cloning, switching
branches, or changing sources, targets, packages, schemes, or build settings,
regenerate before opening Xcode:
<!-- /SECTION:PROJECT_NOTE -->
<!-- SECTION:GENERATE_STEP -->
xcodegen generate
open __SCHEME__.xcodeproj
<!-- /SECTION:GENERATE_STEP -->
<!-- SECTION:DEPENDENCY_NOTE -->
Install the XcodeGen release that `.github/workflows/test.yml` pins (2.46.0
when the repository was generated) and declare that same version as
`options.minimumXcodeGenVersion` in `project.yml`. CI downloads and
checksum-verifies that exact release before generation; when you bump the
pin there, bump the minimum with it. Put durable project
editor changes back into `project.yml`; regeneration overwrites the generated
project. Close and reopen Xcode after regenerating to avoid stale project state.

Dependencies declared only in `project.yml` are not Dependabot-supported.
Pin them with `exactVersion` and update deliberately, or add a supported root
Swift package manifest before enabling Dependabot's `swift` ecosystem.
<!-- /SECTION:DEPENDENCY_NOTE -->
