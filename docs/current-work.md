# Current work

Dated status for whoever picks this repository up next: work in progress,
decisions and when they were made, and anything deliberately not done yet.
`AGENTS.md` holds the durable rules; status that can go stale belongs here.
Date each entry, and delete it once it no longer applies.

## gh-agent-kit (2026-10-27)

gh-agent-kit v0.1.0 is installed, with the settings in
`.github/gh-agent-kit.yml` that the operator chose for every kit repository
on 2026-10-27: `pr-review` reviews each push to a pull request,
`security-scan` scans a pull request when it opens, `issue-triage` triages
issues, and `kit-update-check` opens an issue when a newer kit release is
out. They run beside Codex Cloud's reviews and gate nothing. This repository
keeps its own issue forms (`AGENTS.md`, *Work tracking*). The operator
added the `ANTHROPIC_API_KEY` secret and the labels on 2026-10-27.

## Releases and adoption (2026-10-27)

v0.21.3 (2026-10-27) is the latest release: a comment in
`pr-title-check.yml` says when Dependabot capitalises its pull request
titles ([Upgrading to 0.21.3](upgrading.md#upgrading-to-0213)). v0.21.2
(2026-10-27) has the `review-guidelines` skill tell reviewers to read free
text from the event file, and the `pull-requests` skill keep the merging
account's email address out of squash messages
([Upgrading to 0.21.2](upgrading.md#upgrading-to-0212)). v0.21.1
(2026-10-26) has the title check read the pull request's title and body
from the event file instead of its step env
([Upgrading to 0.21.1](upgrading.md#upgrading-to-0211)). v0.21.0
(2026-10-25) gives new public repositories secret scanning with push
protection, CodeQL default setup and the fork pull request approval policy,
and keeps a managed block of `.gitignore` and `.prettierignore` in step on
adopt ([Upgrading to 0.21.0](upgrading.md#upgrading-to-0210)). v0.20.0
(2026-10-23) added pull request creation limited to collaborators on private
repositories, Dependabot alerts, and conversation resolution in the branch
protection on `main`. Generated repositories take each release in an
adoption round, one `chore: adopt gh-repo-bootstrapper <version>` pull
request per repository; gh-agent-kit adopted 0.21.3 on 2026-10-27.

## Documentation (2026-10-24)

The README is the landing page; the reference that used to follow it lives
in `docs/`, one page per topic, reviewed in pull requests with the code it
describes. The actionlint exceptions this file used to track, with their
evidence from 2026-10-09 to 2026-10-16, are now in
[Existing repositories](existing-repositories.md#prettier-and-actionlint),
since they still apply to every repository that runs actionlint.
