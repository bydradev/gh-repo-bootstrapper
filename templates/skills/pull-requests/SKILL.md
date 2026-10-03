---
name: pull-requests
description: >-
  Use before creating, editing, readying, or merging a pull request, writing a PR title, body, or squash-merge message, handling a Release Please PR, or unblocking a PR stuck on required checks. Covers squash-merge and Release Please changelog rules, CLI-authored bodies, Co-Authored-By trailers in merge bodies, and the branch-protection runbook. Merge still requires explicit authorization.
---

# Pull requests (squash-merge + Release Please)

## Standard pull requests

Standard PRs are squash-merged and parsed by Release Please — write them
merge-ready:

- **Title** — one Conventional Commit subject naming one concrete change, not a
  label summarizing several bundled changes (e.g. not
  `fix: address review follow-ups (path handling, branch protection, clone retry)`
  — that's a summary, not a change). If a PR bundles multiple distinct fixes,
  title it after the single most significant one and list the rest as extra
  changelog entries below, or split the PR. The title becomes the squash
  subject, the changelog entry, and the version-bump signal.
- **Body** — optional prose describing the title's change, then any *extra*
  changelog entries: each a short, imperative, commit-subject-length line at
  column 0 with a bare type token (`fix: short subject`), blank-line separated,
  with any longer explanation on an *optional description line underneath* —
  not packed into the entry line itself. Release Please parses each entry line
  as its own commit subject and will truncate a long one mid-sentence in the
  rendered changelog. A PR body alone never reaches the branch — Release Please
  reads the squash commit — so these lines must also be carried into the merge
  body; see *Squash merges* below. No `-`/`*` bullets, and don't repeat the
  title as an entry.
- **CLI-authored bodies** — create multi-paragraph Markdown in a file passed to
  `gh pr create` or `gh pr edit` with `--body-file`; a shell-quoted `\n` is
  literal text. Before marking a standard PR ready, read it back with
  `gh pr view <n> --json body --jq .body` and verify the paragraphs render.
- **Squash merges** — the body given to `gh pr merge --squash` (`--body`, or
  `--body-file` to match the rule above) *becomes* the squash commit message: it
  replaces whatever GitHub would have generated, and that message is the only
  thing Release Please reads. It must therefore carry the extra changelog entry
  lines *and* every applicable `Co-Authored-By:` trailer — do not pass an empty
  body, and do not assume the PR description is included. Write the prose, then
  each entry line at column 0 and blank-line separated, then the trailers:

  ```sh
  gh pr merge <n> --squash --delete-branch --body-file <merge-body.md>
  ```

  where `<merge-body.md>` holds the PR's prose and entry lines followed by, for
  example:

  ```markdown
  Co-Authored-By: Antigravity CLI (Gemini 3.8 Flash (High)) <224641728+gemini-cli-robot@users.noreply.github.com>
  ```

  If multiple co-authors or manual commits are squashed, include each applicable
  `Co-Authored-By:` trailer separated by newlines. A one-line `--body` is
  correct only when the PR has no extra entry lines. Only `feat` (or its
  `feature` alias), `fix`, `perf`, and `revert` entries render: with no
  `changelog-sections` configured, release-please leaves the section list to the
  preset it depends on, whose defaults hide `docs`, `style`, `chore`, `refactor`,
  `test`, `build`, and `ci` and define no `deps` type at all — so a `docs:`,
  `ci:`, or `deps:` extra is absent from the changelog even when it is delivered.
  (Verified against release-please v17.6.0 and
  conventional-changelog-conventionalcommits 6.1.0, 2026-09-17.) Verify the resulting commit message after merging
  (`git log -1 --format=%B`): a dropped entry line is otherwise invisible until
  the release PR is regenerated.

## Release Please pull requests

Release Please PRs are bot-generated release artifacts, not standard PRs.

- Do not edit their generated title or body merely to apply the standard-PR
  formatting rules.
- When merge is authorized and the required checks and branch-protection
  requirements are satisfied, squash merge using GitHub's default title and
  body content. Do not supply a custom squash title or body.
- Do not add an AI co-author trailer unless it is already applicable to the
  release commit itself.

- **Blocked pull requests** — when a pull request is blocked by required
  status checks (most often a release PR), follow
  `docs/branch-protection-runbook.md` (repository root);
  never weaken the required check set to land a change.
