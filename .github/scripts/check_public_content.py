#!/usr/bin/env python3
"""Find private details in text bound for this public repository.

Checks commit messages, a pull request's title and body, or any other text
for what AGENTS.md *Public repository content* rules out: claude.ai session,
project, artifact and chat links, `Claude-Session:` trailers, session and
thread IDs, paths from an agent's machine or project storage, `bydradev/`
repositories other than the public ones, and the bare names listed in the
PRIVATE_REPO_NAMES environment variable (comma- or whitespace-separated; a
repository secret in CI, an environment variable in a cloud environment).

It reports only where a match is and what kind it is, never the matched text,
so its output cannot repeat a private name or act as a workflow command.

    check_public_content.py --range BASE..HEAD   commit messages in a range
    check_public_content.py --title TEXT         a pull request title
    check_public_content.py --pr-body FILE       a pull request body
    check_public_content.py --text FILE          any other text (a comment)

Options combine. Exits 1 when anything is found, 2 on a usage error. Uses
only the standard library.
"""

import argparse
import os
import re
import subprocess
import sys

PUBLIC_REPOSITORIES = frozenset({"gh-repo-bootstrapper", "gh-agent-kit", "github-agent-kit"})

# Any claude.ai link with a path is found, so a new link format is too; only
# the generic footer link `https://claude.ai/code` stays allowed. A path is
# found under /mnt/, a home directory other than the runner's or Homebrew's,
# /root/, a macOS or Windows user folder, or a Claude scratch folder.
PATTERNS = (
    ("a claude.ai link", re.compile(r"claude\.ai/(?!code(?![\w/-]))[\w-]", re.I)),
    ("a Claude-Session trailer", re.compile(r"Claude-Session:", re.I)),
    ("a project attribution marker", re.compile(r"claude-projects-attribution", re.I)),
    ("a session or thread ID", re.compile(r"\b(?:session|cse|cmsg|chan)_[A-Za-z0-9]{16,}")),
    ("a local or project-storage path", re.compile(
        r"(?<![\w.-])(?:/mnt/[\w.-]|/home/(?!runner\b|linuxbrew\b)[\w.-]|/root/|/Users/[\w.-]|/tmp/claude)"
        r"|\b[A-Za-z]:\\Users\\"
    )),
)
OWNER_REPO = re.compile(r"\bbydradev/([A-Za-z0-9._-]+)", re.I)

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
        (name, re.compile(r"(?<![A-Za-z0-9_-])" + re.escape(name) + r"(?![A-Za-z0-9_])", re.I))
        for name in names
    ]


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
            repository = match[1].rstrip(".").removesuffix(".git").lower()
            if repository not in PUBLIC_REPOSITORIES:
                kinds.append("a bydradev repository outside the public list")
                break
        if any(pattern.search(line) for _, pattern in names):
            kinds.append("a private repository name")
        found += [(number, kind) for kind in kinds]
    return found


def commits(revision_range):
    log = subprocess.run(
        ["git", "log", "--format=%H%x00%B%x00", "--end-of-options", revision_range],
        check=True, capture_output=True, text=True,
    ).stdout
    fields = log.split("\0")
    return [(fields[i].strip(), fields[i + 1]) for i in range(0, len(fields) - 1, 2)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--range", dest="ranges", action="append", default=[], help="commits BASE..HEAD")
    parser.add_argument("--title", action="append", default=[], help="a pull request title")
    parser.add_argument("--pr-body", action="append", default=[], help="a file holding a pull request body")
    parser.add_argument("--text", action="append", default=[], help="a file holding other text")
    args = parser.parse_args(argv)
    if not (args.ranges or args.title or args.pr_body or args.text):
        parser.error("give at least one of --range, --title, --pr-body or --text")

    names = private_names(os.environ.get("PRIVATE_REPO_NAMES"))
    if not names:
        print("PRIVATE_REPO_NAMES is not set, so bare private repository names were not checked.")

    sources = [("title", title, False) for title in args.title]
    sources += [("body", open(path, encoding="utf-8").read(), True) for path in args.pr_body]
    sources += [(f"text {path}", open(path, encoding="utf-8").read(), False) for path in args.text]
    for revision_range in args.ranges:
        sources += [(f"commit {sha[:7]}", message, False) for sha, message in commits(revision_range)]

    total = 0
    for source, text, allow in sources:
        for number, kind in scan(text, names, allow):
            total += 1
            print(f"::error title=Public repository content::{source}, line {number}: {kind}")
    if total:
        print(
            f"{total} finding(s). Reword them as AGENTS.md *Public repository content* says; "
            "this check never prints the matched text."
        )
        return 1
    print(f"No private details found in {len(sources)} text(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
