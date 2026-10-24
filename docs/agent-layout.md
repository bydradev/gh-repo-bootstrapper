# Generated agent layout

The generated `AGENTS.md` is a short hub. It holds the gates every agent must
see (scope, GitHub operations, branches, commits, preservation, definition of
done), what an agent may do without asking and when it must stop and ask, the
type's tooling commands, a skills table, and `## Project specifics` last.
Unless a request says otherwise, the hub counts a code change as done when its
PR is open, its checks pass and review findings are resolved; merging still
needs explicit authorization. Detailed procedures live in skills that load
when they're relevant. Harnesses with skill support load them by their
descriptions; the hub's skills table gives each one a row saying when to load
it, for every session and for harnesses without skill support.

## Skills

Each type generates these skills:

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
OpenCode and Antigravity read `.agents/skills` directly. OpenCode also scans
`.claude/skills`, so it finds each skill twice and logs a `duplicate skill
name` warning for each one. Both copies are the same file, so the skill's text
is the same, but OpenCode loads them concurrently and lists the copy it kept,
by path, in its system prompt, so that path can differ between sessions and
cost a prompt cache miss (`skill/index.ts` and `session/system.ts` in
[OpenCode v1.19.3](https://github.com/anomalyco/opencode/tree/v1.19.3),
checked 2026-10-22). The generated
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
[Checking and adopting](existing-repositories.md#checking-and-adopting)).

## Reviews

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

### The OpenCode reviewer

The OpenCode reviewer has no built-in edit, subagent or shell tool. MCP,
plugin and custom tools follow the user's OpenCode configuration, whose
default allows them, so a connected server's write tools stay available to it.
It reviews the diff and validation results the implementer or person hands
it, asks for the diff when it has none, and reads files with OpenCode's read
tools, which ask before reading most paths outside
the project, such as a diff saved to a scratch directory. It sets
`external_directory: ask` for that, since OpenCode V2 allows those reads
without asking by default, where V1 asks
([Migrate from V1](https://dev.opencode.ai/v2/docs/migrate-v1/), checked
2026-10-22). On V1 the agent's rule comes after OpenCode's defaults and the
user's own configuration, so the reviewer also asks for the directories those
allow, such as OpenCode's temporary directory, except its tool output
directory (`agent/agent.ts` and `permission/index.ts` in v1.19.3, checked
2026-10-22). It gets no shell
because OpenCode's shell rules see each command in a line separately and keep
a redirect only when it sits directly on one command, so an allowed `git log`
still writes in `git diff && git log > notes` (`tool/shell.ts`,
`session/tools.ts` and `agent/agent.ts` in
[OpenCode v1.19.3](https://github.com/anomalyco/opencode/tree/v1.19.3), the
current npm release, checked 2026-10-16). It denies both `bash` and `shell`.
OpenCode v1.19.3 keeps `bash` as the shell tool's permission key, says it will
be renamed (`tool/shell/id.ts`), and accepts and ignores a `shell` key. The
[permissions page](https://opencode.ai/docs/permissions/) for this agent
format names only `shell`. OpenCode V2 reads this format and maps its `bash`
to V2's `shell` action
([Migrate from V1](https://dev.opencode.ai/v2/docs/migrate-v1/)). All three
were checked 2026-10-22; under either key name, the reviewer has no shell.
OpenCode's free-tier models on its own provider currently refuse an agent
whose shell is denied, with "OpenCode's free tier can only be used from within
OpenCode" ([OpenCode issue 49723](https://github.com/anomalyco/opencode/issues/49723),
open on 2026-10-22), so run this reviewer with another model. `bash: ask` or a
narrow allow rule avoids that error, but a command that yields no pattern,
such as a bare `> file`, skips the shell check, so either would let the
reviewer write.

### The Claude Code reviewer

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

## `## Project specifics`

`## Project specifics` belongs to the repository. The guidance on what goes
there is in a generated section of the hub, *When instructions and reality
disagree*, so it stays current through `--adopt`: durable rules with
stop-and-ask items first, never edits to the generated sections or
template-owned files, reference material in a repository-owned skill, and dated status in
`docs/current-work.md`, a repository-owned file every type gets. The Next.js
App Router note sits outside the `next dev`-managed markers because `next dev`
rewrites everything between them; a repository on the Pages Router says so
under `## Project specifics` rather than editing the note.

## Why the hub is short

Why split it? Harnesses cut long instruction files off, and `## Project
specifics` is last, so it's lost first:

- Antigravity reads at most 24,000 B per rule file (its built-in rules
  documentation, checked 2026-10-03).
- Codex stops at `project_doc_max_bytes`, 32 KiB by default
  (`openai/codex` `agents_md.rs` at `c542fb9`, checked 2026-10-03).
- OmO Native, OMO's standalone `omo` command (npm `omo-ai` 5.1.41 on the
  senpi engine 2026.10.21-1; their packaged source, read 2026-10-22), loads
  `AGENTS.md` from the working folder and its ancestors at startup, up to
  64 KiB per file and 128 KiB in all. When it reads a file in a subfolder, it
  injects that folder's `AGENTS.md` as Directory Context, up to 32 KiB per
  file. Its built-in rules extension also adds a second copy of an
  `AGENTS.md` it did not load at startup, on edits and writes as well as
  reads, which it cuts at 12,000 characters (`PI_RULES_MAX_RULE_CHARS`) with
  a `[Rule truncated. Read full rule: <path>]` marker. OMO's OpenCode edition
  (npm `oh-my-openagent` 5.1.41) injects Directory Context on reads only, cut
  to fit the remaining context window, and adds no second copy.

The truncated OMO copy is a duplicate, so OMO needs no setting. To drop it,
run `omo` with `--pi-rules-mode static`. Directory Context still injects the
full file on reads, but an edit or write in a subfolder that wasn't read
first then gets no nested `AGENTS.md`. This only matters for sessions
started above the repository, since a repository root's `AGENTS.md` loads at
startup. Keep stop-and-ask rules first in `## Project specifics` for
the other harnesses. The 20,000 B `AGENTS.md` warning target stays the same.
