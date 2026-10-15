# Current work

**Status:** steps 1 to 3 below are done. Step 4 remains: confirming the
scheduled review's alert read on a live run, which needs a generated Next.js
repository with Dependabot alerts.

## `baseline-review.yml` and actionlint

The canonical Next.js `baseline-review.yml` requests
`vulnerability-alerts: read`, and `validate_templates.py` requires that exact
permission because the scheduled review queries Dependabot alert data.
actionlint reports `vulnerability-alerts` as an unknown permission scope.

1. **Done (2026-10-09).** `vulnerability-alerts: read` is the least-privilege,
   supported permission. GitHub's workflow syntax reference lists it: "Read
   Dependabot alerts ... Only `read` and `none` are supported; `write` is not
   valid." The same page directs Dependabot alerts away from
   `security-events`, which covers code scanning. Source:
   docs.github.com, "Workflow syntax for GitHub Actions", `permissions`,
   checked 2026-10-09.
2. **Done (2026-10-09).** The permission is valid but unsupported by actionlint:
   its newest release, v1.7.12, does not list `vulnerability-alerts`
   (`gh release list -R rhysd/actionlint`, checked 2026-10-09). The canonical
   workflow and its validator stay as they are. Where actionlint runs, record
   this exception in its config rather than editing the workflow:

   ```yaml
   # .github/actionlint.yaml
   paths:
     .github/workflows/baseline-review.yml:
       ignore:
         - 'unknown permission scope "vulnerability-alerts"'
   ```

   actionlint's `paths.<glob>.ignore` takes regular expressions matched against
   error messages (rhysd/actionlint `docs/config.md`, checked 2026-10-09).
   Remove the entry once an actionlint release recognises the scope.
3. **Done (2026-10-15).** actionlint 1.7.12 passes on the rendered workflows
   of all 11 configurations `validate_templates.py` renders, with that
   exception and one more: the release-please workflows set
   `concurrency.queue: max`, which GitHub supports (changelog 2026-05-07,
   checked 2026-10-15) and actionlint 1.7.12 reports as an unexpected key.
   Where actionlint runs, ignore it the same way:

   ```yaml
     .github/workflows/release-please.yml:
       ignore:
         - 'unexpected key "queue" for "concurrency" section'
   ```

4. Verify the scheduled workflow can still read the intended alert data before
   propagating any canonical change to application repositories.

**Completion gate:** template validation and actionlint agree, the scheduled
review retains its intended read-only behaviour, and generated repositories do
not carry per-repository permission workarounds.
