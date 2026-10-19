---
name: pull-requests
description: >-
  Use before creating, editing, readying, or merging a pull request, writing a PR title, body, or squash-merge message, handling a Release Please PR, or unblocking a PR stuck on required checks. Covers squash-merge and Release Please changelog rules, CLI-authored bodies, which Co-Authored-By trailers a merge message carries, and the branch-protection runbook. Merge still requires explicit authorization.
---
<!-- gh-repo-bootstrapper: template-owned; sha256=7702d4c4ae0408eac3b722cadfbab7ab6522c9f1e6ef1bbae9b84e1a77058658 -->

# Pull requests (squash-merge + Release Please)

## Standard pull requests

Standard PRs are squash-merged and parsed by Release Please, so write them
merge-ready:

- **Title:** one Conventional Commit subject naming one concrete change, not a
  label summarizing several bundled changes (e.g. not
  `fix: address review follow-ups (path handling, branch protection, clone retry)`,
  which is a summary, not a change). If a PR bundles multiple distinct fixes,
  title it after the single most significant one and list the rest as extra
  changelog entries below, or split the PR. The title becomes the squash
  subject, the changelog entry, and the version-bump signal.
- **User-visible line:** the body carries one line of its own, at column 0,
  reading `User-visible: yes` or `User-visible: no`. The required title check
  fails without it, and when it disagrees with whether Release Please will
  release the change. Decide the answer from the diff first, then choose the
  type that agrees with it; never change the answer to fit a type. Answer
  `yes` when the change reaches users through a release: what the released
  project does, outputs, or ships changes, so the type is `feat`, `fix`,
  `perf`, or `revert`, or the change is breaking (`!` or a `BREAKING CHANGE:`
  footer). Answer `no` when it does not: documentation readers get from the
  repository or a site as soon as it merges, CI, tests, refactors, and
  tooling, typed `docs`, `chore`, `refactor`, `test`, `build`, or `ci`. Text a
  release ships, such as help output, is `yes`. The check reads the body as
  Release Please does, so an extra entry of a released type, a `Release-As:`
  footer, or a `BREAKING-CHANGE:` token anywhere in the body but a footer's
  own line, even quoted, also makes the answer `yes`. Keep that token, lines
  that open a paragraph with a type, and the `BEGIN_COMMIT_OVERRIDE` marker
  (Release Please replaces the commit with what follows it) out of prose, and
  indent a line that starts with a call such as `f(g(x))`: Release Please
  cannot parse it and drops the commit, which the check also reports. Write a
  `Release-As:` version as numbers on the footer's own line, such as
  `Release-As: 1.2.0`: Release Please stops with an error on one it cannot
  read. Editing the body re-runs the check. Release Please and Dependabot PRs
  have no such line and are not checked.
- **Body:** optional prose describing the title's change, then any *extra*
  changelog entries: each a short, imperative, commit-subject-length line at
  column 0 with a bare type token (`fix: short subject`), blank-line separated,
  with any longer explanation on an *optional description line underneath*,
  not packed into the entry line itself. Release Please parses each entry line
  as its own commit subject and will truncate a long one mid-sentence in the
  rendered changelog. A PR body alone never reaches the branch (Release Please
  reads the squash commit), so these lines must also be carried into the merge
  message; see *Squash merges* below. No `-`/`*` bullets, and don't repeat the
  title as an entry.
- **CLI-authored bodies:** create multi-paragraph Markdown in a file passed to
  `gh pr create` or `gh pr edit` with `--body-file`; a shell-quoted `\n` is
  literal text. Before marking a standard PR ready, read it back with
  `gh pr view <n> --json body --jq .body` and verify the paragraphs render.
- **Squash merges:** the squash commit message is all Release Please reads.
  Whatever performs the merge must be given that message, which replaces the
  one GitHub would have generated: the PR's prose, then each extra entry line
  at column 0 and blank-line separated, then any `Release-As:` footer and the
  applicable `Co-Authored-By:` trailers, one per line. The title check judged
  the PR body, so carry its extra entries, `Release-As:` footer and any
  breaking-change note over unchanged: a message that drops or edits them
  changes what Release Please releases. Do not pass an empty message, and do
  not assume the PR description is included. With `gh`, for example:

  ```sh
  gh pr merge <n> --squash --delete-branch --body-file <merge-body.md>
  ```

  With the GitHub MCP server's `merge_pull_request`, pass
  `merge_method: squash` and the message as `commit_message`. A one-line
  message is correct only when the PR body has no extra entry lines,
  `Release-As:` footer or breaking-change notes. Verify the resulting commit
  message after merging (`git log -1 --format=%B`): a dropped entry line is
  otherwise invisible until the release PR is regenerated.
- **Applicable trailers:** a trailer belongs to a commit an AI tool materially
  wrote or changed, and names the tool and model as `AGENTS.md` specifies.
  Carry the squashed commits' trailers into the merge message. Merging a change
  you did not write, such as a Dependabot PR, adds no trailer.
- **Rendered entries:** only `feat` (or its `feature` alias), `fix`, `perf`,
  and `revert` entries render: with no `changelog-sections` configured,
  release-please leaves the section list to the preset it depends on, whose
  defaults hide `docs`, `style`, `chore`, `refactor`, `test`, `build`, and `ci`
  and define no `deps` type at all, so a `docs:`, `ci:`, or `deps:` extra is
  absent from the changelog even when it is delivered.

## Release Please pull requests

Release Please PRs are bot-generated release artifacts, not standard PRs.

- Do not edit their generated title or body merely to apply the standard-PR
  formatting rules.
- When merge is authorized and the required checks and branch-protection
  requirements are satisfied, squash merge using GitHub's default title and
  body content. Do not supply a custom squash title or body, and add no
  co-author trailer: you did not write the release commit.

## Blocked pull requests

When required status checks block a pull request (most often a release PR),
follow `docs/branch-protection-runbook.md` (repository root) and the
`AGENTS.md` rule on the required check set.

## Sources

- Which changelog entries render: release-please v17.6.0 and
  conventional-changelog-conventionalcommits 6.1.0, checked 2026-09-17.
- Which changes Release Please releases (a release needs a rendered entry; a
  breaking change or a `Release-As:` footer renders whatever its type) and
  how it reads a squash body: release-please v17.6.0, the version
  release-please-action v5.0.0 locks, and v17.11.2, with
  conventional-changelog-conventionalcommits 6.1.0, checked 2026-10-18.
- `merge_pull_request` parameters: the `github/github-mcp-server` README,
  checked 2026-10-16.
