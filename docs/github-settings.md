# GitHub settings

When `bootstrap.py` creates a repository it also applies GitHub settings
to it, and `--configure-only` applies them to a repository that already
exists. This page lists those settings, and then covers the GitHub App that
Release Please runs as.

## What the script configures

Beyond file generation, the script applies GitHub configuration to the repo:

- **Merge strategy:** squash-merge only; merge commits and rebase disabled,
  and the default squash commit title and message are set to the PR title and
  body (the Conventional Commits text Release Please parses)
- **Delete branch on merge:** enabled automatically
- **Always suggest updating pull request branches:** enabled
- **Projects:** enabled
- **Actions permissions:** restricted to GitHub-owned and Marketplace-verified
  actions, plus an explicit allowlist for `amannn/action-semantic-pull-request`
  (used by `pr-title-check.yml`) and, for `--type rust`, `dtolnay/rust-toolchain`
  and `Swatinem/rust-cache` (used by `test.yml`; both are user-owned, so the
  verified-creator rule does not cover them). Every action must also be pinned
  to a full commit SHA (`sha_pinning_required`).
- **Workflow permissions:** default `read`, with GitHub Actions unable to
  approve pull requests. Release Please uses its dedicated GitHub App token.
- **Fork PR workflows:** disabled for private repos. A public repo runs
  them, and its approval policy is set to *Require approval for all external
  contributors* (`all_external_contributors`): a fork pull request from
  anyone without write access waits for a maintainer before its workflows
  run, so it cannot spend Actions minutes or an API key's credits unseen.
  GitHub's default asks only first-time contributors. Endpoint from
  [GitHub Actions permissions](https://docs.github.com/en/rest/actions/permissions),
  read 2026-10-24.
- **Pull request creation:** limited to collaborators (users with write
  access) on a private repo; a public repo stays open to outside pull
  requests, which only someone with write access can merge. Dependabot still
  opens its pull requests (a GitHub staff answer in
  [community discussion 187038](https://github.com/orgs/community/discussions/187038),
  2026-02-24), and so does Release Please with its GitHub App's token (seen on
  a private repository with the setting on, 2026-10-21). On a personal
  account every collaborator has write access, so the setting changes most on
  an organization's private repo, where read and triage roles exist.
- **Dependabot alerts:** turned on, which Dependabot malware alerts need.
- **Secret scanning and push protection** (public repos): turned on.
  Both are free on a public repo, but the repository's `security_and_analysis`
  settings report them disabled until they are turned on (seen on this
  repository after it went public, 2026-10-24). Setting them needs admin
  access to the repository
  ([Update a repository](https://docs.github.com/en/rest/repos/repos#update-a-repository),
  `security_and_analysis`, read 2026-10-24).
- **CodeQL default setup** (public repos): configured, with GitHub's default
  languages and query suite. It needs GitHub Actions enabled and analyses
  the languages GitHub detects, workflows included
  ([Update a code scanning default setup configuration](https://docs.github.com/en/rest/code-scanning/code-scanning#update-a-code-scanning-default-setup-configuration),
  [Configuring default setup](https://docs.github.com/en/code-security/code-scanning/enabling-code-scanning/configuring-default-setup-for-code-scanning),
  read 2026-10-24).
- **Branch protection on `main`:** requires the relevant status checks to pass
  before merging, and requires a pull request with **zero** required approving
  reviews. That combination is deliberate: direct pushes to `main` are blocked
  (enforcing the convention in the generated `AGENTS.md`) without demanding
  self-review on a solo repository. `enforce_admins: true`, so the gates bind
  the account doing the merging; `strict` is left false, because a
  "branch must be up to date" requirement strands every open PR (release PRs
  worst) on each advance of `main`. Every review conversation must be
  resolved before a merge (`required_conversation_resolution`). The runbook
  for PRs blocked by those checks, most often release PRs, or by unresolved
  conversations is a short symptom, check and action procedure at
  [`docs/branch-protection-runbook.md`](branch-protection-runbook.md)
  and ships into every generated repository. The incident behind several of
  its rules, with its run IDs and SHAs, is kept only in this repository, in
  [`docs/archive/branch-protection-incident.md`](archive/branch-protection-incident.md).

GitHub has no API for two more settings (checked 2026-10-23), so the script
lists them at the end, and in `--dry-run`, to set by hand under *Settings >
Advanced Security*:

- **Dependabot malware alerts:** on.
- **Auto-triage preset** *dismiss low-impact alerts for development-scoped
  dependencies*: off. GitHub turns it on by default only for public repos.
  With it off, an unfixable development advisory stays an open alert until it
  has an advisory-baseline row; with it on, nothing checks an alert it
  dismissed.

With `--configure-only` the repository already exists, so three of these are
handled differently. Branch protection on `main` is never replaced: the script
prints the required checks it finds and whether conversation resolution is
required, and points to the runbook, because an existing repository's checks
must come from its own pull requests, not from `--type`. The Actions settings
(allowlist, SHA pinning, default token permissions and fork PR controls, or
for a public repository its fork PR approval policy) are compared with the
generated policy; any difference is listed and applied only after you
confirm, and `--non-interactive` lists it and leaves it unchanged. Pull
request creation (private repositories), Dependabot alerts, and secret
scanning, push protection and CodeQL default setup (public repositories) are
compared the same way, with their own confirmation, since limiting pull
requests to collaborators stops outside contributors on a repository that
takes them, and push protection blocks a push that carries a secret.

These settings are applied one at a time and nothing is rolled back. If one
fails after the files are pushed, the script lists the settings it applied and
the ones it did not, and prints the `--configure-only` command that applies
the rest. A failed pull request creation, Dependabot alerts, secret scanning
or CodeQL setting is only reported, so the steps after it, branch protection
included, still run.

GitHub requires a paid plan for branch protection on **private**
repositories. The script detects that case and reports it as manual follow-up
rather than failing.

## GitHub App for Release Please

Release Please runs via a GitHub App rather than the default `GITHUB_TOKEN` so
it can open PRs that trigger other workflows. In every type but `simple`, the
untested-merge guard before it reads with the workflow's `GITHUB_TOKEN`, and the
App token goes only to `release-please-action`. The guard lists merged release
pull requests with `gh pr list --label`, which searches through GraphQL, and
compares commits. No docs page states the permission that search needs (the
REST search endpoint for issues and pull requests requires none,
[Search issues and pull requests](https://docs.github.com/en/rest/search/search#search-issues-and-pull-requests),
read 2026-10-22), so the release job declares `contents: read` and
`pull-requests: read`, the reads the REST endpoints for the same data require
([List pull requests](https://docs.github.com/en/rest/pulls/pulls#list-pull-requests),
[Compare two commits](https://docs.github.com/en/rest/commits/commits#compare-two-commits),
checked 2026-10-21). That is inferred, and has not yet been run on a private
repository. A job-level block replaces the workflow's, so both are listed. You
will need to supply:

- `RELEASE_PLEASE_CLIENT_ID`: set as a GitHub variable
- `RELEASE_PLEASE_APP_KEY`: set as a GitHub secret

The script prompts for these interactively, or reads them from environment
variables in `--non-interactive` mode. The App key is the complete multi-line
PEM file GitHub gives you, so the interactive prompt asks for the path to that
`.pem` file rather than its text: a one-line prompt keeps only the first line
of a pasted key. In either mode, a value that is not a complete, unencrypted
RSA private key in PKCS#1 (`BEGIN RSA PRIVATE KEY`) or PKCS#8
(`BEGIN PRIVATE KEY`) PEM form (for example one
cut short before its `-----END … PRIVATE KEY-----` line, one missing lines of
key data, or one converted to the OpenSSH format) is refused instead of being stored as a secret that fails on the
first release. A `--dry-run` stores nothing, so it does not check the key. The path is read without echo, like a password, so a key pasted there
by mistake is not shown; type it as plain text, without the quotes or
backslashes a terminal adds when a file is dragged onto it. In
`--non-interactive` mode, a key stored on one line with literal `\n`
separators is accepted and turned back into PEM lines.

Until both are set, `release-please.yml` skips the release instead of failing.
The release job's first step, "Check Release Please credentials", adds a
warning annotation to the run that names `RELEASE_PLEASE_CLIENT_ID` and
`RELEASE_PLEASE_APP_KEY` and says releases are skipped until both are set; the
token and release steps after it are skipped, and the job passes. In every
type but `simple`, the `test` job in the same workflow still runs and still
gates the release. A run with that warning has not released anything. The
same happens when both exist but the run cannot read them: an organization
secret whose access policy leaves the repository out
([Secrets](https://docs.github.com/en/actions/concepts/security/secrets)), or
a run that Dependabot triggers, which gets only Dependabot secrets
([Dependabot on GitHub Actions](https://docs.github.com/en/code-security/reference/supply-chain-security/troubleshoot-dependabot/dependabot-on-actions)),
both checked 2026-10-16. The check reads only whether each value is set,
because GitHub does not allow secrets in `if:` conditions
([Using secrets in GitHub Actions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets),
checked 2026-10-16). `release-please.yml` is template-owned, so `--adopt`
brings the check to existing repositories; a repository whose release
workflow is `local-modified` keeps its own behaviour. In a `nextjs`
repository, the weekly baseline review reports a successful run that skipped
the release this way as `Release pipeline: not configured`, and fails, until
a run can read both.

Once both are set, the next push to `main` runs the release; check that it
creates or updates a release PR before treating release automation as
operational. In every type but `simple`, a release PR merged while the
credentials were missing is not released by a later push: the untested-merge
guard fails each later run, because none of them tested that merge. Re-run
the merge's own workflow run instead, and check that its release job no
longer warns. GitHub allows a re-run up to 30 days after the original run
([Re-running workflows and jobs](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs),
checked 2026-10-16). If the re-run still warns, or the run is too old, remove
the `autorelease: pending` label from that release PR to abandon the release,
then fix forward.

If you skip them during setup, set them manually afterwards, reading the key
from its file:

```sh
gh variable set RELEASE_PLEASE_CLIENT_ID --repo owner/name --body "<app-client-id>"
gh secret set RELEASE_PLEASE_APP_KEY --repo owner/name < path/to/app-key.pem
```

The same command replaces a key that an earlier version stored with only its
first line.
