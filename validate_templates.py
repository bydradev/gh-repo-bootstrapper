#!/usr/bin/env python3
"""
validate_templates.py — Render every supported bootstrap.py configuration and
validate the generated files.

Checks performed on each generated file:
  - YAML syntax     (every .yml/.yaml file parses with yaml.safe_load)
  - JSON syntax      (every .json file parses with json.loads)
  - marker replacement (no leftover "__MARKER__" or "# <<MARKER>>" placeholders)
  - workflow/job consistency, checked both directions: every context in
    bootstrap.py.required_status_checks() must name a job that actually
    exists in the generated ci.yml / test.yml / pr-title-check.yml, AND
    every reusable-workflow context the generated ci.yml / test.yml would
    actually produce must be listed in required_status_checks() (so an
    added test.yml job can't silently go unenforced)
  - npm-script assumption consistency: every `npm run <script>` and `npm test`
    command in a template is declared by bootstrap.ASSUMED_NPM_SCRIPTS, and
    every declared assumption is documented by at least one template
  - README rendering: every repository type receives its starter, and Swift
    commands retain the safe formatter path and configured test destination
  - shared AGENTS.md guidance: every generated repository type carries the
    required SDLC, safety-gate, dependency, external-knowledge, and completion
    guidance,
    each phrase in the hub or in the template-owned skill that now owns it
  - AGENTS.md hub structure: the generated part fits its byte budget, has no
    bare `@path` imports, and points only at skills the render contains;
    every SKILL.md has valid agentskills.io frontmatter with a unique name;
    relative Markdown links in the hub and in every SKILL.md resolve from
    their own directory;
    every template-owned file carries a valid stamp; the reviewer agents are
    read-only and leave the model unset

  - branch-protection payload semantics: bootstrap.branch_protection_payload()
    must pin the operator-ruled configuration (strict False, enforce_admins
    True, a required PR with zero required approvals, no push restrictions)
    and contexts identical to required_status_checks(), for every repo type
  - release-gated full-suite contract: rendered Python, Swift, and Rust
    release-please.yml callers must select the full suite for manual dispatch
    and for the Release Please release commit
  - runbook presence: every generated repo carries
    docs/branch-protection-runbook.md with the load-bearing operational facts

Also runs a handful of self-contained self-tests (see run_self_tests())
against synthetic workflow fixtures to prove the missing/unexpected-context
branches of the consistency check actually fire, rather than only exercising
already-consistent generated configurations.

Requires PyYAML (`pip install pyyaml`) — a dev-only dependency for this
script; bootstrap.py itself remains stdlib-only.

Exit status is non-zero if any configuration or self-test fails any check.
"""

import itertools
import json
import posixpath
import re
import shlex
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Optional, Union

try:
    import yaml
except ImportError:
    sys.exit("error: PyYAML is required to run this script — pip install pyyaml")

import bootstrap

MARKER_RE = re.compile(r"__[A-Z_]+__|# <<[A-Z_]+>>")
NPM_SCRIPT_RE = re.compile(r"\bnpm\s+run\s+([A-Za-z0-9:_-]+)|\bnpm\s+test\b")
# The optional local E2E helper may be documented without making it a
# generated-scaffold contract. Keep the script name and phrase deliberately
# exact so other npm commands remain validated against
# bootstrap.ASSUMED_NPM_SCRIPTS.
OPTIONAL_NPM_SCRIPT_RE = re.compile(
    r"\bnpm\s+run\s+(test:e2e:local)`\s+when that\s+script is available\b"
)
COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
RELEASE_FULL_SUITE_EXPRESSION = (
    "${{ github.event_name == 'workflow_dispatch' || "
    "startsWith(github.event.head_commit.message, 'chore(main): release') }}"
)

OWN_WORKFLOWS_DIR = Path(__file__).parent / ".github" / "workflows"

BASELINE_DOCUMENT_REQUIREMENTS = {
    "docs/lint-baseline.md": (
        "self-cleaning",
        "docs/advisory-baseline.md",
        "Why this is accepted",
        "Review date",
        "review cadence is six months from acceptance",
    ),
    "docs/advisory-baseline.md": (
        "not self-cleaning",
        # The enforced command, not a severity threshold. audit-production.mjs
        # runs `npm audit --omit=dev --json` and demands a row for every
        # reported advisory at any severity; pinning the old
        # "--audit-level=high" phrase here made the validator enforce the
        # documentation of a gate the code does not implement.
        "npm audit --omit=dev",
        "zero undocumented findings at any severity",
        "npm run audit:production",
        "Re-check trigger",
    ),
}

NEXTJS_BASELINE_REQUIRED_FILES = {
    *bootstrap.NEXTJS_BASELINE_DOCUMENTS,
    bootstrap.NEXTJS_ENFORCED_AUDIT_SCRIPT,
    *bootstrap.NEXTJS_BASELINE_SCRIPTS,
    bootstrap.NEXTJS_BASELINE_REVIEW_WORKFLOW,
    bootstrap.README,
    "AGENTS.md",
}

README_REQUIREMENTS = {
    "nextjs": (
        "## Start here",
        "## Local development",
        "## Verification",
    ),
    "python": (
        "## Local development",
        "### Preferred: uv",
        "uv venv",
        "### Standard-library alternative",
        "python3 -m venv .venv",
    ),
    "swift": ("## Local development", "## Verification"),
    "rust": (
        "## Start here",
        "## Local development",
        "## Verification",
        "cargo clippy --workspace --all-targets -- -D warnings",
    ),
    "simple": ("## Start here", "## Project guide"),
}

def _skill_path(name: str) -> str:
    return f".agents/skills/{name}/SKILL.md"


HUB = "AGENTS.md"
# The screenshot process lives in the screenshot-review skill for the types
# that generate one (nextjs, swift) and inline in the hub for every other type.
# The privacy and pre-commit visual-review gates are pinned to the hub for
# every type: a gate must not depend on loading a skill.
SCREENSHOT_OWNER = "<screenshot-review skill, or the hub when the type has none>"
SCREENSHOT_GATES = (
    "Treat screenshot generation and visual approval as separate gates.",
    "A successful screenshot-generation workflow means only that artifacts were produced; it is not visual approval.",
    "Never capture live or private data, and do not commit regenerated assets "
    "until the required visual and privacy review has passed.",
)
# Hub sentence (nextjs, swift) that sends agents to the skill for the process.
HUB_SCREENSHOT_POINTER = "Load `screenshot-review` for the full process."
# Skill sentence that routes agents to a repository-owned screenshot skill first.
SCREENSHOT_ROUTING = (
    "names a repository-owned skill, or a section of one, for screenshot or "
    "visual-review work, load it first."
)

# (phrase, owning file) pairs. The hub keeps the gates; the detail moved into
# template-owned skills, so each phrase is required in the file that owns it.
AGENTS_COMMON_REQUIREMENTS = (
    ("## Development workflow", HUB),
    ("more-local `AGENTS.md`", HUB),
    ("A terminal condition does not broaden authorization", HUB),
    ("not standing authorization to mutate state.", HUB),
    ("## GitHub operations", HUB),
    (
        "Merge only when the user's current request or an approved repository plan "
        "expressly authorizes autonomous merge; successful checks alone do not authorize it.",
        HUB,
    ),
    (
        "do not dispatch a release, deployment, provider, or other externally mutating "
        "workflow without explicit authority.",
        HUB,
    ),
    (
        "Never bypass required checks, branch protection, or repository policy, and never "
        "force-push or use administrative bypass without explicit authorization.",
        HUB,
    ),
    ("## Branches", HUB),
    ("Never commit directly to `main`.", HUB),
    ("never weaken the required check set", HUB),
    ("## Preservation and destructive operations", HUB),
    ("Preserve existing user work and unrelated repository changes.", HUB),
    (
        "Do not discard, reset, overwrite, destructively clean, or otherwise destroy existing "
        "work unless the user's request explicitly requires it",
        HUB,
    ),
    ("## Dependencies and external interfaces", HUB),
    ("Prefer the existing stack.", HUB),
    (
        "Before adding a dependency or external integration, consider its purpose, "
        "maintenance and security posture, licence, and runtime impact.",
        HUB,
    ),
    ("Update dependency manifests and lockfiles through the package manager;", HUB),
    ("do not hand-edit a lockfile.", HUB),
    ("## External knowledge and capabilities", _skill_path("verify-external-claims")),
    ("Use connected documentation or research capabilities", _skill_path("verify-external-claims")),
    ("Use an installed skill only when it matches the task", _skill_path("verify-external-claims")),
    ("Do not send secrets, private source, or customer data to external services.", HUB),
    (
        "A successful screenshot-generation workflow means only that artifacts were produced; it is not visual approval.",
        SCREENSHOT_OWNER,
    ),
    *((phrase, HUB) for phrase in SCREENSHOT_GATES),
    ("Screenshot guidance is capability-conditional", SCREENSHOT_OWNER),
    ("do not assume browser or native", SCREENSHOT_OWNER),
    ("## Definition of done", HUB),
    ("do not claim unrun checks passed.", HUB),
    ("# Worktrees, verification copies, and scratch output", _skill_path("worktrees-and-scratch")),
    ("git worktree add --detach", _skill_path("worktrees-and-scratch")),
    ("Never copy a checkout with `cp -R`", _skill_path("worktrees-and-scratch")),
    ("Keep worktrees outside the checkout", _skill_path("worktrees-and-scratch")),
    ("Reuse one worktree per purpose", _skill_path("worktrees-and-scratch")),
    ("never at fixed paths in `/tmp`", _skill_path("worktrees-and-scratch")),
    ("Remove only what this task created", _skill_path("worktrees-and-scratch")),
    ("Remove the worktrees, verification copies, and scratch output the task created", HUB),
    ("## Project specifics", HUB),
)

# Per-type mechanisms behind the shared worktree and scratch-output rules: where
# a worktree's dependencies and build output live, so they are not multiplied.
# Each lives in the type's local-validation skill.
AGENTS_TYPE_REQUIREMENTS = {
    "nextjs": tuple(
        (phrase, _skill_path("local-validation-nextjs"))
        for phrase in (
            "Never copy `node_modules`, `.next`, `test-results`, or `playwright-report`",
            "--trace=retain-on-failure",
            "stop a manually started `next dev`",
            "reported as `flaky`, not failed",
        )
    ),
    "python": (("Never copy `.venv/`", _skill_path("local-validation-python")),),
    "rust": tuple(
        (phrase, _skill_path("local-validation-rust"))
        for phrase in (
            "set `CARGO_TARGET_DIR` to one fixed directory",
            "Never copy `target/`",
            "the task that removes the last one deletes it too",
        )
    ),
    "swift": tuple(
        (phrase, _skill_path("local-validation-swift"))
        for phrase in (
            "pass one fixed `-derivedDataPath` for that worktree",
            "Never choose a new derived-data path per run or per commit.",
            "does not change the app's `MARKETING_VERSION`",
        )
    ),
    "simple": (),
}

# The hub's generated part (everything above `## Project specifics`, with the
# `next dev` block masked) must stay within HUB_BUDGET_BYTES so every harness
# reads it whole. HUB_CEILING_BYTES is the hard ceiling the budget exists to
# keep well clear of; the self-test proves a hub just over it is rejected.
HUB_BUDGET_BYTES = 8_000
HUB_CEILING_BYTES = 10_000
# A bare `@path` token is an import directive in some harnesses (Claude Code
# expands `@AGENTS.md`); the hub must not pull other files in that way.
AT_IMPORT_RE = re.compile(r"(^|\s)@[\w./-]+")
INLINE_CODE_RE = re.compile(r"(`+)(?!`).+?(?<!`)\1(?!`)", re.DOTALL)
SKILLS_HEADING = "## Skills"
SKILL_ROW_RE = re.compile(r"^\|.*\|\s*`([^`]+)`\s*\|\s*$")
SKILL_PATH_RE = re.compile(r"^\.agents/skills/([^/]+)/SKILL\.md$")
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SKILL_NAME_MAX = 64
SKILL_DESCRIPTION_MAX = 1024
CLAUDE_REVIEWER = ".claude/agents/fresh-eyes-reviewer.md"
OPENCODE_REVIEWER = ".opencode/agents/fresh-eyes-reviewer.md"
CLAUDE_WRITE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
SCREENSHOT_SKILL = _skill_path("screenshot-review")
SCREENSHOT_POINTER = "`docs/screenshot-review.md` (repository root)"
BASELINE_SKILL = _skill_path("baseline-process")
PROJECT_SPECIFICS_HEADING = "## Project specifics"
NEXTJS_AGENT_RULES_END = "<!-- END:nextjs-agent-rules -->"
APP_ROUTER_HEADING = "# This project uses the App Router"
WORKTREE_GITIGNORE_ENTRIES = (".worktrees/", ".claude/worktrees/", "*.xcresult/")

SCREENSHOT_HEADINGS = (
    "# Screenshot review guidance",
    "## Safety boundary",
    "## Review workflow",
)
SCREENSHOT_PLATFORM_HEADINGS = {
    "nextjs": "## Next.js/browser-capable projects",
    "swift": "## Swift/native projects",
}
SCREENSHOT_PLATFORM_FORBIDDEN = {
    "nextjs": ("xcodebuild", "swift-format", "simulator"),
    "swift": ("playwright", "chromium", "npm run", "browser capture"),
}
SCREENSHOT_FORBIDDEN_INVENTED_TOOLING = (
    "npm run screenshot",
    "npm run screenshots",
    "npx playwright",
    "xcodebuild screenshot",
    ".github/workflows/screenshots",
)
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+.+$", re.MULTILINE)

BRANCH_PROTECTION_RUNBOOK = "docs/branch-protection-runbook.md"

# The bootstrapper ships the runbook into every generated repository from
# templates/docs-branch-protection-runbook.md, and (after item 20) carries its
# own docs/branch-protection-runbook.md for readers here. The two must not drift;
# check_runbook_copy_matches_template enforces that.
#
# REPO_RUNBOOK uses the same literal path as BRANCH_PROTECTION_RUNBOOK: the
# bootstrapper's own copy and the file generated into each repository are the
# same runbook. The constants are separate because they name different roles
# (this repo's copy vs. the per-generated-repo copy), not different files.
REPO_RUNBOOK = "docs/branch-protection-runbook.md"
TEMPLATE_RUNBOOK = "templates/docs-branch-protection-runbook.md"
REPO_RUNBOOK_PATH = Path(__file__).parent / REPO_RUNBOOK
TEMPLATE_RUNBOOK_PATH = Path(__file__).parent / TEMPLATE_RUNBOOK

RUNBOOK_REQUIRED_PHRASES = (
    "update-branch",
    "skipped",
    "never reports",
    "latest result per check name",
    "disable protection",
)


def configurations():
    """Yield (label, cfg) for every supported bootstrap.py configuration."""
    for postgres in (False, True):
        yield (
            f"nextjs postgres={postgres}",
            {
                "name": "sample-app",
                "repo_type": "nextjs",
                "postgres": postgres,
                "scheme": "",
                "destination": "",
            },
        )

    yield (
        "python",
        {
            "name": "sample-lib",
            "repo_type": "python",
            "postgres": False,
            "scheme": "",
            "destination": "",
        },
    )

    for destination, xcodegen in itertools.product(
        ("iphone", "ipad", "macos"), [False, True]
    ):
        yield (
            f"swift destination={destination} xcodegen={xcodegen}",
            {
                "name": "sample-app",
                "repo_type": "swift",
                "postgres": False,
                "scheme": "SampleApp",
                "destination": destination,
                "xcodegen": xcodegen,
            },
        )

    yield (
        "rust",
        {
            "name": "sample-service",
            "repo_type": "rust",
            "postgres": False,
            "scheme": "",
            "destination": "",
        },
    )

    yield (
        "simple",
        {
            "name": "sample-repo",
            "repo_type": "simple",
            "postgres": False,
            "scheme": "",
            "destination": "",
        },
    )


def check_syntax(label: str, files: dict) -> list:
    errors = []
    for path, content in files.items():
        if path.endswith((".yml", ".yaml")):
            try:
                yaml.safe_load(content)
            except yaml.YAMLError as exc:
                errors.append(f"[{label}] {path}: invalid YAML — {exc}")
        elif path.endswith(".json") or path.endswith(".swift-format"):
            try:
                json.loads(content)
            except json.JSONDecodeError as exc:
                errors.append(f"[{label}] {path}: invalid JSON — {exc}")
    return errors


def check_nextjs_provider_free(label: str, repo_type: str, files: dict) -> list:
    """Keep provider provisioning out of generated Next.js content.

    `.gitignore` intentionally retains local Vercel and Wrangler cache entries
    for applications that later add their own deployment workflow.
    """
    if repo_type != "nextjs":
        return []

    rendered = "\n".join(
        content for path, content in files.items() if path != ".gitignore"
    ).lower()
    errors = []
    for term in ("vercel", "cloudflare", "wrangler", "deployments: write"):
        if term in rendered:
            errors.append(
                f"[{label}] generated Next.js output still contains retired provider surface {term!r}"
            )
    if "wrangler.jsonc" in files:
        errors.append(f"[{label}] generated Next.js output includes retired wrangler.jsonc")
    gitignore = files.get(".gitignore", "")
    for cache_path in (".vercel/", ".wrangler/"):
        if cache_path not in gitignore:
            errors.append(f"[{label}] .gitignore is missing local tool cache {cache_path!r}")
    return errors


def check_markers(label: str, files: dict) -> list:
    errors = []
    for path, content in files.items():
        leftover = MARKER_RE.findall(content)
        if leftover:
            errors.append(f"[{label}] {path}: unreplaced marker(s) {sorted(set(leftover))}")
    return errors


def check_markdown_blank_lines(label: str, files: dict) -> list:
    """Reject runs of blank lines in generated Markdown.

    An optional fragment composed in as an empty string can leave two blank
    lines behind its marker. markdownlint (MD012) catches that in CI too; this
    keeps the check in the Python validator, which runs without Node.
    """
    errors = []
    for path, content in files.items():
        if path.endswith(".md") and "\n\n\n" in content:
            line = content[: content.index("\n\n\n")].count("\n") + 2
            errors.append(f"[{label}] {path}:{line}: multiple consecutive blank lines")
    return errors


def render_markdown(out_dir: Path) -> int:
    """Write every configuration's generated Markdown under out_dir/<label>/.

    validate.yml lints the result with markdownlint-cli2, using
    markdownlint-generated.jsonc.
    """
    for label, cfg in configurations():
        slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
        for path, content in bootstrap.generate_files(cfg).items():
            if path.endswith(".md"):
                target = out_dir / slug / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
    # Skills (.agents/skills/*/SKILL.md) and reviewer agents (.claude/agents,
    # .opencode/agents) are Markdown too, so they are written and linted here.
    print(f"Rendered generated Markdown to {out_dir}")
    return 0


def _owner_path(owner: str, files: dict) -> str:
    if owner == SCREENSHOT_OWNER:
        return SCREENSHOT_SKILL if SCREENSHOT_SKILL in files else HUB
    return owner


def _missing_phrases(label: str, files: dict, pairs, kind: str) -> list:
    """Each (phrase, owner) pair must appear, outside code fences and with
    whitespace normalized, in the file that owns it."""
    errors, normalized = [], {}
    for phrase, owner in pairs:
        path = _owner_path(owner, files)
        if path not in files:
            errors.append(f"[{label}] missing {path}, which owns {kind} {phrase!r}")
            continue
        if path not in normalized:
            normalized[path] = " ".join(_unfenced(files[path]).split())
        if phrase not in normalized[path]:
            errors.append(f"[{label}] {path} is missing {kind} {phrase!r}")
    return errors


def check_agents_guidance(label: str, files: dict) -> list:
    """Require the shared SDLC guidance for every generated repository type."""
    if HUB not in files:
        return [f"[{label}] missing AGENTS.md"]
    return _missing_phrases(label, files, AGENTS_COMMON_REQUIREMENTS, "common guidance")


def _hub_generated_part(agents: str) -> str:
    """The hub above `## Project specifics`, with the `next dev` block masked.

    Uses bootstrap's fence-aware splitter, so a `## Project specifics` line
    inside a fenced example does not end the generated part early.
    """
    return bootstrap._split_project_specifics(bootstrap._mask_nextjs_rules(agents))[0]


def check_hub_budget(label: str, files: dict) -> list:
    """Hub budget: the generated part of AGENTS.md fits HUB_BUDGET_BYTES."""
    size = len(_hub_generated_part(files.get(HUB, "")).encode())
    if size <= HUB_BUDGET_BYTES:
        return []
    ceiling = ", above the hard ceiling" if size > HUB_CEILING_BYTES else ""
    return [
        f"[{label}] AGENTS.md hub budget: generated part is {size} B > {HUB_BUDGET_BYTES} B"
        f" (ceiling {HUB_CEILING_BYTES} B{ceiling}); move detail into a skill"
    ]


def check_no_at_imports(label: str, files: dict) -> list:
    """No bare `@path` token outside code spans and fences in AGENTS.md."""
    prose = INLINE_CODE_RE.sub("", _unfenced(files.get(HUB, "")))
    return [
        f"[{label}] AGENTS.md has a bare @-import token {match.group(0).strip()!r}; "
        "wrap it in backticks or name the file without '@'"
        for match in AT_IMPORT_RE.finditer(prose)
    ]


def _hub_skill_names(agents: str) -> list:
    section = _unfenced(agents).split("\n" + SKILLS_HEADING + "\n", 1)
    if len(section) < 2:
        return []
    body = re.split(r"^## ", section[1], maxsplit=1, flags=re.MULTILINE)[0]
    return [m.group(1) for m in map(SKILL_ROW_RE.match, body.splitlines()) if m]


def check_skill_pointers(label: str, files: dict) -> list:
    """Every skill named in the hub's `## Skills` table exists in the render."""
    names = _hub_skill_names(files.get(HUB, ""))
    if not names:
        return [f"[{label}] AGENTS.md has no skills in its {SKILLS_HEADING!r} table"]
    return [
        f"[{label}] AGENTS.md points at skill {name!r}, but {_skill_path(name)} is not generated"
        for name in names
        if _skill_path(name) not in files
    ]


def _frontmatter(text: str):
    """(mapping, None) for a `---`-delimited YAML frontmatter block, or
    (None, reason) when it is absent, unterminated, or not a mapping."""
    lines = text.split("\n")
    if not lines or lines[0] != "---":
        return None, "does not start with a '---' frontmatter line"
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None, "has no closing '---' frontmatter line"
    try:
        data = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as exc:
        return None, f"has invalid YAML frontmatter — {exc}"
    if not isinstance(data, dict):
        return None, "frontmatter is not a mapping"
    return data, None


def check_skill_frontmatter(label: str, files: dict) -> list:
    """agentskills.io frontmatter for every SKILL.md, with unique names."""
    errors, names = [], Counter()
    for path in sorted(files):
        match = SKILL_PATH_RE.match(path)
        if not match:
            continue
        data, problem = _frontmatter(files[path])
        if problem:
            errors.append(f"[{label}] {path} {problem}")
            continue
        name, description = data.get("name"), data.get("description")
        names[name if isinstance(name, str) else repr(name)] += 1
        if name != match.group(1):
            errors.append(f"[{label}] {path}: name {name!r} must equal its directory {match.group(1)!r}")
        if not isinstance(name, str) or not SKILL_NAME_RE.match(name) or len(name) > SKILL_NAME_MAX:
            errors.append(
                f"[{label}] {path}: name {name!r} must be lowercase-hyphen and "
                f"at most {SKILL_NAME_MAX} characters"
            )
        if not isinstance(description, str) or not description.strip():
            errors.append(f"[{label}] {path}: description must be a non-empty string")
        elif len(description) > SKILL_DESCRIPTION_MAX:
            errors.append(
                f"[{label}] {path}: description is {len(description)} characters "
                f"> {SKILL_DESCRIPTION_MAX}"
            )
    errors += [
        f"[{label}] duplicate skill name {name!r} in {count} SKILL.md files"
        for name, count in sorted(names.items(), key=str)
        if count > 1
    ]
    return errors


def check_template_stamps(label: str, cfg: dict, files: dict) -> list:
    """Every template-owned file is rendered with a stamp matching its body."""
    errors = []
    for path in sorted(bootstrap.template_owned_paths(cfg)):
        if path not in files:
            errors.append(f"[{label}] template-owned {path} is not generated")
        elif not bootstrap.stamp_is_valid(files[path]):
            errors.append(f"[{label}] template-owned {path} has no valid {bootstrap.STAMP_PREFIX!r} stamp")
    return errors


def _tool_names(tools) -> set:
    if isinstance(tools, str):
        return {tool.strip() for tool in tools.split(",") if tool.strip()}
    if isinstance(tools, list):
        return {str(tool).strip() for tool in tools}
    return set()


def check_reviewer_agents(label: str, files: dict) -> list:
    """Both fresh-eyes reviewer agents are read-only and leave the model unset."""
    errors = []
    for path in (CLAUDE_REVIEWER, OPENCODE_REVIEWER):
        if path not in files:
            errors.append(f"[{label}] missing {path}")
            continue
        data, problem = _frontmatter(files[path])
        if problem:
            errors.append(f"[{label}] {path} {problem}")
            continue
        if "model" in data:
            errors.append(f"[{label}] {path} must not set 'model'; the harness picks it")
        if path == CLAUDE_REVIEWER:
            if "tools" not in data:
                errors.append(f"[{label}] {path} must list 'tools' (omitting it grants every tool)")
            writers = sorted(_tool_names(data.get("tools")) & set(CLAUDE_WRITE_TOOLS))
            if writers:
                errors.append(f"[{label}] {path} must be read-only but grants {writers}")
        else:
            if data.get("mode") != "subagent":
                errors.append(f"[{label}] {path} must set 'mode: subagent'")
            permission = data.get("permission")
            if not isinstance(permission, dict) or permission.get("edit") != "deny":
                errors.append(f"[{label}] {path} must set 'permission.edit: deny'")
    return errors


_FENCE_LINE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")


def _unfenced(text: str) -> str:
    """The text with fenced code blocks removed, so an example cannot stand in
    for operative guidance. A fence closes only on the same character repeated
    at least as many times as it opened with."""
    kept, fence = [], None
    for line in text.splitlines():
        match = _FENCE_LINE_RE.match(line)
        if fence is None:
            if match and not (match.group(1)[0] == "`" and "`" in match.group(2)):
                fence = (match.group(1)[0], len(match.group(1)))
            else:
                kept.append(line)
        elif (
            match
            and match.group(1)[0] == fence[0]
            and len(match.group(1)) >= fence[1]
            and not match.group(2).strip()
        ):
            fence = None
    return "\n".join(kept)


def check_workspace_guidance(label: str, repo_type: str, files: dict) -> list:
    """Require the per-type worktree mechanisms and the repo-owned section layout.

    `## Project specifics` must be the last second-level section so everything
    a repository adds sits below the generated sections, and the Next.js App
    Router note must sit after the `next dev`-managed markers, which rewrite
    everything between them.
    """
    agents = files.get("AGENTS.md", "")
    prose = _unfenced(agents)
    errors = _missing_phrases(
        label, files, AGENTS_TYPE_REQUIREMENTS[repo_type], f"{repo_type} worktree guidance"
    )
    headings = [line for line in prose.splitlines() if line.startswith("## ")]
    if not headings or headings[-1] != PROJECT_SPECIFICS_HEADING:
        errors.append(
            f"[{label}] AGENTS.md must end with {PROJECT_SPECIFICS_HEADING!r} as its last "
            f"second-level section (found {headings[-1] if headings else None!r})"
        )
    if repo_type == "nextjs":
        end = agents.find(NEXTJS_AGENT_RULES_END)
        note = agents.find(APP_ROUTER_HEADING)
        if note == -1:
            errors.append(f"[{label}] Next.js AGENTS.md is missing {APP_ROUTER_HEADING!r}")
        elif end == -1 or note < end:
            errors.append(
                f"[{label}] {APP_ROUTER_HEADING!r} must follow {NEXTJS_AGENT_RULES_END!r}; "
                "`next dev` rewrites everything between the markers"
            )
    gitignore = files.get(".gitignore", "")
    for entry in WORKTREE_GITIGNORE_ENTRIES:
        if entry not in gitignore.splitlines():
            errors.append(f"[{label}] .gitignore is missing {entry!r}")
    if repo_type == "rust" and "/target/" not in gitignore.splitlines():
        errors.append(f"[{label}] Rust .gitignore is missing Cargo build output '/target/'")
    return errors


def _markdown_heading_errors(label: str, path: str, content: str) -> list:
    errors = []
    previous_level = 0
    for match in MARKDOWN_HEADING_RE.finditer(content):
        level = len(match.group(1))
        if previous_level and level > previous_level + 1:
            errors.append(
                f"[{label}] {path} skips Markdown heading level "
                f"{previous_level} -> {level}"
            )
        previous_level = level
    return errors


def _local_markdown_link_errors(label: str, path: str, content: str, files: dict) -> list:
    errors = []
    for raw_target in MARKDOWN_LINK_RE.findall(content):
        target = raw_target.split(None, 1)[0].split("#", 1)[0]
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
        if resolved not in files:
            errors.append(
                f"[{label}] {path} contains a broken local Markdown link "
                f"{raw_target!r} (resolved as {resolved!r})"
            )
    return errors


def check_markdown_links(label: str, files: dict) -> list:
    """Relative links in the hub and every SKILL.md resolve from their own directory."""
    errors = []
    for path in sorted(files):
        if path == HUB or SKILL_PATH_RE.match(path):
            errors += _local_markdown_link_errors(label, path, files[path], files)
    return errors


def _invented_tooling(text: str) -> list:
    """Forbidden capture-tooling phrases in text, matched case- and whitespace-insensitively."""
    normalized = " ".join(text.lower().split())
    return [phrase for phrase in SCREENSHOT_FORBIDDEN_INVENTED_TOOLING if phrase.lower() in normalized]


def check_screenshot_guidance(label: str, repo_type: str, files: dict) -> list:
    """Validate the composed screenshot contract and its type boundaries."""
    errors = []
    document = files.get(bootstrap.SCREENSHOT_REVIEW)
    agents = files.get("AGENTS.md", "")

    if repo_type not in SCREENSHOT_PLATFORM_HEADINGS:
        if document is not None:
            errors.append(
                f"[{label}] {bootstrap.SCREENSHOT_REVIEW} must not be generated for {repo_type}"
            )
        if "docs/screenshot-review.md" in agents:
            errors.append(f"[{label}] {repo_type} AGENTS.md must not link screenshot guidance")
        if SCREENSHOT_SKILL in files:
            errors.append(f"[{label}] {SCREENSHOT_SKILL} must not be generated for {repo_type}")
        if "`screenshot-review`" in agents:
            errors.append(f"[{label}] {repo_type} AGENTS.md must not point at the screenshot-review skill")
        return errors

    if HUB_SCREENSHOT_POINTER not in " ".join(agents.split()):
        errors.append(f"[{label}] AGENTS.md is missing its pointer {HUB_SCREENSHOT_POINTER!r}")

    if document is None:
        return [f"[{label}] missing {bootstrap.SCREENSHOT_REVIEW} for {repo_type}"]

    # The screenshot-review skill, not the hub, points at the platform
    # document by its repository-root path (check_markdown_links covers links).
    skill = files.get(SCREENSHOT_SKILL)
    if skill is None:
        errors.append(f"[{label}] missing {SCREENSHOT_SKILL} for {repo_type}")
    elif SCREENSHOT_POINTER not in skill:
        errors.append(
            f"[{label}] {SCREENSHOT_SKILL} is missing its pointer {SCREENSHOT_POINTER!r}"
        )
    if skill is not None:
        if SCREENSHOT_ROUTING not in " ".join(skill.split()):
            errors.append(f"[{label}] {SCREENSHOT_SKILL} is missing its routing {SCREENSHOT_ROUTING!r}")
        for phrase in _invented_tooling(skill):
            errors.append(f"[{label}] {SCREENSHOT_SKILL} invents tooling or workflow {phrase!r}")

    for heading in SCREENSHOT_HEADINGS + (SCREENSHOT_PLATFORM_HEADINGS[repo_type],):
        if heading not in document:
            errors.append(f"[{label}] {bootstrap.SCREENSHOT_REVIEW} is missing heading {heading!r}")
    errors += _markdown_heading_errors(label, bootstrap.SCREENSHOT_REVIEW, document)
    errors += _local_markdown_link_errors(label, bootstrap.SCREENSHOT_REVIEW, document, files)

    if SCREENSHOT_PLATFORM_HEADINGS[repo_type] not in document:
        return errors

    lowered = document.lower()
    for phrase in _invented_tooling(document):
        errors.append(
            f"[{label}] {bootstrap.SCREENSHOT_REVIEW} invents tooling or workflow {phrase!r}"
        )

    platform_heading = SCREENSHOT_PLATFORM_HEADINGS[repo_type]
    platform_section = document.split(platform_heading, 1)[1].lower()
    for phrase in SCREENSHOT_PLATFORM_FORBIDDEN[repo_type]:
        if phrase.lower() in platform_section:
            errors.append(
                f"[{label}] {bootstrap.SCREENSHOT_REVIEW} leaks {phrase!r} into {repo_type} guidance"
            )

    for phrase in (
        "does not create any of them",
        "does not add capture dependencies",
        "local or fictional fixture data",
        "visual and privacy review",
    ):
        if phrase.lower() not in lowered:
            errors.append(
                f"[{label}] {bootstrap.SCREENSHOT_REVIEW} is missing truthful safety guidance {phrase!r}"
            )
    return errors


def _template_npm_scripts(templates: dict) -> dict:
    """Map required documented npm scripts to the template paths that reference them."""
    scripts = {}
    for path, content in templates.items():
        optional_script_spans = {
            match.span(1) for match in OPTIONAL_NPM_SCRIPT_RE.finditer(content)
        }
        for match in NPM_SCRIPT_RE.finditer(content):
            script = match.group(1) or "test"
            if match.group(1) and match.span(1) in optional_script_spans:
                continue
            scripts.setdefault(script, set()).add(path)
    return scripts


def check_npm_script_assumptions(templates: dict = None, assumptions: set = None) -> list:
    """Check the bootstrapper-owned documentation contract, not generated repos.

    bootstrap.py intentionally does not create package.json, so this cannot
    prove a future scaffold actually provides a script. It only makes the
    commands in templates explicit and self-consistent with that assumption.
    """
    if templates is None:
        templates = {
            path.relative_to(bootstrap.TEMPLATES_DIR).as_posix(): path.read_text()
            for path in bootstrap.TEMPLATES_DIR.rglob("*")
            if path.is_file()
        }
    if assumptions is None:
        assumptions = bootstrap.ASSUMED_NPM_SCRIPTS

    documented = _template_npm_scripts(templates)
    errors = []
    undeclared = set(documented) - assumptions
    unused = assumptions - set(documented)

    for script in sorted(undeclared):
        errors.append(
            f"template npm script '{script}' is not declared in "
            f"bootstrap.ASSUMED_NPM_SCRIPTS (referenced by {sorted(documented[script])})"
        )
    for script in sorted(unused):
        errors.append(
            f"bootstrap.ASSUMED_NPM_SCRIPTS entry '{script}' is never documented by a template"
        )
    return errors


def check_baseline_documents(label: str, repo_type: str, files: dict) -> list:
    """Ensure policy documents are generated only for the npm/ESLint repo type."""
    expected = set(bootstrap.NEXTJS_BASELINE_DOCUMENTS) if repo_type == "nextjs" else set()
    actual = {path for path in files if path.startswith("docs/") and path.endswith("-baseline.md")}
    errors = []

    missing = expected - actual
    unexpected = actual - expected
    if missing:
        errors.append(f"[{label}] missing baseline document(s) {sorted(missing)}")
    if unexpected:
        errors.append(f"[{label}] unexpected baseline document(s) {sorted(unexpected)}")

    for path in expected & actual:
        for phrase in BASELINE_DOCUMENT_REQUIREMENTS[path]:
            if phrase not in files[path]:
                errors.append(f"[{label}] {path} is missing required policy text {phrase!r}")

    if repo_type == "nextjs":
        missing_files = NEXTJS_BASELINE_REQUIRED_FILES - set(files)
        if missing_files:
            errors.append(f"[{label}] missing baseline file(s) {sorted(missing_files)}")

        audit_script = files.get(bootstrap.NEXTJS_ENFORCED_AUDIT_SCRIPT)
        if audit_script is None:
            errors.append(f"[{label}] missing {bootstrap.NEXTJS_ENFORCED_AUDIT_SCRIPT}")
        else:
            for phrase in ("docs/advisory-baseline.md", "npm", "--omit=dev"):
                if phrase not in audit_script:
                    errors.append(
                        f"[{label}] {bootstrap.NEXTJS_ENFORCED_AUDIT_SCRIPT} is missing {phrase!r}"
                    )
        if "# Baseline process" not in files.get(BASELINE_SKILL, ""):
            errors.append(f"[{label}] {BASELINE_SKILL} is missing the baseline process guidance")
        readme = files.get(bootstrap.README, "")
        for phrase in ("docs/lint-baseline.md", "docs/advisory-baseline.md"):
            if phrase not in readme:
                errors.append(f"[{label}] README.md is missing the baseline pointer {phrase!r}")

        prettierignore = files.get(".prettierignore", "")
        if ".release-please-manifest.json" not in prettierignore:
            errors.append(
                f"[{label}] .prettierignore must ignore the generated Release Please manifest"
            )

        # Item 11: the lint baseline now carries a review-date column and an
        # honest "Why this is accepted" header. The verifier must parse that
        # shape and the weekly review must report lint expiry, so a generated
        # repo whose scripts drift back to the old single-purpose lint parser
        # must fail validation rather than silently shipping a stale checker.
        baseline_table = files.get("scripts/baseline-table.mjs", "")
        for phrase in ("parseLintRows", "Why this is accepted"):
            if phrase not in baseline_table:
                errors.append(f"[{label}] scripts/baseline-table.mjs is missing {phrase!r}")
        verify_script = files.get("scripts/verify-baselines.mjs", "")
        if "parseLintRows" not in verify_script:
            errors.append(f"[{label}] scripts/verify-baselines.mjs is missing 'parseLintRows'")
        review_script = files.get("scripts/review-baselines.mjs", "")
        for phrase in ("parseLintRows", "Overdue lint reviews"):
            if phrase not in review_script:
                errors.append(f"[{label}] scripts/review-baselines.mjs is missing {phrase!r}")

        test_yml = files.get(".github/workflows/test.yml", "")
        try:
            test_workflow = yaml.safe_load(test_yml) or {}
            build_job = test_workflow["jobs"]["build"]
            steps = build_job["steps"]
        except (KeyError, TypeError, yaml.YAMLError):
            errors.append(f"[{label}] test.yml does not define build steps for the production audit")
        else:
            errors.extend(_blocking_build_job_errors(label, build_job))
            errors.extend(
                _blocking_step_errors(label, steps, "npm run audit:production", "production audit")
            )
            errors.extend(
                _blocking_step_errors(label, steps, "npm run verify:baselines", "baseline verification")
            )

        review_yml = files.get(bootstrap.NEXTJS_BASELINE_REVIEW_WORKFLOW, "")
        try:
            review_workflow = yaml.safe_load(review_yml) or {}
        except yaml.YAMLError as exc:
            errors.append(f"[{label}] baseline-review.yml is invalid YAML — {exc}")
        else:
            triggers = review_workflow.get("on", review_workflow.get(True, {})) or {}
            if set(triggers) != {"schedule", "workflow_dispatch"}:
                errors.append(
                    f"[{label}] baseline-review.yml must be schedule-and-dispatch only, got {sorted(triggers)}"
                )
            permissions = review_workflow.get("permissions", {}) or {}
            if not isinstance(permissions, dict):
                errors.append(
                    f"[{label}] baseline-review.yml permissions must be a mapping granting vulnerability-alerts: read"
                )
            else:
                if permissions.get("actions") != "read":
                    errors.append(f"[{label}] baseline-review.yml must grant actions: read")
                if permissions.get("vulnerability-alerts") != "read":
                    errors.append(f"[{label}] baseline-review.yml must grant vulnerability-alerts: read")
                if "security-events" in permissions:
                    errors.append(f"[{label}] baseline-review.yml must not use security-events permissions")
    return errors


def check_readme(label: str, cfg: dict, files: dict) -> list:
    """Ensure every generated repository has an actionable README starter."""
    repo_type = cfg["repo_type"]
    readme = files.get(bootstrap.README)
    if readme is None:
        return [f"[{label}] missing {bootstrap.README}"]

    errors = [
        f"[{label}] README.md is missing {phrase!r}"
        for phrase in README_REQUIREMENTS[repo_type]
        if phrase not in readme
    ]
    if repo_type == "swift":
        destination = cfg.get("destination") or "iphone"
        expected_commands = (
            "xcrun swift-format lint --recursive --strict .",
            "xcodebuild test",
            f"-scheme {shlex.quote(cfg['scheme'])}",
            f'-destination "{bootstrap._DESTINATION_EXAMPLES[destination]}"',
        )
        for command in expected_commands:
            if command not in readme:
                errors.append(f"[{label}] Swift README.md is missing {command!r}")
    return errors


RUST_SUITE_STEPS = (
    "[ ! -f Cargo.toml ]",
    "cargo fmt --all -- --check",
    "cargo clippy --workspace --all-targets -- -D warnings",
    "cargo test --workspace",
)


def check_rust_suite(label: str, repo_type: str, files: dict) -> list:
    """The Rust test.yml must keep its manifest guard and every CI command.

    The job-context check only proves a `test` job exists; this proves the job
    still runs the guard, fmt, clippy with warnings denied, and the tests.
    """
    if repo_type != "rust":
        return []
    workflow = yaml.safe_load(files.get(".github/workflows/test.yml", "")) or {}
    runs = [
        str(step.get("run", ""))
        for step in (workflow.get("jobs", {}).get("test", {}).get("steps") or [])
        if isinstance(step, dict)
    ]
    guard = [run for run in runs if "Cargo.toml" in run]
    errors = []
    if not any("[ ! -f Cargo.toml ]" in run and "exit 1" in run for run in guard):
        errors.append(f"[{label}] Rust test.yml is missing its blocking Cargo.toml guard")
    for command in RUST_SUITE_STEPS[1:]:
        if command not in [run.strip() for run in runs]:
            errors.append(f"[{label}] Rust test.yml is missing step {command!r}")
    return errors


def check_release_full_suite_contract(label: str, repo_type: str, files: dict) -> list:
    """Keep the release-gated Python/Swift caller on the full-suite contract.

    The reusable test workflows accept a boolean `full` input. A release
    workflow that only checks the commit message silently turns manual
    dispatch into the cheap path, so validate the rendered caller value rather
    than only checking that the input exists.
    """
    if repo_type not in ("python", "swift", "rust"):
        return []

    path = ".github/workflows/release-please.yml"
    source = files.get(path)
    if source is None:
        return [f"[{label}] missing {path} for release-gated {repo_type} output"]

    try:
        workflow = yaml.safe_load(source) or {}
        full = workflow["jobs"]["test"]["with"]["full"]
    except (KeyError, TypeError, yaml.YAMLError) as exc:
        return [f"[{label}] {path} has no readable jobs.test.with.full contract — {exc}"]

    if full != RELEASE_FULL_SUITE_EXPRESSION:
        return [
            f"[{label}] {path} jobs.test.with.full must be "
            f"{RELEASE_FULL_SUITE_EXPRESSION!r}, got {full!r}"
        ]
    return []


def _blocking_build_job_errors(label: str, build_job: dict) -> list:
    if "if" in build_job:
        return [f"[{label}] template build job must not be conditional"]
    if build_job.get("continue-on-error", False) is not False:
        return [f"[{label}] template build job must be blocking"]
    return []


def _blocking_step_errors(label: str, steps: list, command: str, description: str) -> list:
    matching = [
        step for step in steps if isinstance(step, dict) and step.get("run") == command
    ]
    if len(matching) != 1:
        return [f"[{label}] test.yml does not run the enforced {description} exactly once"]
    step = matching[0]
    if "if" in step:
        return [f"[{label}] template {description} must not be conditional"]
    if step.get("continue-on-error", False) is not False:
        return [f"[{label}] template {description} must be blocking"]
    return []


def _job_ids(workflow: dict) -> set:
    return set((workflow or {}).get("jobs", {}) or {})


def _reusable_call_targets(workflow: dict) -> dict:
    """Map caller job id -> local workflow file path it calls via `uses:`."""
    targets = {}
    for job_id, job in (workflow.get("jobs", {}) or {}).items():
        uses = job.get("uses", "")
        if uses.startswith("./.github/workflows/"):
            targets[job_id] = uses.removeprefix("./.github/workflows/")
    return targets


def _actual_reusable_contexts(ci_yml: str, test_yml: str, target_name: str = "test.yml") -> set:
    """Required-check-style "{caller job} / {called job}" contexts actually
    produced by a caller workflow (e.g. ci.yml) invoking a reusable workflow
    (e.g. test.yml) via `uses: ./.github/workflows/<target_name>`."""
    ci = yaml.safe_load(ci_yml)
    test = yaml.safe_load(test_yml)
    call_targets = _reusable_call_targets(ci)
    test_jobs = _job_ids(test)
    return {
        f"{caller} / {job}"
        for caller, target in call_targets.items()
        if target == target_name
        for job in test_jobs
    }


def _compare_contexts(expected: set, actual: set) -> tuple:
    """Return (missing, unexpected): contexts required-status-checks expects
    that don't exist, and contexts that exist but aren't required — either
    direction means the branch-protection check list has drifted from the
    generated workflows."""
    return expected - actual, actual - expected


def check_workflow_job_consistency(
    label: str, repo_type: str, files: dict, checks: list = None
) -> list:
    errors = []
    if checks is None:
        checks = bootstrap.required_status_checks(repo_type)

    title_check_job = "validate-title"
    pr_title_yml = files.get(".github/workflows/pr-title-check.yml")
    if pr_title_yml is not None:
        jobs = _job_ids(yaml.safe_load(pr_title_yml))
        if title_check_job not in jobs:
            errors.append(
                f"[{label}] required check '{title_check_job}' has no matching job "
                f"in pr-title-check.yml (jobs: {sorted(jobs)})"
            )

    ci_yml = files.get(".github/workflows/ci.yml")
    test_yml = files.get(".github/workflows/test.yml")
    non_title_checks = [c for c in checks if c != title_check_job]

    # Even with no non-title checks expected, a generated ci.yml/test.yml
    # pair that calls out to reusable jobs would produce *unexpected*
    # contexts — so run the comparison whenever those files exist, not only
    # when non_title_checks is non-empty.
    if ci_yml is None or test_yml is None:
        if non_title_checks:
            errors.append(
                f"[{label}] required check(s) {non_title_checks} expect ci.yml/test.yml "
                f"but one or both were not generated"
            )
        return errors

    actual_contexts = _actual_reusable_contexts(ci_yml, test_yml)
    expected_contexts = set(non_title_checks)
    missing, unexpected = _compare_contexts(expected_contexts, actual_contexts)

    if missing:
        errors.append(
            f"[{label}] required check context(s) {sorted(missing)} do not "
            f"correspond to any job in the generated ci.yml/test.yml "
            f"(available: {sorted(actual_contexts)})"
        )
    if unexpected:
        errors.append(
            f"[{label}] generated ci.yml/test.yml produce context(s) "
            f"{sorted(unexpected)} that required_status_checks({repo_type!r}) "
            f"doesn't list — update required_status_checks() to match"
        )

    return errors


def _triggers(workflow: dict) -> dict:
    """Return a workflow's `on:` mapping.

    YAML 1.1 resolves the bare word `on` to boolean True, so yaml.safe_load
    keys a workflow's trigger block under True rather than "on". Reading
    workflow["on"] silently yields nothing and every trigger-based assertion
    passes vacuously — so both spellings are accepted here, and this is the
    only place that detail needs to be known.
    """
    return workflow.get("on") or workflow.get(True) or {}


def _workflow_paths(files: dict) -> list:
    return sorted(
        path
        for path in files
        if path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml"))
    )


# Every generated workflow's top-level permissions, asserted exactly. A
# rendered path absent from this map is itself an error (see
# check_workflow_permissions) — a new workflow template must be a deliberate
# addition here, not an oversight.
#
# release-please.yml holds only {contents: read}: verified empirically against
# a live release run (finding #11), not by reasoning. googleapis/release-
# please-action was passed the explicit App token from create-github-app-token,
# and with the workflow scoped to read and no job-level override, PR creation,
# PR merge, tag creation, and GitHub Release creation all succeeded with no
# GITHUB_TOKEN write-permission error. That shows this run did not need a
# write fallback for those operations — it does not prove no read-only-shaped
# fallback path exists for some unobserved case. Do not broaden this without
# re-verifying against a live run first: narrowing it wrongly fails loudly
# (the next release is dead), but widening it wrongly fails silently — nothing
# breaks, it just grants standing write for no reason, which is exactly #11's
# original complaint.
EXPECTED_WORKFLOW_PERMISSIONS = {
    ".github/workflows/ci.yml": {"contents": "read"},
    ".github/workflows/test.yml": {"contents": "read"},
    ".github/workflows/release-please.yml": {"contents": "read"},
    ".github/workflows/pr-title-check.yml": {"pull-requests": "read"},
    ".github/workflows/baseline-review.yml": {
        "actions": "read",
        "contents": "read",
        "vulnerability-alerts": "read",
    },
}

# Job-level permissions, keyed by (workflow path, job id) and asserted as an
# exact expected *declaration*, not merely an allowlist for whatever a job
# happens to declare. A value of `None` means the job must declare no
# permissions block at all; a dict means it must declare exactly that one —
# in both cases the check is active whether or not the job currently has a
# block, so removing a required block is caught exactly like widening one.
# A (path, job_id) pair absent from this map entirely is a job this policy
# has no opinion on: it may or may not declare permissions, but if it does,
# the declaration must still be a recognised one (see the "unexpected
# job-level permissions block" branch below).
#
# release-please: relies entirely on the workflow-level {contents: read} plus
# the App token — a job-level grant here is exactly the kind of future
# addition #11 was raised to stop from passing unexamined, the way the old
# filename exemption let it.
EXPECTED_JOB_PERMISSIONS = {
    (".github/workflows/release-please.yml", "release-please"): None,
}


def check_workflow_permissions(label: str, files: dict) -> list:
    """Every generated workflow and job must scope GITHUB_TOKEN explicitly,
    minimally, and exactly — not merely "some mapping" (#10) and not merely
    "this file may hold write" (#11).

    Four assertions, because presence and boundedness are each weaker than
    the property that actually matters — an exact match:

    1. Every generated workflow path is a recognised one. An unmapped path
       means a new workflow template was added without updating
       EXPECTED_WORKFLOW_PERMISSIONS — the same "presence is not correctness"
       gap #10 exposed, one layer up, for the map itself.
    2. Its top-level permissions block exists, is a mapping (not a scalar like
       `read-all`, valid GitHub syntax but not an explicit per-scope grant),
       and equals its expected map exactly.
    3. Every job named in EXPECTED_JOB_PERMISSIONS is checked as an exact
       expected *declaration*, not merely an allowlist for a block it happens
       to have: a job expected to hold `None` must declare no block, and a job
       expected to hold a map must declare exactly that map — declaring
       nothing when a map is expected is caught the same as declaring the
       wrong map, closing the gap where deleting a required permission block
       passed silently and left a workflow to inherit an unsuitable default.
    4. A job outside that map that declares any permissions block is rejected
       outright as unexpected — an allowlist by (file, job), not a write/read
       heuristic that a new job-level grant could satisfy just by being
       read-only-shaped.
    """
    errors = []
    for path in _workflow_paths(files):
        workflow = yaml.safe_load(files[path]) or {}

        expected_top = EXPECTED_WORKFLOW_PERMISSIONS.get(path)
        if expected_top is None:
            errors.append(
                f"[{label}] {path} is not a recognised generated workflow — add "
                f"its expected permissions to EXPECTED_WORKFLOW_PERMISSIONS"
            )
        else:
            permissions = workflow.get("permissions")
            if permissions is None:
                errors.append(
                    f"[{label}] {path} declares no top-level permissions — "
                    f"expected exactly {expected_top}"
                )
            elif not isinstance(permissions, dict):
                errors.append(
                    f"[{label}] {path} permissions must be a mapping of "
                    f"explicit scopes, not {permissions!r}"
                )
            elif permissions != expected_top:
                errors.append(
                    f"[{label}] {path} must grant exactly {expected_top}, got "
                    f"{permissions}"
                )

        for job_id, job in (workflow.get("jobs") or {}).items():
            if not isinstance(job, dict):
                continue
            # "permissions" in job, not job.get("permissions") is not None: a
            # bare `permissions:` key with no value parses to None in YAML,
            # same as an absent key — .get() alone cannot tell a declared-null
            # block from no block at all, and a declared-null block is still a
            # declaration that must be rejected wherever none is expected.
            declared = "permissions" in job
            job_permissions = job.get("permissions")
            key = (path, job_id)
            if key not in EXPECTED_JOB_PERMISSIONS:
                if declared:
                    errors.append(
                        f"[{label}] {path} job '{job_id}' declares an unexpected "
                        f"job-level permissions block {job_permissions!r} — add "
                        f"it to EXPECTED_JOB_PERMISSIONS if intentional"
                    )
                continue

            expected_job = EXPECTED_JOB_PERMISSIONS[key]
            if expected_job is None:
                if declared:
                    errors.append(
                        f"[{label}] {path} job '{job_id}' must not declare its "
                        f"own permissions block — it relies on the "
                        f"workflow-level {EXPECTED_WORKFLOW_PERMISSIONS.get(path)} "
                        f"plus the explicit App token (verified against a live "
                        f"release run, finding #11)"
                    )
            elif not declared:
                errors.append(
                    f"[{label}] {path} job '{job_id}' declares no permissions "
                    f"block — expected exactly {expected_job}"
                )
            elif not isinstance(job_permissions, dict):
                errors.append(
                    f"[{label}] {path} job '{job_id}' permissions must be a "
                    f"mapping of explicit scopes, not {job_permissions!r}"
                )
            elif job_permissions != expected_job:
                errors.append(
                    f"[{label}] {path} job '{job_id}' must grant exactly "
                    f"{expected_job}, got {job_permissions}"
                )
    return errors


def check_sha_pinned_actions(label: str, files: dict) -> list:
    """Every external `uses:` must pin a full 40-character commit SHA.

    GitHub's "Require actions to be pinned to a full-length commit SHA" repo
    setting (bootstrap.py's configure_repo() sets sha_pinning_required: true)
    rejects any run whose workflow references a tag or branch instead — a
    regression here would fail the first real workflow run, not just this
    validator, so it is caught here. Local reusable-workflow calls
    (`./.github/workflows/...`) are exempt: the setting does not require them
    to use SHAs, and they carry no external supply-chain exposure.
    """
    errors = []
    for path in _workflow_paths(files):
        workflow = yaml.safe_load(files[path]) or {}
        for job_id, job in (workflow.get("jobs", {}) or {}).items():
            if not isinstance(job, dict):
                continue
            refs = []
            job_uses = job.get("uses")
            if isinstance(job_uses, str):
                refs.append(("job", job_uses))
            for step in job.get("steps") or []:
                if isinstance(step, dict) and isinstance(step.get("uses"), str):
                    refs.append(("step", step["uses"]))

            for kind, uses in refs:
                if uses.startswith("./"):
                    continue
                if "@" not in uses:
                    errors.append(
                        f"[{label}] {path} job '{job_id}' {kind} `uses: {uses}` "
                        f"has no @ref to pin"
                    )
                    continue
                ref = uses.rsplit("@", 1)[1]
                if not COMMIT_SHA_RE.match(ref):
                    errors.append(
                        f"[{label}] {path} job '{job_id}' {kind} `uses: {uses}` "
                        f"is not pinned to a full 40-character commit SHA"
                    )
    return errors


# Marketplace verified creators whose actions the generated workflows use.
# verified_allowed covers them, so they need no explicit pattern; every other
# third-party action must match bootstrap.selected_action_patterns().
# googleapis: "GitHub has manually verified the creator" on the
# release-please-action Marketplace page, checked 2026-10-08.
VERIFIED_ACTION_OWNERS = frozenset({"googleapis"})
GITHUB_OWNED_ACTION_OWNERS = frozenset({"actions", "github"})
APP_TOKEN_PERMISSIONS = {"permission-contents": "write", "permission-pull-requests": "write"}
PYTHON_SUITE_COMMANDS = ("ruff check .", "mypy .", "pytest")
PYTHON_TOOL_PIN_RE = re.compile(r"\b(ruff|mypy|pytest)==\d+(\.\d+)+\b")
PYTHON_TOOL_LOOP_RE = re.compile(r"^\s*for tool in ([^;\n]+); do\s*$", re.MULTILINE)
PYTHON_UNPINNED_INSTALL_RE = re.compile(r"pip install\b[^\n]*\b(ruff|mypy|pytest)\b(?!==)")
PLAYWRIGHT_INSTALLS = (
    ("${{ inputs.full }}", "npx playwright install --with-deps"),
    ("${{ !inputs.full }}", "npx playwright install --with-deps chromium"),
)
PLAYWRIGHT_RUNS = (
    ("${{ inputs.full }}", "npm run test:e2e"),
    ("${{ !inputs.full }}", "npm run test:e2e -- --project=chromium"),
)
E2E_JOB_CONDITION = "${{ inputs.e2e || inputs.full }}"
BRANCH_PROTECTION_KEYS = frozenset({
    "required_status_checks", "enforce_admins", "required_pull_request_reviews", "restrictions",
})


# Falsy literals in GitHub's expression syntax (false, 0, -0, null, ''),
# checked 2026-10-09 against docs.github.com "Evaluate expressions".
FALSY_EXPRESSION_LITERALS = frozenset({"false", "null", "''"})
HEX_LITERAL_RE = re.compile(r"[-+]?0x[0-9a-f]+")


def _never_runs(condition) -> bool:
    """True for an `if:` that is a falsy literal, with or without `${{ }}`.

    Only the expression's outer whitespace is trimmed: `' '` is a non-empty,
    truthy string. Numbers are compared by value, so 0, -0, 0.0, 0e0 and 0x0
    all count as zero.
    """
    if condition is False or condition is None or condition == 0:
        return True
    text = str(condition).strip()
    if text.startswith("${{") and text.endswith("}}"):
        text = text[3:-2].strip()
    text = text.lower()
    if text in FALSY_EXPRESSION_LITERALS:
        return True
    try:
        return (int(text, 16) if HEX_LITERAL_RE.fullmatch(text) else float(text)) == 0
    except ValueError:
        return False


def _executable_lines(script: str) -> list:
    """Shell lines with whole-line comments removed."""
    return [line for line in script.splitlines() if not line.strip().startswith("#")]


def check_workflow_gates(label: str, repo_type: str, files: dict) -> list:
    """Executable gates the phrase and context checks cannot see.

    A release that no longer waits for `test`, a suite step that cannot fail
    or never runs, a job without a timeout, a third-party action the generated
    Actions policy would block, an App token wider than release-please needs,
    or an e2e run whose browsers do not match its projects all leave every
    other check green.
    """
    errors = []
    # Every generated pattern is `owner/repo@*`: the repository must match exactly.
    allowed_actions = {p.removesuffix("@*") for p in bootstrap.selected_action_patterns(repo_type)}
    for path in _workflow_paths(files):
        workflow = yaml.safe_load(files[path]) or {}
        for job_id, job in (workflow.get("jobs", {}) or {}).items():
            if not isinstance(job, dict):
                continue
            where = f"[{label}] {path} job '{job_id}'"
            if job.get("continue-on-error", False) is not False:
                errors.append(f"{where} must not set continue-on-error")
            if "if" in job and _never_runs(job["if"]):
                errors.append(f"{where} has an `if:` that never runs")
            if "runs-on" in job:
                timeout = job.get("timeout-minutes")
                if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
                    errors.append(f"{where} needs a positive integer timeout-minutes")
            uses_refs = [job["uses"]] if isinstance(job.get("uses"), str) else []
            for step in job.get("steps") or []:
                if not isinstance(step, dict):
                    continue
                name = step.get("name") or step.get("run") or step.get("uses")
                if step.get("continue-on-error", False) is not False:
                    errors.append(f"{where} step {name!r} must not set continue-on-error")
                if "if" in step and _never_runs(step["if"]):
                    errors.append(f"{where} step {name!r} has an `if:` that never runs")
                if isinstance(step.get("uses"), str):
                    uses_refs.append(step["uses"])
                    if step["uses"].startswith("actions/create-github-app-token@"):
                        granted = {k: v for k, v in (step.get("with") or {}).items() if k.startswith("permission-")}
                        if granted != APP_TOKEN_PERMISSIONS:
                            errors.append(
                                f"{where} App token must request exactly {APP_TOKEN_PERMISSIONS}, got {granted}"
                            )
            for uses in uses_refs:
                if uses.startswith("./"):
                    continue
                action = uses.split("@", 1)[0]
                owner = action.split("/", 1)[0]
                if owner in GITHUB_OWNED_ACTION_OWNERS | VERIFIED_ACTION_OWNERS:
                    continue
                if action not in allowed_actions:
                    errors.append(
                        f"{where} uses {action}, which the generated Actions policy for "
                        f"{repo_type!r} does not allow (see bootstrap.selected_action_patterns)"
                    )

    release = yaml.safe_load(files.get(".github/workflows/release-please.yml", "")) or {}
    release_jobs = release.get("jobs", {}) or {}
    if repo_type in ("nextjs", "python", "swift", "rust"):
        needs = (release_jobs.get("release-please") or {}).get("needs")
        if "test" not in ([needs] if isinstance(needs, str) else (needs or [])):
            errors.append(f"[{label}] release-please.yml job 'release-please' must need 'test'")
        # Any `if:` here (always(), failure(), !cancelled()) can run the job
        # after `test` fails; `needs` alone is the success gate. Deliberately
        # strict: even a safe condition such as success() needs this rule
        # changed first, so no release condition lands without review.
        if "if" in (release_jobs.get("release-please") or {}):
            errors.append(f"[{label}] release-please.yml job 'release-please' must not be conditional")
        if "if" in (release_jobs.get("test") or {}):
            errors.append(f"[{label}] release-please.yml job 'test' must not be conditional")

    test = yaml.safe_load(files.get(".github/workflows/test.yml", "")) or {}
    test_jobs = test.get("jobs", {}) or {}
    if repo_type in ("python", "rust"):
        suite = test_jobs.get("test") or {}
        if "if" in suite:
            errors.append(f"[{label}] {repo_type} test.yml job 'test' must not be conditional")
        steps = suite.get("steps") or []
        commands = PYTHON_SUITE_COMMANDS if repo_type == "python" else RUST_SUITE_STEPS[1:]
        for command in commands:
            matching = [s for s in steps if isinstance(s, dict) and str(s.get("run", "")).strip() == command]
            if len(matching) != 1:
                errors.append(f"[{label}] {repo_type} suite step {command!r} must run exactly once")
            elif "if" in matching[0] or matching[0].get("continue-on-error", False) is not False:
                errors.append(f"[{label}] {repo_type} suite step {command!r} must be unconditional and blocking")
    if repo_type == "python":
        install = "\n".join(
            line
            for step in (test_jobs.get("test") or {}).get("steps") or []
            if isinstance(step, dict) and step.get("name") == "Install dependencies"
            for line in _executable_lines(str(step.get("run", "")))
        )
        loop = PYTHON_TOOL_LOOP_RE.search(install)
        pinned = {m.group(1) for m in PYTHON_TOOL_PIN_RE.finditer(loop.group(1))} if loop else set()
        unpinned = PYTHON_UNPINNED_INSTALL_RE.search(install)
        if pinned != {"ruff", "mypy", "pytest"} or unpinned:
            errors.append(
                f"[{label}] Python test.yml must install ruff, mypy and pytest only through its "
                f"pinned fallback loop, found pins for {sorted(pinned)}"
                + (f" and unpinned {unpinned.group(0)!r}" if unpinned else "")
            )
    if repo_type == "nextjs":
        e2e = test_jobs.get("e2e") or {}
        if e2e.get("if") != E2E_JOB_CONDITION:
            errors.append(f"[{label}] Next.js e2e job must run when {E2E_JOB_CONDITION}, got {e2e.get('if')!r}")
        pairs = [
            (str(step.get("if", "")), str(step.get("run", "")).strip())
            for step in e2e.get("steps") or []
            if isinstance(step, dict)
        ]
        installs = sorted(pair for pair in pairs if "playwright install" in pair[1])
        if installs != sorted(PLAYWRIGHT_INSTALLS):
            errors.append(
                f"[{label}] Next.js e2e must install every default browser for full runs and "
                f"Chromium otherwise, got {installs}"
            )
        runs = sorted(pair for pair in pairs if "test:e2e" in pair[1])
        if runs != sorted(PLAYWRIGHT_RUNS):
            errors.append(
                f"[{label}] Next.js e2e must run every project on full runs and Chromium "
                f"otherwise, got {runs}"
            )
    return errors


def _own_workflow_files() -> dict:
    return {
        f".github/workflows/{path.name}": path.read_text()
        for path in OWN_WORKFLOWS_DIR.glob("*.yml")
    }


def check_reusable_workflow_inputs(label: str, files: dict) -> list:
    """Assert every `with:` key on a local reusable-workflow call is declared.

    GitHub fails the whole workflow at parse time on an undeclared input
    ("Invalid input, <name> is not defined in the referenced workflow"), so a
    caller/callee drift here doesn't degrade a run — it stops the workflow ever
    running. That is how release-please.yml came to be inert on every generated
    Python repo: the `full` input was added to test.yml, test-swift.yml and
    test-swift-xcodegen.yml and passed by both callers, but never declared in
    test-python.yml. check_workflow_job_consistency matches job *ids*, so it saw
    nothing wrong. Checked both directions — a required input the caller never
    supplies fails the same way.
    """
    errors = []
    for caller_path in _workflow_paths(files):
        caller = yaml.safe_load(files[caller_path]) or {}
        for job_id, job in (caller.get("jobs", {}) or {}).items():
            if not isinstance(job, dict):
                continue
            uses = job.get("uses", "")
            if not uses.startswith("./.github/workflows/"):
                continue

            target_path = f".github/workflows/{uses.removeprefix('./.github/workflows/')}"
            target_source = files.get(target_path)
            if target_source is None:
                errors.append(
                    f"[{label}] {caller_path} job '{job_id}' calls {uses} "
                    f"but that workflow is not generated"
                )
                continue

            target = yaml.safe_load(target_source) or {}
            triggers = _triggers(target)
            if "workflow_call" not in triggers:
                # Checked before the input comparison, not folded into it: a
                # target that dropped `on: workflow_call` while its caller
                # supplies no inputs produces two empty dicts, so every
                # per-input assertion below passes vacuously while the call
                # itself is invalid. GitHub refuses to run it.
                errors.append(
                    f"[{label}] {caller_path} job '{job_id}' calls {target_path}, "
                    f"which does not declare `on: workflow_call` and is "
                    f"therefore not callable (triggers: {sorted(map(str, triggers))})"
                )
                continue

            call_trigger = triggers.get("workflow_call") or {}
            declared = call_trigger.get("inputs") or {}
            supplied = job.get("with") or {}

            for name in sorted(set(supplied) - set(declared)):
                errors.append(
                    f"[{label}] {caller_path} job '{job_id}' passes input "
                    f"'{name}' to {target_path}, which does not declare it — "
                    f"GitHub rejects this at parse time (declared: "
                    f"{sorted(declared)})"
                )
            for name, spec in sorted(declared.items()):
                if isinstance(spec, dict) and spec.get("required") and name not in supplied:
                    errors.append(
                        f"[{label}] {caller_path} job '{job_id}' omits required "
                        f"input '{name}' of {target_path}"
                    )
    return errors


def check_release_please_config(label: str, cfg: dict, files: dict) -> list:
    """Assert the *values* in the rendered Release Please config, not just that
    it parses.

    check_syntax calls json.loads and discards the result, so every rendered
    JSON file was checked for parseability and nothing else. That is how every
    Swift repo came to ship "package-name": "DEPENDENCY_NOTE" — generate_files()
    rebound its `name` local in an unrelated marker loop, and no assertion ever
    looked at the value.
    """
    source = files.get("release-please-config.json")
    if source is None:
        return [f"[{label}] missing release-please-config.json"]
    try:
        config = json.loads(source)
    except json.JSONDecodeError as exc:
        return [f"[{label}] release-please-config.json: invalid JSON — {exc}"]

    errors = []
    package = (config.get("packages") or {}).get(".")
    if not isinstance(package, dict):
        return [f"[{label}] release-please-config.json has no '.' package entry"]

    expected_name = cfg["name"]
    if package.get("package-name") != expected_name:
        errors.append(
            f"[{label}] release-please-config.json package-name is "
            f"{package.get('package-name')!r}, expected {expected_name!r}"
        )
    expected_release_type = "node" if cfg["repo_type"] == "nextjs" else "simple"
    if package.get("release-type") != expected_release_type:
        errors.append(
            f"[{label}] release-please-config.json release-type is "
            f"{package.get('release-type')!r}, expected {expected_release_type!r}"
        )
    if config.get("include-component-in-tag") is not False:
        errors.append(
            f"[{label}] release-please-config.json must set "
            f"include-component-in-tag: false (single-package repos tag vX.Y.Z)"
        )

    manifest_source = files.get(".release-please-manifest.json")
    if manifest_source is None:
        errors.append(f"[{label}] missing .release-please-manifest.json")
    else:
        try:
            if json.loads(manifest_source).get(".") != "0.1.0":
                errors.append(
                    f"[{label}] .release-please-manifest.json must start a new "
                    f"repo at '.': '0.1.0'"
                )
        except json.JSONDecodeError as exc:
            errors.append(f"[{label}] .release-please-manifest.json: invalid JSON — {exc}")
    return errors


def check_branch_protection_payload(label: str, repo_type: str, payload: dict = None) -> list:
    """Assert the branch-protection policy a generated repo is born with.

    The contexts check (check_workflow_job_consistency) proves the required
    checks exist; this proves the *configuration* carrying them matches the
    operator's item-10 rulings — a payload proposing strict True again, or a
    dropped context, must fail here rather than in the next generated repo.
    """
    if payload is None:
        payload = bootstrap.branch_protection_payload(repo_type)
    errors = []

    rsc = payload.get("required_status_checks") or {}
    if rsc.get("strict") is not False:
        errors.append(
            f"[{label}] branch protection must set strict: False "
            f"(ruled: up-to-date requirement strands release PRs)"
        )
    expected_contexts = bootstrap.required_status_checks(repo_type)
    if rsc.get("contexts") != expected_contexts:
        errors.append(
            f"[{label}] protection contexts {rsc.get('contexts')} do not match "
            f"required_status_checks({repo_type!r}) {expected_contexts}"
        )
    if payload.get("enforce_admins") is not True:
        errors.append(f"[{label}] branch protection must enforce admins")

    reviews = payload.get("required_pull_request_reviews")
    if not isinstance(reviews, dict) or reviews.get("required_approving_review_count") != 0:
        errors.append(
            f"[{label}] branch protection must require a PR with zero required approvals"
        )
    if isinstance(reviews, dict) and (
        reviews.get("dismiss_stale_reviews") is not False
        or reviews.get("require_code_owner_reviews") is not False
    ):
        errors.append(
            f"[{label}] branch protection must not dismiss stale reviews or require code owners"
        )
    if payload.get("restrictions") is not None:
        errors.append(f"[{label}] branch protection must not add push restrictions")
    # Any other key (allow_force_pushes, allow_deletions, ...) changes the policy.
    if set(payload) != BRANCH_PROTECTION_KEYS:
        errors.append(
            f"[{label}] branch protection must set exactly {sorted(BRANCH_PROTECTION_KEYS)}, "
            f"got {sorted(payload)}"
        )
    return errors


def check_runbook(label: str, files: dict) -> list:
    """Every generated repo is born with the branch-protection runbook.

    Its facts were bought with real incidents; a generated repo that lacks
    them rediscovers each one the hard way."""
    content = files.get(BRANCH_PROTECTION_RUNBOOK)
    if content is None:
        return [f"[{label}] missing {BRANCH_PROTECTION_RUNBOOK}"]
    return [
        f"[{label}] {BRANCH_PROTECTION_RUNBOOK} is missing operational fact {phrase!r}"
        for phrase in RUNBOOK_REQUIRED_PHRASES
        if phrase not in content
    ]


def _read_file_or_none(path: Union[str, Path]) -> Optional[bytes]:
    """Read the file at the given path, or None if it is absent.

    Used by check_runbook_copy_matches_template so a missing file becomes a
    labelled error instead of an abort — the same defensive discipline case 21
    established for the generated-runbook check."""
    try:
        with open(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None


def check_runbook_copy_matches_template(
    label: str, repo_copy: Optional[bytes], template_copy: Optional[bytes]
) -> list:
    """The bootstrapper's own docs/ runbook must match the template as rendered.

    Generated repositories receive the runbook stamped (bootstrap.stamp), so
    the bootstrapper's own copy must equal the stamped render. Until the
    bootstrapper adopts its own stamped copy, the exact unstamped template is
    accepted too; any other byte difference fails.

    The template ships into every generated repository; the repo's own copy is
    what readers here see. A silent drift between the two means the repository
    documents one operational runbook while shipping another. Both files live in
    this one repository and validate-templates is already a required check here,
    so the assertion is enforced the moment it is written."""
    if repo_copy is None:
        return [f"[{label}] missing {REPO_RUNBOOK}"]
    if template_copy is None:
        return [f"[{label}] missing {TEMPLATE_RUNBOOK}"]
    if repo_copy == template_copy:
        return []
    try:
        stamped = bootstrap.stamp(template_copy.decode()).encode()
    except UnicodeDecodeError:
        stamped = None
    if repo_copy != stamped:
        return [
            f"[{label}] {REPO_RUNBOOK} differs from {TEMPLATE_RUNBOOK} rendered through "
            "bootstrap.stamp — the repository's own runbook must match the template "
            "so this repo and the repositories it generates never document "
            "different gates"
        ]
    return []


def _digest_table(table: dict) -> dict:
    return {path: set(digests) for path, digests in table.items()}


def check_legacy_digests(computed: Optional[dict] = None, recorded: Optional[dict] = None) -> list:
    """bootstrap.LEGACY_TEMPLATE_DIGESTS must equal what the released tags give.

    Without git tags (a shallow clone) the table cannot be rebuilt, so the
    check is skipped with a notice rather than passed silently."""
    if computed is None:
        if not bootstrap._legacy_tags():
            print("notice: git vX.Y.Z release tags unavailable; skipped the LEGACY_TEMPLATE_DIGESTS check")
            return []
        computed = bootstrap.compute_legacy_digests()
    if recorded is None:
        recorded = bootstrap.LEGACY_TEMPLATE_DIGESTS
    if _digest_table(computed) != _digest_table(recorded):
        return [
            "bootstrap.LEGACY_TEMPLATE_DIGESTS is stale; regenerate it with "
            "`python3 validate_templates.py --regenerate-legacy-digests` and paste the output"
        ]
    return []


def format_legacy_digests(table: dict) -> str:
    """LEGACY_TEMPLATE_DIGESTS as deterministic Python source."""
    lines = ["LEGACY_TEMPLATE_DIGESTS: dict[str, frozenset[str]] = {"]
    for path in sorted(table):
        lines.append(f"    {json.dumps(path)}: frozenset({{")
        lines += [f"        {json.dumps(digest)}," for digest in sorted(table[path])]
        lines.append("    }),")
    lines.append("}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Self-tests for check_workflow_job_consistency itself — these use synthetic
# workflow fixtures (not bootstrap.generate_files output) to prove the missing
# and unexpected branches of the consistency check actually fire, rather than
# only exercising the already-consistent generated configurations.
# ---------------------------------------------------------------------------


def _fixture_files(test_job_ids: list) -> dict:
    jobs_yaml = "\n".join(f"    {job_id}: {{}}" for job_id in test_job_ids)
    return {
        ".github/workflows/pr-title-check.yml": "jobs:\n  validate-title: {}\n",
        ".github/workflows/ci.yml": "jobs:\n  test:\n    uses: ./.github/workflows/test.yml\n",
        ".github/workflows/test.yml": f"jobs:\n{jobs_yaml}\n",
    }


def run_self_tests() -> list:
    errors = []

    # Case 1: missing context — required_status_checks expects "test / test"
    # but test.yml's only job is "unit", so no "test / test" context exists.
    files = _fixture_files(["unit"])
    result = check_workflow_job_consistency(
        "self-test:missing", "python", files, checks=["validate-title", "test / test"]
    )
    if not any("do not correspond" in e for e in result):
        errors.append(f"self-test 'missing context' did not fail as expected: {result}")

    # Case 2: unexpected context — test.yml has an extra "lint" job producing
    # "test / lint", which required_status_checks doesn't list.
    files = _fixture_files(["test", "lint"])
    result = check_workflow_job_consistency(
        "self-test:unexpected", "python", files, checks=["validate-title", "test / test"]
    )
    if not any("doesn't list" in e for e in result):
        errors.append(f"self-test 'unexpected context' did not fail as expected: {result}")

    # Case 3: consistent — no errors expected.
    files = _fixture_files(["test"])
    result = check_workflow_job_consistency(
        "self-test:consistent", "python", files, checks=["validate-title", "test / test"]
    )
    if result:
        errors.append(f"self-test 'consistent' unexpectedly failed: {result}")

    # Case 4: template command omitted from assumptions.
    result = check_npm_script_assumptions(
        {"AGENTS-nextjs-commands.md": "npm run lint\nnpm test\n"}, {"test"}
    )
    if not any("not declared" in e for e in result):
        errors.append(f"self-test 'undeclared npm script' did not fail as expected: {result}")

    # Case 5: stale assumption no template actually documents.
    result = check_npm_script_assumptions(
        {"AGENTS-nextjs-commands.md": "npm test\n"}, {"test", "lint"}
    )
    if not any("never documented" in e for e in result):
        errors.append(f"self-test 'unused npm assumption' did not fail as expected: {result}")

    # Case 6: an explicitly optional local workaround must not become a
    # generated-scaffold script contract.
    result = check_npm_script_assumptions(
        {"AGENTS-nextjs-commands.md": "npm run test:e2e:local` when that script is available"},
        set(),
    )
    if result:
        errors.append(f"self-test 'optional npm script' unexpectedly failed: {result}")

    # Case 7: optional wording must not exempt another undeclared script.
    result = check_npm_script_assumptions(
        {"AGENTS-nextjs-commands.md": "npm run invented` when that script is available"},
        set(),
    )
    if not any("not declared" in e for e in result):
        errors.append(f"self-test 'optional script exemption' did not fail: {result}")

    # Case 8: shared agent guidance applies to every generated repository type,
    # not only the Next.js configuration that has baseline guidance.
    files = bootstrap.generate_files(
        next(cfg for _, cfg in configurations() if cfg["repo_type"] == "python")
    )
    files["AGENTS.md"] = files["AGENTS.md"].replace("## Definition of done", "")
    result = check_agents_guidance("self-test:missing common agents guidance", files)
    if not any("Definition of done" in e for e in result):
        errors.append(
            "self-test 'missing common agents guidance' did not fail as expected: "
            f"{result}"
        )

    # Case 8b: the screenshot privacy and pre-commit review gates are pinned to
    # the hub for every type, even where the screenshot-review skill repeats
    # them, so dropping them from the hub fails closed.
    for repo_type in ("nextjs", "swift", "python", "rust", "simple"):
        cfg = next(cfg for _, cfg in configurations() if cfg["repo_type"] == repo_type)
        files = bootstrap.generate_files(dict(cfg))
        result = check_agents_guidance(f"self-test:{repo_type} screenshot gates", files)
        if result:
            errors.append(f"self-test '{repo_type} screenshot gates' unexpectedly failed: {result}")
        files[HUB] = files[HUB].replace("Never capture live or private data", "Capture data", 1)
        result = check_agents_guidance(f"self-test:{repo_type} screenshot gate dropped", files)
        if not any("AGENTS.md is missing common guidance 'Never capture live" in e for e in result):
            errors.append(f"self-test '{repo_type} screenshot gate dropped' did not fail as expected: {result}")

    # Case 6b: screenshot guidance is composed only for browser-capable and
    # native configurations, and each safety/structure guard fails closed when
    # its source is mutated.
    for repo_type in ("nextjs", "swift"):
        cfg = next(cfg for _, cfg in configurations() if cfg["repo_type"] == repo_type)
        files = bootstrap.generate_files(dict(cfg))
        result = check_screenshot_guidance(f"self-test:{repo_type} screenshot guidance", repo_type, files)
        if result:
            errors.append(f"self-test '{repo_type} screenshot guidance' unexpectedly failed: {result}")

        missing = dict(files)
        del missing[bootstrap.SCREENSHOT_REVIEW]
        result = check_screenshot_guidance(f"self-test:{repo_type} missing screenshot document", repo_type, missing)
        if not any("missing docs/screenshot-review.md" in e for e in result):
            errors.append(f"self-test '{repo_type} missing screenshot document' did not fail as expected: {result}")

        heading = dict(files)
        heading[bootstrap.SCREENSHOT_REVIEW] = files[bootstrap.SCREENSHOT_REVIEW].replace(
            SCREENSHOT_PLATFORM_HEADINGS[repo_type], "## Platform guidance", 1
        )
        result = check_screenshot_guidance(f"self-test:{repo_type} heading drift", repo_type, heading)
        if not any("missing heading" in e for e in result):
            errors.append(f"self-test '{repo_type} heading drift' did not fail as expected: {result}")

        broken_link = dict(files)
        broken_link[bootstrap.SCREENSHOT_REVIEW] = files[bootstrap.SCREENSHOT_REVIEW].replace(
            "../AGENTS.md", "../missing-AGENTS.md", 1
        )
        result = check_screenshot_guidance(f"self-test:{repo_type} broken screenshot link", repo_type, broken_link)
        if not any("broken local Markdown link" in e for e in result):
            errors.append(f"self-test '{repo_type} broken screenshot link' did not fail as expected: {result}")

        marker = dict(files)
        marker[bootstrap.SCREENSHOT_REVIEW] += "\n# <<PLATFORM_GUIDANCE>>\n"
        result = check_markers(f"self-test:{repo_type} unreplaced screenshot marker", marker)
        if not result:
            errors.append(f"self-test '{repo_type} unreplaced screenshot marker' did not fail as expected")

        platform_leak = dict(files)
        leak = "xcodebuild" if repo_type == "nextjs" else "browser capture"
        platform_leak[bootstrap.SCREENSHOT_REVIEW] += f"\n{leak}\n"
        result = check_screenshot_guidance(f"self-test:{repo_type} platform separation", repo_type, platform_leak)
        if not any("leaks" in e for e in result):
            errors.append(f"self-test '{repo_type} platform separation' did not fail as expected: {result}")

        invented = dict(files)
        invented[bootstrap.SCREENSHOT_REVIEW] += "\nnpm run screenshots\n"
        result = check_screenshot_guidance(f"self-test:{repo_type} invented tooling", repo_type, invented)
        if not any("invents tooling" in e for e in result):
            errors.append(f"self-test '{repo_type} invented tooling' did not fail as expected: {result}")

        skill_invented = dict(files)
        skill_invented[SCREENSHOT_SKILL] += "\nRun `npm run screenshots` to capture.\n"
        result = check_screenshot_guidance(f"self-test:{repo_type} skill invented tooling", repo_type, skill_invented)
        if not any("screenshot-review/SKILL.md invents tooling" in e for e in result):
            errors.append(f"self-test '{repo_type} skill invented tooling' did not fail as expected: {result}")

        for variant in ("npx  playwright test", "npx\tplaywright test", "npm run\nscreenshots"):
            spaced = dict(files)
            spaced[SCREENSHOT_SKILL] += f"\nRun `{variant}` to capture.\n"
            result = check_screenshot_guidance(f"self-test:{repo_type} skill tooling spacing", repo_type, spaced)
            if not any("screenshot-review/SKILL.md invents tooling" in e for e in result):
                errors.append(f"self-test '{repo_type} skill tooling spacing {variant!r}' did not fail as expected: {result}")
            spaced_doc = dict(files)
            spaced_doc[bootstrap.SCREENSHOT_REVIEW] += f"\nRun `{variant}` to capture.\n"
            result = check_screenshot_guidance(f"self-test:{repo_type} document tooling spacing", repo_type, spaced_doc)
            if not any("screenshot-review.md invents tooling" in e for e in result):
                errors.append(f"self-test '{repo_type} document tooling spacing {variant!r}' did not fail as expected: {result}")

        no_routing = dict(files)
        no_routing[SCREENSHOT_SKILL] = " ".join(files[SCREENSHOT_SKILL].split()).replace("load it first.", "", 1)
        result = check_screenshot_guidance(f"self-test:{repo_type} skill routing", repo_type, no_routing)
        if not any("missing its routing" in e for e in result):
            errors.append(f"self-test '{repo_type} skill routing' did not fail as expected: {result}")

        no_pointer = dict(files)
        no_pointer[HUB] = files[HUB].replace("Load `screenshot-review` for the full process.", "", 1)
        result = check_screenshot_guidance(f"self-test:{repo_type} hub screenshot pointer", repo_type, no_pointer)
        if not any("missing its pointer 'Load" in e for e in result):
            errors.append(f"self-test '{repo_type} hub screenshot pointer' did not fail as expected: {result}")

    for repo_type in ("python", "rust", "simple"):
        cfg = next(cfg for _, cfg in configurations() if cfg["repo_type"] == repo_type)
        files = bootstrap.generate_files(dict(cfg))
        result = check_screenshot_guidance(f"self-test:{repo_type} platform separation", repo_type, files)
        if result:
            errors.append(f"self-test '{repo_type} screenshot omission' unexpectedly failed: {result}")
        pointer = dict(files)
        pointer[HUB] += "\nLoad `screenshot-review` for the full process.\n"
        result = check_screenshot_guidance(f"self-test:{repo_type} stray screenshot pointer", repo_type, pointer)
        if not any("must not point at the screenshot-review skill" in e for e in result):
            errors.append(f"self-test '{repo_type} stray screenshot pointer' did not fail as expected: {result}")
        files[bootstrap.SCREENSHOT_REVIEW] = "# Screenshot review guidance\n"
        result = check_screenshot_guidance(f"self-test:{repo_type} unexpected screenshot document", repo_type, files)
        if not any("must not be generated" in e for e in result):
            errors.append(f"self-test '{repo_type} unexpected screenshot document' did not fail as expected: {result}")

    # Case 7: a Next.js configuration must carry both policy documents.
    result = check_baseline_documents("self-test:missing baseline", "nextjs", {})
    if not any("missing baseline document" in e for e in result):
        errors.append(f"self-test 'missing baseline document' did not fail as expected: {result}")

    # Case 7: npm/ESLint policy docs are not valid output for Swift.
    result = check_baseline_documents(
        "self-test:unexpected baseline",
        "swift",
        {"docs/lint-baseline.md": ""},
    )
    if not any("unexpected baseline document" in e for e in result):
        errors.append(f"self-test 'unexpected baseline document' did not fail as expected: {result}")

    # Case 8: a Next.js configuration must ship the executable audit checker,
    # not only prose that claims an advisory floor is enforced.
    files = bootstrap.generate_files(next(cfg for _, cfg in configurations() if cfg["repo_type"] == "nextjs"))
    files.pop(bootstrap.NEXTJS_ENFORCED_AUDIT_SCRIPT, None)
    result = check_baseline_documents("self-test:missing audit checker", "nextjs", files)
    if not any("missing scripts/audit-production.mjs" in e for e in result):
        errors.append(f"self-test 'missing audit checker' did not fail as expected: {result}")

    # Case 9: the template must run the checker as a blocking step. Quoting a
    # truthy value must not evade the semantic workflow check.
    files = bootstrap.generate_files(next(cfg for _, cfg in configurations() if cfg["repo_type"] == "nextjs"))
    files[".github/workflows/test.yml"] = files[".github/workflows/test.yml"].replace(
        "- run: npm run audit:production",
        "- run: npm run audit:production\n        continue-on-error: \"true\"",
        1,
    )
    result = check_baseline_documents("self-test:quoted non-blocking audit", "nextjs", files)
    if not any("template production audit must be blocking" in e for e in result):
        errors.append(f"self-test 'quoted non-blocking audit' did not fail as expected: {result}")

    # Case 10: YAML permits mapping keys in either order, so the same guard
    # must reject a truthy continue-on-error before the run command too.
    files = bootstrap.generate_files(next(cfg for _, cfg in configurations() if cfg["repo_type"] == "nextjs"))
    files[".github/workflows/test.yml"] = files[".github/workflows/test.yml"].replace(
        "- run: npm run audit:production",
        "- continue-on-error: true\n        run: npm run audit:production",
        1,
    )
    result = check_baseline_documents("self-test:reordered non-blocking audit", "nextjs", files)
    if not any("template production audit must be blocking" in e for e in result):
        errors.append(f"self-test 'reordered non-blocking audit' did not fail as expected: {result}")

    # Case 11: a conditional audit step can be skipped entirely, so the
    # template must reject it rather than trying to classify conditions.
    files = bootstrap.generate_files(next(cfg for _, cfg in configurations() if cfg["repo_type"] == "nextjs"))
    files[".github/workflows/test.yml"] = files[".github/workflows/test.yml"].replace(
        "- run: npm run audit:production",
        "- run: npm run audit:production\n        if: false",
        1,
    )
    result = check_baseline_documents("self-test:conditional audit", "nextjs", files)
    if not any("template production audit must not be conditional" in e for e in result):
        errors.append(f"self-test 'conditional audit' did not fail as expected: {result}")

    # Case 12: the verifier is equally blocking; it cannot be weakened by a
    # quoted truthy value or a step condition.
    files = bootstrap.generate_files(next(cfg for _, cfg in configurations() if cfg["repo_type"] == "nextjs"))
    files[".github/workflows/test.yml"] = files[".github/workflows/test.yml"].replace(
        "- run: npm run verify:baselines",
        "- run: npm run verify:baselines\n        continue-on-error: \"true\"\n        if: false",
        1,
    )
    result = check_baseline_documents("self-test:conditional verifier", "nextjs", files)
    if not any("baseline verification" in e for e in result):
        errors.append(f"self-test 'conditional verifier' did not fail as expected: {result}")

    # Case 13: job-level settings can neutralise every step together and must
    # be rejected just as firmly as a step-level bypass.
    files = bootstrap.generate_files(next(cfg for _, cfg in configurations() if cfg["repo_type"] == "nextjs"))
    files[".github/workflows/test.yml"] = files[".github/workflows/test.yml"].replace(
        "  build:\n", "  build:\n    continue-on-error: \"true\"\n", 1
    )
    result = check_baseline_documents("self-test:non-blocking build job", "nextjs", files)
    if not any("template build job must be blocking" in e for e in result):
        errors.append(f"self-test 'non-blocking build job' did not fail as expected: {result}")

    # Case 14: job-level conditions can skip every required gate.
    files = bootstrap.generate_files(next(cfg for _, cfg in configurations() if cfg["repo_type"] == "nextjs"))
    files[".github/workflows/test.yml"] = files[".github/workflows/test.yml"].replace(
        "  build:\n", "  build:\n    if: false\n", 1
    )
    result = check_baseline_documents("self-test:conditional build job", "nextjs", files)
    if not any("template build job must not be conditional" in e for e in result):
        errors.append(f"self-test 'conditional build job' did not fail as expected: {result}")

    # Case 15: the scheduled review must not quietly become a PR gate or lose
    # either API permission its Dependabot and release-pipeline checks need.
    files = bootstrap.generate_files(next(cfg for _, cfg in configurations() if cfg["repo_type"] == "nextjs"))
    files[bootstrap.NEXTJS_BASELINE_REVIEW_WORKFLOW] = files[
        bootstrap.NEXTJS_BASELINE_REVIEW_WORKFLOW
    ].replace("vulnerability-alerts: read", "security-events: read").replace(
        "actions: read", "actions: none"
    ).replace(
        "  workflow_dispatch:\n", "  workflow_dispatch:\n  pull_request:\n"
    )
    result = check_baseline_documents("self-test:invalid review workflow", "nextjs", files)
    if not any("schedule-and-dispatch only" in e for e in result) or not any(
        "vulnerability-alerts: read" in e for e in result
    ) or not any("actions: read" in e for e in result):
        errors.append(f"self-test 'invalid review workflow' did not fail as expected: {result}")

    # Case 16: scalar permissions are valid GitHub syntax, but not sufficient
    # for this workflow's explicit Dependabot permission contract.
    files = bootstrap.generate_files(next(cfg for _, cfg in configurations() if cfg["repo_type"] == "nextjs"))
    files[bootstrap.NEXTJS_BASELINE_REVIEW_WORKFLOW] = files[
        bootstrap.NEXTJS_BASELINE_REVIEW_WORKFLOW
    ].replace(
        "permissions:\n  actions: read\n  contents: read\n  vulnerability-alerts: read",
        "permissions: read-all",
    )
    result = check_baseline_documents("self-test:scalar review permissions", "nextjs", files)
    if not any("permissions must be a mapping" in e for e in result):
        errors.append(f"self-test 'scalar review permissions' did not fail as expected: {result}")

    # Case 17: Release Please controls its generated manifest's formatting, so
    # the template must not make a generated first-release update fail Prettier.
    files = bootstrap.generate_files(next(cfg for _, cfg in configurations() if cfg["repo_type"] == "nextjs"))
    files[".prettierignore"] = files[".prettierignore"].replace(
        ".release-please-manifest.json\n", "", 1
    )
    result = check_baseline_documents("self-test:manifest formatting", "nextjs", files)
    if not any("generated Release Please manifest" in e for e in result):
        errors.append(f"self-test 'manifest formatting' did not fail as expected: {result}")

    # Case 18: the ruled protection configuration must not drift back to
    # strict True — the failure mode the operator ruled against.
    payload = bootstrap.branch_protection_payload("nextjs")
    payload["required_status_checks"]["strict"] = True
    result = check_branch_protection_payload("self-test:strict drift", "nextjs", payload)
    if not any("strict: False" in e for e in result):
        errors.append(f"self-test 'strict drift' did not fail as expected: {result}")

    # Case 19: a context dropped from the payload must not pass silently.
    payload = bootstrap.branch_protection_payload("nextjs")
    payload["required_status_checks"]["contexts"] = ["validate-title"]
    result = check_branch_protection_payload("self-test:dropped context", "nextjs", payload)
    if not any("do not match" in e for e in result):
        errors.append(f"self-test 'dropped context' did not fail as expected: {result}")

    # Case 20: enforce_admins weakened to False must be caught.
    payload = bootstrap.branch_protection_payload("swift")
    payload["enforce_admins"] = False
    result = check_branch_protection_payload("self-test:admin bypass", "swift", payload)
    if not any("must enforce admins" in e for e in result):
        errors.append(f"self-test 'admin bypass' did not fail as expected: {result}")

    # Case 21: the runbook never being generated at all (as when the render
    # line is removed from generate_files) must produce a labelled missing-file
    # error, not a KeyError that aborts the run and leaves later configs
    # unchecked.
    files = bootstrap.generate_files(next(cfg for _, cfg in configurations() if cfg["repo_type"] == "nextjs"))
    files.pop(BRANCH_PROTECTION_RUNBOOK, None)
    result = check_runbook("self-test:never-generated runbook", files)
    if not any("missing docs/branch-protection-runbook.md" in e for e in result):
        errors.append(f"self-test 'never-generated runbook' did not fail as expected: {result}")

    # Case 22: a runbook that loses an operational fact must fail validation.
    # The fixture reads the key defensively — a direct index here was what
    # turned a missing runbook into the run-aborting KeyError case 21 covers.
    files = bootstrap.generate_files(next(cfg for _, cfg in configurations() if cfg["repo_type"] == "nextjs"))
    files[BRANCH_PROTECTION_RUNBOOK] = files.get(BRANCH_PROTECTION_RUNBOOK, "").replace(
        "update-branch", "update branch"
    )
    result = check_runbook("self-test:gutted runbook", files)
    if not any("update-branch" in e for e in result):
        errors.append(f"self-test 'gutted runbook' did not fail as expected: {result}")

    # Case 23: the bootstrapper's own docs/ runbook must match the template
    # byte-for-byte. A single-character drift between the two means the
    # repository documents one operational runbook while shipping another, so
    # the check must flag it rather than letting it pass silently.
    result = check_runbook_copy_matches_template(
        "self-test:drifted repo runbook",
        repo_copy=b"# branch protection and release PRs\n\nalpha\n",
        template_copy=b"# branch protection and release PRs\n\nbeta\n",
    )
    if not any("docs/branch-protection-runbook.md differs from" in e for e in result):
        errors.append(f"self-test 'drifted repo runbook' did not fail as expected: {result}")

    # Case 24: a missing repo-side copy must produce a labelled missing-file
    # error, not an abort — the same defensive-read discipline as case 21.
    result = check_runbook_copy_matches_template(
        "self-test:missing repo runbook", repo_copy=None, template_copy=b"# ...\n"
    )
    if not any("missing docs/branch-protection-runbook.md" in e for e in result):
        errors.append(f"self-test 'missing repo runbook' did not fail as expected: {result}")

    # Case 24b: the bootstrapper's own runbook may be the stamped render of the
    # template, but a stamped copy whose body drifted still fails.
    template_runbook = "# branch protection and release PRs\n\nbeta\n"
    stamped_runbook = bootstrap.stamp(template_runbook)
    result = check_runbook_copy_matches_template(
        "self-test:stamped repo runbook",
        repo_copy=stamped_runbook.encode(),
        template_copy=template_runbook.encode(),
    )
    if result:
        errors.append(f"self-test 'stamped repo runbook' unexpectedly failed: {result}")
    result = check_runbook_copy_matches_template(
        "self-test:stamped drifted runbook",
        repo_copy=stamped_runbook.replace("beta", "gamma").encode(),
        template_copy=template_runbook.encode(),
    )
    if not any("rendered through bootstrap.stamp" in e for e in result):
        errors.append(f"self-test 'stamped drifted runbook' did not fail as expected: {result}")

    # Case 25: the lint baseline must carry the review-date column and the
    # honest "Why this is accepted" header, not the old "unavoidable false
    # positive" wording that misdescribes accepted true positives.
    files = bootstrap.generate_files(next(cfg for _, cfg in configurations() if cfg["repo_type"] == "nextjs"))
    files["docs/lint-baseline.md"] = files["docs/lint-baseline.md"].replace(
        "Why this is accepted", "Why the warning is an unavoidable false positive"
    ).replace("Review date", "Removed")
    result = check_baseline_documents("self-test:stale lint header", "nextjs", files)
    if not any("Why this is accepted" in e for e in result) or not any(
        "'Review date'" in e for e in result
    ):
        errors.append(f"self-test 'stale lint header' did not fail as expected: {result}")

    # Case 26: a generated verifier that drifts back to the old single-purpose
    # lint parser (no parseLintRows) must fail validation rather than silently
    # shipping a checker that cannot validate the new review-date column.
    files = bootstrap.generate_files(next(cfg for _, cfg in configurations() if cfg["repo_type"] == "nextjs"))
    files["scripts/verify-baselines.mjs"] = files["scripts/verify-baselines.mjs"].replace(
        "parseLintRows", "parseTable"
    )
    result = check_baseline_documents("self-test:stale lint parser", "nextjs", files)
    if not any("scripts/verify-baselines.mjs is missing 'parseLintRows'" in e for e in result):
        errors.append(f"self-test 'stale lint parser' did not fail as expected: {result}")

    # Case 27: the regression that shipped. release-please-gated.yml passes
    # `full` to test.yml; a called workflow that doesn't declare it fails at
    # parse time, so the whole release pipeline never runs. This is the exact
    # shape of the Python bug — reproduced by deleting the declaration.
    files = bootstrap.generate_files(next(cfg for _, cfg in configurations() if cfg["repo_type"] == "python"))
    files[".github/workflows/test.yml"] = re.sub(
        r"    inputs:\n(?:.*\n)*?        default: true\n",
        "",
        files[".github/workflows/test.yml"],
        count=1,
    )
    result = check_reusable_workflow_inputs("self-test:undeclared input", files)
    if not any("does not declare it" in e for e in result):
        errors.append(f"self-test 'undeclared input' did not fail as expected: {result}")

    # Case 28: the mirror direction — a called workflow that starts requiring an
    # input its caller never supplies fails just as hard.
    files = bootstrap.generate_files(next(cfg for _, cfg in configurations() if cfg["repo_type"] == "python"))
    files[".github/workflows/test.yml"] = files[".github/workflows/test.yml"].replace(
        "        type: boolean\n        default: true\n",
        "        type: boolean\n        required: true\n",
        1,
    )
    files[".github/workflows/release-please.yml"] = re.sub(
        r"    with:\n      full: .*\n", "", files[".github/workflows/release-please.yml"], count=1
    )
    result = check_reusable_workflow_inputs("self-test:omitted required input", files)
    if not any("omits required input" in e for e in result):
        errors.append(f"self-test 'omitted required input' did not fail as expected: {result}")

    # Case 28b: a target that stops being callable at all. With no inputs
    # supplied, the declared/supplied comparison comes down to two empty dicts
    # and passes vacuously — so callability is asserted separately.
    files = bootstrap.generate_files(next(cfg for _, cfg in configurations() if cfg["repo_type"] == "python"))
    files[".github/workflows/test.yml"] = files[".github/workflows/test.yml"].replace(
        "on:\n  workflow_call:", "on:\n  push:", 1
    )
    files[".github/workflows/release-please.yml"] = re.sub(
        r"    with:\n      full: .*\n", "", files[".github/workflows/release-please.yml"], count=1
    )
    result = check_reusable_workflow_inputs("self-test:non-callable target", files)
    if not any("not callable" in e for e in result):
        errors.append(f"self-test 'non-callable target' did not fail as expected: {result}")

    # Case 29: a generated workflow that drops its permissions block falls
    # back to inheriting whatever its caller grants — which can change out
    # from under it later even if the caller happens to be read-only today.
    # Absence must fail regardless of the caller's current scope.
    for repo_type in ("nextjs", "python", "swift", "rust", "simple"):
        files = bootstrap.generate_files(
            next(cfg for _, cfg in configurations() if cfg["repo_type"] == repo_type)
        )
        target = ".github/workflows/test.yml" if repo_type != "simple" else ".github/workflows/pr-title-check.yml"
        files[target] = re.sub(r"\npermissions:\n(?:  \S+: \S+\n)+", "\n", files[target], count=1)
        result = check_workflow_permissions(f"self-test:unscoped token {repo_type}", files)
        if not any("declares no top-level permissions" in e for e in result):
            errors.append(
                f"self-test 'unscoped token {repo_type}' did not fail as expected: {result}"
            )

    # Case 29b: presence is not the property that matters. Broadening the test
    # suite's own scope to contents: write satisfies "declares a mapping" while
    # restoring the exact exposure #10 removed — the write-scoped token reaches
    # pip/pytest/xcodebuild again, this time by declaration rather than by
    # inheritance. Both the caller and the suite must be rejected.
    for repo_type in ("nextjs", "python", "swift", "rust"):
        files = bootstrap.generate_files(
            next(cfg for _, cfg in configurations() if cfg["repo_type"] == repo_type)
        )
        for path in (".github/workflows/ci.yml", ".github/workflows/test.yml"):
            broadened = dict(files)
            broadened[path] = files[path].replace(
                "permissions:\n  contents: read", "permissions:\n  contents: write", 1
            )
            result = check_workflow_permissions(f"self-test:broadened {repo_type} {path}", broadened)
            if not any("must grant exactly" in e for e in result):
                errors.append(
                    f"self-test 'broadened scope {repo_type} {path}' did not fail "
                    f"as expected: {result}"
                )

    # Case 29c: the exact-map guard covers workflows outside the ci/test pair
    # too — every generated workflow's scope is asserted, not just the two most
    # obviously security-sensitive ones.
    files = bootstrap.generate_files(next(cfg for _, cfg in configurations() if cfg["repo_type"] == "nextjs"))
    files[bootstrap.NEXTJS_BASELINE_REVIEW_WORKFLOW] = files[
        bootstrap.NEXTJS_BASELINE_REVIEW_WORKFLOW
    ].replace("contents: read", "contents: write", 1)
    result = check_workflow_permissions("self-test:write-scoped observer", files)
    if not any("must grant exactly" in e for e in result):
        errors.append(f"self-test 'write-scoped observer' did not fail as expected: {result}")

    # Case 29e: release-please.yml no longer needs GITHUB_TOKEN write — verified
    # empirically against a live release run (finding #11): PR creation, PR
    # merge, tag creation, and GitHub Release creation all succeeded under
    # {contents: read}, with no write-required GITHUB_TOKEN fallback needed.
    # Regressing the workflow-level grant back to write must fail exactly like
    # any other workflow drifting from its expected map.
    files = bootstrap.generate_files(next(cfg for _, cfg in configurations() if cfg["repo_type"] == "simple"))
    files[".github/workflows/release-please.yml"] = files[".github/workflows/release-please.yml"].replace(
        "permissions:\n  contents: read", "permissions:\n  contents: write\n  pull-requests: write", 1
    )
    result = check_workflow_permissions("self-test:release write regressed", files)
    if not any("must grant exactly" in e for e in result):
        errors.append(f"self-test 'release write regressed' did not fail as expected: {result}")

    # Case 29f: an extra scope alongside the correct one is still a drift from
    # the expected map, not a superset that happens to be fine — equality, not
    # containment, is what "exactly" means.
    files = bootstrap.generate_files(next(cfg for _, cfg in configurations() if cfg["repo_type"] == "python"))
    files[".github/workflows/release-please.yml"] = files[".github/workflows/release-please.yml"].replace(
        "permissions:\n  contents: read", "permissions:\n  contents: read\n  issues: write", 1
    )
    result = check_workflow_permissions("self-test:release extra scope", files)
    if not any("must grant exactly" in e for e in result):
        errors.append(f"self-test 'release extra scope' did not fail as expected: {result}")

    # Case 29g: a workflow path this check has never seen — well-formed
    # permissions and all — must still be rejected. An unmapped path is a new
    # template added without updating EXPECTED_WORKFLOW_PERMISSIONS, the same
    # "presence is not correctness" gap #10 exposed, one layer up.
    files = bootstrap.generate_files(next(cfg for _, cfg in configurations() if cfg["repo_type"] == "simple"))
    files[".github/workflows/mystery.yml"] = files[".github/workflows/pr-title-check.yml"]
    result = check_workflow_permissions("self-test:unrecognised workflow", files)
    if not any("is not a recognised generated workflow" in e for e in result):
        errors.append(f"self-test 'unrecognised workflow' did not fail as expected: {result}")

    # Case 29h: the release-please job must not acquire its own permissions
    # block. This is the exact shape a future "helpful" addition would take —
    # a job-level grant that looks locally reasonable while reopening the
    # standing write access the live-run test proved unnecessary.
    for repo_type in ("nextjs", "python", "swift", "rust", "simple"):
        files = bootstrap.generate_files(
            next(cfg for _, cfg in configurations() if cfg["repo_type"] == repo_type)
        )
        files[".github/workflows/release-please.yml"] = re.sub(
            r"(\n  release-please:\n)",
            r"\1    permissions:\n      contents: write\n",
            files[".github/workflows/release-please.yml"],
            count=1,
        )
        result = check_workflow_permissions(f"self-test:release job permissions {repo_type}", files)
        if not any("must not declare its own permissions block" in e for e in result):
            errors.append(
                f"self-test 'release job permissions {repo_type}' did not fail "
                f"as expected: {result}"
            )

    # Case 29h-null: a bare `permissions:` key with no value parses to None in
    # YAML — identical to an absent key under `.get()`. That makes it a
    # distinct way to sneak a "declaration" past the None-expected check if
    # the check only asks whether the value is not None rather than whether
    # the key exists at all. Must fail exactly like a real mapping would.
    files = bootstrap.generate_files(next(cfg for _, cfg in configurations() if cfg["repo_type"] == "simple"))
    files[".github/workflows/release-please.yml"] = re.sub(
        r"(\n  release-please:\n)",
        r"\1    permissions:\n",
        files[".github/workflows/release-please.yml"],
        count=1,
    )
    result = check_workflow_permissions("self-test:release job null permissions", files)
    if not any("must not declare its own permissions block" in e for e in result):
        errors.append(
            f"self-test 'release job null permissions' did not fail as expected: {result}"
        )

    # Case 30: `permissions: read-all` is valid GitHub syntax but not an
    # explicit per-scope grant, so it must not satisfy the check.
    files = bootstrap.generate_files(next(cfg for _, cfg in configurations() if cfg["repo_type"] == "swift"))
    files[".github/workflows/test.yml"] = files[".github/workflows/test.yml"].replace(
        "permissions:\n  contents: read", "permissions: read-all", 1
    )
    result = check_workflow_permissions("self-test:scalar permissions", files)
    if not any("must be a mapping" in e for e in result):
        errors.append(f"self-test 'scalar permissions' did not fail as expected: {result}")

    # Case 31: the other regression that shipped — generate_files() rebinding
    # its `name` local put "DEPENDENCY_NOTE" in every Swift package-name, and
    # check_syntax's parse-only JSON check could not see it.
    for _, cfg in configurations():
        files = bootstrap.generate_files(dict(cfg))
        files["release-please-config.json"] = files["release-please-config.json"].replace(
            f'"package-name": "{cfg["name"]}"', '"package-name": "DEPENDENCY_NOTE"'
        )
        result = check_release_please_config("self-test:wrong package name", cfg, files)
        if not any("package-name is 'DEPENDENCY_NOTE'" in e for e in result):
            errors.append(f"self-test 'wrong package name' did not fail as expected: {result}")
            break

    # Case 32: release-type is equally load-bearing and equally invisible to a
    # parse-only check — nextjs must stay 'node', everything else 'simple'.
    cfg = next(cfg for _, cfg in configurations() if cfg["repo_type"] == "nextjs")
    files = bootstrap.generate_files(dict(cfg))
    files["release-please-config.json"] = files["release-please-config.json"].replace(
        '"release-type": "node"', '"release-type": "simple"'
    )
    result = check_release_please_config("self-test:wrong release type", cfg, files)
    if not any("release-type is 'simple'" in e for e in result):
        errors.append(f"self-test 'wrong release type' did not fail as expected: {result}")

    # Case 33: a config that parses but has no '.' package entry must produce a
    # labelled error, not a crash — the same defensive discipline as case 21.
    cfg = next(cfg for _, cfg in configurations() if cfg["repo_type"] == "simple")
    result = check_release_please_config(
        "self-test:packageless config", cfg, {"release-please-config.json": "{}"}
    )
    if not any("no '.' package entry" in e for e in result):
        errors.append(f"self-test 'packageless config' did not fail as expected: {result}")

    # Case 34: a mutation test for the SHA-pinning gate itself — regressing one
    # pinned `uses:` back to a tag must fail, not pass silently. This is the
    # exact reintroduction bootstrap.py's sha_pinning_required: true depends on
    # the validator catching before it reaches GitHub, which rejects the run
    # outright once that repo setting is enabled.
    files = bootstrap.generate_files(
        next(cfg for _, cfg in configurations() if cfg["repo_type"] == "python")
    )
    files[".github/workflows/test.yml"] = re.sub(
        r"uses: actions/checkout@[0-9a-f]{40}(?: # v[\w.]+)?",
        "uses: actions/checkout@v7",
        files[".github/workflows/test.yml"],
        count=1,
    )
    result = check_sha_pinned_actions("self-test:tag reintroduced", files)
    if not any("not pinned to a full 40-character commit SHA" in e for e in result):
        errors.append(f"self-test 'tag reintroduced' did not fail as expected: {result}")

    # Case 35: a Swift README must retain the safe formatter invocation and
    # the configured local xcodebuild destination. Omitting the formatter's
    # final path makes swift-format wait for standard input, while omitting the
    # destination gives users a different test command than generated AGENTS.md.
    cfg = next(cfg for _, cfg in configurations() if cfg["repo_type"] == "swift")
    files = bootstrap.generate_files(dict(cfg))
    for name, old, new in (
        (
            "formatter path omitted",
            "xcrun swift-format lint --recursive --strict .",
            "xcrun swift-format lint --recursive --strict",
        ),
        (
            "destination omitted",
            f'-destination "{bootstrap._DESTINATION_EXAMPLES[cfg["destination"]]}"',
            "",
        ),
    ):
        mutated = dict(files)
        mutated[bootstrap.README] = files[bootstrap.README].replace(old, new, 1)
        result = check_readme(f"self-test:{name}", cfg, mutated)
        if not any("Swift README.md is missing" in e for e in result):
            errors.append(f"self-test '{name}' did not fail as expected: {result}")

    # Line continuations are presentation, not command semantics. Keep the
    # validator flexible enough for a one-line README command while retaining
    # the formatter, scheme, and destination checks above.
    reflowed = dict(files)
    reflowed[bootstrap.README] = (
        files[bootstrap.README]
        .replace("xcodebuild test \\\n  -scheme", "xcodebuild test -scheme", 1)
        .replace(" \\\n  -destination", " -destination", 1)
    )
    result = check_readme("self-test:reflowed Swift command", cfg, reflowed)
    if result:
        errors.append(f"self-test 'reflowed Swift command' unexpectedly failed: {result}")

    # generate_files() defaults an empty programmatic destination to iphone;
    # the README validator must use that same default rather than rejecting a
    # configuration the generator itself accepts.
    defaulted_cfg = dict(cfg, destination="")
    result = check_readme(
        "self-test:default Swift destination",
        defaulted_cfg,
        bootstrap.generate_files(defaulted_cfg),
    )
    if result:
        errors.append(f"self-test 'default Swift destination' unexpectedly failed: {result}")

    # Case 36: SampleApp is shell-safe, so its normal rendered output cannot
    # distinguish the raw display marker from the shell-quoted command marker.
    # A spaced scheme must keep quotes in xcodebuild while leaving prose clean.
    spaced_readme = bootstrap.generate_files(dict(cfg, scheme="Sample App"))[bootstrap.README]
    if "-scheme 'Sample App'" not in spaced_readme:
        errors.append("self-test 'spaced scheme' lost shell quoting in the command")
    if "| Test scheme | `Sample App` |" not in spaced_readme:
        errors.append("self-test 'spaced scheme' leaked shell quoting into prose")

    # Case 37: every release-gated generated repository type must keep manual
    # dispatch on the full suite, not only the Release Please merge commit.
    release_only = "${{ startsWith(github.event.head_commit.message, 'chore(main): release') }}"
    for repo_type in ("python", "swift", "rust"):
        cfg = next(cfg for _, cfg in configurations() if cfg["repo_type"] == repo_type)
        files = bootstrap.generate_files(dict(cfg))
        mutated = dict(files)
        mutated[".github/workflows/release-please.yml"] = files[
            ".github/workflows/release-please.yml"
        ].replace(RELEASE_FULL_SUITE_EXPRESSION, release_only, 1)
        result = check_release_full_suite_contract(
            f"self-test:{repo_type} release-only contract", repo_type, mutated
        )
        if not any("jobs.test.with.full must be" in e for e in result):
            errors.append(
                f"self-test '{repo_type} release-only contract' did not fail as expected: {result}"
            )

    # Case 38: workspace guidance fails closed — a missing per-type mechanism,
    # repo-owned content placed below `## Project specifics`, an App Router note
    # moved inside the `next dev` markers, and a dropped worktree ignore entry.
    for repo_type in AGENTS_TYPE_REQUIREMENTS:
        cfg = next(cfg for _, cfg in configurations() if cfg["repo_type"] == repo_type)
        files = bootstrap.generate_files(dict(cfg))
        result = check_workspace_guidance(f"self-test:{repo_type} workspace", repo_type, files)
        if result:
            errors.append(f"self-test '{repo_type} workspace guidance' unexpectedly failed: {result}")
        for phrase, owner in AGENTS_TYPE_REQUIREMENTS[repo_type]:
            mutated = dict(files)
            mutated[owner] = " ".join(files[owner].split()).replace(phrase, "", 1)
            result = check_workspace_guidance(f"self-test:{repo_type} mechanism", repo_type, mutated)
            if not any(repr(phrase) in e for e in result):
                errors.append(
                    f"self-test '{repo_type} missing {phrase!r}' did not fail as expected: {result}"
                )
        trailing = dict(files)
        trailing["AGENTS.md"] = files["AGENTS.md"] + "\n## Local notes\n\nText.\n"
        result = check_workspace_guidance(f"self-test:{repo_type} trailing", repo_type, trailing)
        if not any("must end with" in e for e in result):
            errors.append(f"self-test '{repo_type} trailing section' did not fail as expected: {result}")
        unignored = dict(files)
        unignored[".gitignore"] = files[".gitignore"].replace(".worktrees/\n", "", 1)
        result = check_workspace_guidance(f"self-test:{repo_type} gitignore", repo_type, unignored)
        if not any("'.worktrees/'" in e for e in result):
            errors.append(f"self-test '{repo_type} worktree ignore' did not fail as expected: {result}")

    cfg = next(cfg for _, cfg in configurations() if cfg["repo_type"] == "nextjs")
    files = bootstrap.generate_files(dict(cfg))
    phrase, owner = AGENTS_TYPE_REQUIREMENTS["nextjs"][1]
    fenced = dict(files)
    fenced[owner] = files[owner].replace(phrase, "", 1) + "\n```text\n" + phrase + "\n```\n"
    result = check_workspace_guidance("self-test:fenced phrase", "nextjs", fenced)
    if not any(repr(phrase) in e for e in result):
        errors.append(f"self-test 'fenced phrase' did not fail as expected: {result}")
    fenced_heading = dict(files)
    fenced_heading["AGENTS.md"] = files["AGENTS.md"] + "\n````md\n```\n## Example\n```\n````\n"
    result = check_workspace_guidance("self-test:fenced heading", "nextjs", fenced_heading)
    if result:
        errors.append(f"self-test 'fenced heading' unexpectedly failed: {result}")

    simple_cfg = next(cfg for _, cfg in configurations() if cfg["repo_type"] == "simple")
    simple_files = bootstrap.generate_files(dict(simple_cfg))
    worktree_skill = _skill_path("worktrees-and-scratch")
    fenced_common = dict(simple_files)
    fenced_common[worktree_skill] = "````text\n" + simple_files[worktree_skill] + "````\n"
    result = check_agents_guidance("self-test:fenced common guidance", fenced_common)
    if not any("# Worktrees, verification copies, and scratch output" in e for e in result):
        errors.append(f"self-test 'fenced common guidance' did not fail as expected: {result}")

    note_start = files["AGENTS.md"].index(APP_ROUTER_HEADING)
    note_end = files["AGENTS.md"].index("# Working in this repo")
    note = files["AGENTS.md"][note_start:note_end]
    inside = dict(files)
    inside["AGENTS.md"] = (
        files["AGENTS.md"]
        .replace(note, "", 1)
        .replace(NEXTJS_AGENT_RULES_END, note + NEXTJS_AGENT_RULES_END, 1)
    )
    result = check_workspace_guidance("self-test:app router inside markers", "nextjs", inside)
    if not any("must follow" in e for e in result):
        errors.append(f"self-test 'app router inside markers' did not fail as expected: {result}")

    cfg = next(cfg for _, cfg in configurations() if cfg["repo_type"] == "rust")
    suite = bootstrap.generate_files(dict(cfg))
    if check_rust_suite("self-test:rust suite", "rust", suite):
        errors.append("self-test 'rust suite' unexpectedly failed")
    for command in RUST_SUITE_STEPS[1:] + ("exit 1",):
        mutated = dict(suite)
        mutated[".github/workflows/test.yml"] = suite[".github/workflows/test.yml"].replace(command, "echo skipped", 1)
        if not check_rust_suite(f"self-test:rust suite without {command}", "rust", mutated):
            errors.append(f"self-test 'rust suite without {command!r}' did not fail as expected")

    files = bootstrap.generate_files(dict(cfg))
    files[".gitignore"] = files[".gitignore"].replace("/target/\n", "", 1)
    result = check_workspace_guidance("self-test:rust target ignore", "rust", files)
    if not any("'/target/'" in e for e in result):
        errors.append(f"self-test 'rust target ignore' did not fail as expected: {result}")

    errors += _structure_self_tests()
    return errors


# Number of hub/skill/stamp fixtures _structure_self_tests ran, so the success
# line shows they executed rather than being skipped.
STRUCTURE_FIXTURES_RUN = [0]


def _structure_self_tests() -> list:
    """Each hub, skill, stamp, and reviewer-agent check fails on its fixture."""
    errors = []

    def expect(name: str, result: list, needle: Optional[str]) -> None:
        STRUCTURE_FIXTURES_RUN[0] += 1
        if needle is None:
            if result:
                errors.append(f"self-test '{name}' unexpectedly failed: {result}")
        elif not any(needle in e for e in result):
            errors.append(f"self-test '{name}' did not fail as expected: {result}")

    cfg = next(cfg for _, cfg in configurations() if cfg["repo_type"] == "nextjs")
    files = bootstrap.generate_files(dict(cfg))

    # (a) budget: a hub just over the hard ceiling fails; exactly the budget passes.
    over = {HUB: "# Hub\n\n" + "x" * (HUB_CEILING_BYTES + 1 - 8) + "\n## Project specifics\n"}
    if len(_hub_generated_part(over[HUB]).encode()) != HUB_CEILING_BYTES + 1:
        errors.append("self-test 'hub over ceiling' fixture is not HUB_CEILING_BYTES + 1 bytes")
    expect("hub over ceiling", check_hub_budget("self-test:hub", over), "hub budget")
    at_budget = {HUB: "x" * (HUB_BUDGET_BYTES - 1) + "\n## Project specifics\n" + "y" * 5000}
    expect("hub at budget", check_hub_budget("self-test:hub", at_budget), None)
    # The `next dev` block is masked, so its size never counts against the hub.
    managed = {
        HUB: bootstrap.NEXTJS_RULES_BEGIN + "\n" + "z" * HUB_CEILING_BYTES + "\n"
        + bootstrap.NEXTJS_RULES_END + "\n\n## Project specifics\n"
    }
    expect("hub masks next dev block", check_hub_budget("self-test:hub", managed), None)

    # (b) bare @-imports fail; addresses, code spans, and fences do not.
    expect(
        "bare @-import",
        check_no_at_imports("self-test:at", {HUB: files[HUB] + "\n@AGENTS.md\n"}),
        "'@AGENTS.md'",
    )
    expect(
        "indented @-import",
        check_no_at_imports("self-test:at", {HUB: "See @docs/rules.md first.\n"}),
        "'@docs/rules.md'",
    )
    benign = "Mail noreply@openai.com.\nUse `@AGENTS.md` here.\n```text\n@AGENTS.md\n```\n"
    expect("benign @ tokens", check_no_at_imports("self-test:at", {HUB: benign}), None)

    # (c) a pointer row naming a skill the render lacks fails.
    dangling = dict(files)
    dangling[HUB] = files[HUB].replace(
        "| fan out to subagents | `delegation` |\n",
        "| fan out to subagents | `delegation` |\n| do magic | `no-such-skill` |\n",
        1,
    )
    expect("dangling skill pointer", check_skill_pointers("self-test:ptr", dangling), "'no-such-skill'")
    expect("no skills table", check_skill_pointers("self-test:ptr", {HUB: "# Hub\n"}), "no skills")

    # (d) frontmatter: unterminated, over-long description, name/dir mismatch,
    # bad name characters, empty description.
    def skill(path_name: str, front: str) -> dict:
        return {_skill_path(path_name): front + "\n# Body\n"}

    expect(
        "unterminated frontmatter",
        check_skill_frontmatter("self-test:fm", skill("demo", "---\nname: demo\ndescription: x")),
        "no closing '---'",
    )
    expect(
        "long description",
        check_skill_frontmatter(
            "self-test:fm",
            skill("demo", f"---\nname: demo\ndescription: {'d' * (SKILL_DESCRIPTION_MAX + 1)}\n---"),
        ),
        f"{SKILL_DESCRIPTION_MAX + 1} characters",
    )
    expect(
        "name differs from directory",
        check_skill_frontmatter("self-test:fm", skill("demo", "---\nname: other\ndescription: x\n---")),
        "must equal its directory",
    )
    expect(
        "uppercase name",
        check_skill_frontmatter("self-test:fm", skill("Demo", "---\nname: Demo\ndescription: x\n---")),
        "lowercase-hyphen",
    )
    expect(
        "empty description",
        check_skill_frontmatter("self-test:fm", skill("demo", "---\nname: demo\ndescription: ''\n---")),
        "non-empty",
    )

    # (e) two SKILL.md files declaring one name fail.
    duplicate = {
        **skill("demo", "---\nname: demo\ndescription: x\n---"),
        **skill("demo-copy", "---\nname: demo\ndescription: x\n---"),
    }
    expect("duplicate skill names", check_skill_frontmatter("self-test:fm", duplicate), "duplicate skill name 'demo'")

    # (f) a template-owned file whose body drifted from its stamp, or lost it, fails.
    owned = sorted(bootstrap.template_owned_paths(cfg))
    target = next(path for path in owned if SKILL_PATH_RE.match(path))
    edited = dict(files)
    edited[target] = files[target] + "\nA local edit.\n"
    expect("edited template-owned skill", check_template_stamps("self-test:stamp", cfg, edited), target)
    unstamped = dict(files)
    unstamped[BRANCH_PROTECTION_RUNBOOK] = bootstrap.read_stamp(files[BRANCH_PROTECTION_RUNBOOK])[1]
    expect(
        "unstamped runbook",
        check_template_stamps("self-test:stamp", cfg, unstamped),
        BRANCH_PROTECTION_RUNBOOK,
    )
    expect("rendered stamps", check_template_stamps("self-test:stamp", cfg, files), None)

    # (g) reviewer agents: a model, a write tool, a missing tools list, an
    # allowed edit, or a primary mode each fail.
    for name, path, old, new, needle in (
        ("claude model", CLAUDE_REVIEWER, "tools:", "model: opus\ntools:", "'model'"),
        ("claude write tool", CLAUDE_REVIEWER, "tools: Read,", "tools: Read, Edit,", "'Edit'"),
        ("claude without tools", CLAUDE_REVIEWER, "\ntools:", "\nx-tools:", "must list 'tools'"),
        ("opencode model", OPENCODE_REVIEWER, "mode:", "model: x/y\nmode:", "'model'"),
        ("opencode edit allowed", OPENCODE_REVIEWER, "edit: deny", "edit: allow", "permission.edit: deny"),
        ("opencode primary", OPENCODE_REVIEWER, "mode: subagent", "mode: primary", "mode: subagent"),
    ):
        mutated = dict(files)
        if old not in files[path]:
            errors.append(f"self-test '{name}' fixture anchor {old!r} is absent from {path}")
        mutated[path] = files[path].replace(old, new, 1)
        expect(name, check_reviewer_agents("self-test:agent", mutated), needle)

    # (h) a phrase moved out of its owning skill fails, naming that skill.
    phrase, owner = next(pair for pair in AGENTS_COMMON_REQUIREMENTS if SKILL_PATH_RE.match(pair[1]))
    moved = dict(files)
    moved[owner] = files[owner].replace(phrase, "", 1)
    moved[HUB] = files[HUB] + "\n" + phrase + "\n"
    expect("phrase outside its owner", check_agents_guidance("self-test:owner", moved), f"{owner} is missing")

    # The screenshot-review skill must point at docs/screenshot-review.md.
    unpointed = dict(files)
    unpointed[SCREENSHOT_SKILL] = files[SCREENSHOT_SKILL].replace(SCREENSHOT_POINTER, "the guide", 1)
    expect(
        "screenshot skill without pointer",
        check_screenshot_guidance("self-test:shot", "nextjs", unpointed),
        "missing its pointer",
    )

    # Skill links resolve from the skill's directory, hub links from the root:
    # a root-relative link in a skill fails, the same target rebased passes.
    expect("rendered links", check_markdown_links("self-test:links", files), None)
    for name, path, link, needle in (
        ("root-relative skill link", BASELINE_SKILL, "[x](docs/lint-baseline.md)", "broken local Markdown link"),
        ("rebased skill link", BASELINE_SKILL, "[x](../../../docs/lint-baseline.md)", None),
        ("broken hub link", HUB, "[x](docs/absent.md)", "broken local Markdown link"),
    ):
        linked = dict(files)
        linked[path] = files[path] + "\n" + link + "\n"
        expect(name, check_markdown_links("self-test:links", linked), needle)

    # Legacy digests: a stale recorded table fails.
    expect(
        "stale legacy digests",
        check_legacy_digests(computed={"docs/x.md": {"a"}}, recorded={"docs/x.md": {"b"}}),
        "LEGACY_TEMPLATE_DIGESTS is stale",
    )

    # Budget edges: one byte over the budget fails, and a fenced example of the
    # `## Project specifics` heading does not end the generated part early.
    over_budget = {HUB: "x" * HUB_BUDGET_BYTES + "\n## Project specifics\n"}
    if len(_hub_generated_part(over_budget[HUB]).encode()) != HUB_BUDGET_BYTES + 1:
        errors.append("self-test 'hub one byte over budget' fixture is not HUB_BUDGET_BYTES + 1 bytes")
    expect("hub one byte over budget", check_hub_budget("self-test:hub", over_budget), "hub budget")
    fenced = {HUB: "# Hub\n\n```markdown\n## Project specifics\n```\n\n" + "x" * HUB_CEILING_BYTES + "\n\n## Project specifics\n"}
    expect("fenced Project specifics example", check_hub_budget("self-test:hub", fenced), "hub budget")

    # Branch protection: review dismissal and code-owner settings are pinned.
    for key in ("dismiss_stale_reviews", "require_code_owner_reviews"):
        payload = bootstrap.branch_protection_payload("nextjs")
        payload["required_pull_request_reviews"][key] = True
        expect(f"protection with {key}", check_branch_protection_payload("self-test:bp", "nextjs", payload),
               "must not dismiss stale reviews or require code owners")

    # Workflow gates: each executable gate fails when broken.
    def gates(repo_type, path=None, change=None, text=None):
        render = bootstrap.generate_files(dict(next(c for _, c in configurations() if c["repo_type"] == repo_type)))
        if change is not None:
            workflow = yaml.safe_load(render[path])
            change(workflow)
            render[path] = yaml.safe_dump(workflow, sort_keys=False)
        if text is not None:
            render[path] = text(render[path])
        return check_workflow_gates("self-test:gates", repo_type, render)

    def step(workflow, job, predicate):
        return next(s for s in workflow["jobs"][job]["steps"] if predicate(s))

    release, test = ".github/workflows/release-please.yml", ".github/workflows/test.yml"
    for repo_type in ("nextjs", "python", "swift", "rust", "simple"):
        expect(f"gates on a clean {repo_type} render", gates(repo_type), None)
    expect("release without needs: test",
           gates("python", release, lambda w: w["jobs"]["release-please"].pop("needs")), "must need 'test'")
    expect("conditional release test job",
           gates("rust", release, lambda w: w["jobs"]["test"].update({"if": "github.event_name == 'push'"})),
           "'test' must not be conditional")
    expect("cargo test allowed to fail",
           gates("rust", test, lambda w: step(w, "test", lambda s: "cargo test" in str(s.get("run", "")))
                 .update({"continue-on-error": True})), "continue-on-error")
    expect("cargo test never runs",
           gates("rust", test, lambda w: step(w, "test", lambda s: "cargo test" in str(s.get("run", "")))
                 .update({"if": False})), "never runs")
    expect("python suite without pytest",
           gates("python", test, lambda w: w["jobs"]["test"]["steps"].remove(
               step(w, "test", lambda s: s.get("run") == "pytest"))), "suite step 'pytest' must run exactly once")
    expect("conditional python suite job",
           gates("python", test, lambda w: w["jobs"]["test"].update({"if": "github.event_name == 'push'"})),
           "job 'test' must not be conditional")
    expect("duplicated conditional cargo test",
           gates("rust", test, lambda w: w["jobs"]["test"]["steps"].extend(
               [dict(step(w, "test", lambda s: "cargo test" in str(s.get("run", ""))), **{"if": "github.event_name == 'push'"})] * 2)),
           "must run exactly once")
    expect("a whitespace string is truthy",
           gates("python", test, lambda w: step(w, "test", lambda s: str(s.get("uses", "")).startswith("actions/checkout@"))
                 .update({"if": "${{ ' ' }}"})), None)
    for falsy in ("${{false}}", "${{  false  }}", "${{ null }}", "${{ '' }}", "${{ -0 }}",
                  "${{ 0.0 }}", "${{ 0e0 }}", "${{ 0x0 }}"):
        expect(f"cargo test under {falsy}",
               gates("rust", test, lambda w, falsy=falsy: step(w, "test", lambda s: "cargo test" in str(s.get("run", "")))
                     .update({"if": falsy})), "never runs")
    expect("release job that runs after a failed test",
           gates("nextjs", release, lambda w: w["jobs"]["release-please"].update({"if": "always()"})),
           "'release-please' must not be conditional")
    expect("python job without timeout",
           gates("python", test, lambda w: w["jobs"]["test"].pop("timeout-minutes")), "timeout-minutes")
    expect("python tools unpinned",
           gates("python", test, text=lambda t: t.replace("mypy==2.4.0", "mypy")), "pinned fallback loop")
    expect("python pins only in a comment",
           gates("python", test, text=lambda t: re.sub(
               r"( *)for tool in [^\n]*\n[^\n]*\n *done\n",
               lambda m: f"{m.group(1)}# ruff==0.16.10 mypy==2.4.0 pytest==9.1.1\n{m.group(1)}pip install ruff mypy pytest\n",
               t, count=1)), "pinned fallback loop")
    expect("App token with an extra permission",
           gates("python", release, lambda w: step(w, "release-please", lambda s: str(s.get("uses", "")).startswith(
               "actions/create-github-app-token@"))["with"].update({"permission-workflows": "write"})),
           "App token must request exactly")
    expect("third-party action outside the allowlist",
           gates("python", test, lambda w: w["jobs"]["test"]["steps"].append(
               {"uses": "someone/thing@" + "0" * 40})), "does not allow")
    expect("Rust action on a non-Rust allowlist",
           gates("python", test, lambda w: w["jobs"]["test"]["steps"].append(
               {"uses": "Swatinem/rust-cache@" + "0" * 40})), "does not allow")
    expect("allowlisted name used as a prefix",
           gates("python", test, lambda w: w["jobs"]["test"]["steps"].append(
               {"uses": "amannn/action-semantic-pull-request-evil@" + "0" * 40})), "does not allow")
    expect("full e2e test run limited to Chromium",
           gates("nextjs", test, lambda w: step(w, "e2e", lambda s: s.get("run") == "npm run test:e2e")
                 .update({"if": "${{ !inputs.full }}"})), "run every project on full runs")
    expect("e2e job that no longer runs on full runs",
           gates("nextjs", test, lambda w: w["jobs"]["e2e"].update({"if": "${{ inputs.e2e }}"})),
           "e2e job must run when")
    for key in ("allow_force_pushes", "allow_deletions"):
        payload = bootstrap.branch_protection_payload("nextjs")
        payload[key] = True
        expect(f"protection with {key}", check_branch_protection_payload("self-test:bp", "nextjs", payload),
               "must set exactly")
    expect("full e2e run with Chromium only",
           gates("nextjs", test, lambda w: step(w, "e2e", lambda s: s.get("run") == "npx playwright install --with-deps")
                 .update({"run": "npx playwright install --with-deps chromium"})), "install every default browser")
    return errors


def main() -> int:
    STRUCTURE_FIXTURES_RUN[0] = 0
    all_errors = []
    all_errors += run_self_tests()
    all_errors += check_npm_script_assumptions()

    total = 0
    for label, cfg in configurations():
        total += 1
        files = bootstrap.generate_files(cfg)
        all_errors += check_syntax(label, files)
        all_errors += check_nextjs_provider_free(label, cfg["repo_type"], files)
        all_errors += check_markers(label, files)
        all_errors += check_markdown_blank_lines(label, files)
        all_errors += check_agents_guidance(label, files)
        all_errors += check_hub_budget(label, files)
        all_errors += check_no_at_imports(label, files)
        all_errors += check_skill_pointers(label, files)
        all_errors += check_skill_frontmatter(label, files)
        all_errors += check_markdown_links(label, files)
        all_errors += check_template_stamps(label, cfg, files)
        all_errors += check_reviewer_agents(label, files)
        all_errors += check_workspace_guidance(label, cfg["repo_type"], files)
        all_errors += check_screenshot_guidance(label, cfg["repo_type"], files)
        all_errors += check_workflow_job_consistency(label, cfg["repo_type"], files)
        all_errors += check_workflow_permissions(label, files)
        all_errors += check_sha_pinned_actions(label, files)
        all_errors += check_workflow_gates(label, cfg["repo_type"], files)
        all_errors += check_reusable_workflow_inputs(label, files)
        all_errors += check_release_full_suite_contract(label, cfg["repo_type"], files)
        all_errors += check_rust_suite(label, cfg["repo_type"], files)
        all_errors += check_release_please_config(label, cfg, files)
        all_errors += check_baseline_documents(label, cfg["repo_type"], files)
        all_errors += check_readme(label, cfg, files)
        all_errors += check_branch_protection_payload(label, cfg["repo_type"])
        all_errors += check_runbook(label, files)

    # The bootstrapper's own docs/ runbook must match the template it ships
    # into every generated repository. Both files live in this one repo, and
    # validate-templates is already a required check here, so a single
    # byte-equality assertion closes the drift class for the repo's own copy.
    all_errors += check_runbook_copy_matches_template(
        "bootstrapper self",
        _read_file_or_none(REPO_RUNBOOK_PATH),
        _read_file_or_none(TEMPLATE_RUNBOOK_PATH),
    )
    all_errors += check_sha_pinned_actions("bootstrapper own workflows", _own_workflow_files())
    all_errors += check_workflow_gates("bootstrapper own workflows", "simple", _own_workflow_files())
    all_errors += check_legacy_digests()
    if STRUCTURE_FIXTURES_RUN[0] == 0:
        all_errors.append("no hub/skill/stamp self-test fixture ran; run_self_tests() is not wired in")

    if all_errors:
        print(f"FAILED — {len(all_errors)} error(s) across {total} configuration(s):\n")
        for err in all_errors:
            print(f"  {err}")
        return 1

    print(
        f"OK — {total} configuration(s) validated, {STRUCTURE_FIXTURES_RUN[0]} "
        "hub/skill/stamp self-test fixture(s) behaved as expected, no errors."
    )
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--render-markdown":
        sys.exit(render_markdown(Path(sys.argv[2])))
    if sys.argv[1:] == ["--regenerate-legacy-digests"]:
        print(format_legacy_digests(bootstrap.compute_legacy_digests()), end="")
        sys.exit(0)
    if len(sys.argv) > 1:
        sys.exit(
            "usage: validate_templates.py [--render-markdown <dir> | --regenerate-legacy-digests]"
        )
    sys.exit(main())
