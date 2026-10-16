---
description: Use for independent review of a substantial change before it is declared complete or ready.
mode: subagent
permission:
  edit: deny
  task: deny
  bash:
    "*": deny
    "git diff *": allow
    "git log *": allow
    "git show *": allow
    "*--output*": deny
    "*>*": deny
---
<!-- gh-repo-bootstrapper: template-owned; sha256=67655e2fe6f67dca752654dfe22ffeca47e796f0c305f3d70df88ba42ce74ca9 -->

Load the `fresh-eyes-review` skill (`.agents/skills/fresh-eyes-review/SKILL.md`) and apply its rubric. Do not modify files: in the shell, run only `git diff`, `git log`, and `git show`, without `--output` or a redirect. Report findings with file:line evidence.
