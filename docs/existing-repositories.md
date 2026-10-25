# Existing repositories

`bootstrap.py` generates a repository once. Templates change afterwards, so
`--check` and `--adopt` bring an existing local checkout back in line. Neither
contacts GitHub; follow with `--configure-only` for repository settings, which
keeps the repository's own branch protection.

A typical round, for a repository generated as `--type nextjs --screenshots`:

```sh
# 1. Read-only report; exits 1 on drift
./bootstrap.py --check ../my-app --type nextjs --screenshots
# 2. Write the changes, on a branch, then review them with git diff
./bootstrap.py --adopt ../my-app --type nextjs --screenshots
# 3. Once, after the first adopt: the repository settings
./bootstrap.py --name my-app --type nextjs --configure-only
```

Commit what `--adopt` changed and open a pull request. Before adopting a new
release, read its notes in [Upgrading](upgrading.md): some ask for a step of
your own, such as a formatter run or a hand merge.

## Checking and adopting

### The report

`--check PATH --type TYPE` renders the current templates for that type and
reports each file as `same`, `differs`, `missing`, `symlink`, or `unreadable`,
and an unedited `nextjs` baseline script from an earlier release as `stale`
(see below).
It reports `.github/pull_request_template.md` as `own` when the repository
already has a pull request template of its own, which `--adopt` keeps, and as
`ignored` when git ignores that path and the repository has no other template
(see [Repository types](repository-types.md)). Template-owned files get their own
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
| `other-type` | a stamped template skill that another `--type`, or `--screenshots`, generates, such as `local-validation-nextjs` under `--type simple`; a `(--type)` row lists them all | refused before anything changes, along with every other file; re-run with the `--type`, and `--screenshots` where it applies, that the repository was generated with |
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

### Pass the options the repository was generated with

Pass the same type options the repository was generated with (`--postgres` for
Next.js, `--scheme`, `--destination`, and `--xcodegen` for Swift), or the
workflows they shape report as drift. `--screenshots` is the exception: a
`nextjs` or `swift` repository that already has the template's copy of
`.agents/skills/screenshot-review/SKILL.md` or `docs/screenshot-review.md` is
treated as using it, and the report says so, so `--adopt` keeps and updates
those files without the flag. The template's copy is a file whose stamp,
edited or not, is its first non-blank line or the first after its frontmatter
(even behind a byte-order mark), or an unstamped doc whose text a release
shipped. A repository's own `docs/screenshot-review.md`, such as its own
screenshot-review process, does not count, even one that shows the stamp in an
example further down. Without the template's skill it is left alone; next to
the template's skill it is reported as `local-modified`, as before, so move it
to another path first.

A Next.js repository's `test.yml` is its own, so `--check` reports it as
`differs`, not `stale`, whether the repository edited it or it was generated
with the other `--postgres`; under that row a line says whether the file and
the render each have a Postgres service (one named `postgres`, or one whose
image is `postgres`), such as "Postgres service: in the render (--postgres),
not in this file; drop --postgres if the repository does not use it". When the
file uses YAML the script does not read, or gives a service's image as a block
scalar or an expression, the line says it cannot tell.

Pass the same `--type` too: when the repository holds a template-owned skill
of another type (for example `local-validation-nextjs` under `--type simple`),
or a stamped `screenshot-review` skill this configuration does not generate,
`--check` reports each such skill as `other-type` and adds a `(--type)` row
naming them, and `--adopt` refuses before changing anything, since it would
otherwise delete those skills.

### How `AGENTS.md` is compared

For `AGENTS.md` it reports per section: a generated section that is `missing`
or `differs` (including generated sections in a different order), and anything
`local`: repository text outside `## Project specifics`, including a
subsection added inside a generated section, or structure it does not parse
(setext headings, an unclosed code fence, a fence indented four or more
columns, an HTML block such as a `<!-- -->` comment or `<details>`, a
generated heading that appears more than once, or a generated heading that
falls inside a code block). A file with CRLF or CR line endings, which
`--adopt` refuses, gets one `differs` row naming them in place of a `differs`
row per section, and keeps its `missing`, `local` and `retired` rows and the
order of its generated sections. A file that mixes LF lines with CRLF ones
keeps every row and gains `(CRLF and LF line endings mixed; convert to LF
first)`. A file with LF lines and a carriage return inside a line keeps every
row too and gains `(carriage return inside a line; remove it first)`, since
converting the line endings leaves it. A leading byte-order mark is one
`local` row. Convert or remove it, then re-run. The `next dev`-managed block
and everything from `## Project specifics` on are the repository's own and are
not compared, except that an unedited guidance paragraph from an older
template there is `retired`. The block must stay at the top of the file: a
moved block is `local`, and a missing one is `missing`. Only a `## Project
specifics` heading indented by at most three spaces counts; deeper indentation
is a code block. Everything from the first such heading on is the
repository's, so a generated heading that appears only after it, as under a
second, early copy of the heading, is `local` and `--adopt` refuses the
rebuild. Only the sections the template places after the last generated
section the file still has above the heading count, so a repository's own
section that shares the name of an earlier generated one stays `missing`.

### Other files

For `.gitignore` and `.prettierignore` it says whether the managed block is
missing or differs, and lists the `.gitignore` entries outside the block the
repository lacks; for `CLAUDE.md` it flags a file that does not import
`AGENTS.md`. It never writes,
and exits 1 on drift. Templates that embed the repository name use the
directory's name, or, for a linked git worktree whose shared git directory is
its main checkout's `.git`, that checkout's name, so a verification worktree
such as `.worktrees/app/align` renders as `app`.

### What `--adopt` writes

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

### The `nextjs` baseline scripts

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

### `.gitignore` and `.prettierignore`

Both files belong to the repository except for one block, between the
`# >>> gh-repo-bootstrapper managed block` and
`# <<< gh-repo-bootstrapper managed block` lines, which holds the entries the
template's own files need: the Playwright CLI and MCP session folders in
`.gitignore`, and the three template-owned workflows in a `nextjs`
`.prettierignore`. A missing file is created like any other. In an existing
one, `--adopt` adds the block at the end, after a blank line, or replaces the
block's lines with the template's, and leaves every line outside it as it
is. Put the repository's own rules outside the block: `--adopt` overwrites an
edit inside it.

The block is left to a person, with the reason, when:

- a `!` line outside it may re-include a path at or under one of its
  entries: one with a component that matches an entry's last component as a
  glob, ignoring case, or one with `**` or a backslash escape. Appended last,
  the block's rules would win over that exception. A `!` line that only
  re-includes a folder above an entry does not count;
- the file has uncommitted changes, is not tracked, or is not LF-terminated
  UTF-8 text, as for the `AGENTS.md` rewrite;
- the markers do not form one begin and one end line (refused).

Other template `.gitignore` entries the repository lacks are still listed,
not written: whether one would override an existing `!` exception depends on
git's full ignore rules across every ignore file (git cannot re-include a
file once a parent directory is excluded). When an entry of the block is also
listed outside it, `--adopt` says so; that line can go.

### Safety

The `AGENTS.md` rewrite needs the file tracked by git with no uncommitted
changes, LF line endings, and UTF-8 text, so the result can be reviewed with
`git diff` and reverted. An index entry marked `skip-worktree` or
`assume-unchanged` counts as uncommitted, because `git status` hides its
edits. When git cannot read the repository at all, for example when its
ownership check (`safe.directory`) refuses it or `.git` or its index cannot be
read, this refusal and the others that need a clean file name git's reason and
the repository instead. It replaces the file atomically with a new one, keeping its
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

### The squash commit default

The user-visible step in `pr-title-check.yml` judges a pull request's title
and body, so it agrees with Release Please only when the squash commit is made
of them. `bootstrap.py` sets that squash default (the pull request title as
the commit title, its body as the message) when it creates a repository and
with `--configure-only`; `--adopt` never contacts GitHub, so it leaves the
setting as it is. A repository `bootstrap.py` did not create, and that never
ran `--configure-only`, usually still has GitHub's default: the commit's own
title and message for a pull request of one commit, and the pull request
title with a list of its commits for more ("Configuring commit squashing for
pull requests" and "Pull request merges", GitHub Docs, read
2026-10-22). A merge through the web interface then commits a message the
check never read, and Release Please may release it differently. After the
first `--adopt`, run `--configure-only` once, which also applies the other
repository settings listed in
[What the script configures](github-settings.md#what-the-script-configures), or pick only the
pull request title and description as the default message under *Allow
squash merging* in the repository's general settings.

## Template-owned files

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
edited up to date (see
[The `nextjs` baseline scripts](#the-nextjs-baseline-scripts)).
`.github/pull_request_template.md` isn't in the set either: it is the
repository's to edit once written, and
[Repository types](repository-types.md) says when `--adopt` writes it.

### Prettier and actionlint

A `nextjs` repository's `.prettierignore` lists the three template-owned
workflows in its managed block, since they must stay verbatim, so a scaffold whose `format:check` is
`prettier --check .` cannot fail on them. Prettier can format the same text
differently between releases (patch releases included;
[Install](https://prettier.io/docs/install), Prettier docs, checked
2026-10-21), and a reformatted workflow would be `local-modified`. `ci.yml`
and `test.yml` stay formatted.

The template's `release-please.yml` sets `concurrency.queue: max`, so a push
no longer cancels the pending run of a release merge (unless 100 runs are
already waiting; then re-run the cancelled one). actionlint 1.7.12 does not
know that key yet, and in `nextjs` it also reports the `vulnerability-alerts:
read` permission of `baseline-review.yml` as an unknown scope, although
GitHub's workflow syntax reference lists it (checked 2026-10-09) and the
weekly review needs it to read Dependabot alerts. A repository that runs
actionlint ignores both for those files:

```yaml
# .github/actionlint.yaml
paths:
  .github/workflows/release-please.yml:
    ignore:
      - 'unexpected key "queue" for "concurrency" section'
  .github/workflows/baseline-review.yml:
    ignore:
      - 'unknown permission scope "vulnerability-alerts"'
```

Remove an entry once an actionlint release recognises it.

### Stamps

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

### Workflows

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

### Action pins

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

### Narrowing a template skill

To narrow a template skill for one repository, don't edit the stamped file.
Write the narrower rule in `## Project specifics`, or add a repository-owned
skill under `.agents/skills/` whose name doesn't start with a template skill
name. A stamped file that has been edited is reported as `local-modified` and
is never overwritten.

### Files from before stamps

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
the workflow was forked from. It does the same when no tag holds the template,
as for a copy of `bootstrap.py` with no `.git` of its own inside another
repository, where git lists that repository's tags. Each release read is a
`git show` that may take up to 10 seconds; if one takes longer (in a partial
clone, git fetching a missing object from a remote that does not answer or
waits on a credential prompt), `--check` stops that git and the fetch it
started, prints a notice naming the read, reads no more releases and skips
the diff.
