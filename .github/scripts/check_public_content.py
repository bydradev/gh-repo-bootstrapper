#!/usr/bin/env python3
"""Find private details in text bound for this public repository.

Checks commit messages, the lines commits add to files, a pull request's
title and body, or any other text for what AGENTS.md *Public repository
content* rules out: claude.ai session, project, artifact and chat links,
`Claude-Session:` trailers, session and thread IDs, paths from an agent's
machine or project storage, email addresses other than noreply ones,
`bydradev/` and `bydraio/` repositories other than the public ones, and the
bare names listed in the PRIVATE_REPO_NAMES environment variable (comma- or
whitespace-separated; a repository secret in CI, an environment variable in a
cloud environment). gh-agent-kit's `.github/scripts/public-content.mjs` is the
same check in JavaScript: keep the two in step.

It reports only where a match is and what kind it is, never the matched text,
so its output cannot repeat a private name or act as a workflow command.

    check_public_content.py --range BASE..HEAD   commit messages in a range
    check_public_content.py --files BASE..HEAD   lines the range adds to files
    check_public_content.py --title TEXT         a pull request title
    check_public_content.py --pr-body FILE       a pull request body
    check_public_content.py --text FILE          any other text (a comment)

`--files` reads each commit of the range, as `--range` does, so a line one
commit adds and a later one removes is still found, and takes REV^! for one
commit. It checks the path of each file a commit adds or changes and the
lines it adds (for a merge, the lines that are in none of its parents), but
not this script or its tests, which hold every pattern and example it finds.

Options combine. Exits 1 when anything is found, 2 on a usage error. Uses
only the standard library.
"""

import argparse
import os
import re
import subprocess
import sys

PUBLIC_REPOSITORIES = frozenset(
    {"gh-repo-bootstrapper", "gh-agent-kit", "github-agent-kit", "gh-actions-dashboard"}
)
# The made-up repository the template tests' mock GitHub API serves.
PLACEHOLDER_REPOSITORIES = frozenset({"fixture"})

# Any claude.ai link with a path is found, so a new link format is too; only
# the generic footer link `https://claude.ai/code`, the Claude Code installer
# and its downloads host stay allowed. A trailer or marker is found with its
# value, so the rule that names it in backticks is not. A path is found when
# something follows the folder: under /mnt/, /workspace/, /root/, a home or
# user folder other than the runner's, Homebrew's or the placeholder `you`, a
# macOS volume or temporary folder, a Claude scratch folder, or a folder under
# `~/`.
PATTERNS = (
    ("a claude.ai link", re.compile(
        r"(?<!downloads\.)claude\.ai/(?!code(?![\w/-])|install\.(?:sh|ps1|cmd)(?![\w/-]))[\w-]", re.I
    )),
    ("a Claude-Session trailer", re.compile(r"Claude-Session:[ \t]*[^\s`]", re.I)),
    ("a project attribution marker", re.compile(r"claude-projects-attribution\s*:", re.I)),
    ("a session or thread ID", re.compile(r"\b(?:session|cse|cmsg|chan)_[A-Za-z0-9]{16,}")),
    ("a local or project-storage path", re.compile(
        r"(?<![\w.-])(?:/mnt/|/workspace/|/root/|/home/(?!(?:runner|linuxbrew|you)\b)|/Users/(?!you\b)"
        r"|/Volumes/|(?:/private)?/var/folders/)[\w.-]"
        r"|(?<![\w.-])(?:/tmp/claude|~/[\w.-]+/)"
        r"|\b[A-Za-z]:\\Users\\(?!you\b)[\w.-]"
    )),
)
# bydraio is the maintainer's earlier account name. The owner takes the bare
# names' boundary rather than \b, so an underscore before it (Markdown
# emphasis, _bydradev/name_) does not hide a reference.
OWNER_REPO = re.compile(r"(?<![A-Za-z0-9-])(?:bydradev|bydraio)/([A-Za-z0-9._-]+)", re.I)

# An address is found unless it is a noreply one, at an example domain, or
# the contact address CODE_OF_CONDUCT.md publishes; git@github.com is SSH's
# login, not a person's. A backslash before it is an escape such as `\n`.
EMAIL = re.compile(r"(?<![\w.%+\\-])([\w.%+-]+(?:\[bot\])?)@((?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})(?![\w-])")
NOREPLY_LOCAL_PARTS = frozenset({"noreply", "no-reply"})
NOREPLY_DOMAINS = ("users.noreply.github.com", "example.com", "example.org", "example.net")
PUBLISHED_ADDRESSES = frozenset({"github@bydra.dev", "git@github.com"})

# The check's own script and tests hold every pattern and example it finds.
EXEMPT_FILES = frozenset({".github/scripts/check_public_content.py", "tests/test_public_content.py"})
# A changed file's path is printed only when it has no finding and only these
# characters, so it cannot repeat a private name or start a workflow command.
PRINTABLE_PATH = re.compile(r"[\w./+@-]+")

# The two lines a Claude project thread must put at the top of a pull request
# body. AGENTS.md lets them stay there and keeps them out of squash commits,
# so a body may open with them and a commit may not.
ATTRIBUTION = (
    re.compile(r'<!-- claude-projects-attribution: \{"github_login":"[A-Za-z0-9-]+"\} -->'),
    re.compile(
        r"_Requested by \*\*[^*\n]+\*\* · \[project thread\]"
        r"\(https://claude\.ai/code/project/chan_[A-Za-z0-9]+\?thread=cmsg_[A-Za-z0-9]+\)_"
    ),
)


def private_names(value):
    names = [name for name in re.split(r"[\s,]+", value or "") if name]
    return [
        # An underscore is a boundary, so Markdown emphasis (`_name_`) is found.
        (name, re.compile(r"(?<![A-Za-z0-9-])" + re.escape(name) + r"(?![A-Za-z0-9])", re.I))
        for name in names
    ]


def private_address(local, domain):
    local, domain = local.lower(), domain.lower()
    return not (
        local in NOREPLY_LOCAL_PARTS
        or any(domain == allowed or domain.endswith("." + allowed) for allowed in NOREPLY_DOMAINS)
        or f"{local}@{domain}" in PUBLISHED_ADDRESSES
    )


def scan(text, names, allow_attribution=False):
    """Return (line number, kind) for each finding in text, in order."""
    lines = text.splitlines()
    skip = 0
    if allow_attribution and len(lines) >= 2 and all(
        pattern.fullmatch(line.strip()) for pattern, line in zip(ATTRIBUTION, lines)
    ):
        skip = 2
    found = []
    for number, line in enumerate(lines, 1):
        if number <= skip:
            continue
        kinds = [kind for kind, pattern in PATTERNS if pattern.search(line)]
        for match in OWNER_REPO.finditer(line):
            # Trailing dots end a sentence. Trailing underscores close emphasis
            # only when an underscore opened it earlier in the line; otherwise
            # they are part of the name, so bydradev/gh-agent-kit_ is another
            # repository.
            emphasised = re.search(r"(?:^|\W)_", line[: match.start()])
            repository = re.sub(r"[._]+$" if emphasised else r"\.+$", "", match[1])
            repository = repository.removesuffix(".git").lower()
            if repository not in PUBLIC_REPOSITORIES | PLACEHOLDER_REPOSITORIES:
                kinds.append("a bydradev or bydraio repository outside the public list")
                break
        if any(private_address(*match.groups()) for match in EMAIL.finditer(line)):
            kinds.append("an email address other than a noreply one")
        if any(pattern.search(line) for _, pattern in names):
            kinds.append("a private repository name")
        found += [(number, kind) for kind in kinds]
    return found


def git(*args):
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, encoding="utf-8", errors="replace"
    ).stdout


def commits(revision_range):
    fields = git("log", "--format=%H%x00%B%x00", "--end-of-options", revision_range).split("\0")
    return [(fields[i].strip(), fields[i + 1]) for i in range(0, len(fields) - 1, 2)]


def file_range(value):
    """BASE..HEAD or REV^!, as argparse reads --files."""
    base, dots, head = value.partition("..")
    if (dots and base and head and not head.startswith(".")) or (value.endswith("^!") and len(value) > 2):
        return value
    raise argparse.ArgumentTypeError(f"expected BASE..HEAD or REV^!, got {value!r}")


def changed_files(revision_range):
    """Yield (commit, place, path, [(line number, text)]) for each file a commit in the range adds or changes.

    place is the file's place in `git show --format= --name-only COMMIT`.
    """
    for commit in git("rev-list", "--reverse", "--end-of-options", revision_range).split():
        show = ("show", "--format=", "--no-color", "--no-ext-diff", "--no-textconv", "--find-renames", commit)
        fields = iter(git(*show, "--name-status", "-z").split("\0"))
        place = 0
        for status in fields:
            if not status:
                break
            place += 1
            # A merge has a letter per parent and one path, even for a rename;
            # only a rename or copy in a plain commit, R or C with a score, has two.
            paths = [next(fields)] + ([next(fields)] if re.fullmatch(r"[RC]\d+", status) else [])
            if set(status) == {"D"}:
                continue
            added, columns, number = [], None, 0
            # With no context lines, a hunk holds only changed lines, each led
            # by a column per parent: + where the parent lacks the line, - where
            # only the parent has it. A line every parent lacks is added, even
            # one that reads "+++".
            for line in git(*show, "--unified=0", "--", *paths).split("\n"):
                header = re.match(r"(@@+) .*? \+(\d+)(?:,\d+)? \1", line)
                if header:
                    columns, number = len(header[1]) - 1, int(header[2])
                elif columns and not line.startswith("\\") and "-" not in line[:columns]:
                    if line[:columns] == "+" * columns:
                        added.append((number, line[columns:]))
                    number += 1
            yield commit, place, paths[-1], added


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--range", dest="ranges", action="append", default=[], help="commits BASE..HEAD")
    parser.add_argument(
        "--files", action="append", default=[], type=file_range, help="lines BASE..HEAD or REV^! adds to files"
    )
    parser.add_argument("--title", action="append", default=[], help="a pull request title")
    parser.add_argument("--pr-body", action="append", default=[], help="a file holding a pull request body")
    parser.add_argument("--text", action="append", default=[], help="a file holding other text")
    args = parser.parse_args(argv)
    if not (args.ranges or args.files or args.title or args.pr_body or args.text):
        parser.error("give at least one of --range, --files, --title, --pr-body or --text")

    names = private_names(os.environ.get("PRIVATE_REPO_NAMES"))
    if not names:
        print("PRIVATE_REPO_NAMES is not set, so bare private repository names were not checked.")

    sources = [("title", title, False) for title in args.title]
    sources += [("body", open(path, encoding="utf-8").read(), True) for path in args.pr_body]
    sources += [(f"text {path}", open(path, encoding="utf-8").read(), False) for path in args.text]
    for revision_range in args.ranges:
        sources += [(f"commit {sha[:7]}", message, False) for sha, message in commits(revision_range)]

    findings = []
    for source, text, allow in sources:
        findings += [f"{source}, line {number}: {kind}" for number, kind in scan(text, names, allow)]
    files = 0
    for revision_range in args.files:
        for commit, place, path, added in changed_files(revision_range):
            if path in EXEMPT_FILES:
                continue
            files += 1
            in_name = [kind for _, kind in scan(path, names)]
            source = f"commit {commit[:7]}, file {path}"
            if in_name or not PRINTABLE_PATH.fullmatch(path):
                source = f"commit {commit[:7]}, changed file {place} (name not shown)"
            findings += [f"{source}, name: {kind}" for kind in in_name]
            for number, line in added:
                findings += [f"{source}, line {number}: {kind}" for _, kind in scan(line, names)]

    for finding in findings:
        print(f"::error title=Public repository content::{finding}")
    if findings:
        print(
            f"{len(findings)} finding(s). Reword them as AGENTS.md *Public repository content* says; "
            "this check never prints the matched text. A changed file's number is its place in "
            "`git show --format= --name-only COMMIT`."
        )
        return 1
    print(f"No private details found in {len(sources)} text(s) and {files} file change(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
