- **Lifecycle and state.** UI observes state flows and emits events. ViewModels
  own transitions across configuration changes. Verify process-death recovery
  with `SavedStateHandle` or persistence. Check composables are restartable
  and skippable where intended.
- **Concurrency and cancellation.** Use an explicit scope such as `viewModelScope`. Use
  `Dispatchers.Main` for UI and `Dispatchers.IO` for blocking I/O. Respect
  cancellation in long-running jobs and flows. Discard stale results after
  navigation or context changes.
- **Persistence and storage.** Keep database and file I/O off-main. Test
  transactional migrations. Protect sensitive data and credentials with keys in
  the Android Keystore. Keep them out of plain preferences, unencrypted files and
  logs. Do not add `EncryptedSharedPreferences` or other `security-crypto` APIs.
- **Permissions and privacy.** Request permissions in context with a rationale.
  Handle denial and permanent denial by disabling the feature or offering
  settings. Keep personal data and user content out of logs.
- **API compatibility.** Test the app's range from its `minSdk` to its `targetSdk`.
  Guard newer APIs and test fallbacks at `minSdk`. Before raising `targetSdk`,
  read the new target's behaviour changes (such as edge-to-edge or predictive
  Back). Verify affected devices, including OS changes applying to all apps
  such as 16 KB page sizes for native code.
