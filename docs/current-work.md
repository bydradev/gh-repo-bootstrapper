# Current work

Dated status for whoever picks this repository up next: work in progress,
decisions and when they were made, and anything deliberately not done yet.
`AGENTS.md` holds the durable rules; status that can go stale belongs here.
Date each entry, and delete it once it no longer applies.

## gh-agent-kit (2026-10-27)

gh-agent-kit v0.4.1 is installed, with the settings in
`.github/gh-agent-kit.yml` that the operator chose for every kit repository
on 2026-10-27: `pr-review` reviews each push to a pull request,
`security-scan` scans a pull request when it opens, `issue-triage` triages
issues, and `kit-update-check` opens an issue when a newer kit release is
out. They run beside Codex Cloud's reviews and gate nothing. The install
keeps this repository's own issue forms (`--issue-forms=own`; `AGENTS.md`,
*Work tracking*). The operator added the `ANTHROPIC_API_KEY` secret and the
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

On 2026-10-29 the kit was updated to v0.4.1. When OpenCode Go turns a
request away as at capacity, the review, scan and triage now wait the time
the refusal names and carry on in the same session, up to three times in a
step, and a run that ends in error prints the end of OpenCode's log. Triage
also puts `.git` back in the checkout after its run. No setting, secret or
label changed.

## Releases and adoption (2026-11-12)

v0.23.3 is the latest release. v0.23.0 (2026-11-11) added
`--type android`, and changed nothing for the other types. v0.23.1 to
v0.23.3 fix the Android type: its pull request checks stop with a clear
error when the Spotless plugin is missing, its guidance fits any app
instead of one app's SDK levels, and its `test.yml` validates the Gradle
wrapper and caches Gradle
([Upgrading to 0.23.3](upgrading.md#upgrading-to-0233)). v0.22.0
(2026-10-28) shortened the generated skills. Generated repositories take
each release in an adoption round, one `chore: adopt gh-repo-bootstrapper
<version>` pull request per repository; gh-agent-kit adopted 0.22.0 on
2026-10-29. No adoption round has run since, because 0.23.x changes only
the Android type. Older releases are in the
[changelog](../CHANGELOG.md) and [Upgrading](upgrading.md).

## Documentation (2026-10-24)

The README is the landing page; the reference that used to follow it lives
in `docs/`, one page per topic, reviewed in pull requests with the code it
describes. The actionlint exceptions this file used to track, with their
evidence from 2026-10-09 to 2026-10-16, are now in
[Existing repositories](existing-repositories.md#prettier-and-actionlint),
since they still apply to every repository that runs actionlint.
