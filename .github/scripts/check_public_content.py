#!/usr/bin/env python3
"""Find private details in text bound for this public repository.

Checks commit messages, the lines commits add to files, a pull request's
title and body, or any other text for what AGENTS.md *Public repository
content* rules out: claude.ai session, project, artifact and chat links,
`Claude-Session:` trailers, session and thread IDs, paths from an agent's
machine or project storage, and private email addresses.
Keep this in step with gh-agent-kit's `.github/scripts/public-content.mjs`.

It reports only where a match is and what kind it is, never the matched text,
so its output cannot repeat a private detail or act as a workflow command.

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
import re
import subprocess
import sys

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
# An address is found unless it is a noreply one, at an example domain, or
# the contact address CODE_OF_CONDUCT.md publishes; git@github.com is SSH's
# login, not a person's. A backslash before it is an escape such as `\n`.
# It ends where no letter or digit follows: `_` never appears in a domain,
# and a `-` after the letters-only top-level label opens a suffix
# (`sam@corp.example-related`) or Markdown emphasis closes it (`_..._`).
EMAIL = re.compile(r"(?<![\w.%+\\-])([\w.%+-]+(?:\[bot\])?)@((?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})(?![A-Za-z0-9])")
# The same address ending only where no word character or `-` follows. Where
# EMAIL stops early (before a `-` or `_`), this one keeps searching and can
# find an address that overlaps it (`noreply@x.example-sam@corp.example`)
# or the whole domain a `-` continues, so a line is checked with both and
# nothing this one finds is lost to the earlier end.
EMAIL_WHOLE = re.compile(r"(?<![\w.%+\\-])([\w.%+-]+(?:\[bot\])?)@((?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})(?![\w-])")
# An address right after a complete literal escape in a string, in JSON or
# source text (`"Contact:\nsam@corp.example"`), which the patterns above pass
# over: their start may not follow a backslash, so that `\n@AGENTS.md` stays
# quiet. escaped_address decides whether the escape is one. The local part is
# ASCII so that it agrees with the JavaScript copy, whose \w is ASCII; each
# lookbehind is fixed-width, as Python requires.
EMAIL_AFTER_ESCAPE = re.compile(
    r'(?:(?<=\\[nrtbfv0"\'`/])|(?<=\\u[0-9A-Fa-f]{4})|(?<=\\x[0-9A-Fa-f]{2}))([A-Za-z0-9_.%+-]+(?:\[bot\])?)@((?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})(?![A-Za-z0-9])'
)


def escaped_address(line, index):
    """An EMAIL_AFTER_ESCAPE match counts when its escape's backslash ends an
    odd run of backslashes (an even run is escaped backslashes and text),
    sits inside a string opened by ", ` or a ' that no letter or digit comes
    before (not a Windows path, a regex or an apostrophe in prose), and is
    not in a URL, whose user information the URL guard judges."""
    start = index - 2
    if re.search(r"\\u[0-9A-Fa-f]{4}$", line[max(0, index - 6) : index]):
        start = index - 6
    elif re.search(r"\\x[0-9A-Fa-f]{2}$", line[max(0, index - 4) : index]):
        start = index - 4
    run, j = 0, start
    while j >= 0 and line[j] == "\\":
        run, j = run + 1, j - 1
    if run % 2 == 0:
        return False
    quote, j = None, 0
    while j < start:
        c = line[j]
        if quote:
            if c == "\\":
                j += 1
            elif c == quote:
                quote = None
        elif c in "\"`" or (c == "'" and not (j > 0 and re.match(r"[A-Za-z0-9_]", line[j - 1]))):
            quote = c
        j += 1
    if quote is None:
        return False
    return "://" not in re.split(r"[ \t\r\n\f\v\"'`]", line[:index])[-1]
# A URL's user information (scheme://user@host or scheme://user:password@host),
# as tests of code that refuses credentials in URLs hold, is not an address:
# a match whose text before it ends with this is skipped. mailto: has no //,
# so an address after it is still found.
URL_USERINFO = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://(?:[^\s/?#@:]*:)?$")
NOREPLY_LOCAL_PARTS = frozenset({"noreply", "no-reply"})
NOREPLY_DOMAINS = ("users.noreply.github.com", "example.com", "example.org", "example.net")
PUBLISHED_ADDRESSES = frozenset({"github@bydra.dev", "git@github.com"})

# Only this complete literal line exempts its email; it does not verify authorship.
DEPENDABOT_FOOTER = "Signed-off-by: dependabot[bot] <support@github.com>"

# The check's own script and tests hold every pattern and example it finds.
EXEMPT_FILES = frozenset({".github/scripts/check_public_content.py", "tests/test_public_content.py"})
# A changed file's path is printed only when it has no finding and only these
# characters, so it cannot repeat private details or start a workflow command.
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


def private_address(local, domain):
    local, domain = local.lower(), domain.lower()
    return not (
        local in NOREPLY_LOCAL_PARTS
        or any(domain == allowed or domain.endswith("." + allowed) for allowed in NOREPLY_DOMAINS)
        or f"{local}@{domain}" in PUBLISHED_ADDRESSES
    )


def scan(text, *, allow_attribution=False):
    """Return (line number, kind) for each finding in text, in order."""
    lines = re.split(r"\r?\n", text)
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
        if line != DEPENDABOT_FOOTER and any(
            not URL_USERINFO.search(line[: match.start()]) and private_address(*match.groups())
            for pattern in (EMAIL, EMAIL_WHOLE, EMAIL_AFTER_ESCAPE)
            for match in pattern.finditer(line)
            if pattern is not EMAIL_AFTER_ESCAPE or escaped_address(line, match.start())
        ):
            kinds.append("an email address other than a noreply one")
        found += [(number, kind) for kind in kinds]
    return found


def git(*args):
    return subprocess.run(
        ["git", *args], check=True, capture_output=True
    ).stdout.decode("utf-8", "replace")


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
            diff_lines = git(*show, "--unified=0", "--", *paths).split("\n")
            for index, line in enumerate(diff_lines):
                header = re.match(r"(@@+) .*? \+(\d+)(?:,\d+)? \1", line)
                if header:
                    columns, number = len(header[1]) - 1, int(header[2])
                elif columns and not line.startswith("\\") and "-" not in line[:columns]:
                    if line[:columns] == "+" * columns:
                        ending = "" if diff_lines[index + 1].startswith("\\ No newline") else "\n"
                        added.append((number, line[columns:] + ending))
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

    sources = [("title", title, False) for title in args.title]
    sources += [("body", open(path, encoding="utf-8", newline="").read(), True) for path in args.pr_body]
    sources += [(f"text {path}", open(path, encoding="utf-8", newline="").read(), False) for path in args.text]
    for revision_range in args.ranges:
        sources += [(f"commit {sha[:7]}", message, False) for sha, message in commits(revision_range)]

    findings = []
    for source, text, allow in sources:
        findings += [f"{source}, line {number}: {kind}" for number, kind in scan(text, allow_attribution=allow)]
    files = 0
    for revision_range in args.files:
        for commit, place, path, added in changed_files(revision_range):
            if path in EXEMPT_FILES:
                continue
            files += 1
            in_name = [kind for _, kind in scan(path)]
            source = f"commit {commit[:7]}, file {path}"
            if in_name or not PRINTABLE_PATH.fullmatch(path):
                source = f"commit {commit[:7]}, changed file {place} (name not shown)"
            findings += [f"{source}, name: {kind}" for kind in in_name]
            for number, line in added:
                findings += [f"{source}, line {number}: {kind}" for _, kind in scan(line)]

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
