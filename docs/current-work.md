# Current work

**Status:** all four steps below are done, and the completion gate is met.
Pull requests bringing the generated repositories up to 0.11.0 were opened
on 2026-10-16.

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
   `concurrency.queue: max`, which GitHub supports (docs.github.com
   "Workflow syntax for GitHub Actions", checked 2026-10-15) and actionlint 1.7.12 reports as an unexpected key.
   Where actionlint runs, ignore it the same way:

   ```yaml
     .github/workflows/release-please.yml:
       ignore:
         - 'unexpected key "queue" for "concurrency" section'
   ```

4. **Done (2026-10-16).** The scheduled workflow reads the intended alert
   data on a live generated repository. `bydradev/gh-actions-dashboard`'s
   `baseline-review.yml` matches the canonical template (`--check` reports
   `same`), and its scheduled run on 2026-10-12 (run 38294612389) succeeded
   with "Dependabot parity: every dismissed alert has a row and every row has
   a dismissed alert" against its one accepted advisory. That line needs the
   Dependabot alerts API, which the job's `vulnerability-alerts: read` token
   could therefore call. No generated repository carries a per-repository
   permission workaround.

**Completion gate:** template validation and actionlint agree, the scheduled
review retains its intended read-only behaviour, and generated repositories do
not carry per-repository permission workarounds.
