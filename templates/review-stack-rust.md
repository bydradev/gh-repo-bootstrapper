### Rust

- **Panics.** Each new `unwrap`, `expect`, `panic!` or unchecked index on a
  path that input can reach is justified.
- **Errors.** Errors that cross a boundary carry context (`?` adds none), and
  no `Result` is discarded (`let _ =`) without a reason.
- **`unsafe`.** Each block is minimal and has a `// SAFETY:` comment whose
  invariants actually hold, including at FFI boundaries. No `unsafe impl Send`
  or `Sync` without that argument.
- **Async.** No blocking lock (`std::sync`, `parking_lot`) is held across
  `.await`; blocking calls go through `spawn_blocking`; `select!` branches are
  cancellation-safe.
- **Arithmetic.** Input-driven arithmetic uses checked or saturating
  operations, since release builds wrap silently, and `as` casts cannot
  truncate or change sign unexpectedly.
- **API.** Public API changes follow semver; features stay additive; the MSRV
  holds.
- **Lints.** As generated, CI runs Clippy with `-D warnings`, so a lint is
  allowed only in the `[lints]` table or on the narrowest item, with a reason
  (`local-validation-rust`).
