---
name: fresh-eyes-review
description: >-
  Use before declaring substantial work complete or a branch or pull request ready for review, when acting as an independent reviewer, or after review fixes cause material changes. Covers who reviews, what to hand the reviewer, the review rubric, when to review and re-review, and a cross-family recipe using a read-only reviewer from another model family.
---

# Independent fresh-eyes review

Before substantial changes are considered complete or ready for review, perform
an independent fresh-eyes review of the resulting change.

The review must be performed by a different agent or reviewer from the one that
implemented the work. When model choice is available, prefer a stronger
reasoning model and, where practical, a different model family from the
implementation agent.

Provide the reviewer with the user's requested outcome, relevant repository
requirements and specifications, the resulting diff or changed files, and
available validation results. The reviewer should independently assess the
change rather than rely on the implementing agent's conclusions.

The review should actively look for correctness issues, regressions, incomplete
requirements, missing or inadequate tests, security or privacy concerns,
unnecessary complexity, inconsistent documentation, and other problems the
implementing agent may have overlooked.

Perform fresh-eyes review at meaningful quality gates: after a substantial
implementation phase before it is considered complete, and before a completed
branch or pull request is declared ready for review. Do not require a new review
for every small edit or intermediate push.

Treat review findings as unverified until assessed against the repository and
the requested outcome. Resolve valid blocking findings before declaring the
work complete.

If resolving review findings results in material changes, perform another
independent fresh-eyes review of those changes before completion.

## Cross-family review recipe

This recipe works in any harness. Save the diff, the requested outcome, and the
relevant requirements to the session's scratch directory (see the
`worktrees-and-scratch` skill), write the reviewer prompt to a file there, then
run the reviewer read-only from inside a git worktree:

```sh
git diff <base>...HEAD > <scratch>/review.diff
codex exec --sandbox read-only --ephemeral -o <out> - < <prompt>
```

When the implementer is Codex, use another installed harness in read-only mode
instead, such as `claude -p`, the Antigravity CLI, or OMO. Read `<out>`, assess
each finding against the repository and the requested outcome, and delete the
scratch files when the review is done.
