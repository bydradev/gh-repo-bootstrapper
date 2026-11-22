# Current work

Dated status for whoever picks this repository up next: work in progress,
decisions and when they were made, and anything deliberately not done yet.
`AGENTS.md` holds the durable rules; status that can go stale belongs here.
Date each entry, and delete it once it no longer applies.

## gh-agent-kit (2026-11-17)

gh-agent-kit v0.5.0 is installed, with the settings in
`.github/gh-agent-kit.yml` that the operator chose for every kit repository
on 2026-10-27: `pr-review` reviews each push to a pull request,
`security-scan` scans a pull request when it opens, `issue-triage` triages
issues, and `kit-update-check` opens an issue when a newer kit release is
out. They run beside Codex Cloud's reviews and gate nothing. The install
keeps this repository's own issue forms (`--issue-forms=own`; `AGENTS.md`,
*Issue forms*). The operator added the `ANTHROPIC_API_KEY` secret and the
labels on 2026-10-27; the update from v0.1.0 that day changed no label.

On 2026-10-28 the review, scan and triage moved to OpenCode Go, on its
default model `deepseek-v4.1-flash`: `KIT_REVIEW_PROVIDER`,
`KIT_SECURITY_PROVIDER` and `KIT_TRIAGE_PROVIDER` are `opencode-go` and
`KIT_REVIEW_MAX_TURNS` is 120 in `.github/gh-agent-kit.yml`. The operator
added the `OPENCODE_API_KEY` secret that day; `ANTHROPIC_API_KEY` stays
set, unused while the providers are `opencode-go`.

On 2026-10-28 the kit was updated to v0.4.0 (from v0.3.1). On OpenCode Go
the review, scan and triage now run in OpenCode's CLI, since the runner
follows the provider; before, they ran in Claude Code on Go. The triage
and review skills set out their decision steps case by case, and a claim
comment on an issue carries no session link. The install kept this
repository's own issue forms, and no setting, secret or label changed.

On 2026-10-29 the kit was updated to v0.4.1: a run that ends in error
prints the end of OpenCode's log, and triage puts `.git` back in the
checkout after its run. No setting, secret or label changed.

On 2026-11-17 the kit was updated to v0.5.0. A bug or feature the operator
asks for directly now gets an issue first, labelled `requested`, filed with
the new `github-issue-file` skill. The new `pr-issue-link` workflow checks
that a pull request says `Closes #<n>` or `No issue:`; it stays off until
`KIT_ISSUE_LINK_CHECK` is `on`, which is not set here. The labels go from 15
to 13: `requested` is added, and `ready`, `blocked` and `docs` are dropped,
which `.github/scripts/sync-labels.sh --migrate` applies once this update
is on `main`. When OpenCode Go turns a request away as at capacity, the
review, scan and triage wait 60, 120 and then 180 seconds for each refusal
in a row (or the time the refusal names, when longer), start the count
again once a step is served, and stop when the wait would not fit the
step's `KIT_*_TIMEOUT_MINUTES` less a 300-second reserve. The installer now
writes the *Work tracking* section of `AGENTS.md` between its markers; this
repository's own lines moved to *Issue forms* and *Kit workflows in
validation* after it.

## Releases and adoption (2026-11-22)

[v0.25.1](https://github.com/bydradev/gh-repo-bootstrapper/releases/tag/v0.25.1)
is the latest release. It fixes a partial-adoption case in which a hub could
refer to a commit skill that was not installed; its templates match v0.25.0.
[v0.25.0](https://github.com/bydradev/gh-repo-bootstrapper/releases/tag/v0.25.0)
shortened the generated agent hub and review guidance. See
[Upgrading](upgrading.md) and the [changelog](../CHANGELOG.md) for the
release history.

The v0.25.0 shared agent instructions were selectively rolled out to seven
downstream repositories, preserving each repository's own instructions and
leaving other template drift for audit. The rollout also updated installations
of gh-agent-kit to v0.7.0.

As of 2026-11-22, audit follow-up pull requests in private repositories
include 11 merged, 17 open and ready for review, and one closed without
merging after a slower runner trial. A further repository's audit is pending.
In the public gh-agent-kit repository,
[#79](https://github.com/bydradev/gh-agent-kit/pull/79) is open and ready
for review.

## Documentation (2026-10-24)

The README is the landing page; the reference that used to follow it lives
in `docs/`, one page per topic, reviewed in pull requests with the code it
describes. The actionlint exceptions this file used to track, with their
evidence from 2026-10-09 to 2026-10-16, are now in
[Existing repositories](existing-repositories.md#prettier-and-actionlint),
since they still apply to every repository that runs actionlint.
