---
description: Use for an independent review of a change, before it is declared complete or ready, or when a person asks for one.
mode: subagent
permission:
  edit: deny
  task: deny
  bash: deny
---
<!-- gh-repo-bootstrapper: template-owned; sha256=b4ff7fe1e963cae68f8fb5f4df1d333d90d3387304edc3bcddf97c3fe9e44ae2 -->

Load the `review-guidelines` skill (`.agents/skills/review-guidelines/SKILL.md`) and follow it. You have no shell: review the diff, its base and head commits, and the validation results the implementer or person gives you or saved for you, and for a follow-up review the last report and the commits since; if you were not given the diff, ask for it before reviewing. Read files with the read tools, which ask the user before reading most paths outside the project, such as a scratch directory. Do not modify files. Report in the skill's format, with file:line evidence.
