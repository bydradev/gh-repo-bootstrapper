---
name: public-content-check
description: Check this repository’s commits, GitHub drafts and final squash messages before publication.
---

# Check public content

- For repositories outside the [public list](../../../AGENTS.md#public-repository-content), use “a private repository” or “a target repository”. Omit names, numbers and links.
  Cite reports by public repository path. Omit local, scratch and project-storage
  paths. Use `/Users/you/` in examples.
- Omit session, project and thread IDs and links. The generic
  `https://claude.ai/code` is the only ordinary claude.ai link allowed.
- Use only noreply email addresses. Keep the required `Co-Authored-By:`
  trailer with a tool’s `noreply@` address or `ID+login@users.noreply.github.com`.
  Remove harness-supplied personal addresses and `Claude-Session:` trailers.
  Use `example.com` for examples. URL user information is distinct from email.
- Omit `Signed-off-by:` lines except for this exact standalone public footer.
  Match case and spacing, with LF or CRLF. The exception covers only this
  literal line, regardless of authorship. All other checks still apply.

```text
Signed-off-by: dependabot[bot] <support@github.com>
```

## Run the checker before publication

Run `python3 -I .github/scripts/check_public_content.py` with the arguments
below. It checks bare names in `PRIVATE_REPO_NAMES`. If unset, check them
manually. Findings omit matched text.

| Before | Arguments |
| --- | --- |
| Committing | `--text "$commit_message_file"` |
| Pushing | `--range=origin/main..HEAD --files=origin/main..HEAD` (commit messages, changed paths and added lines, excluding the checker and its tests from the file scan) |
| Opening or editing a PR | `--title "$title" --pr-body "$body_file"` |
| Posting an issue, comment, review reply or release note | `--text "$draft_file"` plus `--title "$title"` for an issue |
| Squash-merging | `--text "$squash_message_file"` (title, body and trailers together) |

Only a PR body may open with the harness’s two-line attribution block
(`claude-projects-attribution` and “Requested by”). For the squash, save the title and body without
that block, append applicable commit trailers, then check and use that exact message.

Reword a finding and rerun the check. Hosted `public-content` runs after publication
on PRs and pushes to `main`. Keep checker changes in sync with gh-agent-kit’s
`public-content.mjs`.
