# Branch protection incident (July 2026)

> **Archived 2026-10-16.** The incident record behind
> `docs/branch-protection-runbook.md`, kept for history and not maintained.
> Until 0.11.1 the generated runbook told this story itself. It now carries
> only the procedure, and its evidence lives here, in the bootstrapper, not
> in generated repositories.

The incident happened in late July 2026, in another repository, before the
bootstrapper's initial public release. The record does not name the
repository. Every SHA, run ID and timestamp below comes from the runbook as it
stood from the initial public release (`529f31f`) to 0.11.1 (`d441718`). Read
its last full text with
`git show v0.11.1:templates/docs-branch-protection-runbook.md`.

## What happened

A Release Please PR was open against a protected `main` with required checks.
Its bot head stayed at `3bfd1f0` while `main` advanced without it, because
Release Please updates its PR only when the release notes change
(googleapis/release-please `src/manifest.ts`, checked 2026-10-16). A file that
failed a required check on the PR had already been fixed on `main`, so the PR
was blocked correctly by the rules and wrongly in substance: the checks had
evaluated a merge result that no longer matched what would be merged.

## Timeline

All times UTC, on one day in late July 2026:

- 06:07:15: `main` advanced to `4d583c5`, which fixed the failing file.
- 07:01:42, 54 minutes later: a close and reopen created run `30244655509`,
  a fresh `pull_request` event. It still fetched the old merge ref `d975919`,
  with parents `1c54021` and bot head `3bfd1f0`, and failed on the same file.
- 07:13:11, 11 minutes after that: a second reopen created run `30245344277`.
  It fetched the recomputed merge ref `f0aef8e`, with parents `4d583c5` and
  `3bfd1f0`, and passed.

The two merge refs differ only in their `main` parent: `1c54021` before the
fix, `4d583c5` after it.

## What was observed, and what was inferred

- Observed: two separate `pull_request` events, the original run and the
  first close and reopen, fetched the same stale merge ref and failed the same
  way. Waiting did not help: the merge ref went unrecomputed for at least 54
  minutes, and the first fresh event still captured the stale value.
- Observed: only a further fresh event produced the recomputed, passing ref.
- Inferred: GitHub recomputes the merge ref lazily. The first event after a
  base change may start the recomputation while its own payload captures the
  old value, and a later event benefits. GitHub documents that the test merge
  commit is computed by a background job when a pull request is read, created
  or edited ("REST API endpoints for pull requests", checked 2026-10-16), which
  is consistent with this.
- Not performed: no explicit re-run. The rule that a re-run does not help
  rests on GitHub's documentation that a re-run keeps the original event's
  `GITHUB_SHA` and `GITHUB_REF` ("Re-running workflows and jobs", checked
  2026-10-16).
- Not needed: the `update-branch` endpoint. The second reopen was enough. The
  runbook still names it as the deterministic lever, because it merges the
  base into the PR branch and starts runs against the current `main`.

## Related observations

The original runbook recorded two more observations alongside the incident,
both on protected branches:

- A release PR whose `validate-title` check reported `skipped` computed
  `CLEAN`: a reported skip satisfied the required check.
- A PR whose `test / build` check had failed twice and then passed computed
  `CLEAN`: mergeability used the latest result per check name, so the old
  failures in the rollup did not block.

## Where each finding went

| Finding | Runbook section today |
| --- | --- |
| Checks on a release PR can describe a superseded tree | A check fails on code that `main` already fixed |
| A re-run tests the same stale tree | A check fails on code that `main` already fixed |
| A fresh event can still capture the stale merge ref | A check fails on code that `main` already fixed |
| `update-branch` is the deterministic lever | A check fails on code that `main` already fixed |
| A reported skip satisfies a required check | A required check stays pending |
| Old failures in the rollup do not block | The checks list shows an old failure |
