# Current work

**Status:** one cross-fleet workflow-compatibility item remains: confirming the
scheduled review's alert read on a live run (step 4 below).

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
3. Validate the template and all rendered Next.js workflows with actionlint,
   using that exception.
4. Verify the scheduled workflow can still read the intended alert data before
   propagating any canonical change to application repositories.

**Completion gate:** template validation and actionlint agree, the scheduled
review retains its intended read-only behaviour, and generated repositories do
not carry per-repository permission workarounds.
