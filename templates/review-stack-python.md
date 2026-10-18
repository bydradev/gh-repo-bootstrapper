### Python

- **Typing.** Public functions are typed; no new `# type: ignore` or `Any`
  without a reason.
- **Errors.** No bare `except:`, and no broad `except Exception` that swallows
  failures. Re-raised exceptions keep their cause (`raise ... from`). Files,
  sockets and locks use context managers.
- **Security.** `subprocess` takes an argument list, never `shell=True` with
  untrusted input. `yaml.safe_load`, not `yaml.load`; no `pickle`, `eval` or
  `exec` on untrusted data. Paths are resolved and checked against their
  allowed root. HTTP calls set a timeout and keep TLS verification on.
- **Traps.** Mutable default arguments; naive and aware datetimes mixed;
  floats for money (use `Decimal`); text I/O without `encoding="utf-8"`;
  output order that depends on set or filesystem order.
- **Packaging.** `uv.lock` changes through uv, never by hand, and
  `local-validation-python` says which dependency set CI installs. New syntax
  and APIs respect `requires-python`.
- **CLIs.** Existing flags and exit codes keep working; errors go to stderr;
  non-interactive mode never prompts.
- **Tests.** pytest covers failure paths, unit tests make no network calls,
  and temporary files use `tmp_path`.
