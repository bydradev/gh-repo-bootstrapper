# gh-repo-bootstrapper

Interactive Python script to create standardised GitHub repositories with
pre-configured Actions workflows, Release Please, and Dependabot.

## Requirements

- Python 3.9+
- [gh CLI](https://cli.github.com/) — authenticated (`gh auth login`)
- git

No runtime pip dependencies — stdlib only. `bootstrap.py` itself never needs
anything installed beyond a base Python interpreter.

## Development

`validate_templates.py` renders every supported `bootstrap.py` configuration
(all repo types × their type-specific options) and asserts:

- YAML/JSON syntax, and no unreplaced `__MARKER__`/`# <<MARKER>>` placeholders
- workflow/job consistency — branch-protection required status checks matching
  job ids in the generated workflows, checked in both directions
- reusable-workflow contracts — every `with:` key declared by the workflow it
  calls, every required input supplied, and every local `uses:` target actually
  declaring `on: workflow_call`
- workflow token scopes — every generated workflow declaring `permissions:`
  explicitly, with `ci.yml` and `test.yml` pinned to exactly `contents: read`
  and no write scope outside `release-please.yml`
- rendered Release Please config *values*, not just that the JSON parses
- the branch-protection payload, the runbook, and the Next.js lint/advisory
  baseline policy documents
- the shared `AGENTS.md` worktree and scratch-output rules, each type's
  mechanism for keeping a worktree's dependencies and build output from
  multiplying, `## Project specifics` as the last section, and the Next.js
  App Router note sitting outside the `next dev`-managed markers

It also runs self-tests that reproduce each past regression from real rendered
output, so a check that stops firing turns the suite red rather than passing
vacuously. Unlike `bootstrap.py`, it requires PyYAML — a dev-only dependency
for this validator, not for the generated repos or for `bootstrap.py` itself.

### Preferred: uv

Create an isolated environment and install the checked-in development
requirements with [uv](https://docs.astral.sh/uv/):

```sh
uv venv
source .venv/bin/activate
uv pip install -r requirements-dev.txt
python validate_templates.py
```

### Standard-library alternative

If `uv` is not available, create the same environment with Python:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python validate_templates.py
```

This runs in CI (`.github/workflows/validate.yml`) on every pull request and
on pushes to `main`.

### Next.js npm-script assumptions

The bootstrapper intentionally does not create or patch `package.json`; that
file belongs to the application scaffold. The Next.js templates therefore
assume the scaffold supplies `dev`, `lint`, `lint:fix`, `format`, `format:check`,
`typecheck`, `test`, `audit:production`, `verify:baselines`, `review:baselines`,
`build`, and `test:e2e` scripts. The canonical set is
`bootstrap.ASSUMED_NPM_SCRIPTS`, and `validate_templates.py` verifies that each
template `npm run <script>` / `npm test` reference is declared there and that
each declared assumption is documented by a template.

This is deliberately a self-consistency check between bootstrapper-owned
artefacts, not a claim that the generated repository's external scaffold
actually provides those scripts. Changing a scaffold's scripts still requires
checking that scaffold separately.

## Usage

```sh
./bootstrap.py
```

Run with no arguments for a fully interactive session. The script will prompt
for the repo name, type, owner, visibility, and any type-specific options, then
confirm before creating anything.

### Flags

| Flag | Description |
|---|---|
| `--name TEXT` | Repository name (lowercase letters, digits, hyphens), or a relative/absolute path ending in one — created in the current directory by default |
| `--type nextjs\|python\|swift\|rust\|simple` | Repository type |
| `--org TEXT` | GitHub org or user (default: authenticated user) |
| `--private` / `--public` | Visibility (default: private) |
| `--postgres` | Add PostgreSQL 16 service to test workflow (nextjs only) |
| `--scheme TEXT` | Xcode scheme name for `xcodebuild test` (swift only) |
| `--destination iphone\|ipad\|macos` | Target destination for `xcodebuild test` (swift only, default: iphone) |
| `--xcodegen` | Generate the Xcode project from `project.yml` in Swift CI |
| `--configure-only` | Apply GitHub config to an existing repo, skip file generation. Cannot be combined with `--dry-run` |
| `--dry-run` | Print all files that would be created without doing anything. The owner lookup is skipped in dry-run; without `--org`, a placeholder owner is used since nothing downstream contacts GitHub |
| `--non-interactive` | Fail instead of prompting for missing options |
| `--check PATH` | Compare an existing local repository with the current templates; read-only, exits 1 on drift. Needs `--type` and the type options the repository was generated with |
| `--adopt PATH` | Bring an existing local repository in line without contacting GitHub — see [Existing repositories](#existing-repositories) |
| `--replace-generated-sections` | With `--adopt`: also replace `AGENTS.md` generated sections whose text differs from the template |

### Examples

```sh
# Fully interactive
./bootstrap.py

# Next.js app — preview files before creating
./bootstrap.py --name my-dashboard --type nextjs --dry-run

# Next.js with PostgreSQL tests in an org
./bootstrap.py --name data-app --type nextjs --postgres --org my-org

# Python library
./bootstrap.py --name my-tool --type python --public

# Rust service or library
./bootstrap.py --name my-service --type rust

# Swift iOS app
./bootstrap.py --name my-app --type swift --scheme MyApp

# Swift macOS app
./bootstrap.py --name my-mac-app --type swift --scheme MyMacApp --destination macos

# Swift macOS app whose Xcode project is generated and not committed
./bootstrap.py --name my-mac-app --type swift --scheme MyMacApp --destination macos --xcodegen

# Simple release-only repo
./bootstrap.py --name docs-site --type simple --org my-org --public

# Apply GitHub config (see "What the script configures") to an existing repo
./bootstrap.py --name my-app --type nextjs --configure-only

# Compare an existing local repository with the current templates, then adopt them
./bootstrap.py --check ../my-app --type nextjs
./bootstrap.py --adopt ../my-app --type nextjs
```

## Existing repositories

`bootstrap.py` generates a repository once. Templates change afterwards, so
`--check` and `--adopt` bring an existing local checkout back in line. Neither
contacts GitHub; follow with `--configure-only` for repository settings.

`--check PATH --type TYPE` renders the current templates for that type and
reports each file as `same`, `differs`, `missing`, `symlink`, or `unreadable`. Pass the same
type options the repository was generated with — `--postgres` for Next.js,
`--scheme`, `--destination`, and `--xcodegen` for Swift — or the workflows
they shape report as drift. For `AGENTS.md` it reports per section: a
generated section that is `missing` or `differs` (including generated
sections in a different order), and anything `local` —
repository text outside `## Project specifics`, including a subsection added
inside a generated section, or structure it does not parse (setext headings,
an unclosed code fence). The `next dev`-managed block and everything from
`## Project specifics` on are the repository's own and are not compared. For
`.gitignore` it lists the template entries the repository lacks, and for
`CLAUDE.md` it flags a file that does not import `AGENTS.md`. It never writes,
and exits 1 on drift.

`--adopt PATH --type TYPE` writes every missing file and never overwrites an
existing one, with one exception that preserves repository-owned content:
`AGENTS.md` is rebuilt from the template, keeping `## Project specifics` (and
everything after it) and the `next dev`-managed block. The rebuild is refused
while anything `local` remains — move those rules under `## Project specifics`
first. A generated section whose text differs may be an older template or a
local edit, and the script cannot tell which, so it is replaced only with
`--replace-generated-sections`, which lists those sections and asks before
writing (`--non-interactive` skips the prompt).

For an existing `.gitignore`, missing entries are listed, not written; a
missing `.gitignore` is created like any other file. Whether an added rule
would override an existing `!` exception depends on git's full ignore rules
across every ignore file — git cannot re-include a file once a parent
directory is excluded — so that edit is left to a person.

The `AGENTS.md` rewrite needs the file tracked by git with no uncommitted
changes, LF line endings, and UTF-8 text, so the result can be reviewed with
`git diff` and reverted. It replaces the file atomically with a new one,
keeping its permission bits, so a hard link elsewhere keeps its old content; a
new file is written in full before it appears, and never replaces one created
meanwhile. Every write walks from `PATH` one directory at a time without
following symlinks, so a symlink met on the way is refused; `PATH` itself is
resolved, and `--adopt` prints the directory it is changing.

`--adopt` assumes nothing else modifies the repository while it runs. It
refuses a rewrite whose target changed since it was read, but it cannot close
every race with a concurrent process — for example one moving a directory out
of `PATH` mid-run — so do not run it while an editor, agent, or build is
writing to the same checkout. A failure on one file is reported as `refused`
without stopping the others, and `--adopt` exits 1 when it refused anything.

## Repository types

Every type gets a type-specific `README.md` starter, `AGENTS.md` and
`CLAUDE.md` (contribution guidance), `.gitignore`, `release-please-config.json`,
and `.release-please-manifest.json` seeded at `0.1.0`. The per-type lists below
highlight the additional files and README guidance for that type.

The generated `AGENTS.md` ends with a `## Project specifics` section. Put
repository-specific rules there, below every generated section, so later
template updates can be applied without overwriting them.

### `nextjs`

Full CI pipeline for Next.js applications.

- `pr-title-check.yml` — Conventional Commits validation on PR titles
- `release-please.yml` — test → release-please; deployment remains application-owned
- `ci.yml` — runs the full test suite on every PR
- `test.yml` — reusable suite: enforced production advisory audit and baseline verification, lint, format check, typecheck, unit tests, production build, Playwright e2e
- `baseline-review.yml` — weekly, non-blocking summary of advisory review dates and Dependabot/document parity
- `dependabot.yml` — weekly npm + GitHub Actions updates
- `.nvmrc`, `.npmrc`, `.prettierrc.json`, `.prettierignore`
- `docs/lint-baseline.md` — policy and an empty table for our own inline lint/type suppressions
- `docs/advisory-baseline.md` — policy and an empty table for accepted dependency advisories
- `docs/branch-protection-runbook.md` — operational runbook for PRs blocked by required status checks
- `docs/current-work.md` — forward-looking bootstrapper compatibility work
- `scripts/baseline-table.mjs`, `scripts/verify-baselines.mjs`, and `scripts/audit-production.mjs` — shared parser plus fail-closed baseline and production-audit checkers
- `scripts/*-baselines.test.mjs` — regression tests for the baseline verifier and scheduled review
- `README.md` and `AGENTS.md` — project starter, quality-baseline pointers, and contribution guidance

Options:
- `--postgres` — adds a PostgreSQL 16 service container to the build job

`ci.yml` and `release-please.yml` use the canonical light-PR/full-release
caller contract. `test.yml` is necessarily scaffold-general: it retains that
`full` input and adds the optional PostgreSQL service, while each generated
application supplies its own package scripts and any application-owned
release-triggered deployment workflow.

### `python`

CI pipeline for Python projects.

- `pr-title-check.yml`
- `release-please.yml` — test gate → release-please (no deploy)
- `ci.yml` — runs the test suite on every PR
- `test.yml` — ruff (lint), mypy (type check), pytest; auto-detects and installs
  `requirements-dev.txt`, `requirements.txt`, or `pyproject.toml` extras
- `dependabot.yml` — weekly pip + GitHub Actions updates
- `.python-version`
- `README.md` — project starter with a preferred `uv venv` setup and a
  standard-library `venv` alternative
- `docs/branch-protection-runbook.md` — operational runbook for PRs blocked by required status checks

### `swift`

CI pipeline for Swift/Xcode projects.

- `pr-title-check.yml`
- `release-please.yml` — test gate → release-please (no deploy)
- `ci.yml` — runs the test suite on every PR
- `test.yml` — `swift-format lint --recursive --strict` (formatting gate) then
  `xcodebuild test` on `macos-26`; scheme set from `--scheme`, destination
  resolved dynamically at CI time from `--destination`; with `--xcodegen`, CI
  installs pinned XcodeGen 2.45.4 and generates the project first
- `dependabot.yml` — weekly GitHub Actions updates
- `.swift-format` — Apple swift-format ruleset (default rules; `AlwaysUseLowerCamelCase`
  left on — disable it deliberately per-repo if wire-format DTOs need snake_case fields)
- `README.md` — project starter with local-development and verification sections
- `docs/branch-protection-runbook.md` — operational runbook for PRs blocked by required status checks

Requires `--scheme`. Destination defaults to `iphone` (an available iPhone
simulator, picked dynamically in CI); pass `--destination ipad` for an iPad
simulator or `--destination macos` for a macOS destination.

Pass `--xcodegen` when `project.yml` will be the source of truth and generated
`.xcodeproj` output should stay out of git. The generated `AGENTS.md` explains
the local Xcode workflow. Swift package declarations inside XcodeGen manifests
are not supported by Dependabot, so a new Swift repo gets the Actions-only
config; after adding a root `Package.swift` or another supported Swift manifest,
opt in deliberately by copying [`templates/dependabot-swift.yml`](templates/dependabot-swift.yml)
over `.github/dependabot.yml`. That file is a reference snippet — the
bootstrapper never renders it.

Formatting is enforced from the first commit: `test.yml` fails CI on any
`swift-format lint --recursive --strict` violation, and the generated
`AGENTS.md` tells agents to run `swift-format format --recursive --in-place .`
after editing Swift files and to check before pushing.

### `rust`

CI pipeline for Rust crates and workspaces.

- `pr-title-check.yml`
- `release-please.yml` — test gate → release-please (no deploy)
- `ci.yml` — runs the test suite on every PR
- `test.yml` — `cargo fmt --check`, `cargo clippy -D warnings`, and
  `cargo test` across the workspace; fails with a clear error until a root
  `Cargo.toml` exists
- `dependabot.yml` — GitHub Actions updates only; the generated `AGENTS.md`
  says to add a `cargo` entry once `Cargo.toml` is committed, since a new
  repository has no manifest for Dependabot to read
- `.gitignore` — adds Cargo's `/target/` build output
- `README.md` — project starter with rustup setup and the CI commands
- `docs/branch-protection-runbook.md` — operational runbook for PRs blocked by required status checks

Release Please uses the `simple` release type, as for Python and Swift: it
maintains the changelog, tags, and releases but does not edit `Cargo.toml`
versions. The generated `AGENTS.md` explains when to move to the `rust` release
type or the `cargo-workspace` plugin.

The bootstrapper does not run `cargo init` or choose a crate layout. The
generated `AGENTS.md` tells agents to share one `CARGO_TARGET_DIR` per
repository across worktrees, so each worktree does not build its own
multi-gigabyte `target/`. It lives beside those worktrees and is deleted with
the last of them.

### `simple`

Release Please only — suitable for scripts, docs, or any project without a
test suite.

- `pr-title-check.yml`
- `release-please.yml` — single-job, no test gate
- `dependabot.yml` — GitHub Actions updates only
- `README.md` — concise project starter and navigation guide
- `docs/branch-protection-runbook.md` — operational runbook for PRs blocked by required status checks

## What the script configures

Beyond file generation, the script applies GitHub configuration to the repo:

- **Merge strategy** — squash-merge only; merge commits and rebase disabled so
  every squash commit title matches the PR title (Conventional Commits format
  that Release Please parses)
- **Delete branch on merge** — enabled automatically
- **Always suggest updating pull request branches** — enabled
- **Projects** — enabled
- **Actions permissions** — restricted to GitHub-owned and Marketplace-verified
  actions, plus an explicit allowlist for `amannn/action-semantic-pull-request`
  (used by `pr-title-check.yml`)
- **Workflow permissions** — default `read`, with GitHub Actions unable to
  approve pull requests. Release Please uses its dedicated GitHub App token.
- **Fork PR workflows** — disabled for private repos (no separate control
  exists for public repos; their fork-PR approval policy is left as-is)
- **Branch protection on `main`** — requires the relevant status checks to pass
  before merging, and requires a pull request with **zero** required approving
  reviews. That combination is deliberate: direct pushes to `main` are blocked
  (enforcing the convention in the generated `AGENTS.md`) without demanding
  self-review on a solo repository. `enforce_admins: true`, so the gates bind
  the account doing the merging; `strict` is left false, because a
  "branch must be up to date" requirement strands every open PR — release PRs
  worst — on each advance of `main`. The operational runbook for PRs blocked by
  those checks — most often release PRs — lives at
  [`docs/branch-protection-runbook.md`](docs/branch-protection-runbook.md)
  and ships into every generated repository.

  Note that GitHub requires a paid plan for branch protection on **private**
  repositories. The script detects that case and reports it as manual follow-up
  rather than failing.

## GitHub App — Release Please

Release Please runs via a GitHub App rather than the default `GITHUB_TOKEN` so
it can open PRs that trigger other workflows. You will need to supply:

- `RELEASE_PLEASE_CLIENT_ID` — set as a GitHub variable
- `RELEASE_PLEASE_APP_KEY` — set as a GitHub secret

The script will prompt for these interactively (or read them from environment
variables in `--non-interactive` mode). If you skip them during setup, set them
manually afterwards:

```sh
gh variable set RELEASE_PLEASE_CLIENT_ID --repo owner/name --body "<app-client-id>"
gh secret set RELEASE_PLEASE_APP_KEY --repo owner/name
```

## Deployment migration

The previous provider-deployment flags are rejected as unknown options. The
bootstrapper no longer generates or configures provider deployments. Add a
reviewed, application-owned deployment workflow after choosing a provider; keep
it separate from `release-please.yml`.

## Non-interactive mode

All prompts can be bypassed by combining `--non-interactive` with the relevant
flags. Secrets and the Release Please key are read from environment variables:

| Environment variable | Used when |
|---|---|
| `RELEASE_PLEASE_CLIENT_ID` | always |
| `RELEASE_PLEASE_APP_KEY` | always |

Example (CI/CD usage):

```sh
export RELEASE_PLEASE_APP_KEY="..."
export RELEASE_PLEASE_CLIENT_ID="..."
./bootstrap.py \
  --name my-app \
  --type python \
  --org my-org \
  --private \
  --non-interactive
```

## Contributing

**Issues are welcome; external code contributions are not accepted.** Bug
reports and feature requests are genuinely wanted — pull requests, patches, and
code snippets offered for inclusion are not, and will be closed unmerged. See
[`CONTRIBUTING.md`](CONTRIBUTING.md) for the policy and the reasoning.

Forking is permitted on the licence's terms; the policy governs only what is
merged back.

[`AGENTS.md`](AGENTS.md) documents the maintainer workflow — branch, commit, and
release conventions — not an invitation to submit changes.

## License

[Apache License 2.0](LICENSE).
