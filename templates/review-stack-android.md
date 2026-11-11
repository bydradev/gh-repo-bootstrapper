### Android

- **Lifecycle and state.** UI receives state and emits events. ViewModels own
  state transitions; state surviving configuration changes and process death
  is verified. Composable functions are restartable and skippable where intended.
- **Concurrency.** Coroutines use structured concurrency and explicit scopes;
  UI work runs on `Dispatchers.Main`, blocking I/O on `Dispatchers.IO`. Jobs and
  flows check cancellation, and stale asynchronous results are discarded.
- **Persistence and storage.** Database and file transactions run off the main
  thread; migrations are tested and transactional. Sensitive data and credentials
  are stored via Android KeyStore or encrypted storage, never plain preferences,
  unencrypted local storage, or log statements.
- **Permissions and privacy.** Runtime permissions are requested in context with
  clear rationale, and denied and permanently denied states are handled.
- **Compatibility and API verification.** Verify behavior across API 35, 36,
  and 37 targets, including edge-to-edge enforcement, predictive Back gestures,
  and 16 KB page-size compatibility. Fallbacks and version checks are tested on
  each supported API level.
- **Time and locale.** Date and time operations use `java.time` with injected
  `Clock` and `ZoneId`, never fixed millisecond arithmetic or assumed system
  defaults, and survive time zone and daylight-saving changes.
- **Scaffold and build boundary.** App source, Gradle build files, and wrapper
  remain application-owned. Build outputs, `local.properties`, and signing
  keystores stay uncommitted. Dynamic dependency versions are rejected in favour
  of qualified pins.
