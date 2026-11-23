# Current work

Dated status for whoever picks this repository up next: work in progress,
decisions and when they were made, and anything deliberately not done yet.
`AGENTS.md` holds the durable rules; status that can go stale belongs here.
Date each entry, and delete it once it no longer applies.

## gh-agent-kit (2026-11-23)

gh-agent-kit v0.7.0 is installed (`.github/gh-agent-kit.lock`, ref
`4f62668e`, updated on 2026-11-20 from v0.5.0). The operator chose its
settings for every kit repository on 2026-10-27: `pr-review` reviews each push
to a pull request, `security-scan` scans a pull request when it opens,
`issue-triage` triages issues, and `kit-update-check` opens an issue when a
newer kit release is out. They run beside Codex Cloud's reviews and gate
nothing. `pr-issue-link` stays off, since `KIT_ISSUE_LINK_CHECK` is not set.
The install keeps this repository's own issue forms (`--issue-forms=own`;
`AGENTS.md`, *Issue forms*). Since v0.6.0 the bots' posts are held to the
public-content check.

The review, scan and triage run on Anthropic: the repository variables
`KIT_REVIEW_PROVIDER`, `KIT_SECURITY_PROVIDER` and `KIT_TRIAGE_PROVIDER` were
set to `anthropic` on 2026-11-18. They override the `opencode-go` values still
in `.github/gh-agent-kit.yml`. On the kit's default models, review and scan
use `claude-opus-5-5` and triage uses `claude-sonnet-5-5` (seen in a triage
run on 2026-11-23). The `ANTHROPIC_API_KEY` and `OPENCODE_API_KEY` secrets are
both set.

The triage bot never plans an issue that `github-actions[bot]` opened, such as
an out-of-scope finding that `pr-review` files, and `github-issue-e2e` accepts
only the bot's plan. Such an issue is worked only on the operator's waiver or
after being re-filed, until bydradev/gh-agent-kit#80 is resolved (recorded
2026-11-23).

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
