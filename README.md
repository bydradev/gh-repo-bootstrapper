# gh-repo-bootstrapper

Interactive Python script to create standardised GitHub repositories with
pre-configured Actions workflows, Release Please, and Dependabot.

## Requirements

- Python 3.11+
- [gh CLI](https://cli.github.com/): authenticated (`gh auth login`)
- git

No runtime pip dependencies: stdlib only. `bootstrap.py` itself never needs
anything installed beyond a base Python interpreter.

## Development

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
  and no write scope outside `release-please.yml`
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
  release App token limited to contents and pull requests; and pinned fallback
  versions of the Python CI tools
- the word `secrets` in every generated workflow and in this repository's own
  only as a static `secrets.NAME` or a `secrets:` key that opens a mapping,
  because some generated repositories run workflow validators that refuse it
  anywhere else, comments and URLs included
- in `nextjs`, the release job keeping the `release-please` id and its
  credentials and App token steps the names the weekly baseline review reads
  to tell a skipped release from one that ran
- the title check's user-visible step, in every generated `pr-title-check.yml`
  and this repository's own: one step after the title step, in the same job,
  reading the pull request title and body only through its `env:`, never
  through a `${{ }}` expression in its script
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
  files it changes
- the bootstrapper's own bug-report form, whose repository types and flags must
  match `bootstrap.py`'s parser

It also runs self-tests that reproduce each past regression from real rendered
output, so a check that stops firing turns the suite red rather than passing
vacuously. Unlike `bootstrap.py`, it requires PyYAML, a dev-only dependency
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

One assumption is about what a script does, not only its name: `lint` must run
`eslint --max-warnings=0`, with unused disable directives reported. The
generated `docs/lint-baseline.md` relies on both to fail CI on an unused
`eslint-disable` directive and calls the baseline mostly self-cleaning on that
condition; without both, a stale baseline row only surfaces at its review date.
Nothing the bootstrapper generates checks either: `test.yml` runs
`npm run lint` as the scaffold defines it, `scripts/verify-baselines.mjs` does
not read `package.json` or the ESLint configuration, and the generated
`README.md`, `docs/lint-baseline.md` and `local-validation-nextjs` skill state
them as requirements. `create-next-app` does not set the flag: its generated
`lint` script is `eslint` (`create-next-app` 16.4.2, `dist/index.js`, checked
2026-10-22), and ESLint exits with an error status on warnings only when
`--max-warnings` is given ([ESLint v9.x command-line reference](https://eslint.org/docs/v9.x/use/command-line-interface#--max-warnings),
checked 2026-10-22). Reporting unused directives is ESLint 9's default
(`linterOptions.reportUnusedDisableDirectives` defaults to `"warn"`, [ESLint v9.x
rules reference](https://eslint.org/docs/v9.x/use/configure/rules#report-unused-eslint-disable-comments);
"Unused disable directives cause warnings by default" in the [ESLint v9.0.0
release post](https://eslint.org/blog/2024/04/eslint-v9.0.0-released/), checked
2026-10-22), so it holds for a new `create-next-app` project, but not for
ESLint 8 or a configuration that sets the option to `"off"`. Add the flag to the
scaffold's `lint` script and keep the reporting on.

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
| `--name TEXT` | Repository name (lowercase letters, digits, hyphens), or a relative/absolute path ending in one; created in the current directory by default |
| `--type nextjs\|python\|swift\|rust\|simple` | Repository type |
| `--org TEXT` | GitHub org or user (default: authenticated user) |
| `--private` / `--public` | Visibility (default: private) |
| `--postgres` | Add PostgreSQL 16 service to test workflow (nextjs only) |
| `--scheme TEXT` | Xcode scheme name for `xcodebuild test` (swift only) |
| `--destination iphone\|ipad\|macos` | Target destination for `xcodebuild test` (swift only, default: iphone) |
| `--xcodegen` | Generate the Xcode project from `project.yml` in Swift CI |
| `--screenshots` | Add the `screenshot-review` skill and `docs/screenshot-review.md`, for a repository with a screenshot capture lane (nextjs and swift only) |
| `--configure-only` | Apply GitHub config to an existing repo, skip file generation. Leaves branch protection unchanged and asks before changing the Actions policy (see "What the script configures"). Cannot be combined with `--dry-run` |
| `--dry-run` | Print all files that would be created without doing anything. The owner lookup is skipped in dry-run: without `--org`, an interactive run asks for the owner, and a `--non-interactive` run uses a placeholder owner, since nothing downstream contacts GitHub. Piping the output to `head` or a pager is fine: the run ends quietly with exit 0 when the reader closes the pipe, and with an error status when a `--non-interactive` run's options are refused |
| `--non-interactive` | Fail instead of prompting for missing options |
| `--check PATH` | Compare an existing local repository with the current templates; read-only, exits 1 on drift (also when the reader of its output closes the pipe early). Needs `--type` and the type options the repository was generated with |
| `--adopt PATH` | Bring an existing local repository in line without contacting GitHub (see [Existing repositories](#existing-repositories)) |
| `--replace-generated-sections` | With `--adopt`: also replace `AGENTS.md` generated sections whose text differs from the template |

### Examples

```sh
# Fully interactive
./bootstrap.py

# Next.js app: preview files before creating
./bootstrap.py --name my-dashboard --type nextjs --dry-run

# Next.js with PostgreSQL tests in an org
./bootstrap.py --name data-app --type nextjs --postgres --org my-org

# Next.js app with a screenshot capture lane
./bootstrap.py --name my-site --type nextjs --screenshots

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
done), what an agent may do without asking and when it must stop and ask, the
type's tooling commands, a skills table, and `## Project specifics` last.
Unless a request says otherwise, the hub counts a code change as done when its
PR is open, its checks pass and review findings are resolved; merging still
needs explicit authorization. Detailed procedures live in skills that load
when they're relevant. Harnesses with skill support load them by their
descriptions; the hub's skills table gives each one a row saying when to load
it, for every session and for harnesses without skill support:

| Skill (`.agents/skills/<name>/SKILL.md`) | Types |
|---|---|
| `pull-requests`, `worktrees-and-scratch`, `verify-external-claims`, `fresh-eyes-review`, `review-guidelines`, `delegation` | all |
| `screenshot-review` | `nextjs`, `swift`, with `--screenshots` |
| `baseline-process`, `public-site-indexing` | `nextjs` |
| `local-validation-<type>` | `nextjs`, `swift`, `rust`, `python` |

`screenshot-review` carries the shared review process for a deterministic
capture lane (image classes, complete-set review, acceptance criteria, promotion
safety) without naming any capture tool. A repository with its own capture lane
or visual-verification procedure keeps those facts in a repository-owned skill,
or a section of one, and names it in `## Project specifics`;
`screenshot-review` tells agents to load that skill first. The skill and
`docs/screenshot-review.md` are generated only with `--screenshots`. Every hub
keeps the screenshot gates in *Definition of done*: generation is not visual
approval, no live or private data, and no regenerated assets committed before
review. Without the skill, that bullet sends agents to the repository's own
screenshot-review process when it has one.

Each skill is mirrored as a relative symlink,
`.claude/skills/<name>` to `../../.agents/skills/<name>`, because Claude Code
doesn't scan `.agents/` but does follow symlinked skill folders. Codex,
OpenCode and Antigravity read `.agents/skills` directly. The generated
`.gitignore` ignores `.agents/*` and `.opencode/*` but re-includes
`!.agents/skills/` and `!.opencode/agents/`, so these files are committed.

Each `local-validation-<type>` skill describes CI tiers, test configuration
and formatter scope as generated, and says which repository file to check for
the current ones. It tells agents to load first a repository-owned validation
skill named in `## Project specifics`, which governs where it is narrower, so
a repository keeps its own tiers, ports and test-server notes there rather
than in `AGENTS.md`.

`verify-external-claims` also covers third-party skills installed in the
repository, committed or not, for agents to load, such as one a vendor's CLI
installs into `.agents/skills/` with a lockfile entry, but not a skill file that
only ships inside a dependency, such as under `node_modules/`. Agents treat such
installed skills as vendored content: they never run a skill's own update
instructions unasked, refresh one only in a pull request that shows the diff and
names the upstream commit or release (pinning that commit in the lockfile when
the install tool supports a ref), and keep corrections in `## Project specifics`,
or in a repository-owned skill a line there points to, rather than editing the
vendored files. A correction that holds in any repository, such as an outdated
limit, is marked as shared and goes in every repository that vendors the skill
at a revision that still has the error; one that reflects a single
repository's configuration stays there. The update instructions of any other
third-party skill, such as one installed for the user outside the repository,
are still input to assess. A repository whose vendored skill tells agents to
update it names that command in a stop-and-ask line there, added in the pull
request that adds the skill. `--adopt` never updates or removes such a skill. It
reports a `SKILL.md` that is not a symlink as `shadowed` when its `name` is a
template skill name or cannot be read unambiguously (see
[Checking and adopting](#checking-and-adopting)).

Reviews are split by role. `fresh-eyes-review` is the implementer's side: when
substantial work needs a review, what to hand the reviewer, and how to handle
the findings of any review (reproduce each one before changing code, fix or
dispute it by ID with evidence, and leave a P0 or P1 that is not fixed to the
operator). `review-guidelines` is the reviewer's side, whoever started the
review: what to read first, initial and follow-up reviews, focus areas, what
counts as a finding, severities P0 to P3, finding IDs and statuses, the
verdict, a report template, and checks for the repository's stack. It is one
skill name for every type; only its stack section differs. A repository adds
its own review rules as a `### Code review rules` subsection of
`## Project specifics`, which the skill reads first.

The reviewer runs as a separate agent,
`.claude/agents/fresh-eyes-reviewer.md` and
`.opencode/agents/fresh-eyes-reviewer.md`, and both load the
`review-guidelines` skill, or its base branch copy when the change under
review edits it (the head copy on a first adoption, when there is none).
Neither gets a built-in edit tool. The implementer
starts it for a fresh-eyes review, or a person starts it on a branch or pull
request.

The OpenCode reviewer has no built-in edit, subagent or shell tool. MCP,
plugin and custom tools follow the user's OpenCode configuration, whose
default allows them, so a connected server's write tools stay available to it.
It reviews the diff and validation results the implementer or person hands
it, asks for the diff when it has none, and reads files with OpenCode's read
tools, which ask before reading most paths outside
the project, such as a diff saved to a scratch directory. It gets no shell
because OpenCode's shell rules see each command in a line separately and keep
a redirect only when it sits directly on one command, so an allowed `git log`
still writes in `git diff && git log > notes` (`tool/shell.ts`,
`session/tools.ts` and `agent/agent.ts` in
[OpenCode v1.19.3](https://github.com/anomalyco/opencode/tree/v1.19.3), the
current npm release, checked 2026-10-16).
OpenCode's free-tier models on its own provider currently refuse an agent
whose shell is denied, with "OpenCode's free tier can only be used from within
OpenCode" ([OpenCode issue 50627](https://github.com/anomalyco/opencode/issues/50627),
open on 2026-10-16), so run this reviewer with another model. `bash: ask` or a
narrow allow rule avoids that error, but a command that yields no pattern,
such as a bare `> file`, skips the shell check, so either would let the
reviewer write.

Claude Code could block a subagent's Bash commands with a `PreToolUse` hook in
its frontmatter, but it skips a project subagent's frontmatter hooks in a
folder whose workspace trust dialog was never accepted, such as a clone where
it has only run as `claude -p`, which never shows that dialog
([Claude Code subagents](https://code.claude.com/docs/en/sub-agents) and
[permissions](https://code.claude.com/docs/en/permissions), checked
2026-10-16). Whether such a hook runs would depend on the folder, and it would
also have to parse shell commands, which the OpenCode case shows is hard to do
completely. So the Claude Code reviewer is read-only by instruction: its file
tells it to use Bash only for read-only commands.

`## Project specifics` belongs to the repository. The guidance on what goes
there is in a generated section of the hub, *When instructions and reality
disagree*, so it stays current through `--adopt`: durable rules with
stop-and-ask items first, never edits to the generated sections or
template-owned files, reference material in a repository-owned skill, and dated status in
`docs/current-work.md`, a repository-owned file every type gets. The Next.js
App Router note sits outside the `next dev`-managed markers because `next dev`
rewrites everything between them; a repository on the Pages Router says so
under `## Project specifics` rather than editing the note.

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
- `docs/screenshot-review.md` (`nextjs` and `swift`, with `--screenshots`);
- `.github/workflows/pr-title-check.yml`;
- `.github/workflows/release-please.yml`;
- `.github/workflows/baseline-review.yml` (`nextjs`).

`docs/lint-baseline.md`, `docs/advisory-baseline.md` and
`docs/current-work.md` aren't in this set. Each repository edits them, so they
keep the plain `kept` behaviour, as do scripts, configs and the other workflows: `ci.yml` and
`test.yml` hold each repository's own test lanes. The `nextjs` baseline scripts
are the repository's too, but `--adopt` brings a copy the repository never
edited up to date (see [Checking and adopting](#checking-and-adopting)).
`.github/pull_request_template.md` isn't in the set either: it is the
repository's to edit once written, and
[Repository types](#repository-types) says when `--adopt` writes it.

The template's `release-please.yml` sets `concurrency.queue: max`, so a push
no longer cancels the pending run of a release merge (unless 100 runs are
already waiting; then re-run the cancelled one). actionlint 1.7.12 does not
know that key yet; a repository that runs actionlint ignores it for that file:

```yaml
# .github/actionlint.yaml
paths:
  .github/workflows/release-please.yml:
    ignore:
      - 'unexpected key "queue" for "concurrency" section'
```

Every template-owned file carries a stamp line:

```text
<!-- gh-repo-bootstrapper: template-owned; sha256=<hex> -->
```

A template-owned workflow carries it as a YAML comment on line 1 instead:

```text
# gh-repo-bootstrapper: template-owned; template=<template file>; sha256=<hex>
```

It names the template the workflow came from, and its digest covers that
name. A stamped workflow from another template, such as a gated release
workflow under `--type simple`, is `local-modified` and the report says to
check `--type`.

In Markdown, the hex is the SHA-256 of the file with the stamp line removed.
In a `SKILL.md` or agent file the stamp sits on the line after the YAML
frontmatter; in other markdown it's line 1. In a workflow, it's the SHA-256 of
a `template=<template file>` line followed by the file with the stamp line
removed and, on each `uses: owner/repo@ref` line, the ref and any comment after
it removed. A digest that no longer matches means someone edited the file
locally.

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
subset of YAML (block mappings and sequences, single-line values, flow
sequences of plain words and quoted items such as `["3.11", '3.12']`, block
scalars, no tabs or other unusual whitespace). A quoted item in a flow
sequence has no escape and no quote of its own. It refuses with "cannot
verify" for anything else, such as a quoted value that spans lines, a quoted
item with an escape or a quote inside, an anchor or an inline `on:` mapping.
When a line is outside the subset, the refusal names the first such line and
shows its text; a refusal for a reason that is no single line, such as a
repeated key or `on:` written as a block sequence, names none. For a workflow
GitHub can load, its answer is right or it refuses; a file GitHub rejects
already fails every run, so that case is out of scope.

Dependabot keeps updating the actions these workflows use. A workflow's
digest ignores the version after `@` on each `uses:` line and the comment
after it, so a Dependabot bump leaves the file `same`. When `--adopt` upgrades
a `stale` workflow, it keeps the repository's own pin for every action it
already uses, so it never undoes a bump, and its report lists each kept pin
that differs from the template's. Any other edit counts as
`local-modified`. The other side of this: a pin the template
changes does not reach a repository through `--adopt`; its Dependabot brings
it. A template change that needs a newer action version must keep working on
the older one, or its release notes must say to merge the Dependabot bump
before adopting.

To narrow a template skill for one repository, don't edit the stamped file.
Write the narrower rule in `## Project specifics`, or add a repository-owned
skill under `.agents/skills/` whose name doesn't start with a template skill
name. A stamped file that has been edited is reported as `local-modified` and
is never overwritten.

Repositories adopted before stamps existed may have edited a legacy
`docs/branch-protection-runbook.md` or `docs/screenshot-review.md`. Migrate
once: move the local changes into `## Project specifics` or a repository-owned
skill, delete the old file, and run `--adopt` to write the stamped version.
For `docs/screenshot-review.md`, run `--adopt --screenshots`: without the flag,
a `nextjs` or `swift` repository left with no template copy of the
screenshot-review skill or doc counts as not using screenshot review, so
`--adopt` refuses its `AGENTS.md`, and with `--replace-generated-sections`
takes the skill's row and pointer out of the hub. The same holds for an
edited, stamped screenshot-review skill or doc that you delete to regenerate.
`--check` shows the local changes as a diff against the nearest body: for an
unstamped doc, one a release through v0.6.0 shipped; for an unstamped workflow,
one any release shipped or today's template, so a workflow forked from a later
template doesn't show that template's own later changes as the repository's.
A workflow's diff header names its base, such as
`legacy/v0.11.0/.github/workflows/release-please.yml` (the first release that
shipped the body) or `current/.github/workflows/release-please.yml`; a body
from another type's template is named by its template file, such as
`legacy/v0.12.0/templates/release-please-gated.yml`. A copy that equals its base
apart from the missing stamp is reported as that, and as one to check `--type`
for when the base is another type's. The diff needs the bootstrapper's git
release tags; from a copy without them, or for a workflow from a shallow clone
or one with no tag through v0.8.1, `--check` prints a notice and skips it,
since the few releases such a clone holds could name a base later than the one
the workflow was forked from.

### Checking and adopting

`--check PATH --type TYPE` renders the current templates for that type and
reports each file as `same`, `differs`, `missing`, `symlink`, or `unreadable`,
and an unedited `nextjs` baseline script from an earlier release as `stale`
(see below).
It reports `.github/pull_request_template.md` as `own` when the repository
already has a pull request template of its own, which `--adopt` keeps, and as
`ignored` when git ignores that path and the repository has no other template
(see [Repository types](#repository-types)). Template-owned files get their own
states:

| State | Meaning | `--adopt` |
|---|---|---|
| `same` | matches the current render | nothing |
| `stale` | valid stamp differs from the current render, or an unstamped non-skill body equals the current unstamped render or a recorded legacy body | overwritten, if tracked, clean, LF-terminated and UTF-8 |
| `local-modified` | invalid or mismatched stamp, or an unrecognized unstamped non-skill body | refused |
| `missing` | not present | written; refused when something other than a file is at the path, such as a directory, or a file where a folder belongs |
| `shadowed` | an unstamped `.agents/skills/<template-name>/SKILL.md`, a repository skill whose frontmatter `name` is a template skill name, or a repository skill whose name cannot be read unambiguously as a plain or quoted single-line scalar, or a path that differs only in case from a generated one and is the same file on a case-insensitive filesystem, or a symlinked skill folder whose `SKILL.md` name is a template skill name | refused; move an unstamped file aside, or rename the skill if it is the repository's own; use a plain single-line name when the name is ambiguous; and `git mv` a case-renamed file back |
| `ignored` | `git check-ignore` matches the path | refused, fix `.gitignore` first |
| `dangling` | a `.claude/skills` symlink, outside the rendered mirrors, whose target does not exist (left behind by a retired template skill or a wrong `--type`) | deleted when it has the mirror shape `../../.agents/skills/<name>` and git tracks it with no uncommitted change; any other symlink, and one git does not track, is refused |
| `orphaned` | a stamped file under `.agents/skills`, `.claude/agents` or `.opencode/agents` that the render no longer produces | deleted, only if its digest matches its stamp and git tracks it with no uncommitted or staged change; refused when git does not track it, outside a git repository, and inside a repository git cannot read. Deleting a skill's files also removes the folders this leaves empty and then, in the same run, the `.claude/skills` mirror that pointed at the folder (see `dangling`); a folder it cannot remove is refused and keeps its mirror |
| `retired` | a generated `AGENTS.md` heading from an older template that the hub dropped, or an unedited guidance paragraph an older template put inside `## Project specifics` | dropped with `--replace-generated-sections`, unless the section holds an unknown level-3 or deeper subheading; any text under a retired heading is dropped too, so `--check` prints its line count and first lines. An edited guidance paragraph is the repository's text and stays |

A path is `unreadable` when the user running the command cannot read the file
or cannot search a directory above it, such as a skill folder owned by another
user in a shared or mounted checkout. The detail names the directory, `--check`
still reports every other file and exits 1, and `--adopt` refuses that path and
goes on with the others. A repository-owned folder under `.agents/skills`,
`.claude/agents` or `.opencode/agents` that can be listed but not searched is
reported as `unreadable` itself, since the scan for orphaned template files
cannot look inside it. That scan skips a folder it cannot even list without a
row.

When a repository's `AGENTS.md` is over 20,000 B in total, `--check` also
prints `warn AGENTS.md total <n> B > 20000 B`. It's a warning only and doesn't
change the exit code; shorten `## Project specifics` by moving reference
material into a repository-owned skill.

Pass the same
type options the repository was generated with (`--postgres` for Next.js,
`--scheme`, `--destination`, and `--xcodegen` for Swift), or the workflows
they shape report as drift. `--screenshots` is the exception: a `nextjs` or
`swift` repository that already has the template's copy of
`.agents/skills/screenshot-review/SKILL.md` or `docs/screenshot-review.md` is
treated as using it, and the report says so, so `--adopt` keeps and updates
those files without the flag. The template's copy is a file whose stamp,
edited or not, is its first non-blank line or the first after its frontmatter
(even behind a byte-order mark), or an unstamped doc whose text a release
shipped. A repository's own `docs/screenshot-review.md`, such as its own
screenshot-review process, does not count, even one that shows the stamp in
an example further down. Without the template's skill it is left alone; next
to the template's skill it is reported as `local-modified`, as before, so
move it to another path first. Pass the same
`--type` too: when the repository holds a template-owned skill of another type
(for example `local-validation-nextjs` under `--type simple`), or a stamped
`screenshot-review` skill this configuration does not generate, `--check`
reports `(--type)` and `--adopt` refuses before changing anything, since it
would otherwise delete those skills. For `AGENTS.md` it reports per section: a
generated section that is `missing` or `differs` (including generated
sections in a different order), and anything `local`:
repository text outside `## Project specifics`, including a subsection added
inside a generated section, or structure it does not parse (setext headings,
an unclosed code fence, a fence indented four or more columns, an HTML
block such as a `<!-- -->` comment or `<details>`, a
generated heading that appears more than once, or a generated heading that
falls inside a code block). A file with CRLF or CR line
endings, which `--adopt` refuses, gets one `differs` row naming them in place of
a `differs` row per section, and keeps its `missing`, `local` and `retired`
rows and the order of its generated sections. A file that mixes LF lines with
CRLF ones keeps every row and gains
`(CRLF and LF line endings mixed; convert to LF first)`. A file with LF lines
and a carriage return inside a line keeps every row too and gains
`(carriage return inside a line; remove it first)`, since converting the line
endings leaves it. A leading byte-order mark is one `local` row. Convert or
remove it, then re-run. The `next dev`-managed block and everything from
`## Project specifics` on are the repository's own and are not compared, except
that an unedited guidance paragraph from an older template there is `retired`.
The block must stay at the top of the file: a moved block is `local`, and a
missing one is `missing`. Only a `## Project specifics` heading
indented by at most three spaces counts; deeper indentation is a code block. For
`.gitignore` it lists the template entries the repository lacks, and for
`CLAUDE.md` it flags a file that does not import `AGENTS.md`. It never writes,
and exits 1 on drift. Templates that embed the repository name use the
directory's name, or, for a linked git worktree whose shared git directory is
its main checkout's `.git`, that checkout's name, so a verification worktree such
as `.worktrees/app/align` renders as `app`.

`--adopt PATH --type TYPE` writes every missing file. It overwrites an
existing file only when it's a `stale` template-owned file (see the table
above) or an unedited `nextjs` baseline script (below), with one more
exception that preserves repository-owned content:
`AGENTS.md` is rebuilt from the template, keeping `## Project specifics` (and
everything after it, less any `retired` guidance paragraph) and the
`next dev`-managed block. The rebuild is refused
while anything `local` remains; move those rules under `## Project specifics`
first. A generated section whose text differs may be an older template or a
local edit, and the script cannot tell which, so it is replaced only with
`--replace-generated-sections`, which lists those sections and asks before
writing (`--non-interactive` skips the prompt).

The `nextjs` baseline scripts, `scripts/audit-production.mjs`,
`scripts/verify-baselines.mjs` and `scripts/review-baselines.mjs` with their
`.test.mjs` files and `scripts/baseline-table.mjs`, belong to the repository,
so a copy that matches no release, such as an edited one, is reported as
`differs` and kept. A copy whose bytes equal one a release shipped was never
edited: `--check` reports it as `stale`, naming that release, and `--adopt`
replaces it with the current template if git tracks it with no uncommitted
changes. Each script changes only together with its test and
`scripts/baseline-table.mjs`, which all three scripts import, so `--adopt`
neither updates an unedited copy nor creates a missing one while another file
of its group is edited, untracked or has uncommitted changes, cannot be
written (such as a folder at a missing file's path), or is kept for the same
reason, and names the file that holds it back. A missing file that git ignores
or still has a change for, such as a staged deletion, is not recreated and
holds its group the same way. Merge the template's changes into that group by hand, or
commit the file and re-run `--adopt`.

For an existing `.gitignore`, missing entries are listed, not written; a
missing `.gitignore` is created like any other file. Whether an added rule
would override an existing `!` exception depends on git's full ignore rules
across every ignore file (git cannot re-include a file once a parent
directory is excluded), so that edit is left to a person.

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
every race with a concurrent process (for example one moving a directory out
of `PATH` mid-run), so do not run it while an editor, agent, or build is
writing to the same checkout. A failure on one file is reported as `refused`
without stopping the others, and `--adopt` exits 1 when it refused anything.

### Upgrading to 0.17.0

`nextjs`: the lint baseline no longer states as fact that `npm run lint` runs
with `--max-warnings=0`. Nothing the bootstrapper generates provides or checks
the flag, and the `lint` script of a new `create-next-app` project with the
ESLint option, `eslint`, does not set it, so the baseline's claim that an unused
`eslint-disable` directive fails CI held only for a scaffold that had added the
flag. The claim also needs ESLint to report unused disable directives, which is
ESLint 9's default but not ESLint 8's or that of a configuration that sets
`reportUnusedDisableDirectives` to `"off"`. The generated `README.md` and
`docs/lint-baseline.md` now say that `npm run lint` must run
`eslint --max-warnings=0` with unused disable directives reported, and that
without both a stale baseline row only surfaces at its review date; the
`local-validation-nextjs` skill says the same. `--adopt` brings the skill, which
is template-owned. The README and `docs/lint-baseline.md` belong to the
repository, so `--adopt` reports them as `kept` and `--check` as `differs`:
merge the wording by hand from the files in `templates/` at the `v0.17.0` tag.
The change that matters is in your own `package.json` and ESLint configuration:
set the `lint` script to `eslint --max-warnings=0`, keeping any other arguments
it has, and keep unused disable directives reported (ESLint 9's default;
`--report-unused-disable-directives` or `reportUnusedDisableDirectives` on
ESLint 8), or a stale `eslint-disable` directive and its baseline row go
unnoticed until the row's review date.

### Upgrading to 0.16.1

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

### Upgrading to 0.16.0

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
[Checking and adopting](#checking-and-adopting)). A repository that still has
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

### Upgrading to 0.15.3

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

### Upgrading to 0.15.2

The `verify-external-claims` skill's *Third-party skills* rules now cover a
third-party skill installed in the repository for agents to load, not a skill
file that only ships inside a dependency, such as under `node_modules/`, so
restoring dependencies is not a skill update unless a dependency's skill is
linked for agents to load. The `AGENTS.md` *Skills* row for the skill now reads
"rely on an external claim or add, update, or follow a third-party skill", so
an agent that only reads the table also loads it before installing one.
`--check` reports the skill as `stale` and *Skills* as `differs`; take both
with `--adopt --replace-generated-sections`.

### Upgrading to 0.15.1

The `verify-external-claims` skill's *Third-party skills* rules now cover only
third-party skills installed in the repository, committed or not; the update
instructions of any other third-party skill, such as one installed for the
user, are still input to assess. A correction to a vendored skill stays in
`## Project specifics` until a refresh brings in the upstream fix, and the
`skills` 1.7.4 pinning example names its source and asks for a full commit
SHA. `--check` reports the skill as `stale`, and `--adopt` updates it.

### Upgrading to 0.14.1

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

### Upgrading to 0.14.0

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
its `env:`, and its script prints none of the body.

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
[Repository types](#repository-types)).
The step follows Release Please's default changelog sections, which every
generated `release-please-config.json` uses; a repository that sets
`changelog-sections` to show other types would see the check disagree with
its releases.

### Upgrading to 0.13.0

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

### Upgrading to 0.12.1

`release-please.yml` changes only in its comments. One no longer uses the
word `secrets` except in `secrets.NAME`: some repositories' workflow
validators refuse the word anywhere else, comments and URLs included. In
`nextjs`, another says which step names the baseline review reads. `--check`
reports the file as `stale`, and `--adopt` updates it. A repository that kept its
0.11.0 `release-please.yml` for that reason can take it now, which also brings
in 0.12.0's credentials check, which the section on the Release Please GitHub
App below describes.

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

### Upgrading to 0.12.0

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
[Checking and adopting](#checking-and-adopting)), and passing the flag
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

### Upgrading to 0.11.0

`bootstrap.py` now needs Python 3.11 or newer.

`--adopt` brings in the template-owned files: the skills, the reviewer agents,
`docs/branch-protection-runbook.md`, `pr-title-check.yml`, `release-please.yml`
and, for `nextjs`, `baseline-review.yml`. Add `--replace-generated-sections` to update the
generated sections of `AGENTS.md`. The new `release-please.yml` uses
`concurrency.queue: max`; a repository that runs actionlint 1.7.12 needs the
exception shown under [Template-owned files](#template-owned-files).

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

## Repository types

Every type gets a type-specific `README.md` starter, `AGENTS.md` and
`CLAUDE.md` (contribution guidance), `docs/current-work.md` (dated status),
`.github/pull_request_template.md` (asks for the `User-visible:` line),
`.gitignore`, `release-please-config.json`, and
`.release-please-manifest.json` seeded at `0.1.0`. The per-type lists below
highlight the additional files and README guidance for that type.

The pull request template belongs to the repository. `--adopt` writes it only
when the repository has no template of its own where GitHub reads one, in
`.github/`, the root or `docs/`: a `pull_request_template` file in any case
and with any extension or none, since GitHub's names are not case sensitive
and can end in `.md` or `.txt`. A symlink at `.github/pull_request_template.md`
counts as the repository's own template too when it points to a file, and
`--adopt` refuses one that does not. A `PULL_REQUEST_TEMPLATE` folder does
not count: GitHub fills a pull request from its templates only when a link
names one with the `template` query parameter, so `--adopt` adds the generated
template beside it as the default. A template that git ignores does not
count, and when git ignores `.github/pull_request_template.md`, `--adopt`
refuses it, whether it is missing or an untracked file is already there,
since neither would reach the default branch. GitHub uses an account or
organization default from a `.github` repository only when a repository has
no template, so the generated one replaces such a default. To go on using the
default, copy it into the repository as its own template
([About issue and pull request templates](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/about-issue-and-pull-request-templates),
[Creating a pull request template for your repository](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository),
[Using query parameters to create a pull request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/using-query-parameters-to-create-a-pull-request)
and [Creating a default community health file](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file),
all checked 2026-10-19).

The generated `AGENTS.md` ends with a `## Project specifics` section. Put
repository-specific rules there, below every generated section, so later
template updates can be applied without overwriting them.

### `nextjs`

Full CI pipeline for Next.js applications.

- `pr-title-check.yml`: Conventional Commits validation on PR titles, and a
  `User-visible: yes` or `User-visible: no` line in PR bodies that must agree
  with the title (see [Upgrading to 0.14.0](#upgrading-to-0140))
- `release-please.yml`: test → release-please; deployment remains application-owned
- `ci.yml`: runs the suite on every PR without the browser e2e lane; pushes
  to `main` add Chromium, and the Release Please merge (or a manual dispatch of
  `release-please.yml`) runs every Playwright project
- `test.yml`: reusable suite (enforced production advisory audit and baseline verification, lint, format check, typecheck, unit tests, production build, Playwright e2e)
- `baseline-review.yml`: weekly, non-blocking summary of advisory review dates and Dependabot/document parity
- `dependabot.yml`: weekly npm + GitHub Actions updates
- `.nvmrc`, `.npmrc`, `.prettierrc.json`, `.prettierignore`
- `docs/lint-baseline.md`: policy and an empty table for our own inline lint/type suppressions
- `docs/advisory-baseline.md`: policy and an empty table for accepted dependency advisories
- `docs/branch-protection-runbook.md`: operational runbook for PRs blocked by required status checks
- `scripts/baseline-table.mjs`, `scripts/verify-baselines.mjs`, and `scripts/audit-production.mjs`: shared parser plus fail-closed baseline and production-audit checkers
- `scripts/*-baselines.test.mjs` and `scripts/audit-production.test.mjs`: regression tests for the baseline verifier, scheduled review, and production audit
- `README.md` and `AGENTS.md`: project starter, quality-baseline pointers, and contribution guidance

Options:

- `--postgres`: adds a PostgreSQL 16 service container to the build job
- `--screenshots`: adds the `screenshot-review` skill and
  `docs/screenshot-review.md`, for an app with a screenshot capture lane

`ci.yml` and `release-please.yml` use the canonical light-PR/full-release
caller contract. `test.yml` is necessarily scaffold-general: it retains that
`full` input and adds the optional PostgreSQL service, while each generated
application supplies its own package scripts, which must include a `lint`
script that runs `eslint --max-warnings=0` (see
[Next.js npm-script assumptions](#nextjs-npm-script-assumptions)), and any
application-owned release-triggered deployment workflow.

### `python`

CI pipeline for Python projects.

- `pr-title-check.yml`
- `release-please.yml`: test gate → release-please (no deploy); refuses to
  tag a release merge whose own test run failed
- `ci.yml`: runs the test suite on every PR
- `test.yml`: ruff format check, ruff (lint), mypy (type check), pytest;
  installs a uv project from `uv.lock` with `uv sync --locked`, and otherwise
  auto-detects `requirements-dev.txt`, `requirements.txt`, or `pyproject.toml`
  with its `dev` extra and `dev` dependency group
- `dependabot.yml`: weekly pip + GitHub Actions updates; switch `pip` to `uv`
  once the project commits a `uv.lock`, so Dependabot updates the lockfile
- `.python-version`
- `README.md`: project starter with a preferred `uv venv` setup and a
  standard-library `venv` alternative
- `docs/branch-protection-runbook.md`: operational runbook for PRs blocked by required status checks

**Upgrading to 0.8.1:** `test.yml` now runs `ruff format --check .`, so CI
fails on unformatted code. When you `--adopt` 0.8.1 into an existing Python
repository, run `ruff format .` and commit the result in the same pull
request.

### `swift`

CI pipeline for Swift/Xcode projects.

- `pr-title-check.yml`
- `release-please.yml`: test gate → release-please (no deploy); refuses to
  tag a release merge whose own test run failed
- `ci.yml`: runs the `swift-format` lint on every PR; `xcodebuild test` runs
  only on the Release Please merge and on a manual dispatch of
  `release-please.yml`, because macOS runners bill at a multiple of Linux ones
- `test.yml`: `swift-format lint --recursive --strict` (formatting gate) then
  `xcodebuild test` on `macos-26`; scheme set from `--scheme`, destination
  resolved dynamically at CI time from `--destination`; with `--xcodegen`, CI
  installs pinned XcodeGen 2.46.0 and generates the project first
- `dependabot.yml`: weekly GitHub Actions updates
- `.swift-format`: Apple swift-format ruleset (default rules; `AlwaysUseLowerCamelCase`
  left on; disable it deliberately per-repo if wire-format DTOs need snake_case fields)
- `README.md`: project starter with local-development and verification sections
- `docs/branch-protection-runbook.md`: operational runbook for PRs blocked by required status checks

Requires `--scheme`. Destination defaults to `iphone` (an available iPhone
simulator, picked dynamically in CI); pass `--destination ipad` for an iPad
simulator or `--destination macos` for a macOS destination. Pass
`--screenshots` for an app with a screenshot capture lane: it adds the
`screenshot-review` skill and `docs/screenshot-review.md`.

Pass `--xcodegen` when `project.yml` will be the source of truth and generated
`.xcodeproj` output should stay out of git. The generated `AGENTS.md` explains
the local Xcode workflow. Swift package declarations inside XcodeGen manifests
are not supported by Dependabot, so a new Swift repo gets the Actions-only
config; after adding a root `Package.swift` or another supported Swift manifest,
opt in deliberately by copying [`templates/dependabot-swift.yml`](templates/dependabot-swift.yml)
over `.github/dependabot.yml`. That file is a reference snippet; the
bootstrapper never renders it.

Formatting is enforced from the first commit: `test.yml` fails CI on any
`swift-format lint --recursive --strict` violation, and the generated
`AGENTS.md` tells agents to run
`xcrun swift-format format --recursive --in-place .` after editing Swift files
and to check before pushing.

### `rust`

CI pipeline for Rust crates and workspaces.

- `pr-title-check.yml`
- `release-please.yml`: test gate → release-please (no deploy); refuses to
  tag a release merge whose own test run failed
- `ci.yml`: runs the test suite on every PR
- `test.yml`: `cargo fmt --check`, `cargo clippy -D warnings`, and
  `cargo test` across the workspace; fails with a clear error until a root
  `Cargo.toml` exists
- `dependabot.yml`: GitHub Actions updates only; the generated
  `local-validation-rust` skill says to add a `cargo` entry once `Cargo.toml`
  is committed, since a new repository has no manifest for Dependabot to read
- `.gitignore`: adds Cargo's `/target/` build output
- `README.md`: project starter with rustup setup and the CI commands
- `docs/branch-protection-runbook.md`: operational runbook for PRs blocked by required status checks

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

Release Please only, suitable for scripts, docs, or any project without a
test suite.

- `pr-title-check.yml`
- `release-please.yml`: single-job, no test gate
- `dependabot.yml`: GitHub Actions updates only
- `README.md`: concise project starter and navigation guide
- `docs/branch-protection-runbook.md`: operational runbook for PRs blocked by required status checks

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
- **Fork PR workflows:** disabled for private repos (no separate control
  exists for public repos; their fork-PR approval policy is left as-is)
- **Branch protection on `main`:** requires the relevant status checks to pass
  before merging, and requires a pull request with **zero** required approving
  reviews. That combination is deliberate: direct pushes to `main` are blocked
  (enforcing the convention in the generated `AGENTS.md`) without demanding
  self-review on a solo repository. `enforce_admins: true`, so the gates bind
  the account doing the merging; `strict` is left false, because a
  "branch must be up to date" requirement strands every open PR (release PRs
  worst) on each advance of `main`. The runbook for PRs blocked by those
  checks, most often release PRs, is a short symptom, check and action
  procedure at
  [`docs/branch-protection-runbook.md`](docs/branch-protection-runbook.md)
  and ships into every generated repository. The incident behind several of
  its rules, with its run IDs and SHAs, is kept only in this repository, in
  [`docs/archive/branch-protection-incident.md`](docs/archive/branch-protection-incident.md).

With `--configure-only` the repository already exists, so two of these are
handled differently. Branch protection on `main` is never replaced: the script
prints the required checks it finds and points to the runbook, because an
existing repository's checks must come from its own pull requests, not from
`--type`. The Actions settings (allowlist, SHA pinning, default token
permissions and, for private repositories, fork PR controls) are compared with
the generated policy; any difference is listed and applied only after you
confirm, and `--non-interactive` lists it and leaves it unchanged.

These settings are applied one at a time and nothing is rolled back. If one
fails after the files are pushed, the script lists the settings it applied and
the ones it did not, and prints the `--configure-only` command that applies
the rest.

  Note that GitHub requires a paid plan for branch protection on **private**
  repositories. The script detects that case and reports it as manual follow-up
  rather than failing.

## GitHub App for Release Please

Release Please runs via a GitHub App rather than the default `GITHUB_TOKEN` so
it can open PRs that trigger other workflows. You will need to supply:

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

## Deployment migration

The previous provider-deployment flags are rejected as unknown options. The
bootstrapper no longer generates or configures provider deployments. Add a
reviewed, application-owned deployment workflow after choosing a provider; keep
it separate from `release-please.yml`.

## Non-interactive mode

All prompts can be bypassed by combining `--non-interactive` with the relevant
flags. The optional features `--postgres`, `--xcodegen` and `--screenshots`
stay off unless their flag is passed; an interactive run asks about each, with
No as the default. Secrets and the Release Please key are read from
environment variables:

| Environment variable | Used when |
|---|---|
| `RELEASE_PLEASE_CLIENT_ID` | always |
| `RELEASE_PLEASE_APP_KEY` | always |

Example (CI/CD usage):

```sh
export RELEASE_PLEASE_APP_KEY="$(cat path/to/app-key.pem)"
export RELEASE_PLEASE_CLIENT_ID="..."
./bootstrap.py \
  --name my-app \
  --type python \
  --org my-org \
  --private \
  --non-interactive
```

## Contributing

Issues and pull requests are welcome, under the
[code of conduct](CODE_OF_CONDUCT.md). Every commit in a pull request needs a
Developer Certificate of Origin sign-off (`git commit -s`). See
[`CONTRIBUTING.md`](CONTRIBUTING.md) for the steps, and
[`AGENTS.md`](AGENTS.md) for the branch, commit and release conventions.

## License

`bootstrap.py`, the validator, the tests and the docs are licensed under the
[Apache License 2.0](LICENSE).
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) is adapted from the Contributor
Covenant 3.0 and keeps its CC BY-SA 4.0 licence.

The files under [`templates/`](templates/) are licensed under
[MIT-0](templates/LICENSE) (`SPDX-License-Identifier: MIT-0`). The files
`bootstrap.py` generates from them belong to the repository they are written
into: use, change and relicense them as you like, with no notice or
attribution to keep.
