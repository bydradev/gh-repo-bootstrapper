# Development

How to work on `bootstrap.py`, its templates and its validator. The
contribution rules (issues first, one change per pull request, the DCO
sign-off) are in [`CONTRIBUTING.md`](../CONTRIBUTING.md), and the branch,
commit and release conventions in [`AGENTS.md`](../AGENTS.md).

`bootstrap.py` uses the standard library only. The validator and the tests
need two development dependencies, PyYAML and pytest, listed in
[`requirements-dev.txt`](../requirements-dev.txt); the template scripts'
tests need Node.

## Set up

With [uv](https://docs.astral.sh/uv/) (preferred):

```sh
uv venv
source .venv/bin/activate
uv pip install -r requirements-dev.txt
```

Without uv, create the same environment with Python:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

## Run the checks

Run the commands under *Tooling* in [`AGENTS.md`](../AGENTS.md) before you
push. They are the same checks CI runs: the validator, the pytest suite, the
`node:test` suites of the generated baseline scripts, Prettier and ESLint on
those scripts, and markdownlint on the generated Markdown and on this
repository's own.

## What CI runs

`.github/workflows/validate.yml` runs on every pull request and on pushes to
`main`, in two jobs:

- `validate-templates`, on a current Python: compiles `bootstrap.py` and
  `validate_templates.py`, runs the validator and the pytest suite under
  `tests/`, then the `node:test` suites (`node --test templates/*.test.mjs`),
  Prettier and ESLint (`no-unused-vars` only) on `templates/*.mjs`, which
  generated Next.js repositories run with their own settings. It also renders
  every configuration's generated Markdown with
  `python validate_templates.py --render-markdown <dir>` and lints it, and
  this repository's own Markdown apart from `CHANGELOG.md`, with
  markdownlint-cli2 and `markdownlint-generated.jsonc`.
- `python-floor`, on Python 3.11, the oldest version `bootstrap.py`
  supports: compiles both scripts and runs the validator and the pytest
  suite, so a newer-only feature cannot slip in.

Both check out the full history and tags, which the validator needs to
rebuild its tables of earlier releases.

`.github/workflows/pr-title-check.yml` runs `validate-title` on each pull
request: the title must be a Conventional Commit subject, and the body's
`User-visible:` line must agree with what Release Please will do with the
title and body. It is the template's copy, kept byte-identical to
`templates/pr-title-check.yml`, and skips merged, Release Please and
Dependabot pull requests.

`.github/workflows/dco.yml` runs `sign-off` on each pull request from an
outside contributor: every commit needs a `Signed-off-by:` trailer with its
author's email, as [`CONTRIBUTING.md`](../CONTRIBUTING.md) asks. Pull
requests from the owner, members, collaborators and bots skip it.

CodeQL runs through GitHub's default setup, configured in the repository's
settings rather than a workflow file: it analyses the Actions workflows,
JavaScript and Python on each pull request and push to `main`, and weekly.

`validate-templates`, `python-floor`, `validate-title`, `sign-off` and
`public-content` are the required checks on `main`; a skipped run counts as
passed.

`.github/workflows/public-content.yml` runs
`.github/scripts/check_public_content.py` on each pull request's title, body
and commits and the lines they add to files, and on each push to `main`, for
the private details that [`AGENTS.md`](../AGENTS.md) *Public repository
content* rules out: claude.ai links and session IDs, local paths, email
addresses other than noreply ones, and repositories outside the public
list. It leaves out the script and its own tests, which hold the patterns.
It reads bare private repository names from the `PRIVATE_REPO_NAMES`
repository secret, which pull requests from forks do not get, and prints
where each finding is and its kind, never the matched text.

## Validator options

`python validate_templates.py` with no option runs every check. Three
options print instead:

- `--render-markdown <dir>` writes every configuration's generated Markdown
  under `<dir>`, for markdownlint.
- `--regenerate-legacy-digests` and `--regenerate-seed-digests` print the
  `LEGACY_TEMPLATE_DIGESTS` and `SEED_DIGESTS` tables in `bootstrap.py`,
  rebuilt from the git release tags. The validator reports a table as stale
  when the tags disagree with it, such as after a release that changed a
  `nextjs` seed script; paste the printed table over the old one.

The digest checks need the release tags: in a shallow clone, or without the
tags, the validator prints a notice and skips them.

## What the validator checks

`validate_templates.py` renders every supported `bootstrap.py` configuration
(all repo types × their type-specific options) and asserts:

- YAML/JSON syntax, and no unreplaced `__MARKER__`/`# <<MARKER>>` placeholders
- workflow/job consistency: branch-protection required status checks matching
  job ids in the generated workflows, checked in both directions
- reusable-workflow contracts: every `with:` key declared by the workflow it
  calls, every required input supplied, and every local `uses:` target actually
  declaring `on: workflow_call`
- workflow token scopes: every generated workflow declaring `permissions:`
  explicitly, with `ci.yml` and `test.yml` pinned to exactly `contents: read`
  and no write scope outside `release-please.yml`, whose release job declares
  exactly `contents: read` and `pull-requests: read` in the types with a gated
  release (for the untested-merge guard) and no block of its own in `simple`
- rendered Release Please config *values*, not just that the JSON parses
- the branch-protection payload, the runbook (its pinned rules, and no
  incident run IDs, SHAs or timestamps), and the Next.js lint/advisory
  baseline policy documents
- the shared `AGENTS.md` worktree and scratch-output rules, each type's
  mechanism for keeping a worktree's dependencies and build output from
  multiplying, `## Project specifics` as the last section, and the Next.js
  App Router note sitting outside the `next dev`-managed markers
- the hub's size (an 8,000 B budget for its generated part, a 10,000 B
  ceiling), its pinned safety gates, skill pointers and frontmatter, reviewer
  agents, and the ownership stamps on template-owned files
- executable workflow gates: every action pinned to a full commit SHA and
  allowed by the Actions policy the script sets; a timeout on every job that
  declares `runs-on`; no job or step set to `continue-on-error` or given an
  `if:` that is a falsy literal (`false`, `0`, `null`, `''`); the Python and
  Rust suite commands run once, unconditionally; the Next.js e2e runs and
  browser installs tied to their `full` conditions; the release job waiting for
  `test` with no condition of its own; its release steps skipped, with a
  warning, only while the Release Please App credentials are missing; the
  release App token limited to contents and pull requests, with the
  untested-merge guard reading with the workflow token instead; pinned
  fallback versions of the Python CI tools; and the step facts the README and
  `--help` state: `setup-node` and `setup-python` reading `.nvmrc` and
  `.python-version`, `npm ci` in every Next.js job that sets up Node, the
  Postgres image `--postgres` names, `swift-format lint` with `--strict`, and a
  weekly schedule for every Dependabot entry, the reference entries included
- the word `secrets` in every generated workflow and in this repository's own
  only as a static `secrets.NAME` or a `secrets:` key that opens a mapping,
  because some generated repositories run workflow validators that refuse it
  anywhere else, comments and URLs included
- in `nextjs`, the release job keeping the `release-please` id and its
  credentials and App token steps the names the weekly baseline review reads
  to tell a skipped release from one that ran
- the title check's user-visible step, in every generated `pr-title-check.yml`
  and this repository's own: one step after the title step, in the same job,
  reading the pull request title and body from the event file
  (`GITHUB_EVENT_PATH`), with no `env:` (the runner prints a step's env
  values in its log) and never through a `${{ }}` expression in its script
- no generated file describing the retired provider-deploy or production e2e
  lanes
- the bootstrapper's own runbook copy, and its legacy-digest and
  seed-script digest tables against the git release tags
- the bootstrapper's own agent files (the general skills and their
  `.claude/skills` links, both reviewer agents, `CLAUDE.md`, and `AGENTS.md`
  above `## Project specifics`), which must match its `--type simple` render.
  To refresh them, the error suggests `./bootstrap.py --adopt . --type simple`;
  that run also stamps `pr-title-check.yml` and refuses `release-please.yml`,
  which is this repository's own and stays as it is, so commit only the agent
  files it changes. For the same reason `./bootstrap.py --check . --type
  simple` reports `pr-title-check.yml` as `stale`: this repository's copy is
  the unstamped template, byte-identical to `templates/pr-title-check.yml`,
  and is expected to stay that way
- the bootstrapper's own bug-report form, whose repository types and flags must
  match `bootstrap.py`'s parser

It also runs self-tests that reproduce each past regression from real rendered
output, so a check that stops firing turns the suite red rather than passing
vacuously.
