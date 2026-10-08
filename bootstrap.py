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

Requirements: Python 3.9+, gh CLI (authenticated), git
"""

from __future__ import annotations

import argparse
import difflib
import errno
import getpass
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import NoReturn

# ---------------------------------------------------------------------------
# Startup version check
# ---------------------------------------------------------------------------

if sys.version_info < (3, 9):
    sys.exit(f"error: Python 3.9+ required (got {sys.version})")

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
NEXTJS_BASELINE_REVIEW_WORKFLOW = ".github/workflows/baseline-review.yml"
SCREENSHOT_REVIEW = "docs/screenshot-review.md"
README = "README.md"
AGENTS_SIZE_WARN_BYTES = 20_000
STAMP_PREFIX = "<!-- gh-repo-bootstrapper: template-owned; sha256="
_STAMP_RE = re.compile(r"^" + re.escape(STAMP_PREFIX) + r"([0-9a-f]{64}) -->$")
_GENERAL_SKILLS = (
    "pull-requests", "worktrees-and-scratch", "verify-external-claims",
    "fresh-eyes-review", "delegation",
)
TEMPLATE_SKILLS: dict[str, tuple[str, ...]] = {
    "simple": _GENERAL_SKILLS,
    "python": _GENERAL_SKILLS + ("local-validation-python",),
    "rust": _GENERAL_SKILLS + ("local-validation-rust",),
    "swift": _GENERAL_SKILLS + ("local-validation-swift", "screenshot-review"),
    "nextjs": _GENERAL_SKILLS + (
        "local-validation-nextjs", "baseline-process", "screenshot-review",
    ),
}
_TEMPLATE_AGENTS = {
    ".claude/agents/fresh-eyes-reviewer.md": "agents/claude-fresh-eyes-reviewer.md",
    ".opencode/agents/fresh-eyes-reviewer.md": "agents/opencode-fresh-eyes-reviewer.md",
}


def template_owned_paths(cfg) -> list[str]:
    """The complete template-owned manifest for this configuration."""
    paths = [f".agents/skills/{name}/SKILL.md" for name in TEMPLATE_SKILLS[cfg["repo_type"]]]
    paths += list(_TEMPLATE_AGENTS) + ["docs/branch-protection-runbook.md"]
    if cfg["repo_type"] in ("nextjs", "swift"):
        paths.append(SCREENSHOT_REVIEW)
    return paths


def _skill_mirrors(names) -> dict[str, str]:
    return {f".claude/skills/{name}": f"../../.agents/skills/{name}" for name in names}


def generate_links(cfg) -> dict[str, str]:
    """Claude's relative directory mirrors of the shared skills."""
    return _skill_mirrors(TEMPLATE_SKILLS[cfg["repo_type"]])


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_stamp(text: str) -> tuple[str | None, str]:
    """Return the single stamp digest and the exact body, without its line."""
    lines = text.splitlines(keepends=True)
    matches = [(i, _STAMP_RE.fullmatch(line.rstrip("\r\n"))) for i, line in enumerate(lines)]
    stamps = [(i, match.group(1)) for i, match in matches if match]
    if len(stamps) != 1:
        return None, text
    index, digest = stamps[0]
    return digest, "".join(lines[:index] + lines[index + 1:])


def stamp(text: str) -> str:
    """Stamp a body, after closed YAML frontmatter or before ordinary Markdown."""
    _, body = read_stamp(text)
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


def stamp_is_valid(text: str) -> bool:
    digest, body = read_stamp(text)
    return digest is not None and digest == _digest(body)


# Rebuilt by compute_legacy_digests(), from the vX.Y.Z release tags through
# LEGACY_LAST_TAG.
LEGACY_TEMPLATE_DIGESTS: dict[str, frozenset[str]] = {
    "docs/branch-protection-runbook.md": frozenset({
        "1f4ce79e3a984e4e76dfdee4b3ca655c6911825eabee6a92dd5a3c76a9526dc1",
        "6639309aab33a20e8b514470e3aa34e3964d8f6bd0118ce7b8c44b940752546d",
        "6d85cc1c360e438c258a11085b387435b8eaf3667a1201fb895b0a24f6d4a494",
        "0393321b93da4028ce9becf74df5af865da24256dee0f035b3a31a8d378f188b",
    }),
    "docs/screenshot-review.md": frozenset({
        "14682e234d008988775c61f361f63e55f6b6d53e05fbc97311919d01aab72948",
        "705bc3cd766b0bdcbf292f1db676f209aebcd30815bf2cde9c25b354df63e884",
        "6382eea5102c54492dbe4f80f942262759dea40296ef2c629065a9efcfc9bfca",
    }),
}


# Ownership stamps arrived in v0.6.0, so later releases ship stamped docs that
# stamp_is_valid() classifies. Only renders through this tag can appear
# unstamped, and stopping here keeps later doc edits from changing the table.
LEGACY_LAST_TAG = (0, 6, 0)


def _legacy_tags() -> list[str] | None:
    """Release tags through LEGACY_LAST_TAG, oldest first; None when git cannot list them."""
    env = _git_env()
    try:
        result = subprocess.run(
            ["git", "-C", str(TEMPLATES_DIR.parent), "tag", "--list", "v*"],
            capture_output=True, text=True, check=True, env=env,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    tags = [tag for tag in result.stdout.splitlines() if re.fullmatch(r"v\d+\.\d+\.\d+", tag)]
    versions = {tag: tuple(int(part) for part in tag[1:].split(".")) for tag in tags}
    return sorted((tag for tag in tags if versions[tag] <= LEGACY_LAST_TAG), key=versions.__getitem__)


def _legacy_template_bodies() -> dict[str, list[str]]:
    """Render historical owned docs; new skills and agents have no legacy copies.

    Without git or release tags (a copy without .git, a shallow clone) there
    is nothing to render: a one-line notice goes to stderr and the result is
    empty, so callers skip the legacy diff instead of failing.
    """
    repo = TEMPLATES_DIR.parent
    env = _git_env()
    refs = _legacy_tags()
    if not refs:
        print(f"notice: no git release tags in {repo}; skipped the diff against legacy template docs",
              file=sys.stderr)
        return {}
    bodies = {}
    for ref in refs:
        def source(name):
            result = subprocess.run(
                ["git", "-C", str(repo), "show", f"{ref}:templates/{name}"],
                capture_output=True, check=False, env=env,
            )
            return result.stdout.decode("utf-8") if result.returncode == 0 else None

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


def compute_legacy_digests() -> dict:
    """Rebuild the checked-in legacy table using the historical template renders."""
    return {
        path: frozenset(_digest(body) for body in bodies)
        for path, bodies in _legacy_template_bodies().items()
    }


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
    return path.read_text()


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


def parse_args():
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
    return p.parse_args()


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


def prompt_choice(question: str, choices: list) -> str:
    for i, c in enumerate(choices, 1):
        print(f"  {i}. {c}")
    while True:
        try:
            raw = input(f"{question} (1-{len(choices)}): ").strip()
        except EOFError:
            _die("unexpected end of input")
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            pass
        print(f"  Enter a number from 1 to {len(choices)}.")


def prompt_secret(question: str) -> str:
    if not sys.stdin.isatty():
        # No real terminal attached (piped/redirected input) — getpass
        # always tries /dev/tty first, which would ignore this input
        # entirely and block on a real terminal, or silently misread
        # unrelated input via its own stdin fallback. Read a normal,
        # visible line instead, matching prompt()'s behavior.
        try:
            return input(f"{question}: ").strip()
        except EOFError:
            _die("unexpected end of input")
    try:
        value = getpass.getpass(f"{question}: ")
    except EOFError:
        _die("unexpected end of input")
    return value.strip()


def prompt_optional(label: str, secret: bool = False) -> str:
    hint = "press Enter to skip and configure later"
    if secret:
        hint = f"hidden, {hint}"
    value = (prompt_secret if secret else prompt)(f"  {label} ({hint})")
    if not value:
        print("    (skipped)")
    return value


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


def split_name_and_path(raw: str) -> tuple:
    """Split a bare name or relative/absolute path into (repo_name, local_dir)."""
    local_dir = Path(raw).expanduser()
    return local_dir.name, local_dir


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
    raw_name = args.name
    if not raw_name:
        if ni:
            _die("--name is required in --non-interactive mode")
        print(
            "\nRepository name — created as a new directory in the current "
            "directory by default.\nTo create it elsewhere, enter a relative "
            "or absolute path instead (e.g. ../my-app or /Users/you/code/my-app)."
        )
        raw_name = prompt_validated("Repository name", validate_name_or_path)
    else:
        err = validate_name_or_path(raw_name)
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
                destination = prompt_choice("Select destination", ["iphone", "ipad", "macos"])
        xcodegen = args.xcodegen
        if not ni and not args.xcodegen:
            xcodegen = prompt_yn("Generate the Xcode project from project.yml?", default=False)

    else:  # python, rust, simple
        if args.postgres:
            print("warning: --postgres is only used with --type nextjs; ignoring")
        if args.scheme:
            print("warning: --scheme is only used with --type swift; ignoring")
        if args.destination:
            print("warning: --destination is only used with --type swift; ignoring")
        if args.xcodegen:
            print("warning: --xcodegen is only used with --type swift; ignoring")

    # --- GitHub variables and secrets ---
    # Non-interactive: read from environment variables.
    # Interactive: prompt the user (skipped entirely in dry-run).
    release_please_client_id = ""
    release_please_app_key = ""

    if ni:
        release_please_client_id = os.environ.get("RELEASE_PLEASE_CLIENT_ID", "")
        release_please_app_key = os.environ.get("RELEASE_PLEASE_APP_KEY", "")
    elif not dry:
        print("\nGitHub App — Release Please:")
        release_please_client_id = prompt_optional("RELEASE_PLEASE_CLIENT_ID")
        release_please_app_key = prompt_optional("RELEASE_PLEASE_APP_KEY", secret=True)


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
    if repo_type == "nextjs":
        cfg = {
            "$schema": schema,
            "include-component-in-tag": False,
            "packages": {".": {"release-type": "node", "package-name": name}},
        }
    else:  # simple, python, swift, rust — all use release-type: simple
        cfg = {
            "$schema": schema,
            "include-component-in-tag": False,
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
        "| change screenshots or captured views | `screenshot-review` |\n",
    ),
    "swift": (
        "| run local validation | `local-validation-swift` |\n",
        "| change screenshots or captured views | `screenshot-review` |\n",
    ),
    "rust": ("| run local validation | `local-validation-rust` |\n",),
    "python": ("| run local validation | `local-validation-python` |\n",),
}


def generate_files(cfg: dict) -> dict:
    name = cfg["name"]
    repo_type = cfg["repo_type"]
    postgres = cfg["postgres"]
    destination = cfg.get("destination") or "iphone"
    xcodegen = bool(cfg.get("xcodegen"))

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
        screenshot_guidance = _load("docs-screenshot-review-nextjs.md")
    elif repo_type == "python":
        files[".github/workflows/release-please.yml"] = _load("release-please-gated.yml")
        files[".github/workflows/ci.yml"] = _load("ci.yml")
        files[".github/workflows/test.yml"] = _load("test-python.yml")
        files[".github/dependabot.yml"] = _load("dependabot-python.yml")
        files[".python-version"] = _load(".python-version")
        screenshot_guidance = ""

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
        screenshot_guidance = _load("docs-screenshot-review-swift.md")

    elif repo_type == "rust":
        files[".github/workflows/release-please.yml"] = _load("release-please-gated.yml")
        files[".github/workflows/ci.yml"] = _load("ci.yml")
        files[".github/workflows/test.yml"] = _load("test-rust.yml")
        # Like Swift: a new Rust repo has no Cargo.toml yet, so a cargo
        # Dependabot entry would be a permanently failing updater until one
        # exists. The generated AGENTS.md says when to add it.
        files[".github/dependabot.yml"] = _load("dependabot-actions-only.yml")
        screenshot_guidance = ""

    else:  # simple
        files[".github/workflows/release-please.yml"] = _load("release-please-simple.yml")
        files[".github/dependabot.yml"] = _load("dependabot-actions-only.yml")
        screenshot_guidance = ""

    if repo_type in ("nextjs", "swift"):
        files[SCREENSHOT_REVIEW] = _compose(
            _load("docs-screenshot-review-common.md"),
            "PLATFORM_GUIDANCE",
            screenshot_guidance,
        )

    # Every generated repo is born with the runbook for the protection applied
    # below — all types get release-please, pr-title-check and required checks.
    files["docs/branch-protection-runbook.md"] = _load("docs-branch-protection-runbook.md")

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
    agents = _compose(agents, "SKILL_ROWS_TYPE", "".join(_TYPE_SKILL_ROWS.get(repo_type, ())))
    if repo_type in ("nextjs", "swift"):
        # The screenshot privacy and pre-commit review gates stay in the hub;
        # the fragment points at the screenshot-review skill for the process.
        agents = _compose(
            agents, "SCREENSHOT_REVIEW_REF", _load("AGENTS-screenshot-review-ref-skill.md")
        )
    else:
        # No screenshot-review skill for this type: keep the generic rule inline.
        agents = _compose(
            agents, "SCREENSHOT_REVIEW_REF", _load("AGENTS-screenshot-review-ref-generic.md")
        )
    files["AGENTS.md"] = agents
    files[".gitignore"] = _load(".gitignore")
    if repo_type == "swift" and xcodegen:
        files[".gitignore"] += "\n# XcodeGen output (project.yml is the source of truth)\n*.xcodeproj/\n"
    if repo_type == "rust":
        files[".gitignore"] += "\n# Rust build output\n/target/\n"
    files["release-please-config.json"] = _release_please_config(name, repo_type)
    files[".release-please-manifest.json"] = json.dumps({".": "0.1.0"}, indent=2) + "\n"

    for skill in TEMPLATE_SKILLS[repo_type]:
        content = _load(f"skills/{skill}/SKILL.md")
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
        files[path] = stamp(files[path])
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
# A heading of any level behind blockquote or list markers (`> ## Ours`,
# `- ## Ours`) is a subsection too, not text inside a generated paragraph.
# Blockquote markers, and list markers only when followed by whitespace — a
# `---` underline must not be read as three list markers.
_CONTAINER_PREFIX_RE = re.compile(r"^[ \t]*(?:(?:>|(?:[-*+]|\d{1,9}[.)])(?=[ \t]))[ \t]*)*")
_CONTAINED_HEADING_RE = re.compile(r"^[ \t]*(?:(?:>|[-*+]|\d{1,9}[.)])[ \t]*)+#{1,6}(?!#)[ \t]+\S")
_SETEXT_UNDERLINE_RE = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
_FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")
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

    Setext headings (a line underlined with === or ---) and a code fence left
    open at the end of the file make section boundaries uncertain.

    This is a line-level approximation, not a CommonMark block parser, and it
    errs towards reporting: a `---` thematic break after a list item or inside
    nested quotes or indented code can be flagged. A false report only makes
    --adopt refuse and ask for a manual edit; it never loses text.
    """
    rows, left_open = _markdown_scan(text)
    problems, previous = [], ""
    for _, raw_line, in_fence in rows:
        # Judge blockquote and list content by what follows its markers, so
        # `> Ours` over `> ----` counts as a setext heading too.
        line = _CONTAINER_PREFIX_RE.sub("", raw_line)
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


def _split_project_specifics(text: str) -> tuple:
    """(generated part, repository-owned part or None) of an AGENTS.md.

    Everything from the `## Project specifics` heading to the end of the file
    belongs to the repository.
    """
    for offset, line, in_fence in _markdown_lines(text):
        if not in_fence and line.strip() == PROJECT_SPECIFICS:
            return text[:offset], text[offset:]
    return text, None


def compare_agents(expected: str, actual: str) -> list:
    """Section-level comparison of a repository AGENTS.md with the rendered one.

    Returns (status, heading) rows. Statuses: same, differs, missing (a
    generated section the repository lacks), and local — repository text that
    --adopt would otherwise overwrite: a section, or a level-3+ subsection
    inside a generated section, outside `## Project specifics`, or structure
    the parser does not model. The `next dev` block and everything from
    `## Project specifics` on are repository-owned and never compared.
    """
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
    for heading, body in exp_sections:
        found = actual_by_heading.get(heading)
        if not found:
            rows.append(("missing", heading))
        elif len(found) == 1 and found[0].strip() == body.strip():
            rows.append(("same", heading))
        else:
            rows.append(("differs", heading))
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
    if _nextjs_rules_block(expected) and not _nextjs_rules_block(actual):
        rows.append(("missing", NEXTJS_RULES_BEGIN))
    return rows


def rebuild_agents(expected: str, actual: str, replace_generated: bool = False) -> str:
    """The rendered AGENTS.md with the repository's own parts carried over.

    Keeps the repository's `## Project specifics` section (and everything after
    it) and its `next dev`-managed block. Callers must first confirm that
    compare_agents() reports no `local` rows, or repository text is lost.
    """
    rows = compare_agents(expected, actual)
    retired = [heading for status, heading in rows if status == "retired"]
    local = [heading for status, heading in rows if status == "local"]
    if retired and (local or not replace_generated):
        raise ValueError("cannot drop retired sections: " + "; ".join(local or retired))
    generated, template_owned = _split_project_specifics(expected)
    _, owned = _split_project_specifics(actual)
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


def _symlink_in_path(repo_dir: Path, rel: str, links: dict = None) -> bool:
    """Refuse symlinks except a declared mirror at the final component."""
    current = repo_dir
    parts = Path(rel).parts
    for index, part in enumerate(parts):
        current = current / part
        if current.is_symlink():
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


def _template_file_state(rel: str, expected: str, actual: str) -> str:
    """Classify exact bytes, not newline-normalized text."""
    digest, body = read_stamp(actual)
    if digest is None:
        if STAMP_PREFIX in actual:
            return "local-modified"
        if rel.startswith(".agents/skills/"):
            return "shadowed"
        if body == read_stamp(expected)[1] or _digest(body) in LEGACY_TEMPLATE_DIGESTS.get(rel, ()):
            return "stale"
        return "local-modified"
    if digest != _digest(body):
        return "local-modified"
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


def _extra_owned_files(repo_dir: Path, files: dict) -> dict:
    """Find orphaned stamped files and name collisions, without following links."""
    extras = {}
    skill_paths = {
        Path(path).parent.name: path for path in files
        if path.startswith(".agents/skills/") and path.endswith("/SKILL.md")
    }
    for base in (".agents/skills", ".claude/agents", ".opencode/agents"):
        if _symlink_in_path(repo_dir, base):
            continue
        for directory, dirs, names in os.walk(repo_dir / base, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not (Path(directory) / d).is_symlink())
            for name in sorted(names):
                path = Path(directory) / name
                rel = path.relative_to(repo_dir).as_posix()
                if rel in files or path.is_symlink() or not path.is_file():
                    continue
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
                if stamped:
                    extras[rel] = (
                        ("ignored", "ignored by git; not deleted")
                        if _git_ignored(repo_dir, rel) else ("orphaned", None)
                    )
    return extras


def compare_repository(repo_dir: Path, files: dict, links: dict = None) -> dict:
    """Per-file status of an existing repository against the rendered files."""
    report = {}
    links = _links_for_files(files) if links is None else links
    legacy_bodies = None
    for rel, expected in files.items():
        path = repo_dir / rel
        if _symlink_in_path(repo_dir, rel):
            report[rel] = ("symlink", "a symlink in this path; not compared or written")
            continue
        owned = read_stamp(expected)[0] is not None
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
            detail = None
            if status == "local-modified" and read_stamp(actual)[0] is None and rel in LEGACY_TEMPLATE_DIGESTS:
                if legacy_bodies is None:
                    legacy_bodies = _legacy_template_bodies()
                candidates = legacy_bodies.get(rel, [])
                if candidates:
                    nearest = max(candidates, key=lambda body: difflib.SequenceMatcher(
                        None, body.splitlines(), actual.splitlines(), autojunk=False
                    ).ratio())
                    detail = "".join(difflib.unified_diff(
                        nearest.splitlines(keepends=True), actual.splitlines(keepends=True),
                        fromfile=f"legacy/{rel}", tofile=rel,
                    ))
            report[rel] = (status, detail)
        elif actual == expected:
            report[rel] = ("same", None)
        elif rel == "AGENTS.md":
            rows = compare_agents(expected, actual)
            aligned = all(row_status == "same" for row_status, _ in rows)
            report[rel] = ("same", None) if aligned else ("differs", rows)
        elif rel == ".gitignore":
            missing = _missing_lines(expected, actual)
            report[rel] = ("differs", missing) if missing else ("same", None)
        elif rel == "CLAUDE.md" and "@AGENTS.md" not in actual.split():
            report[rel] = ("differs", "does not import AGENTS.md (no `@AGENTS.md` line)")
        else:
            report[rel] = ("differs", None)
    report.update(_extra_owned_files(repo_dir, files))
    for rel, target in links.items():
        path = repo_dir / rel
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
    return report


RETIRED_TEXT_PREVIEW_LINES = 3


def _retired_section_text(repo_dir: Path, rows: list) -> dict[str, list[str]]:
    """Non-blank lines under each retired heading of the repository's AGENTS.md.

    --replace-generated-sections drops a retired section whole, so --check
    shows its text first: a repository rule added there would be lost too.
    """
    retired = {heading for row_status, heading in rows if row_status == "retired"}
    if not retired or _symlink_in_path(repo_dir, "AGENTS.md"):
        return {}
    try:
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
    aligned = True
    for rel, (status, detail) in sorted(report.items()):
        if status != "same":
            aligned = False
        print(f"  {status:<8} {rel}")
        if rel == "AGENTS.md" and isinstance(detail, list):
            retired_text = _retired_section_text(repo_dir, detail)
            for row_status, heading in detail:
                if row_status != "same":
                    hint = "  → move under ## Project specifics" if row_status == "local" else ""
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
    if not _symlink_in_path(repo_dir, "AGENTS.md") and agents.is_file():
        size = agents.stat().st_size
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
            parent = _open_parent(repo_dir, rel_dir, create=False)
            try:
                os.rmdir(Path(rel_dir).name, dir_fd=parent)
            finally:
                os.close(parent)
        except OSError:
            pass


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
    files, and deletes digest-valid orphaned template-owned files. Locally
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
    for rel, (status, detail) in sorted(report.items()):
        try:
            if rel in mirrors:
                action = _adopt_link(repo_dir, rel, status, detail, mirrors[rel])
            else:
                action = _adopt_file(repo_dir, rel, status, detail, files.get(rel), replace_generated, confirm)
        except OSError as exc:
            action = ("refused", rel, f"{type(exc).__name__}: {exc.strerror or exc}")
        if action:
            actions.append(action)
    return actions


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
    if status == "local-modified":
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
                if _git_file_state(repo_dir, rel) == "dirty":
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
            _replace_anchored(parent, name, expected, identity)
            return ("updated", rel, "stale template-owned file brought up to date")
        finally:
            os.close(parent)
    if status == "missing":
        if read_stamp(expected)[0] is not None and _git_ignored(repo_dir, rel):
            return ("refused", rel, "ignored by git")
        created = []
        try:
            parent = _open_parent(repo_dir, rel, create=True, created=created)
            try:
                _publish_new(parent, name, expected)
            finally:
                os.close(parent)
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
        if differing and confirm is not None and not confirm(differing):
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
    return {
        "name": existing_repository_name(repo_dir),
        "repo_dir": str(repo_dir),
        "repo_type": args.repo_type,
        "postgres": bool(args.postgres),
        "scheme": args.scheme or "",
        "destination": args.destination or "iphone",
        "xcodegen": bool(args.xcodegen),
    }


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

    if repo_dir.exists() and any(repo_dir.iterdir()):
        _die(f"target directory '{repo_dir}' already exists and is not empty")
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
        _run_with_retry(["gh", "repo", "clone", full, str(repo_dir)])
    except subprocess.CalledProcessError:
        print("The repository was created on GitHub. Clean up with:", file=sys.stderr)
        print(f"  gh repo delete {full}", file=sys.stderr)
        _die(f"failed to clone into '{repo_dir}'")

    print(f"Writing {len(files)} files to {repo_dir}/…")
    for rel, content in files.items():
        dest = repo_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
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


def configure_repo(cfg: dict):
    name = cfg["name"]
    owner = cfg["owner"]
    repo = f"{owner}/{name}"

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

    def set_secret(key: str, value: str):
        if value:
            print(f"  secret {key}")
            subprocess.run(
                ["gh", "secret", "set", key, "--repo", repo],
                input=value.encode(),
                check=True,
            )

    def api(method: str, endpoint: str, payload: dict, *, stderr=None):
        subprocess.run(
            ["gh", "api", endpoint, "--method", method, "--input", "-"],
            input=json.dumps(payload).encode(),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=stderr,
        )

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

    # --- actions permissions ---
    # Only GitHub-owned and Marketplace-verified actions, plus an explicit
    # allowlist for third-party actions this repo's own workflows depend on
    # (amannn/action-semantic-pull-request, used by pr-title-check.yml;
    # sha_pinning_required rejects any workflow run that references an
    # action by tag or branch rather than a full commit SHA;
    # validate_templates.py's check_sha_pinned_actions() enforces the same
    # rule on generated workflows before they ever reach GitHub.
    print("  actions permissions")
    api("PUT", f"repos/{repo}/actions/permissions", {
        "enabled": True,
        "allowed_actions": "selected",
        "sha_pinning_required": True,
    })
    api("PUT", f"repos/{repo}/actions/permissions/selected-actions", {
        "github_owned_allowed": True,
        "verified_allowed": True,
        "patterns_allowed": selected_action_patterns(cfg["repo_type"]),
    })
    api("PUT", f"repos/{repo}/actions/permissions/workflow", {
        "default_workflow_permissions": "read",
        # Generated Release Please workflows use a dedicated GitHub App token,
        # and no generated workflow approves pull requests. Keep the default
        # GITHUB_TOKEN unable to approve reviews.
        "can_approve_pull_request_reviews": False,
    })
    # Fork PR workflow controls only exist as a distinct API for private
    # repos; public repos gate fork PRs via a separate approval-policy
    # endpoint instead, which isn't part of what was asked for here.
    if cfg["private"]:
        api("PUT", f"repos/{repo}/actions/permissions/fork-pr-workflows-private-repos", {
            "run_workflows_from_fork_pull_requests": False,
            "send_write_tokens_to_workflows": False,
            "send_secrets_and_variables": False,
            "require_approval_for_fork_pr_workflows": False,
        })

    # --- branch protection on main ---
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

    if missing:
        print("\n  Still needs manual setup:")
        for item in missing:
            print(f"    {item}")

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    args = parse_args()

    # --- existing local repositories: compare or adopt, no GitHub calls ---
    if args.replace_generated_sections and args.adopt is None:
        _die("--replace-generated-sections is only used with --adopt")
    if args.check is not None or args.adopt is not None:
        if args.configure_only or args.dry_run:
            _die("--check and --adopt cannot be combined with --configure-only or --dry-run")
        cfg = existing_repository_config(args)
        repo_dir = Path(cfg["repo_dir"])
        files = generate_files(cfg)
        if args.check:
            aligned = print_repository_report(repo_dir, cfg, compare_repository(repo_dir, files))
            sys.exit(0 if aligned else 1)
        print(f"\nAdopting {repo_dir} as '{cfg['repo_type']}'")
        def confirm(sections):
            print("\nAGENTS.md: these generated sections differ from the template and will be")
            print("replaced with its text (the file is tracked, so git diff shows the change):")
            for heading in sections:
                print(f"  {heading}")
            return args.non_interactive or prompt_yn("Replace them?", default=False)

        actions = adopt_repository(
            repo_dir, files, replace_generated=args.replace_generated_sections, confirm=confirm
        )
        for action, rel, detail in actions:
            print(f"  {action:<8} {rel}" + (f" — {detail}" if detail else ""))
        print("\nReview the changes (git diff), then commit them on a branch.")
        sys.exit(1 if any(action == "refused" for action, _, _ in actions) else 0)

    if not args.dry_run:
        check_dependencies()
    cfg = gather_config(args)

    # --- configure-only: apply GitHub config to an existing repo ---
    if cfg["configure_only"]:
        if cfg["dry_run"]:
            _die("--configure-only cannot be combined with --dry-run")
        full = f"{cfg['owner']}/{cfg['name']}"
        if subprocess.run(["gh", "repo", "view", full], capture_output=True).returncode != 0:
            _die(f"repository '{full}' not found — verify the name and org")
        print(f"\nAbout to configure: {full} ({cfg['repo_type']})")
        print("  Enforces: squash-merge only, delete branch on merge, required status checks on main")
        print("  Note: file generation is skipped — commit CLAUDE.md and AGENTS.md separately if needed")
        if not args.non_interactive:
            if not prompt_yn("\nProceed?", default=True):
                print("Aborted.")
                return
        try:
            configure_repo(cfg)
            print_success(cfg)
        except subprocess.CalledProcessError as exc:
            print(f"\nerror: command failed: {exc.cmd}", file=sys.stderr)
            sys.exit(1)
        return

    # --- normal flow: create repo, generate files, configure ---
    files = generate_files(cfg)

    if cfg["dry_run"]:
        print_dry_run(cfg, files)
        return

    vis = "private" if cfg["private"] else "public"
    print(f"\nAbout to create: {cfg['owner']}/{cfg['name']} ({cfg['repo_type']}, {vis})")
    print(f"  Local path: {cfg['repo_dir']}/")
    if cfg["repo_type"] == "nextjs":
        extras = []
        if cfg["postgres"]:
            extras.append("Postgres tests")
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
            print("Files were pushed successfully. Fix configuration manually:", file=sys.stderr)
            print(f"  gh repo edit {full}  # merge strategy", file=sys.stderr)
            print(f"  gh api repos/{full}/branches/main/protection --method PUT ...  # branch protection", file=sys.stderr)
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
