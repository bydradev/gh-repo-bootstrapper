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
- the hub's size (an 8,000 B budget for its generated part, a 10,000 B
  ceiling), its pinned safety gates, skill pointers and frontmatter, reviewer
  agents, and the ownership stamps on template-owned files
- executable workflow gates — every action pinned to a full commit SHA and
  allowed by the Actions policy the script sets; a timeout on every job that
  declares `runs-on`; no job or step set to `continue-on-error` or given an
  `if:` that is a falsy literal (`false`, `0`, `null`, `''`); the Python and
  Rust suite commands run once, unconditionally; the Next.js e2e runs and
  browser installs tied to their `full` conditions; the release job waiting for
  `test` with no condition of its own; the release App token limited to contents
  and pull requests; and pinned fallback versions of the Python CI tools
- the bootstrapper's own runbook copy and its legacy-digest table

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

CI (`.github/workflows/validate.yml`) runs this validator, the pytest suite
under `tests/`, and the `node:test` suites for the generated baseline scripts
(`node --test templates/*.test.mjs`) on every pull request and on pushes to
`main`. It also renders every configuration's generated Markdown with
`python validate_templates.py --render-markdown <dir>` and lints it with
markdownlint-cli2 using `markdownlint-generated.jsonc`, so generated
`AGENTS.md`, `CLAUDE.md`, READMEs, and docs stay markdownlint-clean.

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

The e2e job in `test.yml` also assumes two things of the scaffold's Playwright
configuration: a project named `chromium`, which ordinary `main` pushes run
alone (`--project=chromium`), and the HTML reporter enabled in CI, which
writes the `playwright-report/` directory the job uploads. Without the HTML
reporter the upload finds nothing and is skipped silently.

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
| `--configure-only` | Apply GitHub config to an existing repo, skip file generation. Leaves branch protection unchanged and asks before changing the Actions policy (see "What the script configures"). Cannot be combined with `--dry-run` |
| `--dry-run` | Print all files that would be created without doing anything. The owner lookup is skipped in dry-run: without `--org`, an interactive run asks for the owner, and a `--non-interactive` run uses a placeholder owner, since nothing downstream contacts GitHub |
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
contacts GitHub; follow with `--configure-only` for repository settings, which
keeps the repository's own branch protection.

### Generated agent layout

The generated `AGENTS.md` is a short hub. It holds the gates every agent must
see (scope, GitHub operations, branches, commits, preservation, definition of
done), the type's tooling commands, a skills table, and `## Project specifics`
last. Detailed procedures live in skills that load when they're relevant:

| Skill (`.agents/skills/<name>/SKILL.md`) | Types |
|---|---|
| `pull-requests`, `worktrees-and-scratch`, `verify-external-claims`, `fresh-eyes-review`, `delegation` | all |
| `screenshot-review` | `nextjs`, `swift` |
| `baseline-process` | `nextjs` |
| `local-validation-<type>` | `nextjs`, `swift`, `rust`, `python` |

`screenshot-review` carries the shared review process for a deterministic
capture lane (image classes, complete-set review, acceptance criteria, promotion
safety) without naming any capture tool. A repository with its own capture lane
or visual-verification procedure keeps those facts in a repository-owned skill,
or a section of one, and names it in `## Project specifics`;
`screenshot-review` tells agents to load that skill first.

Each skill is mirrored as a relative symlink,
`.claude/skills/<name>` to `../../.agents/skills/<name>`, because Claude Code
doesn't scan `.agents/` but does follow symlinked skill folders. Codex,
OpenCode and Antigravity read `.agents/skills` directly. The fresh-eyes review
runs as a separate read-only reviewer agent,
`.claude/agents/fresh-eyes-reviewer.md` and
`.opencode/agents/fresh-eyes-reviewer.md`, and both load the
`fresh-eyes-review` skill. The generated `.gitignore` ignores `.agents/*` and
`.opencode/*` but re-includes `!.agents/skills/` and `!.opencode/agents/`, so
these files are committed.

Why split it? Harnesses cut long instruction files off, and `## Project
specifics` is last, so it's lost first:

- Antigravity reads at most 24,000 B per rule file (its built-in rules
  documentation, checked 2026-10-03).
- Codex stops at `project_doc_max_bytes`, 32 KiB by default
  (`openai/codex` `agents_md.rs` at `c542fb9`, checked 2026-10-03).
- OMO (5.1.12 to 5.1.19, checked 2026-10-05) loads `AGENTS.md` from the
  working folder and its ancestors in full at startup. When it reads a file
  in a subfolder, it injects that folder's `AGENTS.md` as Directory Context,
  in full up to 32 KiB per file. Its rules plugin also adds a second copy,
  on edits and writes as well as reads, which it cuts at 12,000 characters
  (`PI_RULES_MAX_RULE_CHARS`) with a
  `[Rule truncated. Read full rule: <path>]` marker.

The truncated OMO copy is a duplicate, so OMO needs no setting. To drop it,
run OMO with `--pi-rules-mode static`. Directory Context still injects the
full file on reads, but an edit or write in a subfolder that wasn't read
first then gets no nested `AGENTS.md`. This only matters for sessions
started above the repository, since a repository root's `AGENTS.md` loads at
startup. Keep stop-and-ask rules first in `## Project specifics` for
the other harnesses. The 20,000 B `AGENTS.md` warning target stays the same.

### Template-owned files

These files belong to the template and are replaced, not merged, when it
changes:

- the generated skills;
- the two reviewer agents;
- `docs/branch-protection-runbook.md`;
- `docs/screenshot-review.md`;
- `.github/workflows/pr-title-check.yml`;
- `.github/workflows/release-please.yml`;
- `.github/workflows/baseline-review.yml` (`nextjs`).

`docs/lint-baseline.md` and `docs/advisory-baseline.md` aren't in this set.
They're tables each repository edits, so they keep the plain `kept`
behaviour, as do scripts, configs and the other workflows: `ci.yml` and
`test.yml` hold each repository's own test lanes.

Every template-owned file carries a stamp line:

```text
<!-- gh-repo-bootstrapper: template-owned; sha256=<hex> -->
```

A template-owned workflow carries it as a YAML comment on line 1 instead:

```text
# gh-repo-bootstrapper: template-owned; sha256=<hex>
```

The hex is the SHA-256 of the file with the stamp line removed. In a
`SKILL.md` or agent file the stamp sits on the line after the YAML
frontmatter; in other markdown it's line 1. A digest that no longer matches
means someone edited the file locally.

Workflows were first stamped after v0.8.1. An unstamped workflow whose body
equals one a release through v0.8.1 shipped is `stale`, so `--adopt`
upgrades it. One with local changes is `local-modified` and is never
overwritten. Where the changes are jobs or steps of the repository's own, move
them into a separate workflow file, delete the old file, and run `--adopt` to
write the stamped version. Where they change a template step's settings and
can't be moved, drop them, propose them for the template, or keep the file;
while it stays `local-modified`, `--check` and `--adopt` exit 1. An unchanged
release workflow of another type, such as a gated one under `--type simple`,
is also `local-modified`, and the report says to check `--type`: replacing it
would change how releases are gated. A v0.1.0 Next.js release workflow with a
provider deploy job is always `local-modified`: upgrading it would drop the
deploy job.

Before `--adopt` writes a workflow that calls one of the repository's own
reusable workflows (`release-please.yml` calls `test.yml`), it checks that the
called file declares every input passed to it, because GitHub fails a run that
passes an undeclared input. A repository-owned `test.yml` from an older
template may lack one; `--adopt` then refuses and names the missing inputs, so
add them to `test.yml` and re-run.

`bootstrap.py` has no YAML parser: it reads the called file in a strict
subset of YAML (block mappings and sequences, single-line values, block
scalars, no tabs or other unusual whitespace). It refuses with "cannot
verify" for anything else, such as a quoted value that spans lines, an anchor
or an inline `on:` mapping. For a workflow GitHub can load, its answer is
right or it refuses; a file GitHub rejects already fails every run, so that
case is out of scope.

Dependabot keeps updating the actions these workflows use. A workflow's
digest ignores the version after `@` on each `uses:` line and the comment
after it, so a Dependabot bump leaves the file `same`. When `--adopt` upgrades
a `stale` workflow, it keeps the repository's own pin for every action it
already uses, so it never undoes a bump. Any other edit counts as
`local-modified`.

To narrow a template skill for one repository, don't edit the stamped file.
Write the narrower rule in `## Project specifics`, or add a repository-owned
skill under `.agents/skills/` whose name doesn't start with a template skill
name. A stamped file that has been edited is reported as `local-modified` and
is never overwritten.

Repositories adopted before stamps existed may have edited a legacy
`docs/branch-protection-runbook.md` or `docs/screenshot-review.md`. Migrate
once: move the local changes into `## Project specifics` or a repository-owned
skill, delete the old file, and run `--adopt` to write the stamped version.
`--check` shows the local changes as a diff against the nearest released body.
The diff needs the bootstrapper's git release tags; from a copy without them,
`--check` prints a notice and skips it.

### Checking and adopting

`--check PATH --type TYPE` renders the current templates for that type and
reports each file as `same`, `differs`, `missing`, `symlink`, or `unreadable`.
Template-owned files get their own states:

| State | Meaning | `--adopt` |
|---|---|---|
| `same` | matches the current render | nothing |
| `stale` | valid stamp differs from the current render, or an unstamped non-skill body equals the current unstamped render or a recorded legacy body | overwritten, if tracked, clean, LF-terminated and UTF-8 |
| `local-modified` | invalid or mismatched stamp, or an unrecognized unstamped non-skill body | refused |
| `missing` | not present | written |
| `shadowed` | an unstamped `.agents/skills/<template-name>/SKILL.md`, a repository skill whose frontmatter `name` is a template skill name, or a repository skill whose name cannot be read unambiguously as a plain or quoted single-line scalar, or a path that differs only in case from a generated one and is the same file on a case-insensitive filesystem, or a symlinked skill folder whose `SKILL.md` name is a template skill name | refused; use a plain single-line name when the name is ambiguous, and `git mv` a case-renamed file back |
| `ignored` | `git check-ignore` matches the path | refused, fix `.gitignore` first |
| `dangling` | a `.claude/skills` symlink, outside the rendered mirrors, whose target does not exist — left behind by a retired template skill or a wrong `--type` | deleted when it has the mirror shape `../../.agents/skills/<name>`; any other symlink is refused |
| `orphaned` | a stamped file under `.agents/skills`, `.claude/agents` or `.opencode/agents` that the render no longer produces | deleted, only if its digest matches its stamp and git reports no uncommitted or staged change to it; refused inside a repository git cannot read |
| `retired` | a generated `AGENTS.md` heading from an older template that the hub dropped | dropped with `--replace-generated-sections`, unless it holds an unknown level-3 or deeper subheading; any text under it is dropped too, so `--check` prints its line count and first lines |

When a repository's `AGENTS.md` is over 20,000 B in total, `--check` also
prints `warn AGENTS.md total <n> B > 20000 B`. It's a warning only and doesn't
change the exit code; shorten `## Project specifics` by moving reference
material into a repository-owned skill.

Pass the same
type options the repository was generated with — `--postgres` for Next.js,
`--scheme`, `--destination`, and `--xcodegen` for Swift — or the workflows
they shape report as drift. Pass the same `--type` too: when the repository
holds a template-owned skill of another type (for example
`local-validation-nextjs` under `--type simple`), `--check` reports `(--type)`
and `--adopt` refuses before changing anything, since it would otherwise
delete that type's skills. For `AGENTS.md` it reports per section: a
generated section that is `missing` or `differs` (including generated
sections in a different order), and anything `local` —
repository text outside `## Project specifics`, including a subsection added
inside a generated section, or structure it does not parse (setext headings,
an unclosed code fence). The `next dev`-managed block and everything from
`## Project specifics` on are the repository's own and are not compared,
but the block must stay at the top of the file: a moved block is `local`,
and a missing one is `missing`. Only a `## Project specifics` heading
indented by at most three spaces counts; deeper indentation is a code block. For
`.gitignore` it lists the template entries the repository lacks, and for
`CLAUDE.md` it flags a file that does not import `AGENTS.md`. It never writes,
and exits 1 on drift. Templates that embed the repository name use the
directory's name, or, for a linked git worktree whose shared git directory is
its main checkout's `.git`, that checkout's name, so a verification worktree such
as `.worktrees/app/align` renders as `app`.

`--adopt PATH --type TYPE` writes every missing file. It overwrites an
existing file only when it's a `stale` template-owned file (see the table
above), with one more exception that preserves repository-owned content:
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
`git diff` and reverted. An index entry marked `skip-worktree` or
`assume-unchanged` counts as uncommitted, because `git status` hides its
edits. It replaces the file atomically with a new one, keeping its
permission bits, so a hard link elsewhere keeps its old content; a
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
- `ci.yml` — runs the suite on every PR without the browser e2e lane; pushes
  to `main` add Chromium, and the Release Please merge (or a manual dispatch of
  `release-please.yml`) runs every Playwright project
- `test.yml` — reusable suite: enforced production advisory audit and baseline verification, lint, format check, typecheck, unit tests, production build, Playwright e2e
- `baseline-review.yml` — weekly, non-blocking summary of advisory review dates and Dependabot/document parity
- `dependabot.yml` — weekly npm + GitHub Actions updates
- `.nvmrc`, `.npmrc`, `.prettierrc.json`, `.prettierignore`
- `docs/lint-baseline.md` — policy and an empty table for our own inline lint/type suppressions
- `docs/advisory-baseline.md` — policy and an empty table for accepted dependency advisories
- `docs/branch-protection-runbook.md` — operational runbook for PRs blocked by required status checks
- `scripts/baseline-table.mjs`, `scripts/verify-baselines.mjs`, and `scripts/audit-production.mjs` — shared parser plus fail-closed baseline and production-audit checkers
- `scripts/*-baselines.test.mjs` and `scripts/audit-production.test.mjs` — regression tests for the baseline verifier, scheduled review, and production audit
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
- `release-please.yml` — test gate → release-please (no deploy); refuses to
  tag a release merge whose own test run failed
- `ci.yml` — runs the test suite on every PR
- `test.yml` — ruff format check, ruff (lint), mypy (type check), pytest;
  auto-detects and installs `requirements-dev.txt`, `requirements.txt`, or
  `pyproject.toml` extras
- `dependabot.yml` — weekly pip + GitHub Actions updates
- `.python-version`
- `README.md` — project starter with a preferred `uv venv` setup and a
  standard-library `venv` alternative
- `docs/branch-protection-runbook.md` — operational runbook for PRs blocked by required status checks

**Upgrading to 0.8.1:** `test.yml` now runs `ruff format --check .`, so CI
fails on unformatted code. When you `--adopt` 0.8.1 into an existing Python
repository, run `ruff format .` and commit the result in the same pull
request.

### `swift`

CI pipeline for Swift/Xcode projects.

- `pr-title-check.yml`
- `release-please.yml` — test gate → release-please (no deploy); refuses to
  tag a release merge whose own test run failed
- `ci.yml` — runs the `swift-format` lint on every PR; `xcodebuild test` runs
  only on the Release Please merge and on a manual dispatch of
  `release-please.yml`, because macOS runners bill at a multiple of Linux ones
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
`AGENTS.md` tells agents to run
`xcrun swift-format format --recursive --in-place .` after editing Swift files
and to check before pushing.

### `rust`

CI pipeline for Rust crates and workspaces.

- `pr-title-check.yml`
- `release-please.yml` — test gate → release-please (no deploy); refuses to
  tag a release merge whose own test run failed
- `ci.yml` — runs the test suite on every PR
- `test.yml` — `cargo fmt --check`, `cargo clippy -D warnings`, and
  `cargo test` across the workspace; fails with a clear error until a root
  `Cargo.toml` exists
- `dependabot.yml` — GitHub Actions updates only; the generated
  `local-validation-rust` skill says to add a `cargo` entry once `Cargo.toml`
  is committed, since a new repository has no manifest for Dependabot to read
- `.gitignore` — adds Cargo's `/target/` build output
- `README.md` — project starter with rustup setup and the CI commands
- `docs/branch-protection-runbook.md` — operational runbook for PRs blocked by required status checks

Release Please uses the `simple` release type, as for Python and Swift: it
maintains the changelog, tags, and releases but does not edit `Cargo.toml`
versions. The generated `local-validation-rust` skill explains when to move to
the `rust` release type or the `cargo-workspace` plugin.

The bootstrapper does not run `cargo init` or choose a crate layout. The
generated `local-validation-rust` skill tells agents to share one
`CARGO_TARGET_DIR` per repository across worktrees, so each worktree does not
build its own multi-gigabyte `target/`. It lives beside those worktrees and is
deleted with the last of them.

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

- **Merge strategy** — squash-merge only; merge commits and rebase disabled,
  and the default squash commit title and message are set to the PR title and
  body (the Conventional Commits text Release Please parses)
- **Delete branch on merge** — enabled automatically
- **Always suggest updating pull request branches** — enabled
- **Projects** — enabled
- **Actions permissions** — restricted to GitHub-owned and Marketplace-verified
  actions, plus an explicit allowlist for `amannn/action-semantic-pull-request`
  (used by `pr-title-check.yml`) and, for `--type rust`, `dtolnay/rust-toolchain`
  and `Swatinem/rust-cache` (used by `test.yml`; both are user-owned, so the
  verified-creator rule does not cover them). Every action must also be pinned
  to a full commit SHA (`sha_pinning_required`).
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

With `--configure-only` the repository already exists, so two of these are
handled differently. Branch protection on `main` is never replaced: the script
prints the required checks it finds and points to the runbook, because an
existing repository's checks must come from its own pull requests, not from
`--type`. The Actions settings (allowlist, SHA pinning, default token
permissions and, for private repositories, fork PR controls) are compared with
the generated policy; any difference is listed and applied only after you
confirm, and `--non-interactive` lists it and leaves it unchanged.

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
