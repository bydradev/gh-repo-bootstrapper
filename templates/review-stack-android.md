### Android

# <<ANDROID_SAFEGUARDS>>
- **Time and locale.** Inject `Clock` and `ZoneId` with `java.time`. Test time
  zone and daylight-saving changes. Avoid fixed millisecond arithmetic.
- **Build ownership.** The app owns its source, Gradle build and wrapper.
  Use qualified dependency pins. Keep build outputs, `local.properties` and signing
  keystores uncommitted.
