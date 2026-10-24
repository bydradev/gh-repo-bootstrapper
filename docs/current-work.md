# Current work

Dated status for whoever picks this repository up next: work in progress,
decisions and when they were made, and anything deliberately not done yet.
`AGENTS.md` holds the durable rules; status that can go stale belongs here.
Date each entry, and delete it once it no longer applies.

## Releases and adoption (2026-10-24)

v0.20.0 (2026-10-23) is the latest release. It adds three settings to new
repositories: pull request creation limited to collaborators on private
repositories, Dependabot alerts, and conversation resolution in the branch
protection on `main` ([Upgrading to 0.20.0](upgrading.md#upgrading-to-0200)).
Generated repositories take each release in an adoption round, one
`chore: adopt gh-repo-bootstrapper <version>` pull request per repository;
the 0.20.0 round has not started and waits for the operator.

## Documentation (2026-10-24)

The README is the landing page; the reference that used to follow it lives
in `docs/`, one page per topic, reviewed in pull requests with the code it
describes. The actionlint exceptions this file used to track, with their
evidence from 2026-10-09 to 2026-10-16, are now in
[Existing repositories](existing-repositories.md#prettier-and-actionlint),
since they still apply to every repository that runs actionlint.
