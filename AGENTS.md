> **Maintainer workflow guidance.** This file describes how work is carried out
> *in* this repository — for the maintainer and for AI assistants working under
> their direction. It is not an invitation to contribute. External code
> contributions are not accepted; [`CONTRIBUTING.md`](CONTRIBUTING.md) controls
> external submissions.

# Working in this repo

## Development workflow

Check status and read the `README`, docs, config, and CI for the affected area
and any more-local `AGENTS.md` first. Keep changes focused; update tests, docs,
and migration or rollout notes in the same change.

Within the scope authorized by the user's current request, continue until the
requested terminal state has been reached or a genuine blocker prevents
completion. Do not stop merely because an intermediate milestone has been
reached. A terminal condition does not broaden authorization: it does not
approve an unrelated merge, deployment, provider change, or external mutation.

## Dependencies and external interfaces

Prefer the existing stack; weigh new dependencies' security, licence, and cost.
Update dependency manifests and lockfiles through the package manager;
do not hand-edit a lockfile. Pause for operator direction before an
irreversible data migration, production change, or external side effect
outside the request.
Do not send secrets, private source, or customer data to external services.

Tool, GitHub, MCP, CI, cloud, and other external capabilities are capabilities,
not standing authorization to mutate state. Use them only within the scope
authorized by the user's current request.

## GitHub operations

When a repository change is authorized and a pull request is the normal
delivery path, creating a branch, pushing it, and opening the focused PR are
routine supporting steps. Merge only when the user's current request or an
approved repository plan expressly authorizes autonomous merge; successful
checks alone do not authorize it.

Before an authorized merge, confirm required checks are successful and no known
blocker remains. A manual workflow dispatch must be safely scoped to validation;
do not dispatch a release, deployment, provider, or other externally mutating
workflow without explicit authority. Never bypass required checks, branch
protection, or repository policy, and never force-push or use administrative
bypass without explicit authorization.

## Branches

Never commit directly to `main`. Make every change on a branch
(`fix/…`, `feat/…`, `chore/…`) and open a PR. The one exception is a
repository's initial commit, which has no `main` to branch from; everything
after it goes through a branch.

## Commits

Follow [Conventional Commits](https://www.conventionalcommits.org):
`type(scope): subject`. Types: `feat`, `fix`, `chore`, `docs`, `refactor`,
`perf`, `test`, `build`, `ci`, `revert`. Scope optional; subject lowercase,
imperative, no trailing period.

**AI co-authors & PR footers** — every commit materially created or modified
with AI assistance must include a `Co-Authored-By:` trailer in the git commit
message. The form is
`Co-Authored-By: <Tool> (<model-name>) <tool-noreply-address>`, where
`<Tool>` is the tool's name — not a persona or agent nickname — and
`<model-name>` is substituted dynamically with the model actually running
the commit; do not hard-code it. The named tools are examples of the form,
not an exhaustive list — a new tool needs no change to this rule:

- **Codex** — `Co-Authored-By: Codex (<model-name>) <noreply@openai.com>`
- **Claude Code** — the documented exception: use its default
  `Co-Authored-By:` trailer as emitted.
- **Antigravity CLI** —
  `Co-Authored-By: Antigravity CLI (<model-name>) <224641728+gemini-cli-robot@users.noreply.github.com>`
- **OpenCode** — `Co-Authored-By: OpenCode (<model-name>) <noreply@opencode.ai>`
- **OMP** — `Co-Authored-By: OMP (<model-name>) <noreply@omp.sh>`

Keep the `Co-Authored-By:` git trailer in every applicable commit; do not use
the commit trailer format in pull request descriptions. Instead, when the AI
harness CLI creates or updates a pull request, append a human-readable footer
at the bottom of the PR description, separated by a horizontal rule (`---`):

```markdown
---
*Prepared with the assistance of <Tool> (<model-name>).*
```

## Pull requests

PRs are squash-merged into Release Please changelogs: one change per title,
extra entries at column 0, trailers in the squash body. Load `pull-requests`.

If required status checks block a PR, follow
`docs/branch-protection-runbook.md`; never weaken the required check set to
land a change.

## When instructions and reality disagree

Where this file describes the repository inaccurately, reality wins — but flag
the gap instead of silently diverging. Guardrails are not descriptions: if one
blocks a genuinely better approach, raise it with the operator rather than
working around it.

For user-facing changes, verify the rendered or running product in addition to
automated checks; tests alone do not establish visual or interaction quality.

Screenshot guidance is capability-conditional: do not assume browser or native
capture tooling exists in this repository.

**Treat screenshot generation and visual approval as separate gates.** For
changes affecting tracked screenshots or captured views, follow the
repository's documented screenshot-review process when present. A successful
screenshot-generation workflow means only that artifacts were produced; it is
not visual approval. Never capture live or private data, and do not commit
regenerated assets until the required visual and privacy review has passed.

## Preservation and destructive operations

Preserve existing user work and unrelated repository changes. Do not discard,
reset, overwrite, destructively clean, or otherwise destroy existing work
unless the user's request explicitly requires it and the consequences are
understood. Prefer reversible operations when they satisfy the task equally
well.

## Definition of done

Run the relevant automated checks and targeted tests for changed behaviour,
including failure paths where practical. Update documentation, fixtures, and
migration or rollout notes when they form part of the changed contract. Remove
the worktrees, verification copies, and scratch output the task created, or
report what remains, where, and why. Report the checks run and any validation
that could not be completed; do not claim unrun checks passed.

## Fresh-eyes review

A different agent or reviewer must review substantial work before it is done or
ready for review; resolve valid blocking findings. Load `fresh-eyes-review`.

## Recall is not evidence

Check claims about platform, API, or dependency capabilities, and anything
contradicting the user or this repository, against a current primary source;
cite the source and date in any commit, PR, or committed doc that relies on
such a claim. Load `verify-external-claims`.

## Tooling

Run checks before pushing:

```sh
uv run --with pyyaml python3 validate_templates.py
uv run --with pytest --with pyyaml python3 -m pytest
node --test templates/*.test.mjs
md_dir=$(mktemp -d)
uv run --with pyyaml python3 validate_templates.py --render-markdown "$md_dir"
npx --yes markdownlint-cli2@0.23.3 --config markdownlint-generated.jsonc "$md_dir/**/*.md"
rm -rf "$md_dir"
```

## Skills

| Before you | Load skill |
| --- | --- |
| open, edit, or merge a PR | `pull-requests` |
| create a worktree or temporary files | `worktrees-and-scratch` |
| call substantial work done or ready for review | `fresh-eyes-review` |
| rely on an external platform or dependency claim | `verify-external-claims` |
| fan out to subagents | `delegation` |

If your harness cannot load skills, read `.agents/skills/<name>/SKILL.md`
directly.

## Project specifics

Rules that apply only to this repository live in this section, below every
generated section: product sources of truth, prime directives, points at which
to stop and ask the operator, and boundaries specific to this codebase. Keep
them here rather than editing the generated sections above, so template
updates can be applied without overwriting them. Where a rule here narrows or
conflicts with a generated section, it governs this repository — say so
explicitly, so the difference stays visible. Put stop-and-ask lists and prime
directives first in this section, so they survive any truncation.

Keep this section short. Long reference material (architecture, conventions,
API notes) belongs in a repository-owned skill under `.agents/skills/` with a
name that does not start with a template skill name; narrow a template skill
here, never by editing it.
