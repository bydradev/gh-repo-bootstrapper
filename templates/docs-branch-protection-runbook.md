# Branch protection runbook

Use this when a required check blocks a pull request, most often a release
PR. The live branch-protection rule is the source of truth for required
checks: read it with the commands below, never from another repository.

## Before relying on protection

- The rule must require a pull request, apply to administrators, and require
  only checks the current CI reports. Prove the names and App IDs on a real
  pull request whose current merge result reports every required check.
- A reusable workflow's job reports as `{caller job} / {reusable job}`:
  `test / build` and `test / e2e` for Next.js, `test / test` for Python, Swift
  and Rust. A required check must match that name, not the job name inside
  `test.yml`.
- Release Please uses a token from this repository's GitHub App, so its PRs
  start checks without approval. The operator sets variable
  `RELEASE_PLEASE_CLIENT_ID` and secret `RELEASE_PLEASE_APP_KEY`; never put
  either value in source, logs, issues or pull requests. The workflow's own
  `GITHUB_TOKEN` stays at `contents: read`. Rely on release automation only
  after its first release PR reports every required check.

## A check fails on code that `main` already fixed

**Check:** compare the parents of the PR's test merge commit with the `main`
tip. Release Please updates its PR only when the release notes change, so its
checks can describe a tree that no longer exists.

**Action:** do not re-run the check. A re-run reuses the original event's
commit and ref, so it tests the same stale tree. A new event, such as closing
and reopening the PR, can still capture the stale merge ref, so check the
parents again after it. For a deterministic fix, and only when authorized,
call `update-branch`: it merges `main` into the PR branch and starts new runs.
Release Please replaces that merge commit when it next updates its PR.

## A required check stays pending

**Check:** run `gh pr checks` and find the case that applies:

- A job skipped by its own `if:` reports `skipped`, which satisfies a required
  check. `pr-title-check.yml` relies on this for Release Please's PRs.
- A check that never reports stays pending forever. A workflow skipped by a
  path, branch or commit-message filter never reports, and `pull_request`
  workflows do not run while the PR has a merge conflict.
- Runs on a PR created or updated with `GITHUB_TOKEN` wait for approval. Check
  who opened the PR and whether its runs are waiting. Someone with write
  access selects **Approve workflows to run**; the App token avoids the wait.

**Action:** make the workflow report, and keep the check required.

## The checks list shows an old failure

**Check:** whether a newer success follows it. GitHub uses the latest result
per check name on the latest commit, so that old failure does not block.

**Action:** read `mergeStateStatus` for the real blocker.

## Still blocked

A stuck PR is a pause state, not authority to weaken protection: the rule
binds administrators, the operator included. Repair or retrigger the workflow
through its supported mechanism. Never drop a required check, use an admin
bypass, or disable protection to land a change.

If the rule itself still blocks after materially distinct attempts, stop and
ask for explicit operator authorization. An approved temporary change must:

1. save the complete live rule and an exact restoration payload first;
2. name the single PR and the reason;
3. record the before state, the change, the merge or repair, and the after
   state;
4. restore protection immediately; and
5. independently re-query the complete rule, App IDs included, and diff it.

Making the protected path work is always the preferred fix; a temporary
change is never the normal release procedure.

## Commands

```sh
gh api repos/<owner>/<repo>/branches/main/protection
gh pr view <n> --repo <owner>/<repo> --json mergeable,mergeStateStatus,statusCheckRollup
gh pr checks <n> --repo <owner>/<repo>
gh api repos/<owner>/<repo>/pulls/<n> --jq .merge_commit_sha
gh api repos/<owner>/<repo>/commits/<sha> --jq '[.parents[].sha]'
gh api -X PUT repos/<owner>/<repo>/pulls/<n>/update-branch
```

## Sources

Checked 2026-10-16:

- docs.github.com: "About protected branches", "Troubleshooting required
  status checks", "Status checks", "Re-running workflows and jobs", "Events
  that trigger workflows" (`pull_request`), "GITHUB_TOKEN", and "REST API
  endpoints for pull requests".
- googleapis/release-please, `src/manifest.ts`: an open release PR is updated
  only when its notes change.
- Not documented: the `{caller job} / {reusable job}` name (confirm it with
  `gh pr checks`), the stale merge ref after a reopen, and the latest result
  rule. gh-repo-bootstrapper's `docs/archive/branch-protection-incident.md`
  records the July 2026 incident where the last two were observed.
