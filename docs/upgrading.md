# Upgrading

What changes for an existing repository with each release, newest first.
Read the notes for every release between the one the repository was last
adopted at and the current one, then run `--check` and `--adopt` as
[Existing repositories](existing-repositories.md) describes. The
[changelog](../CHANGELOG.md) lists every change; these notes cover what a
repository has to do or decide.

## Upgrading to 0.21.2

Every type: the `review-guidelines` skill tells reviewers that a workflow
reads free text such as a pull request title, body or comment from the event
file, and passes only short values such as numbers and SHAs through `env:`,
whose values the runner prints in the job log. `--check` reports
`.agents/skills/review-guidelines/SKILL.md` as `stale`, and `--adopt`
updates it. Nothing else changes.

## Upgrading to 0.21.1

Every type: the title check's user-visible step in `pr-title-check.yml`
reads the pull request title and body from the event file instead of its
`env:`. The runner prints a step's env values in the job log, so each run
kept a copy of the body as it was when the run fired, public in a public
repository. The check itself is unchanged and no action pin changes:
`--check` reports `pr-title-check.yml` as `stale`, and `--adopt` updates
it. Logs of earlier runs still hold those copies; deleting the runs is the
only way to remove them.

## Upgrading to 0.21.0

A new public repository gets three more settings: secret scanning with push
protection, CodeQL default setup, and the fork pull request approval policy
set to require approval for all external contributors. See
[What the script configures](github-settings.md#what-the-script-configures).

`--configure-only` on an existing public repository shows how these differ
and asks before changing them: secret scanning and CodeQL with the pull
request and Dependabot settings, the fork approval policy with the Actions
policy. `--non-interactive` lists them and leaves them. Say no to CodeQL
default setup on a repository that runs CodeQL from its own workflow file:
default setup turns that workflow off, and a required check it reports
would then never arrive. Private repositories
are unchanged.

`nextjs`: the weekly Baseline review also checks the `Expires` field of
`public/.well-known/security.txt` when the repository has one. RFC 9116
makes the field mandatory and the file stale once it passes ([RFC 9116,
section 2.5.5](https://www.rfc-editor.org/rfc/rfc9116.html#section-2.5.5),
checked 2026-10-25). An expired, missing or invalid field, or a file that
cannot be read, is actionable; an expiry within 30 days is listed. A
repository without the file gets one informational line and nothing else
changes. `--adopt` updates unedited copies of `scripts/review-baselines.mjs`
and its test. A repository that added this check to its own copy can take
the template's copy instead, so later releases reach it through `--adopt`:
the template reports a missing file as informational, not actionable. The
`baseline-process` skill describes the check; `--check` reports it as
`stale`, and `--adopt` updates it.

Every type: `.gitignore`, and for `nextjs` `.prettierignore`, now end with a
block between `# >>> gh-repo-bootstrapper managed block` and
`# <<< gh-repo-bootstrapper managed block` that `--adopt` keeps in step with
the template, so the entries the template's own files need no longer go in
by hand. It holds `.playwright-cli/` and `.playwright-mcp/` in `.gitignore`
and the three template-owned workflows in `.prettierignore`. `--check`
reports a file without the block as `differs`, and `--adopt` appends it,
unless a `!` rule above it names one of the block's entries, or
the file has uncommitted changes (see [Existing
repositories](existing-repositories.md#gitignore-and-prettierignore)). A
repository that added those lines by hand gets them twice; `--adopt` names
the lines outside the block, which can go. Other template entries missing
outside the block are still listed for a person to add; for
`.prettierignore` they now count as drift instead of any difference from the
template, so its own rules outside the block no longer do. Rust and swift
`--xcodegen` renders put their extra `.gitignore` lines before the block.

## Upgrading to 0.20.0

A new repository gets three more settings: pull request creation limited to
collaborators (private repositories only), Dependabot alerts turned on, and
conversation resolution required in the branch protection on `main`. The
script then lists the two settings GitHub has no API for, to set by hand:
Dependabot malware alerts on, and, on a public repository, the auto-triage
preset that dismisses low-impact alerts for development-scoped dependencies
off. See [What the script configures](github-settings.md#what-the-script-configures).

`--configure-only` on an existing repository shows how its pull request
creation (private repositories) and Dependabot alerts differ and asks before
changing them; `--non-interactive` lists them and leaves them. It reports
whether the branch protection requires conversation resolution and, as
before, never changes the protection.

The branch protection runbook gains a section on pull requests blocked by
unresolved review conversations, and the `nextjs` `baseline-process` skill
says to keep that auto-triage preset off and to record an unfixable
development advisory whose alert it dismissed. `--check` reports both as
`stale`, and `--adopt` updates them.

## Upgrading to 0.19.2

`validate_templates.py` reads the releases for its `SEED_DIGESTS` check the way
`--check` and `--adopt` do since 0.19.1: each read gives up after 10 seconds,
and in a partial clone of the bootstrapper, with a git that knows
`GIT_NO_LAZY_FETCH`, it does not fetch a missing object from the remote.
Either one fails the check, and makes
`--regenerate-seed-digests` exit 1, instead of rebuilding the table without
that release's copy. Generated repositories and `bootstrap.py` runs do not
change.

## Upgrading to 0.19.1

A name whose folder already exists and is not empty is refused as soon as it
is given, typed or with `--name`, before any other question or command,
rather than after the confirmation. A path with a file or a broken symbolic
link where a folder belongs is refused there too, where it used to fail after
`gh repo create` and leave an empty repository behind. Pressing Enter at the
Swift destination question takes `iphone`. Generated repositories do not
change.

`--adopt` names the real cause when git cannot read the repository. Every
file then looked uncommitted, so a stale file was refused with `needs the
file tracked by git with no uncommitted changes` (and an orphaned file or a
seed script with a similar reason) when git's ownership check
(`safe.directory`), an unreadable `.git` or an index git could not open was
the cause. These refusals now say `git cannot read`, the repository and git's
own message. A folder that cannot be listed while the pull request template's
exact spelling is checked is reported as `unreadable` with the folder's name,
as other unreadable folders are, instead of a bare `Permission denied`. No
file is classified, written or refused differently.

`--check` and `--adopt` no longer wait forever on a `git show` of a release
that does not answer, such as one in a partial clone fetching a missing
object from a remote that does not answer or waits on a credential prompt.
Each read of a release now gives up after 10 seconds and stops the fetch it
started: a one-line notice names the read, no more releases are read, and the
diff against earlier releases is skipped, as it is without release tags. No
file is classified or written differently. `validate_templates.py` fails the
`LEGACY_TEMPLATE_DIGESTS` check, and `--regenerate-legacy-digests` exits 1,
instead of rebuilding the table from the releases read before.

In a partial clone of the bootstrapper, those reads no longer fetch a missing
object from its remote, so `--check` and `--adopt` do not contact it. A read
that needs such an object ends the reads the same way, with a notice that names
it, and the diff is skipped; a full clone of the bootstrapper reads every
release as before. This needs a git that knows `GIT_NO_LAZY_FETCH`; an older
one ignores it, fetches as before, and the 10-second limit still applies.

A copy of the bootstrapper with no `.git` of its own, kept inside another
repository that has `vX.Y.Z` tags, some of them v0.8.1 or earlier, read that
repository's tags as releases. None of them holds a bootstrapper template, so
`--check` diffed an unstamped, locally modified workflow against the current
template alone, as if it were the release the workflow was forked from, and
skipped the legacy docs diff without saying so. Both now print the missing-tags
notice, once per run, and skip the diff. No file is classified or written
differently.

`--check` now reports a generated `AGENTS.md` section that comes only after
the first `## Project specifics` heading as `local`, for example
`(generated heading after ## Project specifics: ## Branches)`. This happens
when a second, early `## Project specifics` heading sits before or among the
generated sections, or when the only one does. Everything from that heading
on belongs to the repository, so `--adopt` used to report those sections as
`missing`, add them again above it and keep the old copies below, which split
the file. It now refuses the rebuild, with or without
`--replace-generated-sections`, and leaves the file as it is, byte for byte.
Keep one `## Project specifics` heading, after every generated section, then
re-run `--adopt`. A repository's own section that shares the name of the
template's last generated section, such as `## Skills`, under its one
`## Project specifics` heading, reads the same way while the generated part
lacks that section; rename it to adopt.

The YAML reader `--adopt` uses on a repository's own `test.yml` now refuses
a flow sequence with a lone `-` item, such as `[- , "a"]` or `[a, -]`, which
YAML does not allow, instead of reading the `-` as an item. Such a file is
reported as outside the subset it reads, with the line's number, as other
YAML it does not model is. Flow items that start with `-`, such as `-a`, and
a quoted `"-"` are read as before.

`pr-title-check.yml` now also reads the body as GitHub's default squash commit
ends it. That commit can add a line of dashes and the commits' `Signed-off-by`
and `Co-authored-by` trailers after the body, and Release Please 17.6.0 then
reads the body's trailing footers as body text. A change that only such a
footer releases, such as a `Release-As:` footer under a `chore:` title, a
`Fix:` footer or `BREAKING CHANGE #12`, therefore fails the check with either
answer. Give the release to the title or to an extra entry that opens a
paragraph, write a `BREAKING CHANGE:` note, or put the whole commit message in
a `BEGIN_COMMIT_OVERRIDE` block, which the squash block does not reach. A
`Release-As:` version that only such a footer carries also fails, since
Release Please would propose another one; only the override block keeps it.
The block can also make a release: a breaking-change token that gives no note
as the body stands, such as an empty `BREAKING CHANGE:` footer or a
`BREAKING-CHANGE:` at the end of a line of prose, can give one, and that fails
the check with either answer too. `--check`
reports `pr-title-check.yml` as `stale`, and `--adopt` updates it; no action
pin changes. The `pull-requests` skill gives the same advice, so it is
`stale` too until `--adopt` updates it.

The release workflow's `actions/create-github-app-token` moves to v3.3.0
(from v3.2.0), the newest release at least 7 days old, as the Dependabot
cooldown waits. v3.3.0 adds three `permission-*` inputs and removes
`permission-team-discussions`; the templates set only `client-id`,
`private-key`, `permission-contents` and `permission-pull-requests`, which do
not change. A new repository gets the new pin. An existing one keeps its own,
since a workflow's digest ignores the version after `@` and `--adopt` keeps
the repository's pins: its Dependabot brings the bump, and `--check` reports
no change.

## Upgrading to 0.19.0

The `--check` report widens its state column to fit `local-modified`, its
longest state, so every path starts in the same column; a script that reads
the report by fixed position needs the new width. The state table in
[Existing repositories](existing-repositories.md#checking-and-adopting)
gains the `other-type` row the report already printed.

`python`: the uv that `test.yml` installs for every `uv.lock` project moves
to 0.13.1, and the ruff it falls back to when the project does not bring its
own moves to 0.17.1 (from 0.12.24 and 0.16.10), each the newest release at
least 7 days old, as the Dependabot cooldown waits. uv 0.13 still installs a
`uv.lock` written by 0.12 with `uv sync --locked`. Ruff 0.17 changes its
defaults: Python 3.11 when no version is configured, seven `flake8-datetimez`
rules (DTZ001, DTZ005 to DTZ007, DTZ011, DTZ012 and DTZ901) out of the
default set and F406 in, and trailing pragma comments no longer count toward
line length, which can reformat imports. A project that relies on the ruff
fallback runs `ruff format .` and `ruff check .` with 0.17.1 before taking
the change. `test.yml` belongs to
the repository, so `--check` reports it as `differs` and `--adopt` keeps it;
copy the two pins from the template by hand.

`nextjs`, `rust`, and every type's `pull-requests` skill and
`pr-title-check.yml`: dated sources move to the versions they were re-checked
against (Next.js 16.4.2, Playwright 1.64.1, cargo 1.99.1, and
node-html-parser 6.1.11, which release-please-action v5.0.0 bundles), with no
change in what they say. `--check` reports those skills and the workflow as
`stale`, and `--adopt` updates them.

`nextjs`: when the repository's own `test.yml` differs from the render,
`--check` adds a line under its row saying whether the file and the render
each have a Postgres service, so a `--postgres` that does not match the
repository shows. The check still only reads; nothing else changes.

## Upgrading to 0.18.0

`nextjs`: the `local-validation-nextjs` skill gains an *Agent browser checks*
section. Where `@playwright/test` is installed, it sends agents to the
Playwright CLI that package ships (`npx --no-install playwright cli`) and to
the skill file in `node_modules` that matches the installed version, rather
than a vendored or linked copy, which would drift from the installed version
or break in a checkout without `node_modules`. It asks for Playwright's
Chromium, a session name of each agent's own, a local server with fixture or
test data only, `--debug=cli` to inspect a failing test, and no
`init-agents`, `init-skills` or `cli install`, and it keeps the CLI's output
in its ignored folder and out of commits. `--check` reports the skill as
`stale` and `--adopt` updates it.

Every type: the template `.gitignore`, which all types share, adds
`.playwright-cli/` and `.playwright-mcp/`, where the Playwright CLI and MCP
server write a session. For an existing `.gitignore`, `--check` reports it as
`differs` with the two missing entries and `--adopt` lists them without
writing them, so add them by hand in the adoption pull request.

## Upgrading to 0.17.2

The user-visible step in `pr-title-check.yml` now reads the body as GitHub's
default squash commit holds it. GitHub refills a body line over 72 characters
into lines of at most 72, and a wrap that starts a line with a word and an
unclosed parenthesis, such as `` `hashFiles( ``, made Release Please drop the
change from the changelog while the step passed. The step now fails and names
the long line. A long line in a code fence and indented four spaces is left
as written; one with only a fence or only the indent is still checked as
wrapped, since GitHub's rule for those was not observed. A
`BEGIN_COMMIT_OVERRIDE` block is still read unwrapped, as Release Please reads
it from the pull request body. The `pull-requests` skill says to break such a
line by hand. `--check` reports `pr-title-check.yml` and the skill as `stale`,
and `--adopt` updates them; no action pin changes.

## Upgrading to 0.17.1

The OpenCode reviewer, `.opencode/agents/fresh-eyes-reviewer.md`, now denies
`shell` beside `bash`, so it still has no shell once OpenCode renames the
permission key, and sets `external_directory: ask`, so it asks before reading
outside the project on OpenCode V2, which allows that by default. On V1 it now
also asks for directories that OpenCode's defaults or your own `opencode.json`
allow, such as OpenCode's temporary directory. The `fresh-eyes-review`
skill cites
[OpenCode issue 49723](https://github.com/anomalyco/opencode/issues/49723)
instead of 50627, which was closed on 2026-10-20 as its duplicate. Both files
are template-owned: `--check` reports them `stale` and `--adopt` updates them.

## Upgrading to 0.17.0

`nextjs`: the generated `.prettierignore` now lists
`.github/workflows/pr-title-check.yml`, `.github/workflows/release-please.yml`
and `.github/workflows/baseline-review.yml`, which are template-owned and must
stay verbatim. Before, a scaffold whose `format:check` is `prettier --check .`
covered all three, and a Prettier release that formats YAML differently from
the template text would have failed it. Reformatting a template-owned workflow
to pass would make it `local-modified`, which `--adopt` never overwrites.
Prettier can format the same text differently between releases, patch releases
included ([Install](https://prettier.io/docs/install), Prettier docs, checked
2026-10-21). `.prettierignore` belongs to the repository, so `--adopt` keeps it
and `--check` reports it as `differs`: add the three paths to it by hand, one
per line. `--check` compares the file byte for byte, so it goes on reporting
`.prettierignore` (and `README.md`, which also changed) as `differs` and exiting
1 afterwards, as for other repository-owned files that differ from the template;
the row clears only when the file matches the template, comment included.
`ci.yml` and `test.yml` belong to the repository and stay formatted. The
generated `README.md` of a new repository says the same; an existing one keeps
its own.

Every type's generated `release-please-config.json` now sets
`"bump-minor-pre-major": true`, beside `include-component-in-tag`. While a
repository is below 1.0.0, a breaking change (`feat!`, `chore!` or a
`BREAKING CHANGE:` footer) now proposes the next minor, such as 0.17.0 from
0.16.0, where Release Please proposes 1.0.0 without the option; at 1.0.0 or
above the option has no effect
([manifest releaser documentation](https://github.com/googleapis/release-please/blob/main/docs/manifest-releaser.md),
release-please 17.6.0 `versioning-strategies/default.js`, which
release-please-action v5.0.0 locks, checked 2026-10-21).
`release-please-config.json` belongs to the repository, so `--adopt` keeps it,
and a repository generated before 0.17.0 takes the change by hand: one that
means to stay below 1.0.0 adds `"bump-minor-pre-major": true,` at the top level
of the file, beside `include-component-in-tag`, and one that wants 1.0.0 from
its next breaking change leaves it out. `--check` compares the whole file, so
it reports the file as `differs`, and exits 1, until it matches the template.
An unedited config reads `same` again once the line is added. One that leaves
the line out stays `differs`, as does one with other edits, such as an
`extra-files` entry, even after the line is added. A repository already at
1.0.0 or above can add the line only to clear the row.

In `nextjs`, `python`, `rust` and `swift`, the untested-merge guard in
`release-please.yml` now reads with the workflow's `GITHUB_TOKEN` instead of
the Release Please App token, so the App token, which can write contents and
pull requests, goes only to `release-please-action`. The guard lists merged
release pull requests with `gh pr list --label`, which searches through
GraphQL, and compares commits. No docs page states the permission that search
needs (the REST search endpoint for issues and pull requests requires none,
[Search issues and pull requests](https://docs.github.com/en/rest/search/search#search-issues-and-pull-requests),
read 2026-10-22), so the `release-please` job gains `permissions:` with
`contents: read` and `pull-requests: read`, the reads the REST endpoints for
the same data require
([List pull requests](https://docs.github.com/en/rest/pulls/pulls#list-pull-requests),
[Compare two commits](https://docs.github.com/en/rest/commits/commits#compare-two-commits),
checked 2026-10-21). That is inferred, and has not yet been run on a private
repository. A job-level block replaces the workflow's `contents: read`, so both
are listed
([Workflow syntax for GitHub Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idpermissions),
checked 2026-10-21). The workflow's own block, the App's permissions and the
repository settings do not change. `release-please.yml` is template-owned, so
`--adopt` brings the change to existing repositories, keeping each one's action
pins, and `--check` reports an older copy as `stale`. A repository whose
release workflow is `local-modified` keeps its own and can make the same two
edits by hand: add that `permissions:` block to the `release-please` job, and
set the guard step's `GH_TOKEN` to `${{ github.token }}`. `simple` has no guard,
so its workflow is unchanged. The branch protection runbook,
`docs/branch-protection-runbook.md`, is also template-owned, in every type
including `simple`: its sentence on the workflow's own `GITHUB_TOKEN` said it
stays at `contents: read`, and now says the token only reads, and that the
release job of a repository whose release waits for tests also reads pull
requests, for the guard. `--check` reports an older copy as `stale`, and
`--adopt` replaces an unedited one.

`nextjs`: the lint baseline no longer states as fact that `npm run lint` runs
with `--max-warnings=0`. Nothing the bootstrapper generates provides or checks
the flag, and the `lint` script of a new `create-next-app` project with the
ESLint option, `eslint`, does not set it, so the baseline's claim that an unused
`eslint-disable` directive fails CI held only for a scaffold that had added the
flag. The claim also needs ESLint to report unused disable directives, which is
the default since ESLint 9 but not ESLint 8's, and not that of a configuration
that sets `reportUnusedDisableDirectives` to `"off"`. The generated `README.md`
and `docs/lint-baseline.md` now say that `npm run lint` must run
`eslint --max-warnings=0` with unused disable directives reported, and that
without either a stale baseline row only surfaces at its review date; the
`local-validation-nextjs` skill says the same. `--adopt` brings the skill, which
is template-owned. The README and `docs/lint-baseline.md` belong to the
repository, so `--adopt` reports them as `kept` and `--check` as `differs`:
merge the wording by hand from the files in `templates/` at the `v0.17.0` tag.
The change that matters is in your own `package.json` and ESLint configuration:
add `--max-warnings=0` to the `lint` script's `eslint` command, keeping the
targets and other arguments it has (and wide enough to cover every file
`scripts/verify-baselines.mjs` scans, so a narrowed target such as `eslint src`
does not leave a stale directive elsewhere unreported), and keep unused disable
directives reported
(the default since ESLint 9; `--report-unused-disable-directives` or
`reportUnusedDisableDirectives` on ESLint 8), or a stale `eslint-disable`
directive and its baseline row go unnoticed until the row's review date. Keep a
file target such as `.` on ESLint 8 with an eslintrc configuration: only flat
config lints the current directory when no file is given, and eslintrc then
stops with an error
([ESLint v9.0.0 release notes](https://eslint.org/blog/2024/04/eslint-v9.0.0-released/),
"Running eslint with no file arguments", checked 2026-10-22).

The `nextjs` template's `next dev` block in `AGENTS.md` now matches Next.js
16.4: its heading is `## This is NOT the Next.js you know`, where 16.3 wrote
`# This is NOT the Next.js you know`, and the two paragraphs are unchanged.
`--adopt` brings nothing here: the block is inside the `next dev` markers, which
`--check` does not compare and `--adopt` does not rewrite, so an existing
repository keeps its own block. It gets the new heading from the next `next dev`
run under an AI coding agent on Next.js 16.4 or later (`syncAgentRulesForDev` in
`dist/server/lib/app-info-log.js` writes the block only when it detects one, and
removes it instead when `next.config` sets `agentRules: false`; checked in 16.4.2
on 2026-10-22), as one changed line to commit with your work. A
repository that stays on Next.js 16.3 sees the reverse once: its `next dev`
rewrites a block taken from this release to the level-1 heading. `--adopt` still
restores the template's block in a repository whose `AGENTS.md` has none. There
is nothing to merge by hand.

`python`: a repository with no `pyproject.toml`, `requirements*.txt` or
`uv.lock` used to fail its first `test.yml` run inside `actions/setup-python`,
which throws `No file ... matched` when its pip cache has nothing to hash
([setup-python v7.0.0 source](https://github.com/actions/setup-python/blob/5fda3b95a4ea91299a34e894583c3862153e4b97/src/cache-distributions/cache-distributor.ts),
checked 2026-10-21). The generated `test.yml` now fails one step earlier, at
`Require a dependency manifest`, with a message that says to add a
`pyproject.toml` or a `requirements.txt` or `requirements-dev.txt` (an empty
`requirements-dev.txt` is enough for a project with no dependencies). The
generated `dependabot.yml` is now Actions-only, because Dependabot's `pip`
updater stops with `Repo must contain a requirements.txt, setup.py, setup.cfg,
pyproject.toml, or a Pipfile.` until a manifest exists
([dependabot-core](https://github.com/dependabot/dependabot-core/blob/a026401a0604a43d12f04dfa4a3557ac0d5bf0bb/python/lib/dependabot/python/file_fetcher.rb),
checked 2026-10-21), as for `rust` and `swift`. `test.yml`,
`dependabot.yml` and `README.md` belong to the repository, so `--adopt` reports
them as `kept` and `--check` as `differs`; take the changes by hand from the
files in `templates/` at the `v0.17.0` tag, or accept the `differs` rows. The
`local-validation-python` skill is template-owned, and `--adopt` brings it. A
repository that already commits a manifest needs nothing else: the new step
would never fail there, and its `pip` entry keeps working. One that does not
can paste the step below into `.github/workflows/test.yml` immediately before
the `actions/setup-python` step, after `actions/checkout`, and delete its
`pip` entry until it commits a manifest. In `hashFiles`, list the patterns of
the repository's own `cache-dependency-path` in the same order, then
`'**/pyproject.toml'`:

```yaml
      - name: Require a dependency manifest
        timeout-minutes: 1
        env:
          MANIFEST_HASH: ${{ hashFiles('**/requirements*.txt', 'pyproject.toml', 'uv.lock', '**/pyproject.toml') }}
        run: |
          if [ -z "$MANIFEST_HASH" ]; then
            echo "::error::No dependency manifest. Add a pyproject.toml or a requirements.txt or requirements-dev.txt (an empty requirements-dev.txt is enough for a project with no dependencies)."
            exit 1
          fi
```

## Upgrading to 0.16.1

`--check` and `--adopt` now name the cause in four cases that gave a symptom or
a raw error. No file is classified, written or refused differently, and no
generated file changes, so there is nothing to merge by hand.

- An `AGENTS.md` with CRLF or CR line endings throughout, no line ending in a
  bare LF, is one `differs` row,
  `(CRLF or CR line endings; convert to LF first)`, in place of a `differs` row
  per generated section; its `missing`, `local` and `retired`
  rows and the order of its generated sections stay. A file that mixes LF
  lines with CRLF ones keeps every row and gains
  `(CRLF and LF line endings mixed; convert to LF first)`. A file with LF
  lines and a carriage return inside a line gains
  `(carriage return inside a line; remove it first)`, because converting line
  endings does not remove it. `--adopt` still refuses these files, with
  `not LF-terminated UTF-8 text; update it by hand`. Carriage returns only in
  repository-owned text, such as under `## Project specifics`, still leave
  the file `same`.
- A byte-order mark at the start of `AGENTS.md` is one `local` row,
  `(byte-order mark before the first heading; remove it first)`, in place of
  `(text before the first heading)` and, for most types, a missing
  `# Working in this repo`. The mark is set aside, so the other sections are
  compared normally, and `--adopt` now refuses with
  `remove the byte-order mark at the start of the file first`.
- An unstamped file at a template skill's path, such as an empty
  `.agents/skills/delegation/SKILL.md`, is `shadowed` with a detail saying to
  move it aside, or to rename the skill if it is the repository's own. It had
  no detail.
- A directory, or a file where a folder belongs, at the path of a missing
  template file, such as a directory named `docs/branch-protection-runbook.md`,
  is refused with `something other than a file is at this path; move it aside`,
  as for a seed script, instead of `FileExistsError: File exists` or
  `NotADirectoryError: Not a directory`.

`--dry-run` and `--check` also end quietly when whatever reads their output
closes it, as `--dry-run | head -1` does. They no longer print a traceback, and
a `--dry-run` that ended with one (exit 120, or 1 when the reader left during
its questions) now exits 0. A `--non-interactive` dry run whose options are
refused still fails. An interactive dry run whose reader leaves while it
is still asking exits 0 without reading the remaining answers, since nobody
saw the questions. `--check` keeps its exit status: 0 when aligned, 1 on
drift. A creating run and `--adopt` are unchanged: a closed pipe still ends
them with an error status, so it cannot hide a failed run.

The diff `--check` prints for an unstamped, locally modified
`pr-title-check.yml`, `release-please.yml` or `baseline-review.yml` now picks
its base from the body of every release and from today's template, not only
the releases through v0.8.1, and names it in the header, such as
`legacy/v0.12.0/.github/workflows/release-please.yml`,
`current/.github/workflows/release-please.yml` or, for another type's template,
`legacy/v0.12.0/templates/release-please-gated.yml`. A workflow forked from a
later template used to show that template's own later changes, such as
`queue: max` or the credentials check, as the repository's own additions and
removals. A copy that equals a release body from after v0.8.1 apart from the
missing stamp used to be diffed against an older release; `--check` now says it
is identical to that release, and to check `--type` when the release's template
is another type's. The state (`local-modified`) is unchanged, and `--adopt`
still refuses these files: with that `--type` reason in the second case, and
otherwise with `an unstamped copy of <base>; delete the file and re-run --adopt
to write the stamped version`. From a shallow clone of the bootstrapper, or one
with no tag through v0.8.1, `--check` prints a notice and skips this diff.

`--adopt` now reads quoted items in a flow sequence of the repository's own
`test.yml`, such as `python-version: ["3.11", "3.12"]`,
`node-version: ["20.x"]`, `branches: ["main"]` or `paths: ['**.py']`. Before,
such a line put the file outside the YAML subset `--adopt` reads, so it refused
to create or upgrade `release-please.yml` on every run with "cannot verify the
inputs .github/workflows/test.yml declares", until the line was rewritten as a
block sequence. When `--adopt` still cannot read a called workflow because a
line is outside the YAML subset, the refusal now also gives the number and
text of the first such line, as in
`(line 5 is outside the YAML subset: 'inputs: {full: {}}')`. A quoted item with
an escape, a quote inside or a line break is still refused.

`--check` and `--adopt` no longer stop with a `PermissionError` traceback when
a directory in the repository cannot be searched by the user running them, such
as a skill folder owned by another user in a shared or container-mounted
checkout. The template files below it are reported as `unreadable` with the
directory named, `--check` exits 1 as for any drift, and `--adopt` refuses those paths
and carries on with the rest. Run the command as a user that can search the
directory, or fix its permissions, to compare those files.

`--adopt` now deletes an orphaned template-owned file, or a dangling
`.claude/skills` mirror, only when git tracks it with no uncommitted or staged
change, as every overwrite already required. Before, a digest-valid orphan
that git did not track, such as a stamped copy in `.claude/agents` that was
never committed, or any orphan in a directory that is not a git repository, was
deleted with nothing committed to recover it from. It is now refused with
"not tracked by git", and `--adopt` exits 1 for it: commit the file, then
re-run `--adopt`, or delete it by hand.

Deleting an orphaned skill used to leave its emptied folder behind, and the
`.claude/skills` mirror pointing at it stayed live, so a second `--adopt`
reported nothing to do. `--adopt` now removes a folder that deleting the
skill's files leaves empty and, in the same run, the mirror that pointed at it,
if git tracks that mirror with no uncommitted change. A folder that still holds
other files stays, and so does its mirror. A folder that is empty but cannot be
removed, such as one in a read-only directory, is reported as `refused` and
`--adopt` exits 1; its mirror stays. An empty folder and mirror left by an
earlier run or by such a refusal stay as they are: delete the empty folder by
hand, and the mirror then shows as `dangling`, which `--adopt` deletes.

`--check` now reports a second copy of a generated `AGENTS.md` heading as
`local`, for example `(duplicate generated heading: ## Commits)`, next to the
`differs` row it already printed. Before, a rebuild with
`--adopt --replace-generated-sections` dropped the text under the extra copy.
`--adopt` now refuses the rebuild even with that flag, and leaves the file as
it is. Remove the extra copy, or move its text under `## Project specifics`,
then re-run `--adopt`.

## Upgrading to 0.16.0

`nextjs`: for a row whose Dependabot alert is still open, the weekly Baseline
review now says to reassess the row against the alert, scope included, before
dismissing the alert, instead of only to dismiss it citing the row. GitHub's
auto-triage rules can reopen an alert they dismissed, for example when a
development dependency moves to production scope, and a dev-only row's
rationale then no longer holds ([Dependabot auto-triage
rules](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependabot-auto-triage-rules),
GitHub Docs, checked 2026-10-21). The `baseline-process` skill says the same.
`--adopt` updates unedited copies of `scripts/review-baselines.mjs` and its
test, as the next paragraph describes; merge the one-line change into an
edited copy and its test by hand.

`nextjs`: `--adopt` now brings a baseline script under `scripts/` up to date
when the repository never edited it, together with the rest of its group (see
[Checking and adopting](existing-repositories.md#checking-and-adopting)). A repository that still has
the `scripts/review-baselines.mjs` and `scripts/review-baselines.test.mjs`
copies 0.15.2 shipped gets the 0.15.3 change below from `--adopt`, without
copying them by hand. An edited copy is still `differs`, and its change is
still merged by hand. A missing baseline script is no longer created while
the rest of its group is held back, so `--adopt` no longer pairs a current
test with an older script.

The `verify-external-claims` skill's *Third-party skills* rules now allow a
correction to a vendored skill to live in a repository-owned skill that
`## Project specifics` says to load with it, as long as rules that must always
hold, such as stop-and-ask lines, stay in `## Project specifics`. They also
separate a correction that holds in any repository, which is marked as shared
and recorded by every repository vendoring that skill at a revision that still
has the error, from one about a single repository's configuration. `--check` reports the skill as `stale`, and `--adopt` updates
it.

## Upgrading to 0.15.3

`nextjs`: the weekly Baseline review's Dependabot parity check now reads alerts
in every state (`auto_dismissed`, `dismissed`, `fixed` and `open`) instead of
only dismissed ones. It still fails on an alert a person dismissed without an
advisory row, and on a row whose alert is open, now with its own message and
even when another alert for that advisory is dismissed. A row with no alert at
all, or whose alert GitHub's auto-triage rules dismissed or Dependabot marked
fixed, no longer fails the review: there is nothing to dismiss, so a row with
no alert is listed in the summary instead. Before, every such row failed the
review each week. The `baseline-process` skill describes the new check;
`--check` reports it as `stale`, and `--adopt` updates it.
`scripts/review-baselines.mjs` and `scripts/review-baselines.test.mjs` belong
to the repository, so `--adopt` keeps them and `--check` reports them as
`differs`. Copy both from `templates/` at the `v0.15.3` tag, or merge the
change into an edited copy by hand, and take them together: the new tests
expect the new request and summary lines. The request needs no new permission;
`baseline-review.yml` already grants `vulnerability-alerts: read`.

## Upgrading to 0.15.2

The `verify-external-claims` skill's *Third-party skills* rules now cover a
third-party skill installed in the repository for agents to load, not a skill
file that only ships inside a dependency, such as under `node_modules/`, so
restoring dependencies is not a skill update unless a dependency's skill is
linked for agents to load. The `AGENTS.md` *Skills* row for the skill now reads
"rely on an external claim or add, update, or follow a third-party skill", so
an agent that only reads the table also loads it before installing one.
`--check` reports the skill as `stale` and *Skills* as `differs`; take both
with `--adopt --replace-generated-sections`.

## Upgrading to 0.15.1

The `verify-external-claims` skill's *Third-party skills* rules now cover only
third-party skills installed in the repository, committed or not; the update
instructions of any other third-party skill, such as one installed for the
user, are still input to assess. A correction to a vendored skill stays in
`## Project specifics` until a refresh brings in the upstream fix, and the
`skills` 1.7.4 pinning example names its source and asks for a full commit
SHA. `--check` reports the skill as `stale`, and `--adopt` updates it.

## Upgrading to 0.14.1

The user-visible step in `pr-title-check.yml` catches two more ways Release
Please 17.6.0 would mishandle a change. It fails when an extra entry's scope
is empty or holds a parenthesis, such as `fix(a(b)): y` in the body, because
Release Please cannot parse that entry and drops it with its change. It also
fails when a `<details>` tag sits in the scope or a code span of a released
title or entry, or in a breaking-change note, which is the subject itself for
a change marked `!` with no note of its own: the changelog keeps that text as
HTML, and Release Please then cannot read back its release pull request, so
it stops with an error on every later run (or, with a `<summary>` naming a
version, reads the wrong release). The `pull-requests` skill says how to
avoid both. `--check` reports `pr-title-check.yml` and the skill as `stale`,
and `--adopt` updates them; no action pin changes.

## Upgrading to 0.14.0

`pr-title-check.yml` asks every pull request whether the change is user
visible. A second step in its required `validate-title` job fails unless the
body has a line of its own, at column 0, reading `User-visible: yes` or
`User-visible: no`, and the answer agrees with whether Release Please will
release the change. `yes` needs a `feat`, `fix`, `perf` or `revert` title, a
breaking change, a `Release-As:` footer, or an extra entry of a released type
in the body; `no` needs none of them. The step follows how Release Please
17.6.0 reads a squash commit, a `BEGIN_COMMIT_OVERRIDE` block included. It
also fails when a body line Release Please cannot parse, such as `f(g(x))` at
the start of a line, would make it drop a change from the changelog, and when
Release Please cannot read the version in a `Release-As:` footer, which would
stop it with an error. A yes/no question is harder to get wrong than a type,
so the check catches a mistyped title, such as a `docs:` change that ships in
a release or a `fix:` that ships nothing. Release Please and Dependabot pull
requests skip the job, as before. The step reads the pull request only through
its `env:`, and its script prints none of the body but the numbers of a
`Release-As:` version.

The `pull-requests` skill says how to answer, and `review-guidelines` asks
the reviewer whether the type and the answer are true to the diff. `--check`
reports `pr-title-check.yml` and both skills as `stale`, and `--adopt`
updates them; the new step uses no action, so the repository's action pins
still apply. The adoption pull request runs the new check itself, so its body
needs the line too: `User-visible: no` for the usual `chore:` adoption
title. After it merges, add the line to each open pull request's body:
editing the body re-runs the check. `--adopt` also writes
`.github/pull_request_template.md`, which asks for the line, unless the
repository has a pull request template of its own (see
[Repository types](repository-types.md)).
The step follows Release Please's default changelog sections, which every
generated `release-please-config.json` uses; a repository that sets
`changelog-sections` to show other types would see the check disagree with
its releases.

## Upgrading to 0.13.0

Every type gains the `review-guidelines` skill, for the agent doing a review.
`fresh-eyes-review` now holds only the implementer's side, with new rules for
handling findings, and both reviewer agents load `review-guidelines` instead
of `fresh-eyes-review`. `--check` reports the new skill and its
`.claude/skills` mirror as `missing`, and the changed skill and agents as
`stale`; `--adopt` writes them. A repository that already has a skill of its
own named `review-guidelines` renames it first: `--adopt` refuses to replace
it but still points the reviewer agents at that name. To keep a
repository's own review rules, add them under `## Project specifics` as a
`### Code review rules` subsection: a few bullets naming what a change must
preserve.

The hub's skills table now has a row for every skill: every type gains one
for `review-guidelines`, and `nextjs` one for `public-site-indexing`, which
had none. To make room, the `nextjs` *Tooling* section drops its paragraph on
running `npm run test:e2e` for UI changes, which is now that command's
comment (`local-validation-nextjs` still offers `npm run test:e2e:local` when
a local run hits `EMFILE`).
`--check` reports *Skills*, and for `nextjs` *Tooling*, as `differs`; take
them with `--adopt --replace-generated-sections`, after the comparison the
0.12.0 notes below describe.

## Upgrading to 0.12.1

`release-please.yml` changes only in its comments. One no longer uses the
word `secrets` except in `secrets.NAME`: some repositories' workflow
validators refuse the word anywhere else, comments and URLs included. In
`nextjs`, another says which step names the baseline review reads. `--check`
reports the file as `stale`, and `--adopt` updates it. A repository that kept its
0.11.0 `release-please.yml` for that reason can take it now, which also brings
in 0.12.0's credentials check, which
[GitHub App for Release Please](github-settings.md#github-app-for-release-please)
describes.

For `nextjs`, the weekly baseline review no longer counts a release that was
skipped for missing credentials as healthy. When the latest completed
`release-please.yml` run succeeded, it reads that run's jobs. If every job
that checked the Release Please credentials skipped its App token step, it
reports `Release pipeline: not configured` and fails, as the review did before
0.12.0, when such runs failed. If the `release-please` job did not start, or
only some release jobs ran their token step, it reports `not released` or
`partly released` and fails. A run with no job that has both steps and no
skipped `release-please` job, as from a customised workflow, is judged as
before. `scripts/review-baselines.mjs` and
`scripts/review-baselines.test.mjs` belong to the repository, so `--adopt`
keeps them and `--check` reports them as `differs`, even when they are
unchanged from 0.12.0. Copy both from `templates/` at the `v0.12.1` tag, or
merge the change into an edited copy by hand. Take them together: the 0.12.0
test file answers the new jobs request with a 404, so its healthy-release
tests fail. `baseline-review.yml` already grants `actions: read`, which the
jobs request needs: GitHub lists that endpoint as needing read access to the
Actions repository permission
([List jobs for a workflow run](https://docs.github.com/en/rest/actions/workflow-jobs#list-jobs-for-a-workflow-run),
[Permissions required for GitHub Apps](https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps),
both checked 2026-10-18).

## Upgrading to 0.12.0

The `AGENTS.md` hub changed: it gains an *Autonomy and escalation* section and
a default for when a change is done, its attribution rules are shorter, and
*Fresh-eyes review* and *Recall is not evidence* became *Definition of done*
bullets. Run `--adopt --replace-generated-sections` to take it. The rebuild
also removes the old guidance paragraphs from `## Project specifics` when
they are unedited and above its first subheading, because the guidance is
now in a generated section, and `--adopt` writes `docs/current-work.md` when
it is missing.

The `screenshot-review` skill and `docs/screenshot-review.md` are now
generated only with `--screenshots`. Existing `nextjs` and `swift`
repositories keep theirs: `--check` and `--adopt` treat a repository that has
the template's copy of either file as using `--screenshots` (see
[Checking and adopting](existing-repositories.md#checking-and-adopting)), and passing the flag
silences their notice. To drop them, move any rule of your own into a
repository-owned skill, delete `.agents/skills/screenshot-review/`, its mirror
`.claude/skills/screenshot-review` and `docs/screenshot-review.md`, then run
`--adopt --replace-generated-sections`, which also takes the skill's row and
pointer out of the hub. To add them to a repository later, run
`--adopt --screenshots --replace-generated-sections`. Without the skill, the
screenshot bullet in *Definition of done* keeps the screenshot gates but drops
"Screenshot guidance is capability-conditional".

`--replace-generated-sections` replaces a generated section that differs
without showing its text. Before running it, compare each section `--check`
reports as `differs` with `templates/AGENTS.md` and move any rule of your own
under `## Project specifics`; afterwards, review the result with `git diff`.
For `nextjs`, that includes an edited *This project uses the App Router*
note: the old template asked a Pages Router repository to replace it.

Then tidy `## Project specifics` by hand:

- put stop-and-ask rules first;
- move dated status, such as when the repository was pushed or that Release
  Please is not set up yet, into `docs/current-work.md`;
- move long reference material and corrections of template skills, such as
  CI tiers, ports or test-server notes, into a repository-owned skill, and
  name it in `## Project specifics`;
- delete a sentence that only says a generated section applies as written.

For `nextjs`, the hub no longer lists `npm run lint:fix` and `npm run format`;
the generated `README.md` does. An existing repository's `README.md` is its
own, so `--adopt` leaves it alone: add the line yourself if you want it.

## Upgrading to 0.11.0

`bootstrap.py` now needs Python 3.11 or newer.

`--adopt` brings in the template-owned files: the skills, the reviewer agents,
`docs/branch-protection-runbook.md`, `pr-title-check.yml`, `release-please.yml`
and, for `nextjs`, `baseline-review.yml`. Add `--replace-generated-sections` to update the
generated sections of `AGENTS.md`. The new `release-please.yml` uses
`concurrency.queue: max`; a repository that runs actionlint 1.7.12 needs the
exception shown under [Template-owned files](existing-repositories.md#template-owned-files).

Every other changed file belongs to the repository. `--adopt` reports it as
`kept` and leaves it alone, and `--check` reports it as `differs`. Merge these
changes by hand from the file in `templates/` at the `v0.11.0` tag. For the
`nextjs` scripts, take `verify-baselines.mjs`, `verify-baselines.test.mjs`,
`audit-production.test.mjs` and `review-baselines.test.mjs` from the next
release instead: their `v0.11.0` copies fail a generated repository's Prettier
check and its ESLint `--max-warnings=0` run.

| Type | Repository file | Template | Change |
|---|---|---|---|
| `python` | `.github/workflows/test.yml` | `test-python.yml` | the install step uses `uv sync --locked` when `uv.lock` exists and installs a `[dependency-groups] dev` group; without `uv.lock` it builds the project only when it has a `[build-system]` or `[tool.uv] package = true`, as uv does ([uv docs](https://docs.astral.sh/uv/concepts/projects/config/#build-systems), checked 2026-10-15), or a `setup.py` or a `setup.cfg` with `[metadata]` or `[options]`, and otherwise installs just its dependencies. The test step runs `python -m pytest`, which puts the repository root on `sys.path` ([pytest docs](https://docs.pytest.org/en/stable/explanation/pythonpath.html#invoking-pytest-versus-python-m-pytest), checked 2026-10-15), so tests import modules and flat-layout packages that are not installed. A package below the root that relied on pip's setuptools fallback, such as a `src/` layout with no `[build-system]`, must now declare one (or set `[tool.uv] package = true`), or its tests fail to import it |
| `python` | `README.md` | `README-python.md` | optional: the note on committing `uv.lock`, and `python -m pytest` under Verification |
| `nextjs` | `scripts/verify-baselines.mjs` and `.test.mjs` | same names | counts `.mts`/`.cts` files, JSDoc-style and `@ts-ignore: reason` directives, and wrapped `eslint-disable` lists |
| `nextjs` | `scripts/baseline-table.mjs` | same name | refuses a GHSA ID not in GitHub's casing; such a row never matched an advisory, so fix its casing |
| `nextjs` | `scripts/audit-production.mjs`, its test and `scripts/review-baselines.test.mjs` | same names | a malformed advisory baseline fails with its message instead of a stack trace; tests no longer read the host's `GITHUB_TOKEN` |
| `swift` with `--xcodegen` | `.github/workflows/test.yml` | `test-swift-xcodegen.yml` | XcodeGen 2.46.0 and its SHA-256 |
| `nextjs` | `docs/lint-baseline.md`, `docs/advisory-baseline.md` | `docs-*.md` | optional wording: the lint baseline is "mostly" self-cleaning, and `@ts-expect-error` is preferred to `@ts-ignore` |
| `nextjs` | `.github/workflows/test.yml` | `test.yml` | a comment only |
| all | `.github/dependabot.yml` | `dependabot-*.yml` | optional: `cooldown: default-days: 7` on each update entry |

A Python repository that commits `uv.lock` should also switch its Dependabot
`pip` entry to `uv`.

## Upgrading to 0.8.1

`python`: `test.yml` now runs `ruff format --check .`, so CI fails on
unformatted code. When you `--adopt` 0.8.1 into an existing Python
repository, run `ruff format .` and commit the result in the same pull
request.
