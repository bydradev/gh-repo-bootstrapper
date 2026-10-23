#!/usr/bin/env python3
"""
bootstrap.py — Create a standardised GitHub repository.

Supported types:
  nextjs   Full CI (lint / typecheck / tests / Playwright e2e) with optional
           PostgreSQL test service.
  python   Python CI (ruff / mypy / pytest) with gated Release Please.
  swift    Swift/Xcode CI (xcodebuild test) with gated Release Please.
  rust     Rust CI (fmt / clippy / cargo test) with gated Release Please.
  simple   Release Please only — no test workflows.

Requirements: Python 3.11+, gh CLI (authenticated), git
"""

from __future__ import annotations

import argparse
import base64
import binascii
import difflib
import errno
import getpass
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import NoReturn

# ---------------------------------------------------------------------------
# Startup version check
# ---------------------------------------------------------------------------

if sys.version_info < (3, 11):
    sys.exit(f"error: Python 3.11+ required (got {sys.version})")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


TEMPLATES_DIR = Path(__file__).parent / "templates"

# bootstrap.py deliberately does not create or patch package.json: that file
# belongs to the selected application scaffold. These are the npm scripts the
# Next.js templates assume that scaffold provides. validate_templates.py keeps
# this owned assumption set consistent with the commands those templates show.
ASSUMED_NPM_SCRIPTS = {
    "dev",
    "lint",
    "lint:fix",
    "format",
    "format:check",
    "typecheck",
    "test",
    "audit:production",
    "verify:baselines",
    "review:baselines",
    "build",
    "test:e2e",
}

# These are policy documents for Next.js repositories. The bootstrapper does
# not generate package.json, so its npm-audit and ESLint guidance must not be
# emitted for Python, Swift, or simple repositories.
NEXTJS_BASELINE_DOCUMENTS = (
    "docs/lint-baseline.md",
    "docs/advisory-baseline.md",
)

NEXTJS_ENFORCED_AUDIT_SCRIPT = "scripts/audit-production.mjs"
NEXTJS_BASELINE_SCRIPTS = (
    "scripts/audit-production.test.mjs",
    "scripts/baseline-table.mjs",
    "scripts/verify-baselines.mjs",
    "scripts/verify-baselines.test.mjs",
    "scripts/review-baselines.mjs",
    "scripts/review-baselines.test.mjs",
)
# Repository-owned scripts every release copies verbatim from templates/. A
# repository can edit them, so --adopt never overwrites an edited one, but a copy
# whose bytes equal one a release shipped (SEED_DIGESTS) was never edited, and
# --adopt brings it up to date. Each group changes together: a script, its test,
# and baseline-table.mjs, which every script imports. A stale file in several
# groups changes only when every group holding it can, so an edited script never
# meets a newer baseline-table.mjs it was not written against.
SEED_GROUPS = (
    (NEXTJS_ENFORCED_AUDIT_SCRIPT, "scripts/audit-production.test.mjs", "scripts/baseline-table.mjs"),
    ("scripts/verify-baselines.mjs", "scripts/verify-baselines.test.mjs", "scripts/baseline-table.mjs"),
    ("scripts/review-baselines.mjs", "scripts/review-baselines.test.mjs", "scripts/baseline-table.mjs"),
)
SEED_FILES = frozenset(rel for group in SEED_GROUPS for rel in group)
NEXTJS_BASELINE_REVIEW_WORKFLOW = ".github/workflows/baseline-review.yml"
SCREENSHOT_REVIEW = "docs/screenshot-review.md"
CURRENT_WORK = "docs/current-work.md"
# GitHub fills a new pull request from pull_request_template.md in .github/,
# the root or docs/, in that order; the name is not case sensitive and can
# have an extension such as .md or .txt. Templates in a PULL_REQUEST_TEMPLATE/
# folder there are used only when a link names one with the template query
# parameter ("About issue and pull request templates", "Creating a pull
# request template for your repository", "Creating a default community health
# file" and "Using query parameters to create a pull request", GitHub Docs,
# checked 2026-10-19).
PR_TEMPLATE = ".github/pull_request_template.md"
PR_TEMPLATE_FOLDERS = (".github", "", "docs")
README = "README.md"
AGENTS_SIZE_WARN_BYTES = 20_000
# Fits the longest --check state, `local-modified`, so every path lines up.
REPORT_STATUS_WIDTH = len("local-modified")
STAMP_PREFIX = "<!-- gh-repo-bootstrapper: template-owned; sha256="
_STAMP_RE = re.compile(r"^" + re.escape(STAMP_PREFIX) + r"([0-9a-f]{64}) -->$")
# Workflows are YAML, where an HTML comment is not a comment: they carry the
# stamp as a YAML comment on their first line instead.
# It also names the template the workflow came from, so a release workflow of
# one repository type is never replaced by another type's (see
# _template_file_state); the digest covers that name too.
YAML_STAMP_PREFIX = "# gh-repo-bootstrapper: template-owned; "
_YAML_STAMP_RE = re.compile(
    r"^" + re.escape(YAML_STAMP_PREFIX) + r"template=([A-Za-z0-9_.-]+\.yml); sha256=([0-9a-f]{64})$"
)
TEMPLATE_OWNED_WORKFLOWS = (
    ".github/workflows/pr-title-check.yml",
    ".github/workflows/release-please.yml",
    NEXTJS_BASELINE_REVIEW_WORKFLOW,
)
_GENERAL_SKILLS = (
    "pull-requests", "worktrees-and-scratch", "verify-external-claims",
    "fresh-eyes-review", "review-guidelines", "delegation",
)
# The skills every configuration of a type generates; template_skills() adds
# the screenshot-review skill when the configuration asks for it. A skill that
# some configurations generate and others do not is configuration-specific:
# --check reports a stamped copy of one that this configuration does not
# generate as `(--type)`, and --adopt refuses. Before removing a skill from one
# type while keeping it in another, plan how existing repositories of the
# first type drop their stamped copy, or adopt will refuse.
# Every skill has a row in the hub's skills table: the general skills in
# templates/AGENTS.md, the rest in _TYPE_SKILL_ROWS and _SCREENSHOT_SKILL_ROW.
TEMPLATE_SKILLS: dict[str, tuple[str, ...]] = {
    "simple": _GENERAL_SKILLS,
    "python": _GENERAL_SKILLS + ("local-validation-python",),
    "rust": _GENERAL_SKILLS + ("local-validation-rust",),
    "swift": _GENERAL_SKILLS + ("local-validation-swift",),
    "nextjs": _GENERAL_SKILLS + (
        "local-validation-nextjs", "baseline-process", "public-site-indexing",
    ),
}
# The screenshot-review skill and docs/screenshot-review.md are generated only
# for these types, and only with --screenshots (cfg["screenshots"]). --check
# and --adopt also turn it on for a repository of these types that already has
# either file, so its stamped copies are updated rather than deleted.
SCREENSHOT_REVIEW_SKILL = "screenshot-review"
SCREENSHOT_TYPES = ("nextjs", "swift")
SCREENSHOT_FILES = (f".agents/skills/{SCREENSHOT_REVIEW_SKILL}/SKILL.md", SCREENSHOT_REVIEW)
SCREENSHOTS_QUESTION = "Add the screenshot-review skill and doc (for a screenshot capture lane)?"
SCREENSHOTS_IGNORED = "warning: --screenshots is only used with --type nextjs or swift; ignoring"
_TEMPLATE_AGENTS = {
    ".claude/agents/fresh-eyes-reviewer.md": "agents/claude-fresh-eyes-reviewer.md",
    ".opencode/agents/fresh-eyes-reviewer.md": "agents/opencode-fresh-eyes-reviewer.md",
}


def screenshot_review(cfg) -> bool:
    """True when this configuration generates the screenshot-review skill and doc."""
    return cfg["repo_type"] in SCREENSHOT_TYPES and bool(cfg.get("screenshots"))


def template_skills(cfg) -> tuple[str, ...]:
    """The template skills this configuration generates."""
    names = TEMPLATE_SKILLS[cfg["repo_type"]]
    return names + (SCREENSHOT_REVIEW_SKILL,) if screenshot_review(cfg) else names


def _skill_sets() -> list[set[str]]:
    """The template skill set of every configuration, with and without --screenshots."""
    return [
        set(template_skills({"repo_type": repo_type, "screenshots": screenshots}))
        for repo_type in TEMPLATE_SKILLS for screenshots in (False, True)
    ]


def template_owned_paths(cfg) -> list[str]:
    """The complete template-owned manifest for this configuration."""
    paths = [f".agents/skills/{name}/SKILL.md" for name in template_skills(cfg)]
    paths += list(_TEMPLATE_AGENTS) + ["docs/branch-protection-runbook.md"]
    if screenshot_review(cfg):
        paths.append(SCREENSHOT_REVIEW)
    paths += [".github/workflows/pr-title-check.yml", ".github/workflows/release-please.yml"]
    if cfg["repo_type"] == "nextjs":
        paths.append(NEXTJS_BASELINE_REVIEW_WORKFLOW)
    return paths


def _skill_mirrors(names) -> dict[str, str]:
    return {f".claude/skills/{name}": f"../../.agents/skills/{name}" for name in names}


def generate_links(cfg) -> dict[str, str]:
    """Claude's relative directory mirrors of the shared skills."""
    return _skill_mirrors(template_skills(cfg))


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_yaml(rel: str) -> bool:
    return rel.endswith((".yml", ".yaml"))


def _find_stamp(text: str, is_yaml: bool = False) -> tuple[int, str] | None:
    """(line index, digest) of the file's single stamp line, or None.

    The file type picks the form: a workflow's stamp is a YAML comment and
    must be line 1 (after any BOM); a Markdown stamp is an HTML comment on
    exactly one line. The other form is ordinary content.
    """
    lines = text.splitlines(keepends=True)
    if is_yaml:
        if not lines:
            return None
        match = _YAML_STAMP_RE.fullmatch(lines[0].lstrip("\ufeff").rstrip("\r\n"))
        later = any(line.lstrip().startswith(YAML_STAMP_PREFIX) for line in lines[1:])
        return (0, match.group(2)) if match and not later else None
    stamps = []
    for i, line in enumerate(lines):
        match = _STAMP_RE.fullmatch(line.rstrip("\r\n"))
        if match:
            stamps.append((i, match.group(1)))
    return stamps[0] if len(stamps) == 1 else None


def stamp_template(text: str) -> str | None:
    """The template a stamped workflow names, or None when it has no stamp."""
    if _find_stamp(text, True) is None:
        return None
    return _YAML_STAMP_RE.fullmatch(text.splitlines()[0].lstrip("\ufeff").rstrip("\r")).group(1)


def _yaml_stamp_digest(template: str, body: str) -> str:
    """A workflow stamp's digest: its template name and its body without pins."""
    return _digest(f"template={template}\n" + _unpinned(body))


def has_stamp_text(text: str, is_yaml: bool = False) -> bool:
    """Whether this file type's stamp text appears at all, valid or not."""
    return (YAML_STAMP_PREFIX if is_yaml else STAMP_PREFIX) in text


# A step's or job's `uses: owner/repo[/path]@<ref>`, with any trailing spaces
# or whitespace-separated printable-ASCII comment: the part Dependabot rewrites. Only plain
# characters are allowed, so a tolerated line can never open a quoted scalar,
# flow collection or escape that changes how later lines parse. Quoted,
# local (`./`) and `docker://` references never match and compare exactly.
_USES_RE = re.compile(
    r"(?P<lead>[ \t]*(?:-[ \t]+)?uses:[ \t]+)(?P<q>)"
    r"(?P<action>[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9_./-]+)@(?P<ref>[A-Za-z0-9_./-]+)"
    r"(?P<tail>[ \t]+#[ -~]*|[ \t]*)(?P<eol>\r?\n)?"
)
# A key whose value is a block scalar (`run: |`); its content lines are text.
_BLOCK_SCALAR_RE = re.compile(r"(?P<key>[ \t]*(?:-[ \t]+)?)[^\s#][^:#]*:[ \t]*[|>][-+0-9]*[ \t]*(?:#.*)?")
# A key whose value opens a quoted scalar that continues on later lines.
_OPEN_QUOTE_RE = re.compile(r"[ \t]*(?:-[ \t]+)?[^\s#'\"][^:#]*:[ \t]*(?P<q>['\"])(?P<rest>.*)")


def _uses_lines(lines: list) -> dict:
    """{line index: match} for real `uses:` lines.

    Lines inside a block scalar (`run: |`, measured from its key, after any
    `- ` marker) or a multi-line quoted scalar are text, never actions.
    """
    found, block, quote = {}, None, None
    for i, line in enumerate(lines):
        bare = line.rstrip("\r\n")
        if quote is not None:
            # Inside a multi-line quoted scalar until a line closes it.
            if bare.replace(quote * 2, "").count(quote) % 2:
                quote = None
            continue
        if block is not None:
            if not bare.strip() or len(bare) - len(bare.lstrip(" ")) > block:
                continue
            block = None
        match = _USES_RE.fullmatch(line)
        if match:
            found[i] = match
            continue
        scalar = _BLOCK_SCALAR_RE.fullmatch(bare)
        if scalar:
            block = len(scalar["key"])
            continue
        opened = _OPEN_QUOTE_RE.fullmatch(bare)
        if opened:
            rest = opened["rest"]
            closed = rest.replace(opened["q"] * 2, "").count(opened["q"]) % 2 if opened["q"] == "'" else (
                len(re.findall(r'(?<!\\)"', rest)) % 2)
            if not closed:
                quote = opened["q"]
    return found


def _unpinned(text: str) -> str:
    """Workflow text with every action's ref, quotes and trailing comment removed.

    Generated repositories run Dependabot on their workflows, and a bump
    rewrites only these. Ignoring them keeps a bumped template-owned workflow
    valid and unchanged, while any other edit still counts.
    """
    lines = text.splitlines(keepends=True)
    for i, match in _uses_lines(lines).items():
        lines[i] = f"{match['lead']}{match['action']}@{match['eol'] or ''}"
    return "".join(lines)


def _carry_pins(expected: str, current: str) -> str:
    """expected, with each action's ref and comment taken from current.

    An action keeps the repository's own pin (Dependabot may have bumped it),
    matched by the action's occurrence order; an occurrence current lacks
    keeps the template's pin. The stamp ignores pins, so it stays valid.
    """
    pins = {}
    for match in _uses_lines(current.splitlines(keepends=True)).values():
        pins.setdefault(match["action"], []).append((match["q"], match["ref"], match["tail"]))
    lines = expected.splitlines(keepends=True)
    seen = {}
    for i, match in _uses_lines(lines).items():
        index = seen.get(match["action"], 0)
        seen[match["action"]] = index + 1
        refs = pins.get(match["action"], [])
        if index < len(refs):
            q, ref, tail = refs[index]
            lines[i] = f"{match['lead']}{q}{match['action']}@{ref}{q}{tail}{match['eol'] or ''}"
    return "".join(lines)


def _kept_pin_differences(template: str, carried: str) -> list[str]:
    """The pins _carry_pins kept that differ from the template's, in file order.

    Each is `action@ref (version; template: ref, version)`, with refs cut to 12
    characters and a version only where the pin's comment names one.
    """
    def pin(match):
        version = match["tail"].strip().lstrip("#").strip()
        return match["ref"][:12], version

    kept = []
    pairs = zip(_uses_lines(template.splitlines(keepends=True)).values(),
                _uses_lines(carried.splitlines(keepends=True)).values())
    for ours, theirs in pairs:
        if ours["ref"] == theirs["ref"]:
            continue
        (ref, version), (template_ref, template_version) = pin(theirs), pin(ours)
        theirs_text = f"{ref} ({version}; " if version else f"{ref} ("
        template_text = f"{template_ref}, {template_version}" if template_version else template_ref
        entry = f"{theirs['action']}@{theirs_text}template: {template_text})"
        if entry not in kept:
            kept.append(entry)
    return kept


def _stamp_digest(body: str, is_yaml: bool) -> str:
    """The digest a stamp records for its body; a workflow's ignores action pins."""
    return _digest(_unpinned(body) if is_yaml else body)


def read_stamp(text: str, is_yaml: bool = False) -> tuple[str | None, str]:
    """Return the single stamp digest and the exact body, without its line."""
    found = _find_stamp(text, is_yaml)
    if found is None:
        return None, text
    index, digest = found
    lines = text.splitlines(keepends=True)
    bom = "\ufeff" if is_yaml and lines[0].startswith("\ufeff") else ""
    return digest, bom + "".join(lines[:index] + lines[index + 1:])


def stamp(text: str, is_yaml: bool = False, template: str | None = None) -> str:
    """Stamp a body: a workflow on line 1 (after any BOM) as a YAML comment
    naming its `template`; Markdown after closed YAML frontmatter, or on its
    first line."""
    _, body = read_stamp(text, is_yaml)
    if is_yaml:
        if not template:
            raise ValueError("a workflow stamp names the template it came from")
        bom = "\ufeff" if body.startswith("\ufeff") else ""
        rest = body[len(bom):]
        eol = "\r\n" if rest.split("\n", 1)[0].endswith("\r") else "\n"
        return f"{bom}{YAML_STAMP_PREFIX}template={template}; sha256={_yaml_stamp_digest(template, body)}{eol}{rest}"
    offset = 0
    eol = "\n"
    bom = "\ufeff" if body.startswith("\ufeff") else ""
    opener = next((o for o in ("---\n", "---\r\n") if body.startswith(o, len(bom))), None)
    if opener:
        eol = opener[3:]
        start = len(bom) + len(opener)
        for line in body[start:].splitlines(keepends=True):
            offset += len(line)
            if line.rstrip("\r\n") == "---":
                offset += start
                if not line.endswith("\n"):
                    body = body[:offset] + eol + body[offset:]
                    offset += len(eol)
                break
        else:
            offset = 0
    marker = f"{STAMP_PREFIX}{_digest(body)} -->{eol}"
    return body[:offset] + marker + body[offset:]


def _stamp_slot(text: str) -> str:
    """The line stamp() puts a Markdown stamp on, after any BOM: the first
    after closed YAML frontmatter, or the first line. Blank lines before it
    are skipped, as Prettier adds one after frontmatter. Lines end only at
    Markdown's line endings, not at U+2028 or the other separators
    str.splitlines() honours, so none of those can start a line here."""
    lines = re.split(r"\r\n?|\n", text.removeprefix("\ufeff"))
    start = lines.index("---", 1) + 1 if lines[0] == "---" and "---" in lines[1:] else 0
    return next((line for line in lines[start:] if line.strip(" \t")), "")


def stamp_is_valid(text: str, is_yaml: bool = False) -> bool:
    found = _find_stamp(text, is_yaml)
    if found is None:
        return False
    body = read_stamp(text, is_yaml)[1]
    if is_yaml:
        return found[1] == _yaml_stamp_digest(stamp_template(text), body)
    return found[1] == _stamp_digest(body, False)


# Rebuilt by compute_legacy_digests(), from the vX.Y.Z release tags through
# LEGACY_LAST_TAG (docs) and LEGACY_WORKFLOWS_LAST_TAG (workflows).
LEGACY_TEMPLATE_DIGESTS: dict[str, frozenset[str]] = {
    ".github/workflows/baseline-review.yml#baseline-review.yml": frozenset({
        "261e0abffb824cfa585238d8a14ffdeb74a0c2f89e17d01dbc0cd170248c260e",
        "7df5be81edc1ff0d28a3481b54a8fd8aba516a62ec666c21d715f5b55d0a1bbc",
    }),
    ".github/workflows/pr-title-check.yml#pr-title-check.yml": frozenset({
        "28bb34ca5d6feb066b98781b56a7cb67aa40fc964f6188fc100a1e38def6b728",
        "f703facb0441f2c3bd809baecffe42dc9c0df17aac14be0bbc190f5a5b7cb8ca",
    }),
    ".github/workflows/release-please.yml#release-please-gated.yml": frozenset({
        "23c11b24a99c6b1d9dd76853c06a6cb5974a8f19d07b9cbbb4a492e4b1f51a78",
        "499012ae0990c745a840a06f46d849e0c3ce9a9176a064d6f9551531c6338e3d",
        "aad3b41596efc81171735804f64affc11af69333e99983b128d583ee3895e44d",
        "c2c78eb43e3f881b6ff25a89202b5081274a1f376692fb16312d1e5550473e35",
    }),
    ".github/workflows/release-please.yml#release-please-nextjs.yml": frozenset({
        "24fbd2aab77a28a06793fdef0aec5fda0d97768a5d015922b749e0e0fc4e8260",
        "31f630d6f91a1a5c664822e793aec1776a853ef5e7a634fefdfdf2650093bf8e",
        "328d8ef692fbcc15b689f1a6bf131c8d2b8f9080f5fe9a097228f2ea65584b81",
        "d4982c60960b3f91302ab5db6a54d6c29a65559b117a2d83cee8a1fd3ab77a05",
    }),
    ".github/workflows/release-please.yml#release-please-simple.yml": frozenset({
        "3db35e107cf0e0f5abe24aad85b9d90828318f3d91070c46319aa880119e9f87",
        "4c5b1f588f16c0bec5aae31379ee16e2434b8b7cea68250e6b5de64f62c70e6d",
    }),
    "docs/branch-protection-runbook.md": frozenset({
        "0393321b93da4028ce9becf74df5af865da24256dee0f035b3a31a8d378f188b",
        "1f4ce79e3a984e4e76dfdee4b3ca655c6911825eabee6a92dd5a3c76a9526dc1",
        "6639309aab33a20e8b514470e3aa34e3964d8f6bd0118ce7b8c44b940752546d",
        "6d85cc1c360e438c258a11085b387435b8eaf3667a1201fb895b0a24f6d4a494",
    }),
    "docs/screenshot-review.md": frozenset({
        "14682e234d008988775c61f361f63e55f6b6d53e05fbc97311919d01aab72948",
        "6382eea5102c54492dbe4f80f942262759dea40296ef2c629065a9efcfc9bfca",
        "705bc3cd766b0bdcbf292f1db676f209aebcd30815bf2cde9c25b354df63e884",
    }),
}


# Ownership stamps arrived in v0.6.0, so later releases ship stamped docs that
# stamp_is_valid() classifies. Only renders through this tag can appear
# unstamped, and stopping here keeps later doc edits from changing the table.
LEGACY_LAST_TAG = (0, 6, 0)
# Workflows were first stamped after v0.8.1; every release through it shipped
# them unstamped, verbatim from their template files.
LEGACY_WORKFLOWS_LAST_TAG = (0, 8, 1)
# Each name must be a current file in templates/: _template_source loads every
# listed name from today's templates to find which one renders a workflow, and
# _legacy_template_bodies also reads each name at every legacy release tag to
# rebuild what those releases shipped, and _workflow_diff_bases at every release
# tag for --check's diff. Renaming or removing one of these files is therefore a
# migration, not a one-line edit: the new name goes here; the old name moves to
# a separate list that those two read at release tags, and that _legacy_key and
# _legacy_variant also consult (with its LEGACY_TEMPLATE_DIGESTS rows) so older
# copies are still classified as stale
# rather than local-modified; and the stamp's template= provenance changes with
# it. A test fails if a name here is not a current template file.
_LEGACY_WORKFLOW_SOURCES = {
    ".github/workflows/pr-title-check.yml": ("pr-title-check.yml",),
    ".github/workflows/release-please.yml": (
        "release-please-nextjs.yml", "release-please-gated.yml", "release-please-simple.yml",
    ),
    NEXTJS_BASELINE_REVIEW_WORKFLOW: ("baseline-review.yml",),
}


# Rebuilt by compute_seed_digests() from every vX.Y.Z release tag; regenerate it
# with `python3 validate_templates.py --regenerate-seed-digests` when a change
# to a seed template makes validate_templates.py report it stale.
SEED_DIGESTS: dict[str, dict[str, str]] = {
    "scripts/audit-production.mjs": {
        "80c308a5f93fbbb8e7810a8406eef42c785cd2f182fef7dae612f0e31fc91255": "v0.5.1",
        "6a4c5ee1fb795fd3360ab6580926d8aaf8a1d21d281d9de99593544737986b24": "v0.10.0",
    },
    "scripts/audit-production.test.mjs": {
        "019c796aabe288cf71669e851eb41d34918db2bca638fcf0f03df87eba23fd7c": "v0.10.0",
        "fa8a87c34913abe4f505e81fe24cd8b4dd9e7865c3b2f9cae18fa86b9b6d50e7": "v0.11.0",
    },
    "scripts/baseline-table.mjs": {
        "98a4aaa4d016f6d0cc79868f126b35623ffe2a176fe01e69fc1cdf1855a8f67b": "v0.10.0",
    },
    "scripts/review-baselines.mjs": {
        "709adb3bb6d3d4521aa1543e19f998ad93826cfe05e6cd614f8af3d4e51da7d7": "v0.3.1",
        "d6a3f6160927b30c158c38b8a653ace4108af46cff1d8e13f473e5c67c7a5cee": "v0.5.1",
        "33d6088c3180e8eb0c8de16b962437d983c07b625f273d02999bf24bdf42cb69": "v0.5.4",
        "66a626d6ed20a9abfef999fc9e99f6db84a2e930aef1e91ccae9e270ab24c916": "v0.12.0",
        "db70d489679943de39fe20570eb06ba6ed2a6896ffe7f0b3508e3644a5d67c36": "v0.15.2",
        "1af06303f6f027ac87b82d271aa0dd30a1fba8fc118c39bba4dfca7507921509": "v0.15.3",
    },
    "scripts/review-baselines.test.mjs": {
        "3a4fbf739ae1d41d5bc67a2d0ed85f51c48de99d521585a56b841bd5da9aa501": "v0.3.1",
        "fa6ed40826f62262174bb15a1d5fc25bd4c47730a566f846948d680d56bdd520": "v0.5.1",
        "e135d16a89e3aba900555a57846cf03217b361d3e9752a1f15193eece1b877b3": "v0.10.0",
        "52db61fbe37d392383cba8f83067a7b01560b349e1e7eab030fdf40cff0051d1": "v0.11.0",
        "9ebc1e4c4b41e2fc962f9214827c13d2a92ddbf74237fb6f1cd2f5353faa8dc1": "v0.12.0",
        "a17bf394a4374ea6f27a4af7f52deabe09b02f1c72f7cdf102e87e5ff4f37270": "v0.15.2",
        "acee36a6980ae91c28bf99175d82a93cd7c95fc70c53f1cdc001bdd70396bc07": "v0.15.3",
    },
    "scripts/verify-baselines.mjs": {
        "1da3a761aae451f78d4ec7a352908d89b330532478c5aa0751d6d42bcc2f1674": "v0.5.0",
        "c33704c06347e6778a62e54268ea4afc5302bb0835f60d3113fbeab811ec74d4": "v0.5.1",
        "d65d7c4698ff6c3397e8c857f16673fbd68493e97dccbb796027d71960730261": "v0.5.2",
        "f8ae3f667230941f89f11ba998d82efef5b6e2c39254304d88930fc43e612f65": "v0.5.4",
        "d8ad8997e2bebcde6885d1d7a0c15e5d84aa2e9f0474618495647559323f6512": "v0.10.0",
        "edc493fbd287549687b8adb3e476a29e57c6795546f869560d670c575d083d87": "v0.11.0",
        "d9f52c7074254799aea314cab30ef57d3f9278b1cf916b4c928ee8c5933b1796": "v0.12.0",
    },
    "scripts/verify-baselines.test.mjs": {
        "68e499e3998138de6da611bb90a379801960862e0290fb9f27734a46856841a4": "v0.5.0",
        "1774252577e69e90534b3a6d4d7aa6c497b8c7c6292b3d325cf8cc9dba6f8b81": "v0.5.1",
        "973d9b6d9a3bcdc5cc8686ac631efbaada92c32ea4518ca7c05fa19b5daf5a31": "v0.5.2",
        "c5990fe02e2b221b74a3de26886276343d54d8e0fe4338c55e48647110777d8a": "v0.5.4",
        "3e5dda40b0885c0bcf29affb3e668e82b3cac96c7fc6183bdb04def61e1b83b5": "v0.8.0",
        "d3d262e1b1f1aeb8ff477e3701c3a3626d206d6ceb91b5b9378a0b2bd6468139": "v0.10.0",
        "fd654e9c2a3bb66946c28d388d84fda8544ba3652162533c4047abfe2752fb7f": "v0.11.0",
        "a896e264cb2810665ba2ed4e299011f35a3fb3ec3c7c695fd36ef8573edf9f3b": "v0.12.0",
    },
}


def _tag_version(tag: str) -> tuple:
    return tuple(int(part) for part in tag[1:].split("."))


def _release_tags() -> list[str] | None:
    """Every vX.Y.Z release tag, oldest first; None when git cannot list them."""
    env = _git_env()
    try:
        result = subprocess.run(
            ["git", "-C", str(TEMPLATES_DIR.parent), "tag", "--list", "v*"],
            capture_output=True, text=True, check=True, env=env,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    tags = [tag for tag in result.stdout.splitlines() if re.fullmatch(r"v\d+\.\d+\.\d+", tag)]
    return sorted(tags, key=_tag_version)


def _legacy_tags() -> list[str] | None:
    """Release tags that can have shipped unstamped template-owned files, oldest
    first; None when git cannot list them."""
    tags = _release_tags()
    if tags is None:
        return None
    last = max(LEGACY_LAST_TAG, LEGACY_WORKFLOWS_LAST_TAG)
    return [tag for tag in tags if _tag_version(tag) <= last]


def _shallow_checkout() -> bool:
    """True when the bootstrapper's own checkout is a shallow clone."""
    result = subprocess.run(
        ["git", "-C", str(TEMPLATES_DIR.parent), "rev-parse", "--is-shallow-repository"],
        capture_output=True, text=True, check=False, env=_git_env(),
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def _workflow_diff_tags() -> list[str]:
    """The release tags --check can diff an unstamped workflow against, or []
    when this copy lacks the history to name the right base.

    A shallow clone at one release holds that release's tag and none before it,
    so a fork of an earlier release would be diffed against the template's
    later changes. The tags therefore count only when they reach the unstamped
    releases (some tag through the last of them) and the checkout is not
    shallow. A deep clone missing a few old tags still works.
    """
    tags = _release_tags()
    if not tags or not _legacy_tags() or _shallow_checkout():
        return []
    return tags


class _ReleaseReads:
    """What one run reads from the bootstrapper's release tags: each template at
    each tag is read once, whichever of the legacy docs and the workflow diff
    asks first, and the notice about missing tags is printed once."""

    def __init__(self):
        self._templates = {}
        self._noticed = False

    def template(self, tag: str, name: str) -> bytes | None:
        """templates/<name> as release `tag` shipped it; None if it did not."""
        key = (tag, name)
        if key not in self._templates:
            result = subprocess.run(
                ["git", "-C", str(TEMPLATES_DIR.parent), "show", f"{tag}:templates/{name}"],
                capture_output=True, check=False, env=_git_env(),
            )
            self._templates[key] = result.stdout if result.returncode == 0 else None
        return self._templates[key]

    def notice(self) -> None:
        if not self._noticed:
            self._noticed = True
            print(
                f"notice: no usable git release tags in {TEMPLATES_DIR.parent} (none, or a shallow "
                "or incomplete clone); skipped the diff against legacy template docs or workflows",
                file=sys.stderr,
            )


def _legacy_template_bodies(reads: _ReleaseReads | None = None) -> dict[str, list[str]]:
    """Render historical owned docs; new skills and agents have no legacy copies.

    Without git or release tags (a copy without .git, a shallow clone) there
    is nothing to render: a one-line notice goes to stderr and the result is
    empty, so callers skip the legacy diff instead of failing. `reads` is the
    run's shared reader, so a template another caller read is not read again.
    """
    reads = _ReleaseReads() if reads is None else reads
    refs = _legacy_tags()
    if not refs:
        reads.notice()
        return {}
    bodies = {}
    for ref in refs:
        def source(name, ref=ref):
            body = reads.template(ref, name)
            return body.decode("utf-8") if body is not None else None

        for rel, names in _LEGACY_WORKFLOW_SOURCES.items():
            for name in names:
                body = source(name)
                if body is None:
                    continue
                # v0.1.0 spliced optional deploy jobs into the Next.js release
                # workflow at `# <<MARKER>>` lines. Its default render left them
                # empty; a deploy variant is the repository's own and stays
                # local-modified, since upgrading it would drop the deploy job.
                body = re.sub(r"(?m)^# <<[A-Z_]+>>\n", "", body)
                # Keyed by source template, so one type's release workflow is
                # never recognised as another's (see _template_file_state).
                bodies.setdefault(f"{rel}#{name}", []).append(body)
        if _tag_version(ref) > LEGACY_LAST_TAG:
            continue
        runbook = source("docs-branch-protection-runbook.md")
        if runbook is not None:
            bodies.setdefault("docs/branch-protection-runbook.md", []).append(runbook)
        common = source("docs-screenshot-review-common.md")
        if common is not None:
            for repo_type in ("nextjs", "swift"):
                fragment = source(f"docs-screenshot-review-{repo_type}.md")
                if fragment is not None:
                    bodies.setdefault(SCREENSHOT_REVIEW, []).append(
                        _compose(common, "PLATFORM_GUIDANCE", fragment)
                    )
    return {path: list(dict.fromkeys(texts)) for path, texts in bodies.items()}


# How compare_repository words a workflow that equals its diff base apart from
# the missing stamp; _adopt_file reads the base back out of it.
_UNSTAMPED_COPY = re.compile(r"identical to (\S+) apart from the missing ownership stamp")


def _workflow_diff_bases(
    rel: str, current: str, tags: list[str], reads: _ReleaseReads | None = None
) -> list[tuple[str, str, str | None]]:
    """(label, body, other) of each body --check can diff an unstamped, locally
    modified workflow against: this render without its stamp, then every
    distinct body any of `tags` shipped, labelled with the first release that
    did. `other` is the template this render uses when the body came from
    another type's template, which the label then names; otherwise None.

    The diff only. LEGACY_TEMPLATE_DIGESTS and _legacy_template_bodies stop at
    the last unstamped release, since a later release can only be recognised by
    its stamp; a fork of a later template still needs its own base here, or the
    template's later changes read as local edits. Without tags there is no
    release to name, so the result is empty and the diff is skipped; see
    _workflow_diff_tags for the tags that count. `reads` is the run's shared
    reader, so a template the legacy docs read is not read again.
    """
    if not tags:
        return []
    reads = _ReleaseReads() if reads is None else reads
    own = _template_source(rel, current)
    bases = {current: (f"current/{rel}", None)}
    for tag in tags:
        for name in sorted(_LEGACY_WORKFLOW_SOURCES[rel], key=lambda name: name != own):
            shipped = reads.template(tag, name)
            if shipped is not None:
                # The deploy markers v0.1.0 spliced in (see _legacy_template_bodies).
                body = re.sub(r"(?m)^# <<[A-Z_]+>>\n", "", shipped.decode("utf-8", errors="replace"))
                bases.setdefault(
                    body,
                    (f"legacy/{tag}/{rel}", None) if name == own else (f"legacy/{tag}/templates/{name}", own),
                )
    return [(label, body, other) for body, (label, other) in bases.items()]


def compute_legacy_digests() -> dict:
    """Rebuild the checked-in legacy table using the historical template renders."""
    return {
        path: frozenset(_stamp_digest(body, _is_yaml(path.split("#")[0])) for body in bodies)
        for path, bodies in _legacy_template_bodies().items()
    }


def _checkout_version():
    """The release this checkout's .release-please-manifest.json records, as
    _tag_version gives it, or None when the manifest names no X.Y.Z version."""
    try:
        manifest = json.loads((TEMPLATES_DIR.parent / ".release-please-manifest.json").read_text(encoding="utf-8"))
        version = manifest.get(".")
    except (OSError, ValueError, AttributeError):
        return None
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        return None
    return _tag_version("v" + version)


def compute_seed_digests() -> dict:
    """Rebuild SEED_DIGESTS from every release tag: for each seed file, the
    digest of each copy a release shipped, mapped to the newest release that
    shipped it. The current template's copy is left out, since a file equal to
    it is `same`. A tag newer than the release the checkout's manifest records,
    as in an older checkout that fetched later tags, is a later release, so it
    is left out too. Without git or release tags the result is empty."""
    tags = _release_tags()
    if not tags:
        return {}
    known = _checkout_version()
    if known is not None:
        tags = [tag for tag in tags if _tag_version(tag) <= known]
    env = _git_env()
    table = {}
    for rel in sorted(SEED_FILES):
        name = Path(rel).name
        current = _digest(_load(name))
        for tag in tags:
            result = subprocess.run(
                ["git", "-C", str(TEMPLATES_DIR.parent), "show", f"{tag}:templates/{name}"],
                capture_output=True, check=False, env=env,
            )
            if result.returncode != 0:
                continue
            try:
                digest = _digest(result.stdout.decode("utf-8"))
            except UnicodeDecodeError:
                continue
            if digest != current:
                table.setdefault(rel, {})[digest] = tag
    return table


def _die(msg: str) -> NoReturn:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def _run(cmd: list, **kwargs):
    # gh and git must act on the repository they name, not on one an inherited
    # GIT_DIR or GIT_INDEX_FILE points at; `git -C` alone does not prevent that.
    kwargs.setdefault("env", _git_env())
    subprocess.run(cmd, check=True, **kwargs)


def _run_with_retry(cmd: list, attempts: int = 3, delay: float = 3, **kwargs):
    """Like _run, but retries on failure. `gh repo create --clone` has this
    built in (GitHub's API can return a repo before it's clone-able yet);
    `gh repo create` + `gh repo clone` as two separate calls does not, so we
    replicate it here for the clone step."""
    for attempt in range(1, attempts + 1):
        try:
            _run(cmd, **kwargs)
            return
        except subprocess.CalledProcessError:
            if attempt == attempts:
                raise
            print(f"  clone failed (attempt {attempt}/{attempts}), retrying…")
            time.sleep(delay)


def _load(name: str) -> str:
    path = TEMPLATES_DIR / name
    if not path.exists():
        _die(f"template not found: {path}")
    return path.read_text(encoding="utf-8")


def _compose(template: str, marker: str, fragment: str) -> str:
    line = f"# <<{marker}>>\n"
    if line not in template:
        _die(f"marker '# <<{marker}>>' not found in template")
    return template.replace(line, fragment)


def _extract_section(text: str, name: str) -> str:
    start = f"<!-- SECTION:{name} -->\n"
    end = f"<!-- /SECTION:{name} -->\n"
    if start not in text or end not in text:
        _die(f"section '{name}' not found in delta template")
    return text.split(start, 1)[1].split(end, 1)[0]


# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------


def check_dependencies():
    if not shutil.which("gh"):
        _die("gh CLI not found — install from https://cli.github.com/")
    if not shutil.which("git"):
        _die("git not found — install git and try again")
    result = subprocess.run(["gh", "auth", "status"], capture_output=True)
    if result.returncode != 0:
        _die("not logged in to GitHub CLI — run: gh auth login")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bootstrap.py",
        description="Create a standardised GitHub repository.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Types:
              nextjs   Full CI + optional PostgreSQL tests
              python   Python CI (ruff / mypy / pytest) + gated Release Please
              swift    Swift/Xcode CI (xcodebuild test) + gated Release Please
              rust     Rust CI (fmt / clippy / cargo test) + gated Release Please
              simple   Release Please only (no tests)

            Examples:
              ./bootstrap.py
              ./bootstrap.py --name my-app --type nextjs --public
              ./bootstrap.py --name my-tool --type python --org my-org
              ./bootstrap.py --name my-app --type swift --scheme MyApp
              ./bootstrap.py --name my-app --type swift --scheme MyApp --xcodegen
              ./bootstrap.py --name my-service --type rust --private
              ./bootstrap.py --name my-app --type nextjs --postgres --dry-run
              ./bootstrap.py --name my-app --type nextjs --screenshots
              ./bootstrap.py --name my-app --type nextjs --configure-only
              ./bootstrap.py --check ../my-app --type nextjs
              ./bootstrap.py --adopt ../my-app --type nextjs
        """),
    )
    p.add_argument("--name", help="Repository name, or a relative/absolute path ending in one "
                   "(default: created in the current directory)")
    p.add_argument("--type", choices=["nextjs", "simple", "python", "swift", "rust"],
                   dest="repo_type", help="Repository type")
    p.add_argument("--org", help="GitHub org or user (default: authenticated user)")
    vis = p.add_mutually_exclusive_group()
    vis.add_argument("--private", action="store_true",
                     help="Make repository private (default)")
    vis.add_argument("--public", action="store_true",
                     help="Make repository public")
    p.add_argument("--postgres", action="store_true",
                   help="Add PostgreSQL 16 service to test workflow (nextjs only)")
    p.add_argument("--scheme",
                   help="Xcode scheme name for xcodebuild test (swift only)")
    p.add_argument("--destination", choices=["iphone", "ipad", "macos"],
                   help="Target destination for xcodebuild test (swift only, default: iphone)")
    p.add_argument("--xcodegen", action="store_true",
                   help="Generate the Xcode project from project.yml in CI (swift only)")
    p.add_argument("--screenshots", action="store_true",
                   help="Add the screenshot-review skill and docs/screenshot-review.md, for a "
                        "repository with a screenshot capture lane (nextjs and swift only)")
    p.add_argument("--configure-only", action="store_true",
                   help="Apply GitHub configuration to an existing repo (skip file generation)")
    existing = p.add_mutually_exclusive_group()
    existing.add_argument("--check", metavar="PATH",
                          help="Compare an existing local repository with the current templates "
                               "(read-only; exits 1 on drift)")
    existing.add_argument("--adopt", metavar="PATH",
                          help="Write missing template files into an existing local repository "
                               "and rebuild AGENTS.md where safe (no GitHub calls)")
    p.add_argument("--replace-generated-sections", action="store_true",
                   help="With --adopt: also replace AGENTS.md generated sections whose text "
                        "differs from the template (review the result with git diff)")
    p.add_argument("--dry-run", action="store_true",
                   help="Print files that would be created without doing anything")
    p.add_argument("--non-interactive", action="store_true",
                   help="Fail if required options are missing instead of prompting")
    return p


def parse_args():
    return build_parser().parse_args()


# ---------------------------------------------------------------------------
# Interactive helpers
# ---------------------------------------------------------------------------


def prompt(question: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        return input(f"{question}{suffix}: ").strip() or default
    except EOFError:
        _die("unexpected end of input")


def prompt_validated(question: str, validator) -> str:
    while True:
        try:
            value = input(f"{question}: ").strip()
        except EOFError:
            _die("unexpected end of input")
        error = validator(value)
        if not error:
            return value
        print(f"  {error}")


def prompt_yn(question: str, default: bool = True) -> bool:
    suffix = " [Y/n]" if default else " [y/N]"
    while True:
        try:
            raw = input(f"{question}{suffix}: ").strip().lower()
        except EOFError:
            _die("unexpected end of input")
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  Please enter y or n.")


def prompt_choice(question: str, choices: list, default: str = "") -> str:
    """Ask for one of `choices` by number; an empty answer takes `default`, if any."""
    for i, c in enumerate(choices, 1):
        print(f"  {i}. {c}")
    suffix = f" [{choices.index(default) + 1}]" if default else ""
    while True:
        try:
            raw = input(f"{question} (1-{len(choices)}){suffix}: ").strip()
        except EOFError:
            _die("unexpected end of input")
        if not raw and default:
            return default
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            pass
        print(f"  Enter a number from 1 to {len(choices)}.")


def prompt_optional(label: str) -> str:
    value = prompt(f"  {label} (press Enter to skip and configure later)")
    if not value:
        print("    (skipped)")
    return value


# GitHub issues App keys as PKCS#1 ("RSA PRIVATE KEY") PEM blocks, and PKCS#8
# ("PRIVATE KEY") is the other form the release workflow's token action reads.
# Any other private-key label, such as the OpenSSH form a password manager may
# convert the key to, is refused rather than stored as an unusable secret.
# Trailing spaces and a CR before each line break are tolerated, so a key read
# from a CRLF file through "$(cat key.pem)" is not refused.
_PEM_BEGIN_RE = re.compile(r"^-----BEGIN ((?:[A-Z0-9]+ )*PRIVATE KEY)-----[ \t\r]*$", re.MULTILINE)
_PEM_END_RE = re.compile(r"^-----END ((?:[A-Z0-9]+ )*PRIVATE KEY)-----[ \t\r]*$", re.MULTILINE)
_USABLE_KEY_LABELS = frozenset({"RSA PRIVATE KEY", "PRIVATE KEY"})
_PEM_ENCRYPTED_HEADER_RE = re.compile(r"^Proc-Type:[ \t]*4,ENCRYPTED", re.MULTILINE)
# The DER encoding of the rsaEncryption object identifier, 1.2.840.113549.1.1.1.
_RSA_ENCRYPTION_OID = bytes.fromhex("06092a864886f70d010101")


def _der_items(data: bytes) -> list[tuple[int, bytes]]:
    """Split DER bytes into (tag, content) pairs that cover them exactly.

    Raises ValueError when a length runs past the end, so key data cut short
    or with bytes missing is refused rather than read as a shorter key, and
    for any encoding DER forbids (a non-minimal length or INTEGER), which the
    release workflow's key parser refuses too.
    """
    items, pos = [], 0
    while pos < len(data):
        if pos + 2 > len(data):
            raise ValueError("truncated DER header")
        tag, length = data[pos], data[pos + 1]
        pos += 2
        if length & 0x80:
            count = length & 0x7F
            if not 0 < count <= 4 or pos + count > len(data):
                raise ValueError("bad DER length")
            length = int.from_bytes(data[pos:pos + count], "big")
            if length < 0x80 or data[pos] == 0:
                raise ValueError("non-minimal DER length")
            pos += count
        if pos + length > len(data):
            raise ValueError("DER content runs past the end")
        content = data[pos:pos + length]
        if tag == 0x02 and (not content or (len(content) > 1 and (
                (content[0] == 0x00 and content[1] < 0x80) or (content[0] == 0xFF and content[1] >= 0x80)))):
            raise ValueError("non-minimal DER INTEGER")
        items.append((tag, content))
        pos += length
    return items


def _der_sequence(data: bytes) -> list[tuple[int, bytes]]:
    """The elements of data, which must be exactly one DER SEQUENCE."""
    outer = _der_items(data)
    if len(outer) != 1 or outer[0][0] != 0x30:
        raise ValueError("not a single DER SEQUENCE")
    return _der_items(outer[0][1])


def _rsa_key_consistent(der: bytes) -> bool:
    """Whether der is a PKCS#1 RSAPrivateKey whose numbers fit together.

    A two-prime key (what GitHub issues) is nine INTEGERs: version 0, then
    n, e, d, p, q, d mod (p-1), d mod (q-1) and q^-1 mod p. Checking how they
    relate catches a corrupted byte that still decodes.
    """
    items = _der_sequence(der)
    if len(items) != 9 or any(tag != 0x02 or not content for tag, content in items):
        return False
    version, n, e, d, p, q, dp, dq, qinv = (
        int.from_bytes(content, "big", signed=True) for _tag, content in items)
    # RFC 8017 (A.1.2) puts e between 3 and n - 1; an e that is only
    # congruent to the right value still signs, but wrongly. Section 3.2
    # puts d below n; OpenSSL refuses a larger congruent d as an invalid
    # keypair.
    return (version == 0 and 3 <= e < n and 1 < d < n and min(p, q) > 1 and n == p * q
            and dp == d % (p - 1) and dq == d % (q - 1) and 0 < qinv < p and qinv * q % p == 1
            and e * d % (p - 1) == 1 and e * d % (q - 1) == 1)


def _key_body_error(label: str, body: str) -> str:
    """Return why a PEM body is not a complete RSA private key, or ""."""
    try:
        # Only the line breaks, spaces and tabs a PEM reader skips; any
        # other whitespace would pass here but fail in the release workflow.
        der = base64.b64decode(re.sub(r"[ \t\r\n]+", "", body), validate=True)
        if label == "PRIVATE KEY":
            # PKCS#8: version, AlgorithmIdentifier, then the PKCS#1 key as
            # an OCTET STRING, optionally followed by [0] attributes and a
            # [1] public key, in that order (RFC 5958, section 2).
            items = _der_sequence(der)
            # Version 1 marks a key with the public key, and only then.
            optional = [tag for tag, _content in items[3:]]
            version = b"\x01" if optional[-1:] == [0x81] else b"\x00"
            if (len(items) < 3 or items[0] != (0x02, version)
                    or items[1][0] != 0x30 or items[2][0] != 0x04
                    or optional not in ([], [0xA0], [0x81], [0xA0, 0x81])):
                raise ValueError("not a PKCS#8 PrivateKeyInfo")
            algorithm = _der_items(items[1][1])
            if not algorithm or bytes([algorithm[0][0], len(algorithm[0][1])]) + algorithm[0][1] != _RSA_ENCRYPTION_OID:
                return ("is not an RSA key; GitHub signs App tokens with RS256, so "
                        "use the .pem file GitHub generated for the App")
            # rsaEncryption parameters are NULL (RFC 8017, A.1).
            if algorithm[1:] not in ([], [(0x05, b"")]):
                raise ValueError("unexpected rsaEncryption parameters")
            # Attributes hold arbitrary ASN.1 that Node must decode in full
            # before it will load the key. GitHub never adds them, so a key
            # carrying them is refused rather than half-checked.
            if optional[:1] == [0xA0]:
                return ("carries PKCS#8 attributes, which GitHub's App keys never have; "
                        "use the .pem file GitHub generated for the App")
            der = items[2][1]
            if optional[-1:] == [0x81]:
                # [1] stands in for a BIT STRING's tag: no unused bits, then
                # the RSAPublicKey (RFC 8017, A.1.1), whose n and e must be
                # the private key's own.
                public = items[-1][1]
                if public[:1] != b"\x00" or _der_sequence(public[1:]) != _der_sequence(der)[1:3]:
                    raise ValueError("PKCS#8 public key does not match")
        if _rsa_key_consistent(der):
            return ""
    except (binascii.Error, ValueError):
        pass
    return ("is incomplete or damaged (the data between the BEGIN and END lines "
            "is not a whole RSA private key)")


def app_key_error(value: str) -> str:
    """Return why value is not a complete PEM private key, or "" when it is.

    A GitHub App private key is a multi-line PEM block. A value cut to its
    first line, as a terminal paste into a one-line prompt or a single-line
    environment variable leaves it, would be stored as a secret that only
    fails later, when Release Please first runs. So would one missing lines
    from its middle, so the key data itself is decoded and checked. The
    message never quotes the value.
    """
    begin = _PEM_BEGIN_RE.search(value)
    if not begin:
        return "is not a PEM private key (no -----BEGIN … PRIVATE KEY----- line)"
    label = begin.group(1)
    end = _PEM_END_RE.search(value, begin.end())
    if not end:
        return "is incomplete (no -----END … PRIVATE KEY----- line after the BEGIN line)"
    if end.group(1) != label:
        return "is malformed (its BEGIN and END lines name different key types)"
    body = value[begin.end():end.start()]
    if not body.strip():
        return "is incomplete (no key data between the BEGIN and END lines)"
    # PKCS#8 marks encryption in the label; a traditional OpenSSL PEM keeps
    # the plain label and adds a Proc-Type header. The release workflow's
    # token action takes no passphrase, so neither form can be used.
    if label.startswith("ENCRYPTED") or _PEM_ENCRYPTED_HEADER_RE.search(body):
        return "is encrypted; export the GitHub App key without a passphrase"
    if label not in _USABLE_KEY_LABELS:
        return (f"is in the {label} format, which the release workflow cannot read; "
                "use the .pem file GitHub generated for the App")
    return _key_body_error(label, body)


def normalize_app_key(value: str) -> str:
    """Drop a byte-order mark and turn literal \\n separators back into PEM lines.

    CI secret stores often hold a PEM key on one line with escaped newlines,
    and actions/create-github-app-token accepts that form, so the value is
    accepted here too rather than refused.
    """
    value = value.lstrip("\ufeff")
    if not _PEM_BEGIN_RE.search(value) and "\\n" in value:
        return value.replace("\\n", "\n")
    return value


def _read_hidden(question: str) -> str:
    """Read one line without echoing it when stdin is a terminal.

    getpass also discards the rest of a multi-line paste when it restores the
    terminal, so a key pasted at the prompt by mistake is neither shown nor
    read as further answers.
    """
    try:
        if sys.stdin.isatty():
            return getpass.getpass(f"{question}: ").strip()
        return input(f"{question}: ").strip()
    except EOFError:
        _die("unexpected end of input")


def prompt_app_key_file() -> str:
    """Ask for the App's .pem file and return its contents, or "" to skip.

    The key is read from a file rather than typed or pasted: a one-line
    prompt keeps only the first line of a pasted PEM block. The path is read
    without echo and nothing typed is printed back, so a key pasted here by
    mistake reaches neither the screen nor the terminal's scrollback.
    """
    while True:
        raw = _read_hidden("  RELEASE_PLEASE_APP_KEY .pem file path "
                           "(hidden; press Enter to skip and configure later)")
        if not raw:
            print("    (skipped)")
            return ""
        if raw.startswith("-----"):
            print("    that looks like key text; enter the path to the .pem file instead")
            continue
        path = Path(raw).expanduser()
        try:
            value = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"    cannot read that file ({exc.__class__.__name__})")
            continue
        error = app_key_error(value)
        if not error:
            return value
        print(f"    that file {error}")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_name(name: str) -> str:
    """Return error string or empty string if valid."""
    if not name:
        return "Repository name is required."
    if not re.match(r"^[a-z0-9][a-z0-9\-]*$", name):
        return "Must be lowercase letters, digits, and hyphens only (must start with letter or digit)."
    if len(name) > 100:
        return "Must be 100 characters or fewer."
    return ""


def validate_owner(owner: str) -> str:
    """Return error string or empty string if valid.

    The owner goes into `gh` arguments and API paths, so it must not start
    with a hyphen or contain a slash, dot, or space. Letters, digits, and
    hyphens cover GitHub user and organization names; underscores cover
    Enterprise Managed User names such as `mona-cat_octo`.
    """
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", owner):
        return "Must be letters, digits, hyphens, and underscores, starting with a letter or digit."
    return ""


def split_name_and_path(raw: str) -> tuple:
    """Split a bare name or relative/absolute path into (repo_name, local_dir)."""
    local_dir = Path(raw).expanduser()
    return local_dir.name, local_dir


def target_error(repo_dir: Path) -> str:
    """Return error string, or empty string if repo_dir can take the new clone.

    Missing folders on the way are created later, but a symbolic link that
    leads nowhere, or a file where a folder belongs, would stop that creation
    or the clone after the repository exists on GitHub, so both are refused
    here. Permissions are not checked.
    """
    try:
        for path in (repo_dir, *repo_dir.parents):
            if path.is_symlink() and not path.exists():
                return f"target directory '{repo_dir}' cannot be used: '{path}' is a link that leads nowhere"
            if path.exists():
                if path != repo_dir and not path.is_dir():
                    return f"target directory '{repo_dir}' cannot be used: '{path}' is not a directory"
                break
        if repo_dir.exists() and any(repo_dir.iterdir()):
            return f"target directory '{repo_dir}' already exists and is not empty"
    except OSError as exc:
        return f"target directory '{repo_dir}' cannot be used: {exc.strerror or exc}"
    return ""


def validate_name_or_path(raw: str) -> str:
    """Return error string or empty string if valid. `raw` may be a bare
    repo name or a relative/absolute path ending in the repo name."""
    name, _ = split_name_and_path(raw) if raw else ("", None)
    return validate_name(name)


# ---------------------------------------------------------------------------
# Config gathering
# ---------------------------------------------------------------------------


def _gh_current_user() -> str:
    try:
        r = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            capture_output=True, text=True, check=True,
        )
        return r.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def _gh_repo_is_private(full: str) -> bool:
    try:
        r = subprocess.run(
            ["gh", "api", f"repos/{full}", "--jq", ".private"],
            capture_output=True, text=True, check=True,
        )
        return r.stdout.strip() == "true"
    except subprocess.CalledProcessError:
        return True  # safe default if the lookup itself fails


def _gh_orgs() -> list:
    try:
        r = subprocess.run(["gh", "org", "list"], capture_output=True, text=True, check=True)
        return [line.strip() for line in r.stdout.splitlines() if line.strip()]
    except subprocess.CalledProcessError:
        return []


def gather_config(args) -> dict:
    ni = args.non_interactive
    dry = args.dry_run
    configure_only = args.configure_only

    # --- name ---
    # A run that creates the repository checks the target folder here, before
    # the other questions, rather than only in create_and_push after them all.
    creating = not dry and not configure_only

    def name_error(raw: str) -> str:
        return validate_name_or_path(raw) or (creating and target_error(split_name_and_path(raw)[1])) or ""

    raw_name = args.name
    if not raw_name:
        if ni:
            _die("--name is required in --non-interactive mode")
        print(
            "\nRepository name — created as a new directory in the current "
            "directory by default.\nTo create it elsewhere, enter a relative "
            "or absolute path instead (e.g. ../my-app or /Users/you/code/my-app)."
        )
        raw_name = prompt_validated("Repository name", name_error)
    else:
        err = name_error(raw_name)
        if err:
            _die(err)
    name, repo_dir = split_name_and_path(raw_name)

    # --- type ---
    repo_type = args.repo_type
    if not repo_type:
        if ni:
            _die("--type is required in --non-interactive mode")
        print("\nRepository type:")
        repo_type = prompt_choice("Select type", ["nextjs", "python", "swift", "rust", "simple"])

    # --- owner ---
    owner = args.org
    if owner and (err := validate_owner(owner)):
        _die(f"--org: {err}")
    if not owner:
        user = "" if dry else _gh_current_user()
        if ni:
            if not user:
                if not dry:
                    _die("could not determine GitHub user; pass --org")
                user = "example-org"  # dry-run touches nothing downstream
            owner = user
        else:
            owners = ([user] if user else []) + ([] if dry else _gh_orgs())
            if len(owners) == 1:
                owner = owners[0]
                print(f"\nGitHub owner: {owner}")
            elif owners:
                print("\nGitHub owner:")
                owner = prompt_choice("Select owner", owners)
            else:
                owner = prompt("GitHub org or user")
                if not owner:
                    _die("GitHub owner is required")
                if err := validate_owner(owner):
                    _die(f"GitHub owner: {err}")

    # --- visibility (looked up for --configure-only; repo already exists) ---
    if configure_only:
        if args.public or args.private:
            print("warning: --public/--private are ignored with --configure-only")
        private = True if dry else _gh_repo_is_private(f"{owner}/{name}")
    elif args.public:
        private = False
    elif args.private:
        private = True
    elif ni:
        private = True  # default
    else:
        private = not prompt_yn("\nMake repository public?", default=False)

    # --- type-specific options ---
    postgres = False
    scheme = ""
    destination = ""
    xcodegen = False
    screenshots = False

    if repo_type == "nextjs":
        postgres = args.postgres
        if args.scheme:
            print("warning: --scheme is only used with --type swift; ignoring")
        if args.destination:
            print("warning: --destination is only used with --type swift; ignoring")
        if args.xcodegen:
            print("warning: --xcodegen is only used with --type swift; ignoring")
        if not ni and not args.postgres:
            postgres = prompt_yn("Include PostgreSQL service in tests?", default=False)
        screenshots = args.screenshots
        if not ni and not args.screenshots:
            screenshots = prompt_yn(SCREENSHOTS_QUESTION, default=False)

    elif repo_type == "swift":
        if args.postgres:
            print("warning: --postgres is only used with --type nextjs; ignoring")
        scheme = args.scheme or ""
        if not scheme:
            if ni:
                _die("--scheme is required for --type swift in --non-interactive mode")
            scheme = prompt("\nXcode scheme name")
            if not scheme:
                _die("Xcode scheme name is required for --type swift")
        destination = args.destination or ""
        if not destination:
            if ni:
                destination = "iphone"
            else:
                print("\nTarget destination:")
                destination = prompt_choice("Select destination", ["iphone", "ipad", "macos"], default="iphone")
        xcodegen = args.xcodegen
        if not ni and not args.xcodegen:
            xcodegen = prompt_yn("Generate the Xcode project from project.yml?", default=False)
        screenshots = args.screenshots
        if not ni and not args.screenshots:
            screenshots = prompt_yn(SCREENSHOTS_QUESTION, default=False)

    else:  # python, rust, simple
        if args.postgres:
            print("warning: --postgres is only used with --type nextjs; ignoring")
        if args.scheme:
            print("warning: --scheme is only used with --type swift; ignoring")
        if args.destination:
            print("warning: --destination is only used with --type swift; ignoring")
        if args.xcodegen:
            print("warning: --xcodegen is only used with --type swift; ignoring")
        if args.screenshots:
            print(SCREENSHOTS_IGNORED)

    # --- GitHub variables and secrets ---
    # Non-interactive: read from environment variables.
    # Interactive: prompt the user (skipped entirely in dry-run).
    release_please_client_id = ""
    release_please_app_key = ""

    if ni:
        release_please_client_id = os.environ.get("RELEASE_PLEASE_CLIENT_ID", "")
        release_please_app_key = normalize_app_key(os.environ.get("RELEASE_PLEASE_APP_KEY", ""))
        # A dry run never stores the key, so a stale value must not stop it.
        if release_please_app_key and not dry:
            error = app_key_error(release_please_app_key)
            if error:
                _die(f"RELEASE_PLEASE_APP_KEY {error}; set it from the file, "
                     'e.g. RELEASE_PLEASE_APP_KEY="$(cat key.pem)"')
    elif not dry:
        print("\nGitHub App — Release Please:")
        release_please_client_id = prompt_optional("RELEASE_PLEASE_CLIENT_ID")
        release_please_app_key = prompt_app_key_file()

    return {
        "name": name,
        "repo_dir": repo_dir,
        "repo_type": repo_type,
        "owner": owner,
        "private": private,
        "postgres": postgres,
        "scheme": scheme,
        "destination": destination,
        "xcodegen": xcodegen,
        "screenshots": screenshots,
        "configure_only": configure_only,
        "release_please_client_id": release_please_client_id,
        "release_please_app_key": release_please_app_key,
        "dry_run": dry,
    }


# ---------------------------------------------------------------------------
# File templates — loaded from templates/ at runtime
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# File generation
# ---------------------------------------------------------------------------


def _release_please_config(name: str, repo_type: str) -> str:
    schema = "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json"
    # bump-minor-pre-major: a breaking change on a 0.x version bumps the minor,
    # not the major, so a new repository (seeded at 0.1.0) does not jump to
    # 1.0.0 on its first `feat!`, `chore!` or BREAKING CHANGE footer. Without it
    # release-please 17.6.0, the version release-please-action v5.0.0 locks,
    # proposes 1.0.0 (versioning-strategies/default.js, checked 2026-10-21).
    # This repository's own release-please-config.json sets it too.
    if repo_type == "nextjs":
        cfg = {
            "$schema": schema,
            "include-component-in-tag": False,
            "bump-minor-pre-major": True,
            "packages": {".": {"release-type": "node", "package-name": name}},
        }
    else:  # simple, python, swift, rust — all use release-type: simple
        cfg = {
            "$schema": schema,
            "include-component-in-tag": False,
            "bump-minor-pre-major": True,
            "packages": {".": {"release-type": "simple", "package-name": name}},
        }
    return json.dumps(cfg, indent=2) + "\n"


def required_status_checks(repo_type: str) -> list:
    """Required branch-protection status check contexts for a GENERATED repo.

    These describe the repositories this script generates — never an existing
    repository that merely shares a type. gh-repo-bootstrapper itself emits
    "validate-templates" from its own validate.yml and has no "test / test"
    job; existing product repos may run extra lanes the templates do not
    (a production e2e pass, a Lighthouse budget, and so on). Protecting an
    existing repo requires contexts observed from its own PR check rollups,
    not this function.

    Check names follow GitHub's "{caller job} / {reusable job}" convention
    for workflows that call a reusable test.yml via ci.yml — the caller job
    in ci.yml is always named "test"; the job names it maps to inside
    test.yml vary by repo type. Kept alongside generate_files() so the two
    stay consistent (validated two-way by validate_templates.py).
    """
    if repo_type == "nextjs":
        return ["validate-title", "test / build", "test / e2e"]
    elif repo_type in ("python", "swift", "rust"):
        return ["validate-title", "test / test"]
    else:
        return ["validate-title"]


def branch_protection_payload(repo_type: str) -> dict:
    """Branch-protection API payload for main on a generated repository.

    The policy values are the operator's item-10 rulings (2026-07-27), not
    defaults: strict False because "branch must be up to date" strands every
    open PR — release PRs worst — on every advance of main; enforce_admins
    True so the gates bind the account that does the merging; a required PR
    with zero required approvals so the no-direct-pushes convention is
    enforced without demanding self-review theatre. Contexts come from
    required_status_checks() and are asserted against the generated workflows
    two-way by validate_templates.py, which also pins every value below.
    """
    return {
        "required_status_checks": {
            "strict": False,  # ruled: up-to-date requirement strands release PRs
            "contexts": required_status_checks(repo_type),
        },
        "enforce_admins": True,  # ruled: gates apply to admins too
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": False,
            "require_code_owner_reviews": False,
            "required_approving_review_count": 0,  # PR required; no approval count
        },
        "restrictions": None,  # no push restrictions beyond the above
    }


_DESTINATION_EXAMPLES = {
    "iphone": "platform=iOS Simulator,name=iPhone 16",
    "ipad": "platform=iOS Simulator,name=iPad (10th generation)",
    "macos": "platform=macOS,arch=arm64",
}


# Type-specific rows of the hub's skills pointer table (templates/AGENTS.md).
_TYPE_SKILL_ROWS = {
    "nextjs": (
        "| run local validation | `local-validation-nextjs` |\n",
        "| touch lint or audit baselines | `baseline-process` |\n",
        "| change robots, sitemaps or indexing | `public-site-indexing` |\n",
    ),
    "swift": ("| run local validation | `local-validation-swift` |\n",),
    "rust": ("| run local validation | `local-validation-rust` |\n",),
    "python": ("| run local validation | `local-validation-python` |\n",),
}
_SCREENSHOT_SKILL_ROW = "| change screenshots or captured views | `screenshot-review` |\n"


def _screenshot_doc(repo_type: str) -> str:
    """docs/screenshot-review.md for a type in SCREENSHOT_TYPES, before its stamp."""
    return _compose(
        _load("docs-screenshot-review-common.md"),
        "PLATFORM_GUIDANCE",
        _load(f"docs-screenshot-review-{repo_type}.md"),
    )


def generate_files(cfg: dict) -> dict:
    name = cfg["name"]
    repo_type = cfg["repo_type"]
    postgres = cfg["postgres"]
    destination = cfg.get("destination") or "iphone"
    xcodegen = bool(cfg.get("xcodegen"))
    screenshots = screenshot_review(cfg)

    files = {}

    files[".github/workflows/pr-title-check.yml"] = _load("pr-title-check.yml")
    readme = _load(f"README-{repo_type}.md").replace("__REPOSITORY_NAME__", name)
    if repo_type == "python":
        readme = readme.replace("__PYTHON_VERSION__", _load(".python-version").strip())
    elif repo_type == "swift":
        readme = (
            readme.replace("__SCHEME__", cfg["scheme"])
            .replace("__SCHEME_SHELL__", shlex.quote(cfg["scheme"]))
            .replace("__DESTINATION_EXAMPLE__", _DESTINATION_EXAMPLES[destination])
        )
    files[README] = readme

    if repo_type == "nextjs":
        files[".github/workflows/release-please.yml"] = _load("release-please-nextjs.yml")
        files[".github/workflows/ci.yml"] = _load("ci.yml")
        pg = _load("test-postgres-block.yml") if postgres else ""
        files[".github/workflows/test.yml"] = _compose(
            _load("test.yml"), "POSTGRES_BLOCK", pg
        )
        files[NEXTJS_BASELINE_REVIEW_WORKFLOW] = _load("baseline-review.yml")
        files[".github/dependabot.yml"] = _load("dependabot-full.yml")
        files[".nvmrc"] = _load(".nvmrc")
        files[".npmrc"] = _load(".npmrc")
        files[".prettierrc.json"] = _load(".prettierrc.json")
        files[".prettierignore"] = _load(".prettierignore")
        files["docs/lint-baseline.md"] = _load("docs-lint-baseline.md")
        files["docs/advisory-baseline.md"] = _load("docs-advisory-baseline.md")
        files[NEXTJS_ENFORCED_AUDIT_SCRIPT] = _load("audit-production.mjs")
        for path in NEXTJS_BASELINE_SCRIPTS:
            files[path] = _load(path.removeprefix("scripts/"))
    elif repo_type == "python":
        files[".github/workflows/release-please.yml"] = _load("release-please-gated.yml")
        files[".github/workflows/ci.yml"] = _load("ci.yml")
        files[".github/workflows/test.yml"] = _load("test-python.yml")
        # Like Swift and Rust: a new Python repo has no manifest yet, and the
        # pip updater fails with "Repo must contain a requirements.txt,
        # setup.py, setup.cfg, pyproject.toml, or a Pipfile." until one exists.
        # The generated local-validation-python skill says when to add it;
        # dependabot-python.yml is the reference entry, never rendered.
        files[".github/dependabot.yml"] = _load("dependabot-actions-only.yml")
        files[".python-version"] = _load(".python-version")

    elif repo_type == "swift":
        files[".github/workflows/release-please.yml"] = _load("release-please-gated.yml")
        files[".github/workflows/ci.yml"] = _load("ci.yml")
        swift_test_template = "test-swift-xcodegen.yml" if xcodegen else "test-swift.yml"
        files[".github/workflows/test.yml"] = (
            _load(swift_test_template)
            .replace("__SCHEME_JSON__", json.dumps(cfg["scheme"]))
            .replace("__DESTINATION_KIND__", destination)
        )
        # A new Swift repo has no usable SPM manifest yet. Generating a Swift
        # Dependabot entry at this point creates a permanently failing updater.
        files[".github/dependabot.yml"] = _load("dependabot-actions-only.yml")
        files[".swift-format"] = _load(".swift-format")

    elif repo_type == "rust":
        files[".github/workflows/release-please.yml"] = _load("release-please-gated.yml")
        files[".github/workflows/ci.yml"] = _load("ci.yml")
        files[".github/workflows/test.yml"] = _load("test-rust.yml")
        # Like Swift: a new Rust repo has no Cargo.toml yet, so a cargo
        # Dependabot entry would be a permanently failing updater until one
        # exists. The generated AGENTS.md says when to add it.
        files[".github/dependabot.yml"] = _load("dependabot-actions-only.yml")

    else:  # simple
        files[".github/workflows/release-please.yml"] = _load("release-please-simple.yml")
        files[".github/dependabot.yml"] = _load("dependabot-actions-only.yml")

    if screenshots:
        files[SCREENSHOT_REVIEW] = _screenshot_doc(repo_type)

    # Every generated repo is born with the runbook for the protection applied
    # below — all types get release-please, pr-title-check and required checks.
    files["docs/branch-protection-runbook.md"] = _load("docs-branch-protection-runbook.md")
    # Repository-owned: dated status the hub sends agents to, so it stays out
    # of AGENTS.md. --adopt writes it only when missing.
    files[CURRENT_WORK] = _load("docs-current-work.md")
    # Repository-owned: asks for the user-visible line pr-title-check.yml
    # requires. --adopt writes it only when the repository has no pull
    # request template of its own.
    files[PR_TEMPLATE] = _load("pull-request-template.md")

    preamble = ""
    tooling = ""
    if repo_type == "nextjs":
        preamble = _load("AGENTS-nextjs-block.md")
        tooling = _load("AGENTS-nextjs-commands.md")
    elif repo_type == "python":
        tooling = _load("AGENTS-python-commands.md")
    elif repo_type == "rust":
        tooling = _load("AGENTS-rust-commands.md")
    elif repo_type == "swift":
        swift_tooling = _load("AGENTS-swift-commands.md")
        delta = _load(
            "AGENTS-swift-xcodegen-delta.md" if xcodegen else "AGENTS-swift-tooling-default.md"
        )
        # Not `name`: that local holds the repository name and is still needed
        # below for release-please-config.json, which silently shipped
        # "package-name": "DEPENDENCY_NOTE" on every Swift repo while this loop
        # rebound it. validate_templates.check_release_please_config asserts the
        # rendered value now.
        # The commands fragment holds only the project note and generate step;
        # the dependency note now lives in the local-validation-swift skill.
        for section in ("PROJECT_NOTE", "GENERATE_STEP"):
            swift_tooling = _compose(
                swift_tooling, f"XCODEGEN_{section}", _extract_section(delta, section)
            )
        tooling = (
            swift_tooling
            .replace("__SCHEME__", shlex.quote(cfg["scheme"]))
            .replace("__DESTINATION_EXAMPLE__", _DESTINATION_EXAMPLES[destination])
            .replace("__DESTINATION_KIND__", destination)
        )
    files["CLAUDE.md"] = _load("CLAUDE.md")
    agents = _load("AGENTS.md")
    agents = _compose(agents, "TYPE_PREAMBLE", preamble)
    agents = _compose(agents, "TYPE_TOOLING", tooling)
    skill_rows = "".join(_TYPE_SKILL_ROWS.get(repo_type, ()))
    if screenshots:
        skill_rows += _SCREENSHOT_SKILL_ROW
    agents = _compose(agents, "SKILL_ROWS_TYPE", skill_rows)
    # The screenshot privacy and pre-commit review gates stay in the hub for
    # every configuration. With the screenshot-review skill, the fragment points
    # at it for the process; without it, the fragment must not.
    agents = _compose(
        agents, "SCREENSHOT_REVIEW_REF",
        _load("AGENTS-screenshot-review-ref-skill.md" if screenshots
              else "AGENTS-screenshot-review-ref-generic.md"),
    )
    files["AGENTS.md"] = agents
    files[".gitignore"] = _load(".gitignore")
    if repo_type == "swift" and xcodegen:
        files[".gitignore"] += "\n# XcodeGen output (project.yml is the source of truth)\n*.xcodeproj/\n"
    if repo_type == "rust":
        files[".gitignore"] += "\n# Rust build output\n/target/\n"
    files["release-please-config.json"] = _release_please_config(name, repo_type)
    files[".release-please-manifest.json"] = json.dumps({".": "0.1.0"}, indent=2) + "\n"

    for skill in template_skills(cfg):
        content = _load(f"skills/{skill}/SKILL.md")
        if skill == "review-guidelines":
            # One skill name for every type, so both reviewer agents and
            # fresh-eyes-review can name it; only its stack section differs.
            content = _compose(content, "REVIEW_STACK", _load(f"review-stack-{repo_type}.md"))
        if skill == "local-validation-swift":
            content = _compose(content, "XCODEGEN_DEPENDENCY_NOTE", _extract_section(delta, "DEPENDENCY_NOTE"))
            content = (
                content.replace("__SCHEME__", shlex.quote(cfg["scheme"]))
                .replace("__SCHEME_SHELL__", shlex.quote(cfg["scheme"]))
                .replace("__DESTINATION_EXAMPLE__", _DESTINATION_EXAMPLES[destination])
                .replace("__DESTINATION_KIND__", destination)
            )
        files[f".agents/skills/{skill}/SKILL.md"] = content
    for path, source in _TEMPLATE_AGENTS.items():
        files[path] = _load(source)
    for path in template_owned_paths(cfg):
        files[path] = stamp(
            files[path], is_yaml=_is_yaml(path),
            template=_template_source(path, files[path]) if _is_yaml(path) else None,
        )
    return files


# ---------------------------------------------------------------------------
# Existing repositories — --check and --adopt
# ---------------------------------------------------------------------------

PROJECT_SPECIFICS = "## Project specifics"
NEXTJS_RULES_BEGIN = "<!-- BEGIN:nextjs-agent-rules -->"
NEXTJS_RULES_END = "<!-- END:nextjs-agent-rules -->"
# Stands in for the `next dev`-managed block while comparing: that block is
# rewritten by Next.js itself, so neither --check nor --adopt judges its text.
_NEXTJS_RULES_PLACEHOLDER = "<!-- nextjs-agent-rules: managed by next dev -->"
_SECTION_HEADING_RE = re.compile(r"^ {0,3}#{1,2}(?!#)[ \t]+\S")
_SUBHEADING_RE = re.compile(r"^ {0,3}#{3,6}(?!#)[ \t]+\S")
# Any ATX heading, an empty one included.
_ATX_HEADING_RE = re.compile(r"^ {0,3}#{1,6}(?=[ \t]|$)")
# A heading of any level behind blockquote or list markers (`> ## Ours`,
# `- ## Ours`) is a subsection too, not text inside a generated paragraph.
# Blockquote markers, and list markers only when followed by whitespace — a
# `---` underline must not be read as three list markers.
_CONTAINER_PREFIX_RE = re.compile(r"^[ \t]*(?:(?:>|(?:[-*+]|\d{1,9}[.)])(?=[ \t]))[ \t]*)*")
_CONTAINED_HEADING_RE = re.compile(r"^[ \t]*(?:(?:>|[-*+]|\d{1,9}[.)])[ \t]*)+#{1,6}(?!#)[ \t]+\S")
_SETEXT_UNDERLINE_RE = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
_FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")
# The start of a CommonMark HTML block, types 1 to 7. Its lines are raw HTML
# up to its end condition, so a fence or heading inside one is text, which a
# line scan cannot follow. The type-6 tags are CommonMark 0.31.2's plus
# `source`, which GitHub's cmark-gfm also lists (both checked 2026-10-15).
_HTML_BLOCK_TAGS = (
    "address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|"
    "dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|"
    "hr|html|iframe|legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|"
    "search|section|source|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul"
)
_HTML_BLOCK_START_RE = re.compile(
    r"^[ \t]*(?:<(?:script|pre|style|textarea)(?:[ \t>]|$)|<!--|<\?|<![A-Za-z]|<!\[CDATA\["
    r"|</?(?:" + _HTML_BLOCK_TAGS + r")(?:[ \t>]|/>|$)"
    r"|(?:<[A-Za-z][A-Za-z0-9-]*(?:[ \t]+[A-Za-z_:][\w.:-]*(?:[ \t]*=[ \t]*(?:[^ \t\"'=<>`]+|'[^']*'|\"[^\"]*\"))?)*"
    r"[ \t]*/?>|</[A-Za-z][A-Za-z0-9-]*[ \t]*>)[ \t]*$)",
    re.IGNORECASE,
)
RETIRED_SECTIONS: frozenset[str] = frozenset({
    "## Orchestration and delegation",
    "## Independent fresh-eyes review",
    "## External knowledge and capabilities",
    "## Pull requests (squash-merge + Release Please)",
    "## Worktrees, verification copies, and scratch output",
    "## Baseline process",
    "## Screenshot review",
    "## Local browser-validation constraints",
    "## Formatting",
    "## Fresh-eyes review",
    "## Recall is not evidence",
})
_TYPE_RETIRED_SECTIONS = {
    "nextjs": frozenset({"## Baseline process", "## Local browser-validation constraints"}),
    "swift": frozenset({"## Formatting"}),
}
_RETIRED_SUBHEADINGS = {
    "## Pull requests (squash-merge + Release Please)": frozenset({
        "### Standard pull requests", "### Release Please pull requests",
    }),
}


def _nextjs_rules_block(text: str) -> str:
    """The `next dev`-managed block including its markers, or "" if absent."""
    start = text.find(NEXTJS_RULES_BEGIN)
    end = text.find(NEXTJS_RULES_END)
    if start == -1 or end == -1 or end < start:
        return ""
    return text[start : end + len(NEXTJS_RULES_END)]


def _mask_nextjs_rules(text: str) -> str:
    block = _nextjs_rules_block(text)
    return text.replace(block, _NEXTJS_RULES_PLACEHOLDER, 1) if block else text


def _markdown_scan(text: str) -> tuple:
    """([(offset, line, in_fence), ...], fence_left_open) for the text.

    A fence closes only on a run of the same character at least as long as
    the one that opened it, so a ``` line inside a ```` fence stays fenced.
    The fence lines themselves count as fenced.
    """
    rows, fence, offset = [], None, 0
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip("\r\n")
        match = _FENCE_RE.match(line)
        if fence is None:
            opens = bool(match) and not (match.group(1)[0] == "`" and "`" in match.group(2))
            if opens:
                fence = (match.group(1)[0], len(match.group(1)))
            rows.append((offset, line, opens))
        else:
            if (
                match
                and match.group(1)[0] == fence[0]
                and len(match.group(1)) >= fence[1]
                and not match.group(2).strip()
            ):
                fence = None
            rows.append((offset, line, True))
        offset += len(raw)
    return rows, fence is not None


def _markdown_lines(text: str) -> list:
    return _markdown_scan(text)[0]


def _markdown_ambiguities(text: str) -> list:
    """Structure the section parser does not model, so must not rewrite around.

    Setext headings (a line underlined with === or ---), a code fence left
    open at the end of the file, and a fence line indented four or more
    columns make section boundaries uncertain. CommonMark reads such a line as
    indented code at the top level but as a fence inside a list item; the
    scan cannot tell which, so a wrong guess could hide later headings. An
    HTML block (a comment, <pre>, <details> and so on) can hold a fence line
    that the scan would open, so it is reported too.

    This is a line-level approximation, not a CommonMark block parser, and it
    errs towards reporting: a `---` thematic break after a list item or inside
    nested quotes or indented code can be flagged. A false report only makes
    --adopt refuse and ask for a manual edit; it never loses text.
    """
    rows, left_open = _markdown_scan(text)
    problems, previous = [], ""
    for _, raw_line, in_fence in rows:
        fence = _FENCE_RE.match(raw_line)
        if fence and len(raw_line.expandtabs(4)) - len(raw_line.expandtabs(4).lstrip()) >= 4:
            problems.append(f"(code fence indented four or more columns: {raw_line.strip()})")
        # Judge blockquote and list content by what follows its markers, so
        # `> Ours` over `> ----` counts as a setext heading too.
        line = _CONTAINER_PREFIX_RE.sub("", raw_line)
        if not in_fence and _HTML_BLOCK_START_RE.match(line) and line.strip() != _NEXTJS_RULES_PLACEHOLDER:
            problems.append(f"(HTML block: {line.strip()})")
        if (
            not in_fence
            and _SETEXT_UNDERLINE_RE.match(line)
            and previous.strip()
            and not _SECTION_HEADING_RE.match(previous)
            and not _SUBHEADING_RE.match(previous)
        ):
            problems.append(f"(setext heading: {previous.strip()})")
        previous = "" if in_fence else line
    if left_open:
        problems.append("(code fence left open at end of file)")
    return problems


def _agents_sections(text: str) -> tuple:
    """Split Markdown into (preamble, [(heading, section_text), ...]).

    Only level-1 and level-2 ATX headings start a section, and lines inside
    fenced code never do — a `# comment` in a shell example is not a heading.
    """
    heads = [
        (offset, line.strip())
        for offset, line, in_fence in _markdown_lines(text)
        if not in_fence and _SECTION_HEADING_RE.match(line)
    ]
    bounds = [start for start, _ in heads] + [len(text)]
    preamble = text[: bounds[0]]
    return preamble, [(title, text[start : bounds[i + 1]]) for i, (start, title) in enumerate(heads)]


def _subheadings(section: str) -> list:
    return [
        line.strip()
        for _, line, in_fence in _markdown_lines(section)
        if not in_fence and (_SUBHEADING_RE.match(line) or _CONTAINED_HEADING_RE.match(line))
    ]


# The guidance paragraphs that templates through v0.11 put at the top of
# `## Project specifics` (v0.5.0 to v0.5.5 the first, v0.6.0 on the second and
# third). The guidance now sits in a generated section above the heading, so
# --adopt --replace-generated-sections removes an unedited copy from the
# section's own text, before any subheading; an edited one, or one the
# repository filed under a subheading, is the repository's text and stays.
_RETIRED_SPECIFICS_GUIDANCE = frozenset(" ".join(paragraph.split()) for paragraph in (
    """Rules that apply only to this repository live in this section, below every
generated section: product sources of truth, prime directives, points at which
to stop and ask the operator, and boundaries specific to this codebase. Keep
them here rather than editing the generated sections above, so template
updates can be applied without overwriting them. Where a rule here narrows or
conflicts with a generated section, it governs this repository — say so
explicitly, so the difference stays visible.""",
    """Rules that apply only to this repository live in this section, below every
generated section: product sources of truth, prime directives, points at which
to stop and ask the operator, and boundaries specific to this codebase. Keep
them here rather than editing the generated sections above, so template
updates can be applied without overwriting them. Where a rule here narrows or
conflicts with a generated section, it governs this repository — say so
explicitly, so the difference stays visible. Put stop-and-ask lists and prime
directives first in this section, so they survive any truncation.""",
    """Keep this section short. Long reference material (architecture, conventions,
API notes) belongs in a repository-owned skill under `.agents/skills/` with a
name that does not start with a template skill name; narrow a template skill
here, never by editing it.""",
))
RETIRED_SPECIFICS_GUIDANCE = "(template guidance inside ## Project specifics)"


def _strip_retired_guidance(owned: str) -> str:
    """The `## Project specifics` part without unedited older-template guidance.

    A paragraph is a run of non-blank lines outside code fences. One that
    starts at column 0 on every line, as the templates wrote it, and whose
    whitespace-normalized text is a retired guidance paragraph is removed with
    the blank lines after it (or, at the end of the section, before it); an
    indented copy (under a list item, or indented code) or one with a hard line
    break is kept. Only the section's own text is searched, up to its first
    heading of any level, so a copy under a subheading is kept, and nothing is
    removed from a section with structure `_markdown_ambiguities` reports, such
    as an HTML block. Everything else, whitespace included, is kept byte for
    byte.
    """
    if _markdown_ambiguities(owned):
        # An HTML block (a comment, say) or other structure the line scan does
        # not model could hide or enclose a copy: leave the section alone.
        return owned
    lines = _markdown_lines(owned)
    keep = [True] * len(lines)

    def text_line(index: int) -> bool:
        return not lines[index][2] and bool(lines[index][1].strip())

    # Only the section's own text: stop at the first heading of any level, as
    # the templates put the guidance at the top and a subheading is the
    # repository's own structure.
    limit = next(
        (i for i in range(1, len(lines)) if not lines[i][2] and _ATX_HEADING_RE.match(lines[i][1])),
        len(lines),
    )
    index = 1  # line 0 is the heading itself
    while index < limit:
        if not text_line(index):
            index += 1
            continue
        end = index
        while end < limit and text_line(end):
            end += 1
        run = [line for _, line, _ in lines[index:end]]
        paragraph = " ".join(" ".join(run).split())
        # Leading spaces (a list item or code) and a trailing hard break are
        # edits the whitespace-normalized comparison would not see.
        edited = any(line[:1].isspace() or line.endswith("  ") for line in run)
        if paragraph in _RETIRED_SPECIFICS_GUIDANCE and not edited:
            while end < limit and not lines[end][2] and not lines[end][1].strip():
                end += 1
            start = index
            if end == len(lines):
                # Removed up to the end: also drop the blank lines before it.
                while start > 1 and (
                    not keep[start - 1] or (not lines[start - 1][2] and not lines[start - 1][1].strip())
                ):
                    start -= 1
            keep[start:end] = [False] * (end - start)
        index = end
    if all(keep):
        return owned
    offsets = [offset for offset, _, _ in lines] + [len(owned)]
    return "".join(owned[offsets[i] : offsets[i + 1]] for i in range(len(lines)) if keep[i])


# A heading indented four or more spaces is an indented code block, not a heading.
_PROJECT_SPECIFICS_RE = re.compile(r" {0,3}" + re.escape("## Project specifics") + r"[ \t]*")
NEXTJS_BLOCK_MOVED = "(`next dev` block moved from the top of the file)"
# --adopt rewrites only LF-terminated text (_decode_for_rewrite), and a leading
# byte-order mark hides the first heading; --check says so in one row each.
CARRIAGE_RETURNS = "(CRLF or CR line endings; convert to LF first)"
MIXED_LINE_ENDINGS = "(CRLF and LF line endings mixed; convert to LF first)"
STRAY_CARRIAGE_RETURN = "(carriage return inside a line; remove it first)"
BYTE_ORDER_MARK = "(byte-order mark before the first heading; remove it first)"


def _split_project_specifics(text: str) -> tuple:
    """(generated part, repository-owned part or None) of an AGENTS.md.

    Everything from the `## Project specifics` heading to the end of the file
    belongs to the repository.
    """
    for offset, line, in_fence in _markdown_lines(text):
        if not in_fence and _PROJECT_SPECIFICS_RE.fullmatch(line):
            return text[:offset], text[offset:]
    return text, None


def compare_agents(expected: str, actual: str) -> list:
    """Section-level comparison of a repository AGENTS.md with the rendered one.

    Returns (status, heading) rows. Statuses: same, differs, missing (a
    generated section the repository lacks), and local — repository text that
    --adopt would otherwise overwrite: a section, or a level-3+ subsection
    inside a generated section, outside `## Project specifics`, or structure
    the parser does not model. The `next dev` block and everything from
    `## Project specifics` on are repository-owned and never compared, except
    that unedited guidance an older template put there is reported `retired`.

    A leading byte-order mark is stripped before the comparison and reported
    as one `local` row, since it would otherwise hide the first heading.
    """
    bom = actual.startswith("\ufeff")
    actual = actual.removeprefix("\ufeff")
    exp_generated, _ = _split_project_specifics(_mask_nextjs_rules(expected))
    act_generated, act_owned = _split_project_specifics(_mask_nextjs_rules(actual))
    exp_pre, exp_sections = _agents_sections(exp_generated)
    act_pre, act_sections = _agents_sections(act_generated)
    actual_by_heading = {}
    for heading, body in act_sections:
        actual_by_heading.setdefault(heading, []).append(body)
    rows = [("local", problem) for problem in _markdown_ambiguities(act_generated)]
    if act_pre.strip() and act_pre.strip() != exp_pre.strip():
        rows.append(("local", "(text before the first heading)"))
    elif _NEXTJS_RULES_PLACEHOLDER in exp_pre and _NEXTJS_RULES_PLACEHOLDER not in act_pre:
        # A rebuild puts the block back at the top while keeping the section it
        # was moved into, so a moved block would end up in the file twice.
        if _nextjs_rules_block(actual):
            rows.append(("local", NEXTJS_BLOCK_MOVED))
        else:
            rows.append(("missing", "(`next dev` block)"))
    fenced = {line.strip() for _, line, in_fence in _markdown_lines(act_generated) if in_fence}
    for heading, body in exp_sections:
        found = actual_by_heading.get(heading)
        if not found and heading in fenced:
            # The heading is there but the scan placed it inside code, so its
            # section's text would not be compared and a rebuild could drop it.
            rows.append(("local", f"(generated heading read as code: {heading})"))
        elif not found:
            rows.append(("missing", heading))
        elif len(found) == 1 and found[0].strip() == body.strip():
            rows.append(("same", heading))
        else:
            rows.append(("differs", heading))
            if len(found) > 1:
                # A rebuild keeps one copy of the section, so the text written
                # under the other copies would be dropped.
                rows.append(("local", f"(duplicate generated heading: {heading})"))
            known = set(_subheadings(body))
            rows += [
                ("local", f"{heading} › {sub}")
                for found_body in found
                for sub in _subheadings(found_body)
                if sub not in known
            ]
    expected_headings = {heading for heading, _ in exp_sections}
    retired_headings = RETIRED_SECTIONS.difference(*_TYPE_RETIRED_SECTIONS.values())
    for repo_type, headings in _TYPE_RETIRED_SECTIONS.items():
        if f"`local-validation-{repo_type}`" in exp_generated:
            retired_headings |= headings
    present = [heading for heading, _ in exp_sections if heading in actual_by_heading]
    seen = []
    for heading, _ in act_sections:
        if heading in expected_headings and heading not in seen:
            seen.append(heading)
    if seen != present:
        rows.append(("differs", "(order of generated sections)"))
    for heading, body in act_sections:
        if heading in expected_headings:
            continue
        if heading in retired_headings:
            rows.append(("retired", heading))
            rows += [
                ("local", f"{heading} › {sub}")
                for sub in _subheadings(body)
                if sub not in _RETIRED_SUBHEADINGS.get(heading, ())
            ]
        else:
            rows.append(("local", heading))
    if act_owned is None:
        rows.append(("missing", PROJECT_SPECIFICS))
    elif _strip_retired_guidance(act_owned) != act_owned:
        rows.append(("retired", RETIRED_SPECIFICS_GUIDANCE))
    if _nextjs_rules_block(expected) and not _nextjs_rules_block(actual):
        rows.append(("missing", NEXTJS_RULES_BEGIN))
    if bom:
        rows.insert(0, ("local", BYTE_ORDER_MARK))
    return rows


def rebuild_agents(expected: str, actual: str, replace_generated: bool = False) -> str:
    """The rendered AGENTS.md with the repository's own parts carried over.

    Keeps the repository's `## Project specifics` section (and everything after
    it), less any unedited guidance from an older template, and its `next
    dev`-managed block. Callers must first confirm that compare_agents()
    reports no `local` rows, or repository text is lost.
    """
    rows = compare_agents(expected, actual)
    retired = [heading for status, heading in rows if status == "retired"]
    local = [heading for status, heading in rows if status == "local"]
    if retired and (local or not replace_generated):
        raise ValueError("cannot drop retired sections: " + "; ".join(local or retired))
    generated, template_owned = _split_project_specifics(expected)
    _, owned = _split_project_specifics(actual)
    if owned is not None:
        owned = _strip_retired_guidance(owned)
    repo_block, template_block = _nextjs_rules_block(actual), _nextjs_rules_block(expected)
    if repo_block and template_block:
        generated = generated.replace(template_block, repo_block, 1)
    return generated + (owned if owned is not None else template_owned)


def _missing_lines(expected: str, actual: str) -> list:
    present = {line.strip() for line in actual.splitlines()}
    return [
        line for line in expected.splitlines()
        if line.strip() and not line.startswith("#") and line.strip() not in present
    ]


def _is_symlink(path: Path) -> bool:
    """Whether `path` is a symlink; an error other than "not there" is raised.

    Path.is_symlink() raises on a permission error up to Python 3.13 but
    returns False from 3.14, which would pass a path inside a directory that
    cannot be searched off as absent.
    """
    try:
        return stat.S_ISLNK(os.lstat(path).st_mode)
    except (FileNotFoundError, NotADirectoryError):
        return False


def _symlink_in_path(repo_dir: Path, rel: str, links: dict = None) -> bool:
    """Refuse symlinks except a declared mirror at the final component.

    Raises OSError, naming the directory, when one on the way cannot be
    searched: callers report the path as unreadable rather than guess.
    """
    current = repo_dir
    parts = Path(rel).parts
    for index, part in enumerate(parts):
        current = current / part
        try:
            linked = _is_symlink(current)
        except OSError as exc:
            # Every earlier component answered, so the parent is the one at fault.
            where = current.parent.relative_to(repo_dir).as_posix()
            raise OSError(exc.errno, f"{exc.strerror or type(exc).__name__}: {where}") from exc
        if linked:
            if links and rel in links and index == len(parts) - 1:
                continue
            return True
    return False


def _links_for_files(files: dict) -> dict[str, str]:
    """Infer mirrors for callers that only have the generated files dict."""
    return _skill_mirrors(
        Path(path).parent.name for path in files
        if path.startswith(".agents/skills/") and path.endswith("/SKILL.md")
    )


def _git_ignored(repo_dir: Path, rel: str) -> bool:
    env = _git_env()
    result = subprocess.run(
        ["git", "-C", str(repo_dir), "check-ignore", "-q", "--", rel],
        capture_output=True, env=env,
    )
    return result.returncode == 0


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


_UNVERIFIABLE = object()


# An item of a flow sequence: a plain word, or a quoted string with no escape
# and no quote of its own, which YAML 1.2.2 (sections 7.3.1 and 7.3.2, checked
# 2026-10-21) reads as the text between its quotes. A plain word starts with
# "-" only when a character it allows follows: a lone "-" is a block sequence
# entry's indicator, which YAML 1.2.2 forbids there (section 7.3.3, a plain
# scalar's first character; checked 2026-10-22), and PyYAML rejects `[- , "a"]`.
_FLOW_ITEM = r"""(?:[A-Za-z0-9_./]|-(?=[A-Za-z0-9_./-]))[A-Za-z0-9_./-]*|"[^"\\]*"|'[^']*'"""

# The only flow collections the reader admits: `{}`, `[]`, or a list of those items.
_FLOW_VALUE_RE = re.compile(rf"\{{\s*\}}|\[\s*(?:(?:{_FLOW_ITEM})(?:\s*,\s*(?:{_FLOW_ITEM}))*)?\s*\]")


def _flow_items(value: str) -> list:
    """The strings in a flow sequence _value() admitted, without their quotes."""
    return [item[1:-1] if item[0] in "\"'" else item for item in re.findall(_FLOW_ITEM, value[1:-1])]


def _value(text: str) -> str | None:
    """A single-line value without its comment, or None outside the modelled subset.

    Admitted: plain scalars, quoted scalars without escapes, and the flow
    collections _FLOW_VALUE_RE describes (plain words and quoted strings
    without escapes or quotes inside). Anchors, aliases, tags, escapes, other
    flow collections and indicator-led plain scalars are refused.
    """
    text = text.strip()
    if not text or text.startswith("#"):
        return ""
    if "\t" in text or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", text):
        return None
    if text[0] in "&*!%@`|>]},#" or text in ("-", "?", ":") or text.startswith(("- ", "? ", ": ")):
        return None
    if text[0] in "\"'[{":
        pattern = {'"': r'"[^"\\]*"', "'": r"'[^']*'(?!')"}.get(text[0], _FLOW_VALUE_RE.pattern)
        match = re.match(pattern, text)
        if match is None:
            return None
        rest = text[match.end():].strip()
        return match.group(0) if not rest or rest.startswith("#") else None
    comment = re.search(r"[ \t]#", text)
    value = text[: comment.start()].rstrip() if comment else text
    if ": " in value or value.endswith(":"):
        return None
    return value


# Plain keys a YAML 1.1 parser would read as a boolean, null, number or date.
_IMPLICIT_KEY_RE = re.compile(
    r"(?i:y|yes|n|no|true|false|on|off|null|~)"
    r"|[-+]?(?:0[box][0-9a-fA-F_]+|[0-9][0-9_]*(?:\.[0-9_]*)?|\.[0-9]+)(?:[eE][-+]?[0-9]+)?"
    r"|[-+]?\.(?i:inf|nan)|[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}.*"
)


def _outside_subset_char(char: str) -> bool:
    """A character the reader does not model: one YAML forbids, a tab, or other
    whitespace than space and line breaks, which Python's str.strip() would
    treat differently from YAML."""
    code = ord(char)
    if char in "\n\r" or 0x20 <= code <= 0x7E:
        return False
    if char.isspace() or code in (0x85, 0xFEFF):
        return True
    return not (0xA0 <= code <= 0xD7FF or 0xE000 <= code <= 0xFFFD or 0x10000 <= code <= 0x10FFFF)


def _structural_lines(text: str) -> list | None:
    """(indent, key, value) rows of a workflow in a strict YAML subset, or None.

    bootstrap.py has no YAML parser, so this models only block mappings and
    sequences, single-line scalars and flow collections, and block scalars,
    whose text it skips. Anything else (a quoted scalar or flow collection
    spanning lines, a quoted item with an escape or a quote inside, anchors,
    aliases, tags, a plain scalar continued on the next line, tabs, other
    whitespace than space and line breaks, characters YAML forbids, several
    documents) returns None,
    so callers refuse instead of guessing. Sequence entries are rows with key
    None.

    The guarantee covers workflows GitHub can load: for those, the rows are
    right or the result is None. A file GitHub rejects as invalid YAML already
    fails every run, so it is out of scope. _scan_rows() also says which line.
    """
    return _scan_rows(text)[0]


def _scan_rows(text: str) -> tuple:
    """(rows, None) as _structural_lines() reads them, or (None, n) where n is
    the 1-based number of the first line outside the subset."""
    lines = text.splitlines()
    # `stop` is the number of the first line found outside the subset. The
    # lines from one holding a character the reader does not model are not read.
    stop = next((i for i, char in enumerate(text) if _outside_subset_char(char)), None)
    if stop is not None:
        stop = len((text[:stop] + "x").splitlines())
        lines = lines[: stop - 1]
    rows, numbers, block, content, blank = [], [], None, None, 0
    for number, line in enumerate(lines, 1):
        if not line.strip():
            if block is not None and content is None:
                blank = max(blank, len(line.rstrip("\r")))
            continue
        indent = _indent(line)
        if block is not None:
            if indent > block:
                # Content keeps the first content line's indentation or more,
                # and no leading blank line may be indented deeper than it.
                if (content is not None and indent < content) or (content is None and blank > indent):
                    stop = number
                    break
                content = indent if content is None else content
                continue
            block = None
        body = line[indent:]
        if body.startswith("\t") or body.startswith("#"):
            if body.startswith("\t"):
                stop = number
                break
            continue
        if indent == 0 and body.rstrip() in ("---", "..."):
            stop = number
            break
        while body == "-" or body.startswith("- "):
            rows.append((indent, None, None))
            numbers.append(number)
            rest = body[1:]
            indent += 1 + len(rest) - len(rest.lstrip(" "))
            body = rest.lstrip(" ")
        if not body or body.startswith("#"):
            continue
        key_match = re.match(r'("[^"\\]*"|\'[^\']*\'|[A-Za-z0-9_][A-Za-z0-9_.-]*):(?=[ \t]|$)', body)
        if key_match is None:
            # A sequence entry that is a scalar, not a mapping.
            value = _value(body)
            if value is None or not rows or rows[-1][1] is not None:
                stop = number
                break
            continue
        key = key_match.group(1)
        if key[0] not in "\"'" and not (key == "on" and indent == 0) and _IMPLICIT_KEY_RE.fullmatch(key):
            stop = number  # a YAML 1.1 parser reads it as a boolean, null or number
            break
        key = key[1:-1] if key[0] in "\"'" else key
        raw = body[key_match.end():]
        if re.fullmatch(r"[ \t]*[|>][-+]?(?:[ \t]+#.*)?[ \t]*", raw):
            rows.append((indent, key, "|"))
            numbers.append(number)
            block, content, blank = indent, None, 0
            continue
        value = _value(raw)
        if value is None:
            stop = number
            break
        rows.append((indent, key, value))
        numbers.append(number)
    # A scalar value cannot have deeper children; such a file is outside the subset.
    for k, ((indent, key, value), (next_indent, _, _)) in enumerate(zip(rows, rows[1:])):
        if key is not None and value and next_indent > indent:
            stop = numbers[k + 1] if stop is None else min(stop, numbers[k + 1])
            break
    return (rows, None) if stop is None else (None, stop)


def _children(rows: list, start: int):
    """Direct children (index, key, value) of rows[start], or _UNVERIFIABLE for
    inconsistent indentation."""
    parent = rows[start][0]
    out, child = [], None
    for k in range(start + 1, len(rows)):
        indent, key, value = rows[k]
        if indent <= parent:
            break
        child = indent if child is None else child
        if indent < child:
            return _UNVERIFIABLE
        if indent == child:
            out.append((k, key, value))
    return out


def _only(entries: list, name: str):
    """The single (index, value) for key `name`, None if absent, _UNVERIFIABLE if repeated."""
    found = [(k, value) for k, key, value in entries if key == name]
    if len(found) > 1:
        return _UNVERIFIABLE
    return found[0] if found else None


def _has_postgres_service(text: str):
    """Whether any job in a workflow has a Postgres service container: one
    named `postgres`, as the --postgres block names it, or one whose image is
    `postgres`. None when the file is outside _structural_lines()'s subset, or
    when no such container is found but one the reader cannot see into might
    be one: a flow mapping, a block scalar or an expression."""
    rows = _structural_lines(text)
    if rows is None:
        return None
    root = [(k, key, value) for k, (indent, key, value) in enumerate(rows) if indent == 0]
    jobs = _only(root, "jobs")
    if jobs is None:
        return False
    if jobs is _UNVERIFIABLE or jobs[1]:
        return None
    entries = _children(rows, jobs[0])
    if entries is _UNVERIFIABLE:
        return None
    unsure = False
    for k, _, value in entries:
        job = _UNVERIFIABLE if value else _children(rows, k)
        services = _UNVERIFIABLE if job is _UNVERIFIABLE else _only(job, "services")
        if services is None:
            continue
        containers = _UNVERIFIABLE if services is _UNVERIFIABLE or services[1] else _children(rows, services[0])
        if containers is _UNVERIFIABLE:
            unsure = True
            continue
        for c, name, container in containers:
            if name == "postgres":
                return True
            fields = _UNVERIFIABLE if container else _children(rows, c)
            image = _UNVERIFIABLE if fields is _UNVERIFIABLE else _only(fields, "image")
            if image is None:
                continue
            value = "|" if image is _UNVERIFIABLE else (image[1] or "").strip("\"'")
            if re.fullmatch(r"(?:[^\s/]+/)*postgres(?:[:@].*)?", value):
                return True
            unsure = unsure or value == "|" or "${{" in value
    return None if unsure else False


def _postgres_hint(expected: str, actual: str) -> str:
    """One line on whether an edited test.yml and the render carry the
    --postgres service block, since --check cannot show a wrong --postgres
    once the repository's own test.yml differs."""
    local, render = _has_postgres_service(actual), _has_postgres_service(expected)
    if local is None:
        return "Postgres service: cannot read this file to tell; compare it with the render by hand"
    if local and render:
        return "Postgres service: in this file and in the render (--postgres)"
    if local:
        return "Postgres service: in this file, not in the render; pass --postgres if the repository uses it"
    if render:
        return ("Postgres service: in the render (--postgres), not in this file; "
                "drop --postgres if the repository does not use it")
    return "Postgres service: in neither this file nor the render"


def _declared_inputs(text: str):
    """Names under the root `on.workflow_call.inputs`, [] when it declares none,
    None when the file is not a reusable workflow, or _UNVERIFIABLE."""
    rows = _structural_lines(text)
    if rows is None:
        return _UNVERIFIABLE
    root = [(k, key, value) for k, (indent, key, value) in enumerate(rows) if indent == 0]
    keys = [key for _, key, _ in root]
    if None in keys or len(keys) != len(set(keys)):
        return _UNVERIFIABLE
    on = _only(root, "on")
    if on is None or on is _UNVERIFIABLE:
        return _UNVERIFIABLE
    k, value = on
    if value == "|":
        return _UNVERIFIABLE  # the events are a block scalar's text
    if value:
        # A scalar names one event exactly; only a flow list names several.
        if value.startswith("["):
            events = _flow_items(value)
        elif value.startswith("{"):
            events = []
        else:
            events = [value[1:-1] if value[0] in "\"'" else value]
        return [] if "workflow_call" in events else None
    events = _children(rows, k)
    if events is _UNVERIFIABLE or any(key is None for _, key, _ in events):
        return _UNVERIFIABLE
    call = _only(events, "workflow_call")
    if call is None:
        return None
    if call is _UNVERIFIABLE:
        return _UNVERIFIABLE
    c, value = call
    if value:
        return [] if value in ("{}", "null", "~") else _UNVERIFIABLE
    settings = _children(rows, c)
    inputs = _UNVERIFIABLE if settings is _UNVERIFIABLE else _only(settings, "inputs")
    if inputs is None:
        return []
    if inputs is _UNVERIFIABLE:
        return _UNVERIFIABLE
    n, value = inputs
    if value:
        return [] if value in ("{}", "null", "~") else _UNVERIFIABLE
    names = _children(rows, n)
    if names is _UNVERIFIABLE:
        return _UNVERIFIABLE
    names = [key for _, key, _ in names]
    if None in names or len(names) != len(set(names)):
        return _UNVERIFIABLE
    return names


def _passed_inputs(text: str) -> dict | None:
    """{called local workflow: [input names passed]} for this workflow's
    `uses: ./.github/workflows/...` calls, or None outside the subset."""
    rows = _structural_lines(text)
    if rows is None:
        return None
    calls = {}
    for k, (indent, key, value) in enumerate(rows):
        target = value.strip("'\"") if key == "uses" and value else ""
        if not re.fullmatch(r"\./\.github/workflows/[\w.-]+\.ya?ml", target):
            continue
        parent = max((p for p in range(k) if rows[p][0] < indent), default=None)
        siblings = _children(rows, parent) if parent is not None else None
        if siblings is None or siblings is _UNVERIFIABLE:
            return None
        passed = _only(siblings, "with")
        names = []
        if passed is _UNVERIFIABLE:
            return None
        if passed is not None:
            w, inline = passed
            if inline:
                return None
            entries = _children(rows, w)
            if entries is _UNVERIFIABLE:
                return None
            names = [name for _, name, _ in entries]
        calls.setdefault(target[2:], []).extend(names)
    return calls


def _outside_subset_note(text: str | None) -> str:
    """Names the first line of `text` that _scan_rows() refuses, as a suffix for
    a message; empty when it names none (or there is no text)."""
    number = None if text is None else _scan_rows(text)[1]
    if number is None:
        return ""
    # Split as the stamp does, so a character Python reads as a line break but
    # YAML does not (such as U+0085) stays in the line shown.
    shown = re.split(r"\r\n?|\n", text)[number - 1].strip(" ")
    if len(shown) > 80:
        shown = shown[:77] + "..."
    # repr() keeps a control character in the file from reaching the terminal.
    return f" (line {number} is outside the YAML subset: {shown!r})"


def _undeclared_inputs(repo_dir: Path, workflow: str) -> list:
    """Problems with `workflow`'s calls to the repository's own reusable workflows.

    A called workflow must declare every input passed to it, or GitHub fails
    the run; a repository-owned test.yml from an older template may lack one
    a newer release workflow passes. A called file that does not exist yet is
    written by --adopt from the same render, so it is not checked. Files are
    read with _structural_lines(); anything outside its subset is reported as
    unverifiable, naming the first line outside it when there is one, rather
    than guessed.
    """
    calls = _passed_inputs(workflow)
    if calls is None:
        return ["cannot verify the inputs this workflow passes; check them by hand"
                + _outside_subset_note(workflow)]
    problems = []
    for rel, passed in calls.items():
        called = repo_dir / rel
        text = None
        try:
            if _symlink_in_path(repo_dir, rel) or not called.is_file():
                continue
            text = called.read_text(encoding="utf-8")
            declared = _declared_inputs(text)
        except (OSError, UnicodeDecodeError):
            declared = _UNVERIFIABLE
        if declared is _UNVERIFIABLE:
            problems.append(
                f"cannot verify the inputs {rel} declares; check them by hand" + _outside_subset_note(text)
            )
            continue
        missing = [name for name in passed if declared is None or name not in declared]
        if missing:
            problems.append(f"{rel} does not declare input(s) {', '.join(missing)}")
    return problems


def _template_source(rel: str, body: str) -> str | None:
    """Which template file renders this owned workflow body, by unpinned text."""
    for name in _LEGACY_WORKFLOW_SOURCES.get(rel, ()):
        if _unpinned(_load(name)) == _unpinned(body):
            return name
    return None


def _legacy_key(rel: str, expected: str) -> str:
    """The LEGACY_TEMPLATE_DIGESTS row an older copy of `rel` must match."""
    if rel not in _LEGACY_WORKFLOW_SOURCES:
        return rel
    return f"{rel}#{_template_source(rel, read_stamp(expected, True)[1])}"


def _legacy_variant(rel: str, actual: str) -> str | None:
    """The template an unstamped older workflow came from, whichever type that is."""
    digest = _stamp_digest(actual, True)
    for name in _LEGACY_WORKFLOW_SOURCES.get(rel, ()):
        if digest in LEGACY_TEMPLATE_DIGESTS.get(f"{rel}#{name}", frozenset()):
            return name
    return None


def _template_file_state(rel: str, expected: str, actual: str) -> str:
    """Classify exact bytes, not newline-normalized text.

    An unstamped older copy is stale only when it came from the template this
    render uses: a gated release workflow adopted as `simple` would otherwise
    be replaced and lose its test gate.
    """
    is_yaml = _is_yaml(rel)
    digest, body = read_stamp(actual, is_yaml)
    if digest is None:
        if has_stamp_text(actual, is_yaml):
            return "local-modified"
        if rel.startswith(".agents/skills/"):
            return "shadowed"
        known = LEGACY_TEMPLATE_DIGESTS.get(_legacy_key(rel, expected), frozenset()) | {
            _stamp_digest(read_stamp(expected, is_yaml)[1], is_yaml)
        }
        return "stale" if _stamp_digest(body, is_yaml) in known else "local-modified"
    if not stamp_is_valid(actual, is_yaml):
        return "local-modified"
    if is_yaml and stamp_template(actual) != stamp_template(expected):
        return "local-modified"  # another type's template: replacing it changes the release gate
    if is_yaml:
        # Pins are Dependabot's to move: a workflow that differs only there is current.
        return "same" if _unpinned(actual) == _unpinned(expected) else "stale"
    return "same" if actual == expected else "stale"


def _skill_name(text: str) -> str | None:
    """Read an unambiguous one-line name; never interpret other YAML value forms."""
    if not text.startswith("---\n") or "\n---\n" not in text:
        return None
    frontmatter = text[4:].split("\n---\n", 1)[0]
    for line in frontmatter.splitlines():
        if not line.strip() or line.startswith((" ", "\t", "#")):
            continue
        if not re.match(r"^(?:[\w-]+|\"[\w-]+\"|'[\w-]+')[ \t]*:", line):
            return None
    matches = list(re.finditer(
        r"^(?:name|\"name\"|'name')[ \t]*:[ \t]*([^\n]*)", frontmatter, re.MULTILINE
    ))
    if len(matches) != 1:
        return None
    match = matches[0]
    for line in frontmatter[match.end():].splitlines()[1:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")):
            return None
        break
    scalar = match.group(1).strip()
    if scalar.startswith('"'):
        try:
            name, end = json.JSONDecoder().raw_decode(scalar)
        except ValueError:
            return None
        suffix = scalar[end:].strip()
        return name if not suffix or suffix.startswith("#") else None
    if scalar.startswith("'"):
        quoted = re.fullmatch(r"'((?:[^']|'')*)'(?:[ \t]+#.*)?", scalar)
        return quoted.group(1).replace("''", "'") if quoted else None
    plain = re.fullmatch(r"([A-Za-z0-9_][A-Za-z0-9_-]*)(?:[ \t]+#.*)?", scalar)
    return plain.group(1) if plain else None


def _case_alias(repo_dir: Path, rel: str, files: dict) -> str | None:
    """The expected path that rel names on a case-insensitive filesystem, if any."""
    folded = rel.casefold()
    for expected in files:
        if expected != rel and expected.casefold() == folded:
            try:
                same = os.path.samestat(os.lstat(repo_dir / rel), os.lstat(repo_dir / expected))
                # Two separate entries (case-differing hard links on a
                # case-sensitive volume) are not an alias of one another.
                if same and not _exact_path_exists(repo_dir, expected):
                    return expected
            except OSError:
                continue
    return None


def _exact_path_exists(repo_dir: Path, rel: str) -> bool:
    """True when every component of rel exists with exactly this spelling."""
    current = repo_dir
    for part in Path(rel).parts:
        if part not in os.listdir(current):
            return False
        current = current / part
    return True


SYMLINKED_SKILL_READ_LIMIT = 1 << 20


def _read_regular_prefix(path: Path, limit: int) -> str | None:
    """Up to `limit` bytes of a regular file as text, or None.

    Opens non-blocking and checks the opened descriptor, so a FIFO or device
    behind a symlink can neither block the open nor the read.
    """
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        data = os.read(fd, limit)
    except OSError:
        return None
    finally:
        os.close(fd)
    # A cut inside a multibyte character only affects the tail, not the frontmatter.
    return data.decode("utf-8", errors="replace")


def _target_missing(path) -> bool:
    """True only when following `path` confirms nothing is there.

    os.path.exists() is also False for a target that exists but cannot be
    reached (a permission error), and such a mirror must not be deleted.
    """
    try:
        os.stat(path)
    except (FileNotFoundError, NotADirectoryError):
        return True
    except OSError:
        return False
    return False


def _symlinked_skill_collisions(repo_dir: Path, files: dict, skill_paths: dict) -> dict:
    """Symlinked skill folders whose SKILL.md reuses a template skill's name.

    Harnesses follow symlinked skill folders, so a collision there shadows a
    template skill as much as a real folder would. The target is only read,
    never written, and at most SYMLINKED_SKILL_READ_LIMIT bytes of it.
    """
    base = repo_dir / ".agents/skills"
    try:
        if _symlink_in_path(repo_dir, ".agents/skills") or not base.is_dir():
            return {}
        # On a filesystem whose directory entries carry no file type,
        # is_symlink() asks lstat, which fails in a folder that cannot be searched.
        entries = [entry for entry in sorted(os.scandir(base), key=lambda e: e.name)
                   if entry.is_symlink()]
    except OSError as exc:
        return {".agents/skills": ("unreadable", f"{type(exc).__name__}: {exc.strerror or exc}")}
    found = {}
    for entry in entries:
        rel = f".agents/skills/{entry.name}"
        if f"{rel}/SKILL.md" in files:
            continue
        text = _read_regular_prefix(Path(entry.path) / "SKILL.md", SYMLINKED_SKILL_READ_LIMIT)
        if text is None:
            continue
        body = read_stamp(text.replace("\r\n", "\n"))[1]
        name = _skill_name(body)
        if name is None and body.lstrip("\ufeff").startswith("---"):
            # Same conservative rule as an ordinary folder: a name the parser
            # cannot read unambiguously might still collide.
            found[rel] = ("shadowed", "symlinked skill whose frontmatter name could not be read "
                          "unambiguously; use a plain single-line name")
            continue
        if name in skill_paths:
            found[rel] = ("shadowed", "symlinked skill folder whose name collides with a template skill")
            found[skill_paths[name]] = ("shadowed", f"shadowed by {rel}")
    return found


def _dangling_mirrors(repo_dir: Path, links: dict) -> dict:
    """`.claude/skills` symlinks that point at nothing, outside the declared mirrors.

    A retired template skill, or a wrong --type, leaves its mirror behind once
    the skill folder is gone. Mirrors of a repository's own skills resolve, so
    they are not reported.
    """
    base = repo_dir / ".claude/skills"
    try:
        if _symlink_in_path(repo_dir, ".claude/skills") or not base.is_dir():
            return {}
        # A declared mirror is not asked about; see _symlinked_skill_collisions
        # for what is_symlink() can raise.
        entries = [entry for entry in sorted(os.scandir(base), key=lambda e: e.name)
                   if f".claude/skills/{entry.name}" not in links and entry.is_symlink()]
    except OSError as exc:
        return {".claude/skills": ("unreadable", f"{type(exc).__name__}: {exc.strerror or exc}")}
    found = {}
    for entry in entries:
        rel = f".claude/skills/{entry.name}"
        if not _target_missing(entry.path):
            continue
        found[rel] = ("dangling", f"symlink to {os.readlink(entry.path)}, which does not exist")
    return found


def _own_pr_template(repo_dir: Path) -> str | None:
    """A pull request template of the repository's own, where GitHub reads one.

    Names are compared without case and with any extension, so --adopt never
    adds a second template beside the repository's own. Only a file counts:
    a PULL_REQUEST_TEMPLATE folder fills no pull request unless a link names
    one of its templates, so the generated one goes beside it. Called only
    when PR_TEMPLATE itself is not compared (see _pr_template_state), so an
    entry that opens as PR_TEMPLATE on a case-insensitive filesystem, such as
    .github/PULL_REQUEST_TEMPLATE.md, is the repository's own. A file git
    ignores never reaches the default branch, so it does not count.
    """
    for folder in PR_TEMPLATE_FOLDERS:
        base = repo_dir / folder
        if (folder and _symlink_in_path(repo_dir, folder)) or not base.is_dir():
            continue
        try:
            listing = sorted(os.listdir(base))
        except OSError as exc:
            # Name the folder: the row is for the template, not for the folder.
            raise OSError(exc.errno, f"{exc.strerror or type(exc).__name__}: {folder or '.'}") from exc
        for entry in listing:
            name = Path(entry.lower())
            rel = f"{folder}/{entry}" if folder else entry
            if name.stem != "pull_request_template":
                continue
            try:
                # os.stat, not Path.is_file(): the latter answers False on a
                # permission error from Python 3.14, which would pass a template
                # in a folder that can be listed but not searched off as absent.
                is_file = stat.S_ISREG(os.stat(base / entry).st_mode)
            except (FileNotFoundError, NotADirectoryError):
                continue
            except OSError as exc:
                raise OSError(exc.errno, f"{exc.strerror or type(exc).__name__}: {folder or '.'}") from exc
            if is_file and not _git_ignored(repo_dir, rel):
                return rel
    return None


def _pr_template_state(repo_dir: Path) -> tuple | None:
    """The report entry for PR_TEMPLATE, or None to compare it like any other file.

    It is compared only as a regular file under its exact spelling that git
    does not ignore; on a case-insensitive filesystem another spelling, such
    as .github/PULL_REQUEST_TEMPLATE.md, opens as it. Otherwise the
    repository's own template, a symlink here to a file included, is kept; a
    symlink to anything else, or an ignored path, is refused, since no
    template reaches the default branch through it; and an absent one is
    written.
    """
    path = repo_dir / PR_TEMPLATE
    if _symlink_in_path(repo_dir, str(Path(PR_TEMPLATE).parent)):
        return ("symlink", "a symlink in this path; not compared or written")
    ignored = _git_ignored(repo_dir, PR_TEMPLATE)
    # The folder is no symlink (above), so this asks only about the template,
    # and names a folder that cannot be searched, as path.is_symlink() would not.
    if not ignored and _symlink_in_path(repo_dir, PR_TEMPLATE):
        if not path.is_file():
            return ("symlink", "a symlink to no file here; not compared or written")
        return ("own", "the repository's own pull request template is a symlink here; not compared or written")
    if not ignored and path.is_file() and _exact_path_exists(repo_dir, PR_TEMPLATE):
        return None
    own = _own_pr_template(repo_dir)
    if own:
        return ("own", f"the repository's own pull request template is {own}; not added")
    if ignored:
        return ("ignored", "ignored by git; update the ignore rules before adopting")
    return ("missing", None)


def _extra_owned_files(repo_dir: Path, files: dict) -> dict:
    """Find orphaned stamped files and name collisions, without following links."""
    extras = {}
    skill_paths = {
        Path(path).parent.name: path for path in files
        if path.startswith(".agents/skills/") and path.endswith("/SKILL.md")
    }
    # Template skills that this configuration does not render, such as another
    # type's, would be deleted as orphans under a wrong --type or a missing
    # --screenshots; they are reported instead, and compare_repository turns
    # any of them into a (--type) refusal.
    sets = _skill_sets()
    every, shared = set.union(*sets), set.intersection(*sets)
    other_type = every - shared - set(skill_paths) if skill_paths else set()
    extras.update(_symlinked_skill_collisions(repo_dir, files, skill_paths))
    for base in (".agents/skills", ".claude/agents", ".opencode/agents"):
        try:
            if _symlink_in_path(repo_dir, base):
                continue
        except OSError as exc:
            extras[base] = ("unreadable", f"{type(exc).__name__}: {exc.strerror or exc}")
            continue
        for directory, dirs, names in os.walk(repo_dir / base, followlinks=False):
            # A directory that can be listed but not searched (r without x)
            # answers for none of its entries: report it once, and go no deeper.
            here = Path(directory).relative_to(repo_dir).as_posix()
            try:
                dirs[:] = sorted(d for d in dirs if not _is_symlink(Path(directory) / d))
            except OSError as exc:
                dirs[:] = []
                extras[here] = ("unreadable", f"{type(exc).__name__}: {exc.strerror or exc}")
            for name in sorted(names):
                path = Path(directory) / name
                rel = path.relative_to(repo_dir).as_posix()
                try:
                    if rel in files or _is_symlink(path) or not path.is_file():
                        continue
                except OSError as exc:
                    extras[here] = ("unreadable", f"{type(exc).__name__}: {exc.strerror or exc}")
                    break
                alias = _case_alias(repo_dir, rel, files)
                if alias:
                    extras[rel] = (
                        "shadowed",
                        f"same file as {alias} under a different case; rename it with `git mv`",
                    )
                    continue
                try:
                    text = path.read_bytes().decode("utf-8")
                except (OSError, UnicodeDecodeError):
                    if base == ".agents/skills" and name == "SKILL.md":
                        extras[rel] = (
                            "shadowed",
                            "frontmatter name could not be read unambiguously; use a plain single-line name",
                        )
                    continue
                stamped = any(line.startswith(STAMP_PREFIX) for line in text.splitlines())
                if base == ".agents/skills" and name == "SKILL.md":
                    _, body = read_stamp(text)
                    skill_name = _skill_name(body)
                    if skill_name is None and (body.lstrip("\ufeff").startswith("---") or not stamped):
                        extras[rel] = (
                            "shadowed",
                            "frontmatter name could not be read unambiguously; use a plain single-line name",
                        )
                        continue
                    if skill_name in skill_paths:
                        extras[rel] = ("shadowed", "frontmatter name collides with a template skill")
                        extras[skill_paths[skill_name]] = ("shadowed", f"shadowed by {rel}")
                        continue
                    if stamped and skill_name in other_type:
                        extras[rel] = ("other-type", (
                            f"template skill `{skill_name}`, which only --type "
                            f"{' or '.join(SCREENSHOT_TYPES)} with --screenshots generates"
                            if skill_name == SCREENSHOT_REVIEW_SKILL
                            else f"template skill `{skill_name}` of another repository type"
                        ))
                        continue
                if stamped:
                    extras[rel] = (
                        ("ignored", "ignored by git; not deleted")
                        if _git_ignored(repo_dir, rel) else ("orphaned", None)
                    )
    return extras


TYPE_MISMATCH = "(--type)"
SHADOWED_UNSTAMPED_SKILL = (
    "an unstamped file at a template skill's path; move it aside so --adopt can write the "
    "template skill, or rename the skill if it is the repository's own"
)


SEED_EDITED = "matches no released copy, so --adopt keeps it; merge template changes by hand"


def _seed_holds(report: dict, blocked=frozenset()) -> dict:
    """The files holding back each stale or missing seed script --adopt keeps.

    A stale seed is brought up to date, and a missing one created, only when
    every other file of each group holding it is the same as the render,
    stale, or missing, and no stale or missing file of those groups is held
    back. blocked names files that hold their groups back like an edited
    file: ones --adopt cannot write, and up-to-date ones that are untracked
    or uncommitted. Each seed held back maps to the files at the root of its
    hold.
    """
    def status(rel):
        return report[rel][0] if rel in report else None

    pending = {rel for rel in SEED_FILES if status(rel) in ("stale", "missing")}
    roots = {rel: set() for rel in pending}
    for group in SEED_GROUPS:
        unfit = {rel for rel in group if rel in blocked or status(rel) not in ("same", "stale", "missing")}
        for rel in pending.intersection(group):
            roots[rel] |= unfit - {rel}
    changed = True
    while changed:
        changed = False
        for group in SEED_GROUPS:
            members = pending.intersection(group)
            held = set().union(*(roots[rel] for rel in members))
            for rel in members:
                extra = held - {rel} - roots[rel]
                if extra:
                    roots[rel] |= extra
                    changed = True
    return {rel: sorted(found) for rel, found in roots.items() if found}


def _seed_stale_detail(tag: str, roots) -> str:
    detail = f"unchanged since gh-repo-bootstrapper {tag} shipped it"
    if not roots:
        return detail + "; --adopt brings it up to date"
    return detail + "; --adopt keeps it, since " + _seed_hold_reason(roots)


def _seed_hold_reason(roots) -> str:
    return (
        "it changes only together with " + ", ".join(roots)
        + ", which --adopt leaves as it is; update them together by hand"
    )


def _carriage_return_rows(rows: list, text: str) -> list:
    """compare_agents' rows for an AGENTS.md holding carriage returns, plus the row naming them.

    --adopt refuses such a file whatever its sections hold, so the report says
    why. When no line ends in a bare LF, the file has CRLF or CR line endings
    and every section differs from the LF template, which says nothing about
    its text: the per-section `differs` and `same` rows give way to one row,
    while the `missing`, `local` and `retired` rows, which stay true, remain,
    as does the order of the generated sections. A file with a bare LF line is
    not that case, whatever its other lines end in: only the sections holding a
    carriage return differ because of it, so every row stays and the rows
    added name the cause. CRLF lines among LF ones are mixed endings, which
    converting to LF fixes; a carriage return not followed by an LF is a stray
    character that conversion leaves, so it is named on its own.
    """
    crlf_or_cr = re.search(r"(?<!\r)\n", text) is None
    marks = [row for row in rows if row[1] == BYTE_ORDER_MARK]
    rest = [row for row in rows if row[1] != BYTE_ORDER_MARK]
    if crlf_or_cr:
        named = [("differs", CARRIAGE_RETURNS)]
        rest = [
            (status, heading) for status, heading in rest
            if status in ("missing", "local", "retired") or (status == "differs" and heading.startswith("("))
        ]
    else:
        named = []
        if "\r\n" in text:
            named.append(("differs", MIXED_LINE_ENDINGS))
        if re.search(r"\r(?!\n)", text):
            named.append(("differs", STRAY_CARRIAGE_RETURN))
    return marks + named + rest


def compare_repository(repo_dir: Path, files: dict, links: dict = None) -> dict:
    """Per-file status of an existing repository against the rendered files."""
    report = {}
    links = _links_for_files(files) if links is None else links
    legacy_bodies = None
    release_tags = None
    reads = _ReleaseReads()
    seed_tags = {}
    for rel, expected in files.items():
        path = repo_dir / rel
        if rel == PR_TEMPLATE:
            try:
                state = _pr_template_state(repo_dir)
            except OSError as exc:
                state = ("unreadable", f"{type(exc).__name__}: {exc.strerror or exc}")
            if state is not None:
                report[rel] = state
                continue
        try:
            linked = _symlink_in_path(repo_dir, rel)
        except OSError as exc:
            report[rel] = ("unreadable", f"{type(exc).__name__}: {exc.strerror or exc}")
            continue
        if linked:
            report[rel] = ("symlink", "a symlink in this path; not compared or written")
            continue
        owned = read_stamp(expected, _is_yaml(rel))[0] is not None
        if owned and _git_ignored(repo_dir, rel):
            report[rel] = ("ignored", "ignored by git; update the ignore rules before adopting")
            continue
        try:
            if not path.is_file():
                report[rel] = ("missing", None)
                continue
            actual = path.read_bytes().decode("utf-8", errors="replace")
        except OSError as exc:
            report[rel] = ("unreadable", f"{type(exc).__name__}: {exc.strerror or exc}")
            continue
        if owned:
            status = _template_file_state(rel, expected, actual)
            detail = SHADOWED_UNSTAMPED_SKILL if status == "shadowed" else None
            variant = None
            if status == "local-modified" and rel in _LEGACY_WORKFLOW_SOURCES and stamp_is_valid(actual, True):
                detail = (
                    f"a stamped {stamp_template(actual)}, but this --type renders "
                    f"{stamp_template(expected)}; check --type"
                )
            elif status == "local-modified" and read_stamp(actual, True)[0] is None and rel in _LEGACY_WORKFLOW_SOURCES:
                variant = _legacy_variant(rel, actual)
            if variant is not None:
                detail = (
                    f"an unchanged {variant} from an earlier release, but this --type renders "
                    f"{_template_source(rel, read_stamp(expected, True)[1])}; check --type"
                )
            elif status == "local-modified" and read_stamp(actual, _is_yaml(rel))[0] is None and any(
                key.split("#")[0] == rel for key in LEGACY_TEMPLATE_DIGESTS
            ):
                if rel in _LEGACY_WORKFLOW_SOURCES:
                    if release_tags is None:
                        release_tags = _workflow_diff_tags()
                        if not release_tags:
                            reads.notice()
                    candidates = _workflow_diff_bases(rel, read_stamp(expected, True)[1], release_tags, reads)
                else:
                    if legacy_bodies is None:
                        legacy_bodies = _legacy_template_bodies(reads)
                    candidates = [(f"legacy/{rel}", body, None) for key, bodies in legacy_bodies.items()
                                  if key.split("#")[0] == rel for body in bodies]
                if candidates:
                    label, nearest, other = max(candidates, key=lambda base: difflib.SequenceMatcher(
                        None, base[1].splitlines(), actual.splitlines(), autojunk=False
                    ).ratio())
                    detail = "".join(difflib.unified_diff(
                        nearest.splitlines(keepends=True), actual.splitlines(keepends=True),
                        fromfile=label, tofile=rel,
                    ))
                    if not detail:
                        detail = f"identical to {label} apart from the missing ownership stamp"  # see _UNSTAMPED_COPY
                        if other:
                            detail += f", but this --type renders {other}; check --type"
            report[rel] = (status, detail)
        elif actual == expected:
            report[rel] = ("same", None)
        elif rel in SEED_FILES:
            seed_tags[rel] = SEED_DIGESTS.get(rel, {}).get(_digest(actual))
            report[rel] = ("stale", None) if seed_tags[rel] else ("differs", SEED_EDITED)
        elif rel == "AGENTS.md":
            rows = compare_agents(expected, actual)
            aligned = all(row_status == "same" for row_status, _ in rows)
            if not aligned and "\r" in actual:
                rows = _carriage_return_rows(rows, actual)
            report[rel] = ("same", None) if aligned else ("differs", rows)
        elif rel == ".gitignore":
            missing = _missing_lines(expected, actual)
            report[rel] = ("differs", missing) if missing else ("same", None)
        elif rel == "CLAUDE.md" and "@AGENTS.md" not in actual.split():
            report[rel] = ("differs", "does not import AGENTS.md (no `@AGENTS.md` line)")
        elif rel == ".github/workflows/test.yml" and NEXTJS_BASELINE_REVIEW_WORKFLOW in files:
            # Only nextjs renders --postgres; a repository edits its own test.yml.
            report[rel] = ("differs", _postgres_hint(expected, actual))
        else:
            report[rel] = ("differs", None)
    holds = _seed_holds(report)
    for rel, tag in seed_tags.items():
        if tag:
            report[rel] = ("stale", _seed_stale_detail(tag, holds.get(rel)))
    for rel in SEED_FILES:
        if rel in holds and report[rel][0] == "missing":
            report[rel] = ("missing", "--adopt does not create it, since " + _seed_hold_reason(holds[rel]))
    report.update(_extra_owned_files(repo_dir, files))
    report.update(_dangling_mirrors(repo_dir, links))
    mismatch = sorted(rel for rel, (status, _) in report.items() if status == "other-type")
    if mismatch:
        report[TYPE_MISMATCH] = (
            "differs",
            "this repository holds template skills that this configuration does not generate ("
            + ", ".join(mismatch)
            + "); re-run with the --type, and --screenshots where it applies, that the "
            "repository was generated with",
        )
    for rel, target in links.items():
        path = repo_dir / rel
        try:
            if _symlink_in_path(repo_dir, rel, links):
                report[rel] = ("symlink", "a symlink in the parent path; not compared or written")
            elif _git_ignored(repo_dir, rel):
                report[rel] = ("ignored", "ignored by git; update the ignore rules before adopting")
            elif path.is_symlink():
                report[rel] = ("same", None) if os.readlink(path) == target else ("differs", "wrong mirror target")
            elif path.exists():
                report[rel] = ("differs", "mirror path is not a symlink")
            else:
                report[rel] = ("missing", None)
        except OSError as exc:
            report[rel] = ("unreadable", f"{type(exc).__name__}: {exc.strerror or exc}")
    return report


RETIRED_TEXT_PREVIEW_LINES = 3


def _retired_section_text(repo_dir: Path, rows: list) -> dict[str, list[str]]:
    """Non-blank lines under each retired heading of the repository's AGENTS.md.

    --replace-generated-sections drops a retired section whole, so --check
    shows its text first: a repository rule added there would be lost too.
    """
    retired = {heading for row_status, heading in rows if row_status == "retired"}
    if not retired:
        return {}
    try:
        if _symlink_in_path(repo_dir, "AGENTS.md"):
            return {}
        actual = (repo_dir / "AGENTS.md").read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return {}
    text = {}
    for heading, body in _agents_sections(actual)[1]:
        if heading in retired:
            text.setdefault(heading, []).extend(line.strip() for line in body.splitlines()[1:] if line.strip())
    return text


def print_repository_report(repo_dir: Path, cfg: dict, report: dict) -> bool:
    """Print a --check report; return True when the repository is aligned."""
    print(f"\n{repo_dir} — compared with the '{cfg['repo_type']}' template")
    notice = screenshot_review_notice(cfg)
    if notice:
        print(f"  {notice}")
    aligned = True
    for rel, (status, detail) in sorted(report.items()):
        if status != "same":
            aligned = False
        print(f"  {status:<{REPORT_STATUS_WIDTH}} {rel}")
        if rel == "AGENTS.md" and isinstance(detail, list):
            retired_text = _retired_section_text(repo_dir, detail)
            for row_status, heading in detail:
                if row_status != "same":
                    hint = "  → move under ## Project specifics" if row_status == "local" else ""
                    if heading == NEXTJS_BLOCK_MOVED:
                        hint = "  → move it back to the top of the file"
                    elif heading == BYTE_ORDER_MARK:
                        hint = ""
                    print(f"      {row_status:<8} {heading}{hint}")
                if row_status == "retired" and retired_text.get(heading):
                    lines = retired_text[heading]
                    print(f"        notice: retired section contains {len(lines)} "
                          f"line{'' if len(lines) == 1 else 's'} of text; "
                          "--replace-generated-sections drops this text. First lines:")
                    for line in lines[:RETIRED_TEXT_PREVIEW_LINES]:
                        print(f"          {line}")
        elif rel == ".gitignore" and isinstance(detail, list):
            print(f"      missing entries: {', '.join(detail)}")
        elif isinstance(detail, str):
            print(f"      {detail}")
    agents = repo_dir / "AGENTS.md"
    size = 0
    try:
        if not _symlink_in_path(repo_dir, "AGENTS.md") and agents.is_file():
            size = agents.stat().st_size
    except OSError:
        pass  # the report above already shows AGENTS.md as unreadable
    if size > AGENTS_SIZE_WARN_BYTES:
        print(f"  warn AGENTS.md total {size} B > {AGENTS_SIZE_WARN_BYTES} B")
    print("\nAligned." if aligned else "\nDrift found. Review it, then run --adopt to apply what can be applied.")
    return aligned


def _git_file_state(repo_dir: Path, rel: str) -> str:
    """"clean", "dirty", or "untracked" (also outside a git work tree).

    Tracked is required for "clean", not just absent from `git status`: an
    ignored, untracked file also produces no status line, but has no committed
    copy to review the change against or revert to. An index entry marked
    skip-worktree or assume-unchanged counts as dirty, because `git status`
    then hides working-tree edits that a rewrite would destroy.
    """
    def git(*args):
        # Literal pathspecs: a name such as `x*.md` must not match its siblings.
        return subprocess.run(
            ["git", "--literal-pathspecs", "-C", str(repo_dir), *args], capture_output=True, text=True,
            env=_git_env(),
        )

    try:
        inside = git("rev-parse", "--is-inside-work-tree")
    except OSError:
        inside = None
    if inside is None or inside.returncode != 0 or inside.stdout.strip() != "true":
        # Without a usable answer from git (missing, refused by its ownership
        # check, broken), only a directory with no .git above it is known to be
        # outside a repository; anything else is unknown, so treat it as dirty.
        return "dirty" if _has_git_marker(repo_dir) else "untracked"
    try:
        status = git("status", "--porcelain", "--untracked-files=all", "--", rel)
        listed = git("ls-files", "-v", "--", rel)
    except OSError:
        return "dirty"
    if status.returncode != 0 or listed.returncode != 0:
        return "dirty"
    # A staged change, including a staged removal of a file still on disk, is
    # dirty; only a plain `??` entry is untracked.
    lines = status.stdout.splitlines()
    if any(not line.startswith("?? ") for line in lines):
        return "dirty"
    if not listed.stdout:
        return "untracked"
    tags = {line[:1] for line in listed.stdout.splitlines()}
    if "S" in tags or any(tag.islower() for tag in tags):
        return "dirty"
    return "dirty" if lines else "clean"


def _has_git_marker(repo_dir: Path) -> bool:
    """True when repo_dir or a parent holds a .git entry (directory or file)."""
    path = Path(os.path.abspath(repo_dir))
    return any(os.path.lexists(directory / ".git") for directory in (path, *path.parents))


def _git_file_is_clean(repo_dir: Path, rel: str) -> bool:
    """True when rel is tracked by git and has no uncommitted or hidden changes."""
    return _git_file_state(repo_dir, rel) == "clean"


_DIR_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_ANCHORED_WRITES = hasattr(os, "O_NOFOLLOW") and {
    os.open, os.mkdir, os.rename, os.unlink, os.link, os.rmdir, os.stat
} <= os.supports_dir_fd


def _open_parent(repo_dir: Path, rel: str, create: bool, created: list = None) -> int:
    """A descriptor for rel's parent directory, reached from repo_dir.

    Each component is opened relative to the one before it with O_NOFOLLOW,
    so a symlink present at any component when it is opened — including one
    swapped in after the scan — fails with an OSError instead of redirecting
    the write. This does not stop another process moving an already-opened
    directory out of repo_dir mid-run; --adopt assumes nothing else modifies
    the repository while it runs. Missing directories are created only when
    create is set, and their relative paths are appended to created.
    """
    fd = os.open(repo_dir, _DIR_FLAGS)
    walked = []
    try:
        for part in Path(rel).parent.parts:
            walked.append(part)
            try:
                child = os.open(part, _DIR_FLAGS, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, 0o777, dir_fd=fd)
                if created is not None:
                    created.append("/".join(walked))
                child = os.open(part, _DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _remove_empty_dirs(repo_dir: Path, created: list) -> None:
    """Best-effort removal of directories this run created, deepest first."""
    for rel_dir in reversed(created):
        try:
            _rmdir_anchored(repo_dir, rel_dir)
        except OSError:
            pass


def _rmdir_anchored(repo_dir: Path, rel_dir: str) -> None:
    """Remove the empty directory rel_dir, reached without following a symlink.

    Only an empty directory goes: one that still holds anything, or is a
    symlink, raises OSError and is left as it is.
    """
    parent = _open_parent(repo_dir, rel_dir, create=False)
    try:
        os.rmdir(Path(rel_dir).name, dir_fd=parent)
    finally:
        os.close(parent)


def _read_anchored(parent: int, name: str) -> tuple:
    """(bytes, identity) of name in parent, never following a symlink."""
    fd = os.open(name, os.O_RDONLY | _NOFOLLOW, dir_fd=parent)
    with os.fdopen(fd, "rb") as handle:
        st = os.fstat(handle.fileno())
        return handle.read(), (st.st_ino, st.st_size, st.st_mtime_ns)


def _identity(parent: int, name: str) -> tuple:
    st = os.stat(name, dir_fd=parent, follow_symlinks=False)
    return (st.st_ino, st.st_size, st.st_mtime_ns)


def _decode_for_rewrite(raw: bytes):
    """The file's text for rewriting, or None when rewriting could corrupt it."""
    if b"\r" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _create_anchored(parent: int, name: str, text: str, exact_mode=None) -> None:
    """Create name in parent; fails if anything, including a symlink, is there.

    New files get the usual umask-filtered mode unless exact_mode is given.
    """
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, 0o666, dir_fd=parent)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        if exact_mode is not None:
            os.fchmod(handle.fileno(), exact_mode)
        handle.write(text)


def _temp_name(name: str) -> str:
    return f".{name}.{os.getpid()}.{time.monotonic_ns()}.tmp"


def _publish_new(parent: int, name: str, text: str) -> None:
    """Create name with text, all or nothing, never replacing anything there.

    The text goes to a temporary sibling first and is then hard-linked into
    place, which fails if name exists; a failed write leaves no partial file.
    """
    tmp = _temp_name(name)
    try:
        _create_anchored(parent, tmp, text)
        os.link(tmp, name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
    finally:
        try:
            os.unlink(tmp, dir_fd=parent)
        except FileNotFoundError:
            pass


def _replace_anchored(parent: int, name: str, text: str, identity: tuple) -> None:
    """Write text to a new file in parent, then rename it over name.

    A new inode means a hard link elsewhere keeps its old content, and a
    failed write leaves the original untouched. The permission bits are kept;
    ownership, flags, and extended attributes are not. If name no longer has
    the identity (inode, size, mtime) it had when read, nothing is replaced.
    This narrows, but cannot close, the window for a concurrent edit; --adopt
    assumes nothing else modifies the repository while it runs.
    """
    mode = os.stat(name, dir_fd=parent, follow_symlinks=False).st_mode & 0o7777
    tmp = _temp_name(name)
    try:
        _create_anchored(parent, tmp, text, exact_mode=mode)
        if _identity(parent, name) != identity:
            raise FileExistsError(errno.EBUSY, "changed while --adopt was running", name)
        os.rename(tmp, name, src_dir_fd=parent, dst_dir_fd=parent)
    except BaseException:
        try:
            os.unlink(tmp, dir_fd=parent)
        except FileNotFoundError:
            pass
        raise


def adopt_repository(
    repo_dir: Path, files: dict, replace_generated: bool = False, confirm=None, links: dict = None
) -> list:
    """Bring an existing local repository in line without touching GitHub.

    Writes missing generated files and mirrors, upgrades stale template-owned
    files and unchanged copies of the repository-owned seed scripts (see
    _seed_actions), and deletes digest-valid orphaned template-owned files that git
    tracks with no uncommitted change. Locally
    modified or shadowed owned files and ignored paths are refused. Other
    existing files are kept, except that AGENTS.md is rebuilt while keeping
    `## Project specifics` and the `next dev` block. That rewrite needs the
    file tracked by git with no uncommitted changes, LF line endings, and
    UTF-8 text, so the result can be reviewed and reverted. Writes refuse any
    symlink they meet on the way. --adopt assumes nothing else modifies the
    repository while it runs; it narrows but cannot close races with a
    process that does.

    Missing .gitignore entries are reported, not written: whether an added
    rule would break an existing `!` exception depends on git's full ignore
    semantics across every ignore file, so that edit is left to a person.

    The AGENTS.md rebuild is refused while any repository text sits outside
    `## Project specifics`, or the file has structure the parser does not
    model. A generated section whose text differs may be an older template or
    a local edit, and nothing here can tell which, so it is replaced only when
    replace_generated is set; otherwise the rebuild is refused and the
    differing and retired sections are listed. Retired sections are dropped
    only with replace_generated and no unknown subsections. When it is set,
    confirm(sections) is called with the sections about to be replaced before
    AGENTS.md is written; a falsy result refuses the rebuild.
    Returns (action, path, detail) rows.
    """
    actions = []
    mirrors = _links_for_files(files) if links is None else links
    report = compare_repository(repo_dir, files) if links is None else compare_repository(repo_dir, files, links)
    if TYPE_MISMATCH in report:
        # A wrong --type or a missing --screenshots would delete the template
        # skills this configuration does not render as orphans.
        return [("refused", TYPE_MISMATCH, report[TYPE_MISMATCH][1] + "; nothing was changed")]
    seeds = _seed_actions(repo_dir, report, files)
    for rel, (status, detail) in sorted(report.items()):
        try:
            if status == "dangling":
                action = _adopt_dangling_mirror(repo_dir, rel)
            elif rel in mirrors:
                action = _adopt_link(repo_dir, rel, status, detail, mirrors[rel])
            elif rel in seeds:
                action = seeds[rel] or _adopt_seed(repo_dir, rel, files[rel])
            else:
                action = _adopt_file(repo_dir, rel, status, detail, files.get(rel), replace_generated, confirm)
        except OSError as exc:
            action = ("refused", rel, f"{type(exc).__name__}: {exc.strerror or exc}")
        if action:
            actions.append(action)
    actions.extend(_adopt_emptied_skills(repo_dir, actions, report, mirrors))
    return actions


# What rmdir reports for a folder that holds something (a non-empty directory
# can also fail as EEXIST), that is gone already, or that a symlink or a file
# has replaced. None of those is an emptied folder this run failed to remove.
_NOT_OURS_TO_REMOVE = {errno.ENOTEMPTY, errno.EEXIST, errno.ENOENT, errno.ENOTDIR, errno.ELOOP}


def _adopt_emptied_skills(repo_dir: Path, actions: list, report: dict, mirrors: dict) -> list:
    """Clear what deleting orphaned skill files left behind: emptied folders,
    then the `.claude/skills` mirrors that point at a folder that is gone.

    A folder that still holds anything is left without a row, as is one that
    is gone already or is no longer a plain directory (a symlink put there
    mid-run). A folder that should be empty but cannot be removed, such as
    one in a read-only parent, is refused: its mirror then stays live, and a
    later run has no deleted file left to retry from.

    The mirrors were judged before the deletion, while their folder still
    existed, so they are looked at again, and only ones the scan did not
    already report are added.
    """
    folders = sorted({
        folder.as_posix()
        for action, rel, _ in actions
        if action == "deleted" and rel.startswith(".agents/skills/")
        for folder in Path(rel).parents
        if len(folder.parts) > 2
    })
    if not folders:
        return []
    rows = []
    for folder in reversed(folders):
        try:
            _rmdir_anchored(repo_dir, folder)
        except OSError as exc:
            if exc.errno not in _NOT_OURS_TO_REMOVE:
                rows.append((
                    "refused", folder,
                    f"{type(exc).__name__}: {exc.strerror or exc}; "
                    "folder left in place, so the .claude/skills mirror of its skill stays; "
                    "remove the emptied folders by hand, then re-run --adopt to delete the mirror",
                ))
    try:
        dangling = _dangling_mirrors(repo_dir, mirrors)
    except OSError as exc:
        return rows + [("refused", ".claude/skills", f"{type(exc).__name__}: {exc.strerror or exc}")]
    for rel, (status, _) in sorted(dangling.items()):
        if status != "dangling" or rel in report:
            continue
        try:
            rows.append(_adopt_dangling_mirror(repo_dir, rel))
        except OSError as exc:
            rows.append(("refused", rel, f"{type(exc).__name__}: {exc.strerror or exc}"))
    return rows


def _seed_actions(repo_dir: Path, report: dict, files: dict) -> dict:
    """The --adopt action for each seed script the report finds stale, missing or edited.

    An edited seed is kept. A stale or missing one is written only together
    with its groups (see _seed_holds), so before anything is written each
    stale seed is checked as the write checks it, each missing one for
    something in the way of creating it, an ignore rule, or a change git
    still has for it (such as a staged deletion), and each up-to-date file
    of their groups for being untracked or uncommitted; one that fails
    holds its groups back, so every file of a group that changes is tracked
    and clean, or absent from both disk and git. Only a write that fails
    partway (a full disk, an interrupted run) can still leave a group half
    updated: nothing is rolled back. A stale seed mapped to None is written
    by _adopt_seed; a missing one absent from the result, by _adopt_file.
    """
    def status(rel):
        return report.get(rel, (None,))[0]

    actions = {}
    pending = sorted(rel for rel in SEED_FILES if status(rel) in ("stale", "missing"))
    for rel in SEED_FILES:
        if report.get(rel) == ("differs", SEED_EDITED):
            actions[rel] = ("kept", rel, "matches no released copy; not overwritten, so merge template changes by hand")
        elif status(rel) == "missing" and not _path_is_free(repo_dir, rel):
            actions[rel] = ("refused", rel, "something other than a file is at this path; move it aside")
        elif status(rel) == "missing" and _git_ignored(repo_dir, rel):
            # git status would not show a new copy, so a commit could take the
            # rest of its group without it.
            actions[rel] = ("refused", rel, "ignored by git; update the ignore rules before adopting")
        elif status(rel) == "stale":
            try:
                refusal = _seed_refusal(repo_dir, rel, files[rel])
            except OSError as exc:
                refusal = f"{type(exc).__name__}: {exc.strerror or exc}"
            if refusal:
                actions[rel] = ("refused", rel, refusal)
    blocked = {rel for rel, action in actions.items() if action[0] == "refused"}
    touched = set().union(*(group for group in SEED_GROUPS if set(group).intersection(pending)))
    for rel in sorted(touched):
        if status(rel) == "same" and _git_file_state(repo_dir, rel) != "clean":
            # Up to date on disk, but untracked or not what git has committed
            # and staged, so a commit could pair another copy with its group.
            blocked.add(rel)
            actions[rel] = ("kept", rel, "up to date, but untracked or with uncommitted changes, so the files that "
                            "change with it wait; commit it, then re-run --adopt")
        elif status(rel) == "missing" and rel not in actions and _git_file_state(repo_dir, rel) == "dirty":
            # Absent on disk, but git still tracks or stages it: recreating it
            # untracked would leave that change, such as a staged deletion, to
            # be committed beside the rest of its group.
            blocked.add(rel)
            actions[rel] = ("kept", rel, "missing, but git has an uncommitted change to it, such as a deletion, so "
                            "it and the files that change with it wait; commit or undo that change, then re-run --adopt")
    holds = _seed_holds(report, frozenset(blocked))
    for rel in pending:
        if rel in holds and rel not in actions:
            what = "unchanged since an earlier release" if status(rel) == "stale" else "not created"
            actions[rel] = ("kept", rel, f"{what}, but " + _seed_hold_reason(holds[rel]))
        elif status(rel) == "stale":
            actions.setdefault(rel, None)
    return actions


def _path_is_free(repo_dir: Path, rel: str) -> bool:
    """True when nothing is at rel and every folder on the way is a directory
    or absent, so a missing file can be created there."""
    path = repo_dir
    for part in Path(rel).parts:
        path = path / part
        if not os.path.lexists(path):
            return True
        if not stat.S_ISDIR(os.lstat(path).st_mode):
            return False
    return False


def _seed_tag(rel: str, raw: bytes):
    """The release that shipped these exact bytes of a seed script, or None."""
    text = _decode_for_rewrite(raw)
    return None if text is None else SEED_DIGESTS.get(rel, {}).get(_digest(text))


def _seed_refusal(repo_dir: Path, rel: str, expected: str):
    """Why --adopt cannot bring a stale seed script up to date, or None."""
    if not _ANCHORED_WRITES:
        return "this platform cannot write without following symlinks"
    if _git_ignored(repo_dir, rel):
        return "ignored by git"
    if not _git_file_is_clean(repo_dir, rel):
        return "needs the file tracked by git with no uncommitted changes"
    parent = _open_parent(repo_dir, rel, create=False)
    try:
        raw = _read_anchored(parent, Path(rel).name)[0]
    finally:
        os.close(parent)
    if raw != expected.encode("utf-8") and _seed_tag(rel, raw) is None:
        return "edited locally since the scan; not overwritten"
    return None


def _adopt_seed(repo_dir: Path, rel: str, expected: str):
    """Replace a seed script that is still an earlier release's exact copy."""
    name = Path(rel).name
    parent = _open_parent(repo_dir, rel, create=False)
    try:
        raw, identity = _read_anchored(parent, name)
        if raw == expected.encode("utf-8"):
            return None
        tag = _seed_tag(rel, raw)
        if tag is None:
            return ("refused", rel, "edited locally since the scan; not overwritten")
        _replace_anchored(parent, name, expected, identity)
    finally:
        os.close(parent)
    return ("updated", rel, f"unchanged since gh-repo-bootstrapper {tag} shipped it; brought up to date")


def _adopt_dangling_mirror(repo_dir: Path, rel: str):
    """Delete a `.claude/skills` mirror whose skill folder no longer exists.

    Only the mirror shape bootstrap writes (`../../.agents/skills/<name>`) is
    deleted, and only while it still points at nothing; the symlink itself is
    removed, never anything it names.
    """
    if not _ANCHORED_WRITES:
        return ("refused", rel, "this platform cannot write without following symlinks")
    name = Path(rel).name
    if _git_ignored(repo_dir, rel):
        return ("refused", rel, "ignored by git; not deleted")
    state = _git_file_state(repo_dir, rel)
    if state not in ("clean", "untracked"):
        return ("refused", rel, "dangling mirror has uncommitted or staged changes; not deleted")
    parent = _open_parent(repo_dir, rel, create=False)
    try:
        before = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if not stat.S_ISLNK(before.st_mode):
            return ("refused", rel, "no longer a symlink; not deleted")
        target = os.readlink(name, dir_fd=parent)
        if target != f"../../.agents/skills/{name}":
            return ("refused", rel, f"symlink to {target} is not a skill mirror; remove it by hand")
        if not _target_missing(repo_dir / ".agents/skills" / name):
            return ("refused", rel, "its skill folder exists or cannot be checked; not deleted")
        if state == "untracked":
            # Judged after the shape, so "commit it" is only advised for a real mirror.
            return ("refused", rel, "dangling mirror is not tracked by git; not deleted")
        after = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino):
            return ("refused", rel, "changed while --adopt was running")
        os.unlink(name, dir_fd=parent)
    finally:
        os.close(parent)
    return ("deleted", rel, "mirror of a skill that no longer exists")


def _adopt_link(repo_dir: Path, rel: str, status: str, detail, target: str):
    """Publish a declared mirror only when absent; never replace an existing entry."""
    if status == "same":
        return None
    if status != "missing":
        return ("refused", rel, detail or "mirror path already exists")
    if not _ANCHORED_WRITES or os.symlink not in os.supports_dir_fd:
        return ("refused", rel, "this platform cannot create anchored symlinks")
    if _git_ignored(repo_dir, rel):
        return ("refused", rel, "ignored by git")
    created = []
    try:
        parent = _open_parent(repo_dir, rel, create=True, created=created)
        try:
            os.symlink(target, Path(rel).name, dir_fd=parent)
        finally:
            os.close(parent)
    except BaseException:
        _remove_empty_dirs(repo_dir, created)
        raise
    return ("wrote", rel, f"-> {target}")


def _adopt_file(
    repo_dir: Path, rel: str, status: str, detail, expected: str, replace_generated: bool, confirm=None
):
    """The adopt action for one file, or None when it is already aligned.

    Every write goes through a descriptor chain from repo_dir that refuses
    symlinks, and a rewrite is judged on the content read through that chain
    rather than on the earlier scan. Concurrent modification of the
    repository while --adopt runs is outside what these checks can prevent.
    """
    if status == "same":
        return None
    if status in ("symlink", "unreadable", "ignored", "shadowed"):
        return ("refused", rel, detail)
    if status == "own":
        return ("kept", rel, detail)
    if status == "local-modified":
        if _is_yaml(rel):
            if isinstance(detail, str) and detail.endswith("check --type"):
                return ("refused", rel, detail)
            unstamped = _UNSTAMPED_COPY.fullmatch(detail) if isinstance(detail, str) else None
            if unstamped:
                return (
                    "refused", rel,
                    f"an unstamped copy of {unstamped[1]}; delete the file and re-run --adopt "
                    "to write the stamped version",
                )
            return (
                "refused", rel,
                "edited locally; move the repository's own jobs or steps into a separate "
                "workflow, then delete the file to regenerate (see README, Template-owned files)",
            )
        if rel in SCREENSHOT_FILES:
            # Detection only sees the template's copies, so once this file is
            # deleted a re-run without the flag may turn screenshot review off.
            return (
                "refused", rel,
                "edited locally; move the change to ## Project specifics or a repo-owned skill, "
                "then delete the file and re-run with --screenshots to regenerate it (without "
                "the flag, a repository with neither screenshot file drops screenshot review)",
            )
        return (
            "refused", rel,
            "edited locally; move the change to ## Project specifics or a repo-owned skill, "
            "then delete the file to regenerate",
        )
    if not _ANCHORED_WRITES:
        return ("refused", rel, "this platform cannot write without following symlinks")
    name = Path(rel).name
    if status in ("stale", "orphaned"):
        if status == "stale" and not _git_file_is_clean(repo_dir, rel):
            return ("refused", rel, "needs the file tracked by git with no uncommitted changes")
        parent = _open_parent(repo_dir, rel, create=False)
        try:
            raw, identity = _read_anchored(parent, name)
            if status == "orphaned":
                if _git_ignored(repo_dir, rel):
                    return ("refused", rel, "ignored by git; not deleted")
                state = _git_file_state(repo_dir, rel)
                if state == "untracked":
                    # Nothing committed to recover it from, also outside a git repository.
                    return ("refused", rel, "orphaned file is not tracked by git; not deleted")
                if state != "clean":
                    return ("refused", rel, "orphaned file has uncommitted or staged changes; not deleted")
                try:
                    current = raw.decode("utf-8")
                except UnicodeDecodeError:
                    return ("refused", rel, "not UTF-8 text")
                if not stamp_is_valid(current):
                    return ("refused", rel, "orphaned file edited locally; not deleted")
                if _identity(parent, name) != identity:
                    return ("refused", rel, "changed while --adopt was running")
                os.unlink(name, dir_fd=parent)
                return ("deleted", rel, "unmodified orphaned template-owned file")
            current = _decode_for_rewrite(raw)
            if current is None or not raw.endswith(b"\n"):
                return ("refused", rel, "not LF-terminated UTF-8 text; update it by hand")
            current_status = _template_file_state(rel, expected, current)
            if current_status == "same":
                return None
            if current_status != "stale":
                return ("refused", rel, "edited locally since the scan; not overwritten")
            if _git_ignored(repo_dir, rel):
                return ("refused", rel, "ignored by git")
            if rel in TEMPLATE_OWNED_WORKFLOWS:
                problems = _undeclared_inputs(repo_dir, expected)
                if problems:
                    return ("refused", rel, "; ".join(problems) + "; fix that, then re-run --adopt")
                # Keep the repository's action pins; Dependabot moves those.
                template = expected
                expected = _carry_pins(expected, current)
                kept = _kept_pin_differences(template, expected)
            else:
                kept = []
            _replace_anchored(parent, name, expected, identity)
            detail = "stale template-owned file brought up to date"
            if kept:
                detail += "; kept this repository's pins that differ from the template: " + ", ".join(kept)
            return ("updated", rel, detail)
        finally:
            os.close(parent)
    if status == "missing":
        if read_stamp(expected, _is_yaml(rel))[0] is not None and _git_ignored(repo_dir, rel):
            return ("refused", rel, "ignored by git")
        problems = _undeclared_inputs(repo_dir, expected) if rel in TEMPLATE_OWNED_WORKFLOWS else []
        if problems:
            return ("refused", rel, "; ".join(problems) + "; fix that, then re-run --adopt")
        created = []
        try:
            parent = _open_parent(repo_dir, rel, create=True, created=created)
            try:
                _publish_new(parent, name, expected)
            finally:
                os.close(parent)
        except (FileExistsError, NotADirectoryError):
            _remove_empty_dirs(repo_dir, created)
            # The scan found no file here, so whatever blocks the write is a directory or a
            # file in a folder's place; say so as for a seed script. A file that appeared
            # since the scan keeps its error.
            if _path_is_free(repo_dir, rel) or (repo_dir / rel).is_file():
                raise
            return ("refused", rel, "something other than a file is at this path; move it aside")
        except BaseException:
            _remove_empty_dirs(repo_dir, created)
            raise
        return ("wrote", rel, "")
    if rel == ".gitignore":
        return (
            "kept", rel,
            "add these missing entries by hand, where the repository's own rules allow: "
            + ", ".join(detail),
        )
    if rel != "AGENTS.md":
        return ("kept", rel, "differs from the template; not overwritten")
    if not _git_file_is_clean(repo_dir, rel):
        return ("refused", rel, "needs the file tracked by git with no uncommitted changes")
    parent = _open_parent(repo_dir, rel, create=False)
    try:
        raw, identity = _read_anchored(parent, name)
        current = _decode_for_rewrite(raw)
        if current is None:
            return ("refused", rel, "not LF-terminated UTF-8 text; update it by hand")
        rows = compare_agents(expected, current)
        if all(row_status == "same" for row_status, _ in rows):
            return None
        local = [heading for row_status, heading in rows if row_status == "local"]
        if NEXTJS_BLOCK_MOVED in local:
            return ("refused", rel, "move the `next dev`-managed block back to the top of the file first")
        if BYTE_ORDER_MARK in local:
            return ("refused", rel, "remove the byte-order mark at the start of the file first")
        structure = [heading for heading in local if heading.startswith("(")]
        if structure:
            return ("refused", rel, "fix this structure, or move it under ## Project specifics, first: "
                    + "; ".join(structure))
        if local:
            return ("refused", rel, "move these under ## Project specifics first: " + "; ".join(local))
        differing = [heading for row_status, heading in rows if row_status in ("differs", "retired")]
        if differing and not replace_generated:
            return (
                "refused", rel,
                "these generated sections differ from the template — an older template or a local "
                "edit; move local rules under ## Project specifics, then re-run with "
                "--replace-generated-sections: " + "; ".join(differing),
            )
        added = [f"{heading} (missing; will be added)" for row_status, heading in rows
                 if row_status == "missing" and heading != NEXTJS_RULES_BEGIN]
        if differing and confirm is not None and not confirm(differing + added):
            return ("refused", rel, "replacement of differing generated sections was not confirmed")
        _replace_anchored(parent, name, rebuild_agents(expected, current, replace_generated), identity)
    finally:
        os.close(parent)
    replaced = f"; replaced: {'; '.join(differing)}" if differing else ""
    return ("updated", rel, f"generated sections brought up to date; Project specifics kept{replaced}")


_GIT_REPOSITORY_CONTEXT_VARIABLES = frozenset({
    "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE",
    "GIT_PREFIX",
})


def _git_env() -> dict:
    """The environment without inherited repository-context overrides.

    Command-scope config such as GIT_CONFIG_COUNT (e.g. safe.directory) is kept.
    """
    return {k: v for k, v in os.environ.items() if k not in _GIT_REPOSITORY_CONTEXT_VARIABLES}


def existing_repository_name(repo_dir: Path) -> str:
    """The name templates render for an existing repository.

    A linked worktree lives in a directory named for its purpose (for example
    ``.worktrees/app/align``), so its basename is not the repository's name.
    When ``repo_dir`` is the top level of a git working tree, use the name of the
    main checkout that owns the shared ``.git`` directory instead. Anything else
    (not a repository, a subdirectory of one, a worktree whose shared git
    directory is not a ``.git`` directory, git unavailable) keeps the basename.
    """
    # Inherited repository-context overrides would make git describe some other
    # repository; drop only those, so command-scope config such as
    # GIT_CONFIG_COUNT (e.g. safe.directory) still applies.
    env = _git_env()
    try:
        r = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "--show-toplevel", "--git-common-dir"],
            capture_output=True, text=True, check=True, timeout=10, env=env,
        )
        toplevel, common = r.stdout.splitlines()[:2]
    except (OSError, ValueError, subprocess.SubprocessError):
        return repo_dir.name
    # --git-common-dir may be relative to repo_dir; --show-toplevel is absolute.
    toplevel, common = Path(toplevel), (repo_dir / common).resolve()
    if toplevel.resolve() != repo_dir or common.name != ".git":
        return repo_dir.name
    return common.parent.name


def existing_repository_config(args) -> dict:
    """Configuration for --check/--adopt, built without any GitHub calls."""
    if not args.repo_type:
        _die("--type is required with --check and --adopt")
    if args.repo_type == "swift" and not args.scheme:
        _die("--scheme is required for --type swift")
    raw = args.check if args.check is not None else args.adopt
    if not raw.strip():
        _die("--check and --adopt need a non-empty PATH")
    repo_dir = Path(raw).expanduser().resolve()
    if not repo_dir.is_dir():
        _die(f"not a directory: {repo_dir}")
    screenshots, found = bool(args.screenshots), []
    if args.repo_type not in SCREENSHOT_TYPES:
        if screenshots:
            print(SCREENSHOTS_IGNORED)
        screenshots = False
    elif not screenshots:
        # A repository generated before --screenshots existed has the skill and
        # doc; without this, --adopt would delete the stamped skill as orphaned.
        found = [rel for rel in SCREENSHOT_FILES
                 if _template_screenshot_file(repo_dir, rel, args.repo_type)]
        screenshots = bool(found)
    return {
        "name": existing_repository_name(repo_dir),
        "repo_dir": str(repo_dir),
        "repo_type": args.repo_type,
        "postgres": bool(args.postgres),
        "scheme": args.scheme or "",
        "destination": args.destination or "iphone",
        "xcodegen": bool(args.xcodegen),
        "screenshots": screenshots,
        "screenshots_found": found,
    }


def _template_screenshot_file(repo_dir: Path, rel: str, repo_type: str) -> bool:
    """Whether the repository has the template's copy of a screenshot file.

    That is a file whose stamp, valid or edited, is its first non-blank line
    or the first after its frontmatter (even behind a byte-order mark an
    editor added), or an unstamped
    docs/screenshot-review.md whose body is the current one or one a release
    shipped before stamps. A repository's own file at that path, such as its
    own screenshot-review process, does not count, even one that shows the
    stamp further down, in a sentence or a code example, and neither does a
    copy whose stamp was moved out of that line; nor does one behind a
    symlink or one that cannot be read, which --adopt refuses rather than
    deletes either way.
    """
    path = repo_dir / rel
    try:
        if _symlink_in_path(repo_dir, rel) or not path.is_file():
            return False
        text = path.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return False
    if _stamp_slot(text).startswith(STAMP_PREFIX):
        return True
    # Only a doc with no stamp anywhere is compared with the shipped bodies: a
    # stamp moved out of its slot would still compare as the template's copy.
    if rel != SCREENSHOT_REVIEW or has_stamp_text(text):
        return False
    expected = stamp(_screenshot_doc(repo_type))
    return _template_file_state(rel, expected, text) in ("same", "stale")


def screenshot_review_notice(cfg: dict) -> str | None:
    """Why --check or --adopt kept screenshot review on without --screenshots."""
    found = cfg.get("screenshots_found")
    if not found:
        return None
    return (
        f"notice: screenshot review is on without --screenshots, because the repository "
        f"has the template's {' and '.join(found)}; pass --screenshots to silence this. "
        f"To regenerate a screenshot file you deleted, re-run with --screenshots; to drop "
        f"screenshot review, see the README's \"Upgrading to 0.12.0\""
    )


# ---------------------------------------------------------------------------
# Dry-run output
# ---------------------------------------------------------------------------


def print_dry_run(cfg: dict, files: dict):
    sep = "─" * 60
    vis = "private" if cfg["private"] else "public"
    print(f"\n{'=' * 60}")
    print(f"  DRY RUN — {cfg['owner']}/{cfg['name']} ({cfg['repo_type']}, {vis})")
    print(f"  Local path: {cfg['repo_dir']}/")
    if cfg["repo_type"] == "nextjs":
        print(f"  Postgres: {cfg['postgres']}")
    elif cfg["repo_type"] == "swift":
        print(
            f"  Scheme: {cfg.get('scheme', '')}  |  "
            f"Destination: {cfg.get('destination', 'iphone')}  |  "
            f"XcodeGen: {cfg.get('xcodegen', False)}"
        )
    if cfg["repo_type"] in SCREENSHOT_TYPES:
        print(f"  Screenshot review: {screenshot_review(cfg)}")
    print(f"{'=' * 60}\n")

    for path in sorted(files):
        print(f"{sep}\n  {path}\n{sep}")
        for line in files[path].splitlines():
            print(f"  {line}")
        print()

    links = generate_links(cfg)
    for path, target in sorted(links.items()):
        print(f"  {path} -> {target}")
    print(f"Total files: {len(files)}; links: {len(links)}\n")

    print("GitHub variables to configure:")
    print("  RELEASE_PLEASE_CLIENT_ID")

    print("\nGitHub secrets to configure:")
    print("  RELEASE_PLEASE_APP_KEY")


# ---------------------------------------------------------------------------
# GitHub operations
# ---------------------------------------------------------------------------


def create_and_push(cfg: dict, files: dict):
    name = cfg["name"]
    owner = cfg["owner"]
    repo_dir = cfg["repo_dir"]
    full = f"{owner}/{name}"
    vis = "--private" if cfg["private"] else "--public"

    # gather_config() checked this already; the folder may have changed since.
    if err := target_error(repo_dir):
        _die(err)
    # Checked before the remote exists, so a failure leaves nothing to clean up.
    if generate_links(cfg) and (not _ANCHORED_WRITES or os.symlink not in os.supports_dir_fd):
        _die("this platform cannot create anchored symlinks for the .claude/skills mirrors")

    print(f"\nCreating {full} in {repo_dir}/…")
    try:
        _run(["gh", "repo", "create", full, vis])
    except subprocess.CalledProcessError:
        _die(f"failed to create '{full}' — check it doesn't already exist")
    # Record creation immediately so failures in local clone, file generation,
    # commit, or push report the correct remote cleanup/recovery state to the
    # caller.
    cfg["repo_created"] = True

    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        # An absolute path, so a --name such as "-x/app" is never read as a flag.
        _run_with_retry(["gh", "repo", "clone", full, str(Path(repo_dir).absolute())])
    except subprocess.CalledProcessError:
        print("The repository was created on GitHub. Clean up with:", file=sys.stderr)
        print(f"  gh repo delete {full}", file=sys.stderr)
        _die(f"failed to clone into '{repo_dir}'")

    print(f"Writing {len(files)} files to {repo_dir}/…")
    for rel, content in files.items():
        dest = repo_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    for rel, target in generate_links(cfg).items():
        parent = _open_parent(repo_dir, rel, create=True)
        try:
            os.symlink(target, Path(rel).name, dir_fd=parent)
        finally:
            os.close(parent)

    print("Committing and pushing…")
    _run(["git", "-C", str(repo_dir), "add", "."])
    _run(["git", "-C", str(repo_dir), "commit", "-m", "chore: initial repo setup"])
    _run(["git", "-C", str(repo_dir), "push", "--set-upstream", "origin", "HEAD"])
    cfg["files_pushed"] = True


def selected_action_patterns(repo_type: str) -> list:
    """Third-party actions the generated workflows use outside the verified-creator rule.

    `verified_allowed` covers only GitHub Marketplace verified creators, which are
    organizations; these actions are user-owned, so each needs an explicit pattern.
    """
    patterns = ["amannn/action-semantic-pull-request@*"]
    if repo_type == "rust":
        patterns += ["dtolnay/rust-toolchain@*", "Swatinem/rust-cache@*"]
    return patterns


def actions_policy_requests(cfg: dict) -> list:
    """The (endpoint, payload) PUTs that set a repository's Actions policy.

    Only GitHub-owned and Marketplace-verified actions, plus an explicit
    allowlist for third-party actions the generated workflows depend on;
    sha_pinning_required rejects any workflow run that references an action
    by tag or branch rather than a full commit SHA (validate_templates.py's
    check_sha_pinned_actions() enforces the same rule on generated workflows).
    """
    repo = f"{cfg['owner']}/{cfg['name']}"
    requests = [
        (f"repos/{repo}/actions/permissions", {
            "enabled": True,
            "allowed_actions": "selected",
            "sha_pinning_required": True,
        }),
        (f"repos/{repo}/actions/permissions/selected-actions", {
            "github_owned_allowed": True,
            "verified_allowed": True,
            "patterns_allowed": selected_action_patterns(cfg["repo_type"]),
        }),
        # Generated Release Please workflows use a dedicated GitHub App token,
        # and no generated workflow approves pull requests. Keep the default
        # GITHUB_TOKEN read-only and unable to approve reviews.
        (f"repos/{repo}/actions/permissions/workflow", {
            "default_workflow_permissions": "read",
            "can_approve_pull_request_reviews": False,
        }),
    ]
    # Fork PR workflow controls only exist as a distinct API for private
    # repos; public repos gate fork PRs via a separate approval-policy
    # endpoint instead, which isn't part of what was asked for here.
    if cfg["private"]:
        requests.append((f"repos/{repo}/actions/permissions/fork-pr-workflows-private-repos", {
            "run_workflows_from_fork_pull_requests": False,
            "send_write_tokens_to_workflows": False,
            "send_secrets_and_variables": False,
            "require_approval_for_fork_pr_workflows": False,
        }))
    return requests


# What each Actions policy request sets, as reported when configuration stops
# part-way. The allowlist cannot be sent first: GitHub accepts it only once the
# repository's policy is already "selected".
_ACTIONS_POLICY_STEPS = {
    "actions/permissions": "Actions policy (selected actions, SHA pinning)",
    "actions/permissions/selected-actions": "Actions allowlist",
    "actions/permissions/workflow": "default workflow token permissions",
    "actions/permissions/fork-pr-workflows-private-repos": "fork pull request workflow policy",
}


def _actions_policy_step(endpoint: str) -> str:
    return _ACTIONS_POLICY_STEPS[endpoint.split("/", 3)[3]]


def actions_policy_changes(requests: list, current: dict) -> list:
    """(setting, current value, new value) rows where current differs from requests.

    current maps each endpoint to its GET response, or None when it could not
    be read (selected-actions answers 409 unless the policy is already
    "selected"); every setting of an unreadable endpoint counts as a change.
    """
    def comparable(value):
        return sorted(value) if isinstance(value, list) else value

    changes = []
    for endpoint, payload in requests:
        existing = current.get(endpoint) or {}
        for key, new in payload.items():
            if comparable(existing.get(key)) != comparable(new):
                changes.append((key, existing.get(key), new))
    return changes


def configure_repo(cfg: dict, confirm=None):
    """Apply repository settings.

    For a repository this script just created, every setting is applied. With
    --configure-only the repository already exists, so its branch protection
    is never replaced (its required checks must come from its own pull
    requests; see docs/branch-protection-runbook.md), and Actions policy
    changes are listed and applied only when confirm() returns true; with no
    confirm (--non-interactive) they are listed and left unchanged.
    """
    name = cfg["name"]
    owner = cfg["owner"]
    repo = f"{owner}/{name}"
    existing = cfg.get("configure_only", False)
    # Steps run in order and nothing is rolled back, so a failure part-way
    # leaves the earlier ones applied; print_configuration_progress() reports
    # which, from these lists.
    cfg["configure_plan"] = plan = []
    cfg["configured"] = done = []
    if cfg.get("release_please_client_id"):
        plan.append("RELEASE_PLEASE_CLIENT_ID variable")
    if cfg.get("release_please_app_key"):
        plan.append("RELEASE_PLEASE_APP_KEY secret")
    plan.append("merge strategy")
    requests = actions_policy_requests(cfg)
    plan += [_actions_policy_step(endpoint) for endpoint, _ in requests]
    if not existing:
        plan.append("branch protection on main")

    def set_var(key: str, value: str):
        if value:
            print(f"  var    {key}")
            # Value passed via stdin (not --body) to keep it out of the process
            # argument list and away from ps/audit logs.
            subprocess.run(
                ["gh", "variable", "set", key, "--repo", repo],
                input=value.encode(),
                check=True,
            )
            done.append(f"{key} variable")

    def set_secret(key: str, value: str):
        if value:
            print(f"  secret {key}")
            subprocess.run(
                ["gh", "secret", "set", key, "--repo", repo],
                input=value.encode(),
                check=True,
            )
            done.append(f"{key} secret")

    def api(method: str, endpoint: str, payload: dict, *, stderr=None):
        subprocess.run(
            ["gh", "api", endpoint, "--method", method, "--input", "-"],
            input=json.dumps(payload).encode(),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=stderr,
        )

    def get(endpoint: str):
        result = subprocess.run(["gh", "api", endpoint], capture_output=True)
        if result.returncode != 0:
            return None
        try:
            return json.loads(result.stdout)
        except ValueError:
            return None

    print("\nConfiguring repository…")

    # --- variables and secrets ---
    set_var("RELEASE_PLEASE_CLIENT_ID", cfg.get("release_please_client_id", ""))
    set_secret("RELEASE_PLEASE_APP_KEY", cfg.get("release_please_app_key", ""))

    # --- merge strategy, PR branch updates, Projects ---
    # Squash-merge only: merge commits and rebase disabled so every squash
    # commit title = PR title = Conventional Commit subject (Release Please
    # parses this to determine version bumps and changelog entries).
    print("  merge strategy")
    api("PATCH", f"repos/{repo}", {
        "allow_squash_merge": True,
        "allow_merge_commit": False,
        "allow_rebase_merge": False,
        "delete_branch_on_merge": True,
        "squash_merge_commit_title": "PR_TITLE",
        "squash_merge_commit_message": "PR_BODY",
        "allow_update_branch": True,
        "has_projects": True,
    })
    done.append("merge strategy")

    # --- actions permissions ---
    print("  actions permissions")
    if existing:
        # An existing repository may rely on actions or tag pins the generated
        # policy forbids, or on a writable default token; show before changing.
        changes = actions_policy_changes(requests, {endpoint: get(endpoint) for endpoint, _ in requests})
        if not changes:
            print("    already matches the generated policy")
            done += [_actions_policy_step(endpoint) for endpoint, _ in requests]
            requests = []
        else:
            for key, current, new in changes:
                print(f"    {key}: {json.dumps(current)} -> {json.dumps(new)}")
            if confirm is None or not confirm():
                print("    left unchanged")
                cfg["actions_policy_unchanged"] = True
                for endpoint, _ in requests:
                    plan.remove(_actions_policy_step(endpoint))
                requests = []
    for endpoint, payload in requests:
        api("PUT", endpoint, payload)
        done.append(_actions_policy_step(endpoint))

    # --- branch protection on main ---
    if existing:
        print("  branch protection (main): left as is on an existing repository")
        protection = get(f"repos/{repo}/branches/main/protection")
        if protection is None:
            print("    none found, or it could not be read")
        else:
            contexts = (protection.get("required_status_checks") or {}).get("contexts") or []
            print(f"    required checks: {', '.join(contexts) or 'none'}")
        print("    To change it, use the checks this repository's own pull requests report;")
        print("    see docs/branch-protection-runbook.md.")
        return

    # Required status check names are derived from the job names in the
    # workflow files this script just generated, so they are always correct.
    # The GitHub API accepts these before the checks have run; they show as
    # "Expected — Waiting" on PRs and enforce once the first run completes.
    # The policy shape is the operator's item-10 ruling; see
    # branch_protection_payload() and docs/branch-protection-runbook.md.
    print("  branch protection (main)")

    try:
        api("PUT", f"repos/{repo}/branches/main/protection",
            branch_protection_payload(cfg["repo_type"]), stderr=subprocess.PIPE)
        done.append("branch protection on main")
    except subprocess.CalledProcessError as exc:
        cfg["branch_protection_failed"] = True
        stderr_text = (exc.stderr or b"").decode(errors="replace").strip()
        if "upgrade to github pro" in stderr_text.lower():
            cfg["branch_protection_plan_limited"] = True
            print("  warning: branch protection requires GitHub Pro for private repos; skipping.")
        else:
            print("  warning: branch protection could not be set automatically.")
            if stderr_text:
                print(f"    {stderr_text}")


def print_configuration_progress(cfg: dict):
    """After configure_repo() stopped part-way, say what was applied and what remains."""
    plan, done = cfg.get("configure_plan", []), cfg.get("configured", [])
    remaining = [step for step in plan if step not in done]
    if not remaining:
        return
    out = sys.stderr
    print("Configuration stopped part-way; nothing applied before the failure was undone.", file=out)
    print(f"  Applied:     {', '.join(done) or 'nothing'}", file=out)
    print(f"  Not applied: {', '.join(remaining) or 'nothing'}", file=out)
    if "Actions policy (selected actions, SHA pinning)" in done and "Actions allowlist" in remaining:
        print("  Actions are limited to the selected policy without its allowlist, so workflows", file=out)
        print("  using third-party actions (including the PR title check) cannot run yet.", file=out)
    # The interpreter and script as actually run, so the command works from
    # any directory.
    retry = [sys.executable, str(Path(__file__).resolve()), "--configure-only", "--name", cfg["name"],
             "--type", cfg["repo_type"], "--org", cfg["owner"]]
    if cfg.get("scheme"):
        retry += ["--scheme", cfg["scheme"]]
    print("  Apply the rest by running this interactively, which asks before changing the", file=out)
    print(f"  Actions policy:\n    {shlex.join(retry)}", file=out)
    print("  Press Enter at a credential prompt to keep a value already applied.", file=out)
    if "branch protection on main" in remaining:
        print("  --configure-only leaves branch protection alone; set it as", file=out)
        print("  docs/branch-protection-runbook.md describes.", file=out)


def print_success(cfg: dict):
    name = cfg["name"]
    owner = cfg["owner"]
    print(f"\n{'=' * 60}")
    print(f"  https://github.com/{owner}/{name}")
    print(f"{'=' * 60}")

    missing = []
    if not cfg.get("release_please_client_id"):
        missing.append("RELEASE_PLEASE_CLIENT_ID (variable)")
    if not cfg.get("release_please_app_key"):
        missing.append("RELEASE_PLEASE_APP_KEY (secret)")
    if cfg.get("branch_protection_failed"):
        if cfg.get("branch_protection_plan_limited"):
            missing.append("branch protection on main (requires GitHub Pro for private repos)")
        else:
            missing.append("branch protection on main (failed — see warning above for details)")
    if cfg.get("actions_policy_unchanged"):
        missing.append("Actions policy (left unchanged; re-run --configure-only interactively to apply it)")

    if missing:
        print("\n  Still needs manual setup:")
        for item in missing:
            print(f"    {item}")

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _flush_stdout():
    """Flush stdout inside the caller's try, so a reader that already left is noticed there."""
    if sys.stdout is not None:  # closed before the run began (`>&-`): print() is a no-op
        sys.stdout.flush()


def _stdout_reader_left():
    """Quiet the rest of a run whose stdout reader has gone, as in `--dry-run | head`.

    Python flushes stdout again when it exits and would fail the same way, so
    point the stream at the null device first (the Python docs' note on
    SIGPIPE).
    """
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(devnull, sys.stdout.fileno())
        finally:
            os.close(devnull)
    except (OSError, ValueError):
        pass  # stdout is not a real descriptor, so there is no pipe to close


def main():
    # Template text carries em dashes; a non-UTF-8 locale must not crash output.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    args = parse_args()

    # --- existing local repositories: compare or adopt, no GitHub calls ---
    if args.replace_generated_sections and args.adopt is None:
        _die("--replace-generated-sections is only used with --adopt")
    if args.check is not None or args.adopt is not None:
        if args.configure_only or args.dry_run:
            _die("--check and --adopt cannot be combined with --configure-only or --dry-run")
        # These modes skip check_dependencies(), which also needs gh, but they
        # ask git which files are tracked, ignored or changed.
        if not shutil.which("git"):
            _die("git not found — --check and --adopt need git; install it and try again")
        cfg = existing_repository_config(args)
        repo_dir = Path(cfg["repo_dir"])
        files = generate_files(cfg)
        if args.check:
            report = compare_repository(repo_dir, files)
            try:
                aligned = print_repository_report(repo_dir, cfg, report)
                _flush_stdout()
            except BrokenPipeError:
                _stdout_reader_left()
                # The exit status still says whether the repository is aligned.
                aligned = all(status == "same" for status, _ in report.values())
            sys.exit(0 if aligned else 1)
        print(f"\nAdopting {repo_dir} as '{cfg['repo_type']}'")
        notice = screenshot_review_notice(cfg)
        if notice:
            print(f"  {notice}")
        def confirm(sections):
            print("\nAGENTS.md: these generated sections differ from the template and will be")
            print("replaced with its text, are retired and will be removed, or are missing and")
            print("will be added (the file is tracked, so git diff shows the change):")
            for heading in sections:
                print(f"  {heading}")
            return args.non_interactive or prompt_yn("Replace them?", default=False)

        actions = adopt_repository(
            repo_dir, files, replace_generated=args.replace_generated_sections, confirm=confirm
        )
        for action, rel, detail in actions:
            print(f"  {action:<8} {rel}" + (f" — {detail}" if detail else ""))
        if any(action not in ("refused", "kept") for action, _, _ in actions):
            print("\nReview the changes (git diff), then commit them on a branch.")
        else:
            print("\nNothing was changed.")
        sys.exit(1 if any(action == "refused" for action, _, _ in actions) else 0)

    if not args.dry_run:
        check_dependencies()
    try:
        cfg = gather_config(args)
    except BrokenPipeError:
        if not args.dry_run or args.configure_only:
            raise  # a creating or configuring run must not end quietly
        _stdout_reader_left()  # a dry run writes nothing, so leaving during its questions loses nothing
        if not args.non_interactive:
            return  # the remaining questions were never seen, so there are no answers to check
        cfg = gather_config(args)  # asks nothing, so its refusals still decide the exit status

    # --- configure-only: apply GitHub config to an existing repo ---
    if cfg["configure_only"]:
        if cfg["dry_run"]:
            _die("--configure-only cannot be combined with --dry-run")
        full = f"{cfg['owner']}/{cfg['name']}"
        if subprocess.run(["gh", "repo", "view", full], capture_output=True).returncode != 0:
            _die(f"repository '{full}' not found — verify the name and org")
        print(f"\nAbout to configure: {full} ({cfg['repo_type']})")
        print("  Applies: Release Please credentials, squash-merge only (squash commit title and")
        print("    message from the PR), delete branch on merge, update-branch button, Projects")
        print("  Shows Actions policy changes and asks before applying them")
        print("  Leaves branch protection on main unchanged")
        print("  Note: file generation is skipped — commit CLAUDE.md and AGENTS.md separately if needed")
        if not args.non_interactive:
            if not prompt_yn("\nProceed?", default=True):
                print("Aborted.")
                return
        def confirm_actions_policy():
            return prompt_yn("    Apply these Actions policy changes?", default=False)

        try:
            configure_repo(cfg, confirm=None if args.non_interactive else confirm_actions_policy)
            print_success(cfg)
        except subprocess.CalledProcessError as exc:
            print(f"\nerror: command failed: {exc.cmd}", file=sys.stderr)
            print_configuration_progress(cfg)
            sys.exit(1)
        return

    # --- normal flow: create repo, generate files, configure ---
    files = generate_files(cfg)

    if cfg["dry_run"]:
        try:
            print_dry_run(cfg, files)
            _flush_stdout()
        except BrokenPipeError:
            _stdout_reader_left()  # nothing is written or created, so leaving early loses nothing
        return

    vis = "private" if cfg["private"] else "public"
    print(f"\nAbout to create: {cfg['owner']}/{cfg['name']} ({cfg['repo_type']}, {vis})")
    print(f"  Local path: {cfg['repo_dir']}/")
    extras = []
    if cfg["repo_type"] == "nextjs" and cfg["postgres"]:
        extras.append("Postgres tests")
    if screenshot_review(cfg):
        extras.append("screenshot review")
    if extras:
        print(f"  Extras: {', '.join(extras)}")
    print(f"  Files:  {len(files)}")

    if not args.non_interactive:
        if not prompt_yn("\nProceed?", default=True):
            print("Aborted.")
            return

    full = f"{cfg['owner']}/{cfg['name']}"
    cfg["repo_created"] = False
    cfg["files_pushed"] = False
    try:
        create_and_push(cfg, files)
        configure_repo(cfg)
        print_success(cfg)
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = (
            f"command failed: {exc.cmd}"
            if isinstance(exc, subprocess.CalledProcessError)
            else str(exc)
        )
        print(f"\nerror: {detail}", file=sys.stderr)
        if cfg["files_pushed"]:
            # Configuration failed after a successful push. Don't delete the repo.
            print("Files were pushed successfully.", file=sys.stderr)
            print_configuration_progress(cfg)
        elif cfg["repo_created"]:
            print("The GitHub repository was created, but local setup or push failed.", file=sys.stderr)
            print("Inspect the cloned directory and retry, or clean up with:", file=sys.stderr)
            print(f"  gh repo delete {full}", file=sys.stderr)
        else:
            print("If the repository was created on GitHub, clean up with:", file=sys.stderr)
            print(f"  gh repo delete {full}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
