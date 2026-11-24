"""The public-content check: what it finds, what it lets through, and that it never prints the match."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".github" / "scripts" / "check_public_content.py"
WORKFLOW = ROOT / ".github" / "workflows" / "public-content.yml"

_spec = importlib.util.spec_from_file_location("check_public_content", SCRIPT)
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)

ATTRIBUTION = (
    '<!-- claude-projects-attribution: {"github_login":"someone"} -->\n'
    "_Requested by **Sam** · [project thread](https://claude.ai/code/project/"
    "chan_0123456789abcdefABCDEF?thread=cmsg_0123456789abcdefABCDEF)_\n"
)


def kinds(text, allow_attribution=False):
    return [kind for _, kind in check.scan(text, allow_attribution=allow_attribution)]


class ScanTests(unittest.TestCase):
    def test_finds_each_kind(self):
        cases = {
            "See https://claude.ai/code/session_01ABCDEFGHIJKLMNOPQRSTUV": "a claude.ai link",
            "https://claude.ai/artifact/N8FfuzcNYav6cnmhtVVWQG": "a claude.ai link",
            "Claude-Session: https://example.com": "a Claude-Session trailer",
            '<!-- claude-projects-attribution: {"github_login":"x"} -->': "a project attribution marker",
            "thread cmsg_0123456789abcdefABCD": "a session or thread ID",
            "https://claude.ai/public/artifacts/0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b": "a claude.ai link",
            "start one at claude.ai/new": "a claude.ai link",
            "https://claude.ai/code/routines": "a claude.ai link",
            "https://claude.ai/installer and claude.ai/install.sh/x": "a claude.ai link",
            "the report in /mnt/project-files/assessment/x.md": "a local or project-storage path",
            "see /home/alice/report.md": "a local or project-storage path",
            "(/mnt/data/report.md)": "a local or project-storage path",
            "`/root/.claude/settings.json`": "a local or project-storage path",
            "in /Users/sam/GitHub": "a local or project-storage path",
            r"in C:\Users\sam\GitHub": "a local or project-storage path",
            "cd /workspace/repo && make": "a local or project-storage path",
            "in /private/var/folders/xy/T/report.md": "a local or project-storage path",
            "/var/folders/xy/T/tmp.1234": "a local or project-storage path",
            "on /Volumes/Work/GitHub": "a local or project-storage path",
            "Plan: `~/GitHub/.omo/plans/x.md`": "a local or project-storage path",
            "Signed-off-by: Sam <sam@mailbox.test>": "an email address other than a noreply one",
            "write to Sam.Lee+github@corp.Mailbox.test.": "an email address other than a noreply one",
            "[mail](mailto:sam@mailbox.test)": "an email address other than a noreply one",
            "Co-Authored-By: Sam <noreply.sam@mailbox.test>": "an email address other than a noreply one",
            "see https://github.com/acme or sam@mailbox.test": "an email address other than a noreply one",
            "https://host.test/u/sam@mailbox.test": "an email address other than a noreply one",
            "https://user:password@github.com/acme/repo by sam@mailbox.test": (
                "an email address other than a noreply one"
            ),
            # An address that punctuation no domain holds ends: Markdown
            # emphasis, a hyphenated suffix and an underscore.
            "_contact sam@mailbox.test_": "an email address other than a noreply one",
            "the sam@mailbox.test-related thread": "an email address other than a noreply one",
            "sam@mailbox.test_old": "an email address other than a noreply one",
            "to sam@mailbox.test, then": "an email address other than a noreply one",
            "(ask sam@mailbox.test)": "an email address other than a noreply one",
            "sam@mailbox.test_-x": "an email address other than a noreply one",
            "the sam@mailbox.test-2024 archive": "an email address other than a noreply one",
            # In a template literal, and after an escaped backslash and an escape.
            r'const contact = `Contact:\nsam@mailbox.test`;': "an email address other than a noreply one",
            r'"Contact:\\\nsam@mailbox.test"': "an email address other than a noreply one",
            # An address right after a literal escape in serialized text.
            r'{"message":"Contact:\nalice@mailbox.test"}': "an email address other than a noreply one",
            r'"to:\tsam@mailbox.test"': "an email address other than a noreply one",
            r"'line\rsam@mailbox.test'": "an email address other than a noreply one",
            r'"a\u000asam@mailbox.test" and "b\x0asam@mailbox.test"': "an email address other than a noreply one",
            r'"quote\"sam@mailbox.test\""': "an email address other than a noreply one",
            # After a hyphen the domain may go on, so an allowed-looking start
            # does not make it public.
            "user@team.example.com-xn--p1ai": "an email address other than a noreply one",
            "user@team.example.com-foo.test2": "an email address other than a noreply one",
            "contacts/noreply@anthropic.com-sam@mailbox.test.txt": "an email address other than a noreply one",
            "contacts/noreply@anthropic.com_sam@mailbox.test.txt": "an email address other than a noreply one",
            "https://user@corp.test-sam@mailbox.test/path": "an email address other than a noreply one",
            "report it to github@bydra.dev-ops.mailbox.test": "an email address other than a noreply one",
            "contacts/noreply@anthropic.com\u00e9sam@mailbox.test.txt": "an email address other than a noreply one",
            "contacts/noreply@anthropic.com\u0661sam@mailbox.test.txt": "an email address other than a noreply one",
        }
        for text, kind in cases.items():
            with self.subTest(text=text):
                self.assertIn(kind, kinds(text))

    def test_lets_public_text_through(self):
        for text in (
            "_Generated by [Claude Code](https://claude.ai/code)_",
            "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>",
            "Signed-off-by: Dra <207542236+bydradev@users.noreply.github.com>",
            # A URL's user information, as tests of credential stripping hold.
            "https://user:password@github.com/acme/repo and https://user@github.com/acme/repo",
            '"https://:password@github.com/acme/repo", "https://api.github.com@evil.test/items"',
            "git+ssh://deploy@git.mailbox.test/acme.git",
            "a session_id field, a chan_ prefix",
            "/home/runner/work is the runner's checkout",
            "/home/linuxbrew/.linuxbrew/bin/brew and GET /users/octocat",
            "https://example.com/mnt/data and https://claude.ai/code.",
            "curl -fsSL https://claude.ai/install.sh | bash, or claude.ai/install.ps1",
            "https://downloads.claude.ai/claude-code-releases/2.1.0/manifest.json",
            # A placeholder user, as in a usage message.
            r"/Users/you/code/my-app, /home/you/app or C:\Users\you\app",
            "a file in ~ such as ~/app-key.pem, or ~/My Projects/app",
            "https://example.com/workspace/x and /private/var (a link)",
            # Noreply addresses, example domains and the published contact.
            "Co-Authored-By: Codex (GPT-5) <noreply@openai.com>, No-Reply@Mailbox.test",
            "Signed-off-by: dependabot[bot] <49699333+dependabot[bot]@users.noreply.github.com>",
            "Signed-off-by: Sam <sam@example.com>, t@mail.example.org and a@example.net",
            "report it to github@bydra.dev, or clone git@github.com:bydradev/gh-agent-kit.git",
            # The same trailing punctuation after an allowed address.
            "_write to sam@example.com_ or noreply@anthropic.com, noreply@mailbox.test_x",
            "noreply@anthropic.com_ and sam@example.com_",
            "noreply@anthropic.com-x and github@bydra.dev-ops",
            # Package versions and decorators are not addresses, nor is an escape.
            "npx eslint@9.39.5, actions/checkout@v7.0.1, @anthropic-ai/sdk@0.71.0 and @property",
            r'files[HUB] + "\n@AGENTS.md\n"',
            # An escape not followed by an address, and an allowed address after one.
            r'"\t@decorator", "\r@x", "\u0040", "line\nnoreply@anthropic.com"',
            r'"Contact:\nsam@example.com"',
            # A Windows path, a regex and an escaped backslash are not escapes
            # before an address, and Python's Unicode letters do not count.
            r"C:\new@v2.config and /\new@v2.config/",
            # A regex after a closed string, an apostrophe in prose, an even run
            # of backslashes, and an escape in a URL's user information.
            r'const label = "regex"; const pattern = /\new@v2.config/;',
            r"Don't use C:\new@v2.config",
            r'"C:\\\\new@v2.config"',
            r'"https://user:pa\u0073s@host.test"',
            r'"C:\\new@v2.config"',
            r'"\n李@host.test", "\nénoreply@host.test"',
            # The rule's own text names the prefixes and markers it rules out.
            "No paths (`/mnt/`, `/home/`, `/root/`, `/Users/`, `/workspace/`, `/Volumes/`, `~/`)",
            "carries no `Claude-Session:` trailer and no `claude-projects-attribution` marker",
        ):
            with self.subTest(text=text):
                self.assertEqual(kinds(text), [])

    def test_exact_public_footer_only(self):
        footer = "Signed-off-by: dependabot[bot] <support@github.com>"
        for text in (footer, footer + "\n", footer + "\r\n", "update\n\n" + footer,
                     footer + "\n" + footer):
            self.assertEqual(kinds(text), [])
        near = [" " + footer, footer + " ", "\t" + footer, footer + "\t",
                footer.lower(), footer.replace("dependabot", "otherbot"),
                footer.replace("github.com", "github.org"), footer.replace("support", "Support"),
                footer.replace(": ", ":  "), footer.replace("[bot]", ""),
                footer.replace("github.com", "GITHUB.COM"), "`" + footer + "`",
                "support@github.com", footer + " <sam@mailbox.test>",
                "sam@mailbox.test " + footer, footer + "\r", footer + "\u2028",
                footer + "\v", footer + "\x85", footer + "\x00"]
        for text in near:
            with self.subTest(text=text):
                self.assertIn("an email address other than a noreply one", kinds(text))
        for forbidden in ("sam@mailbox.test", "Claude-Session: x", "/Users/sam/x"):
            self.assertEqual(kinds(footer + "\n" + forbidden), kinds(forbidden))
            self.assertEqual(kinds(forbidden + "\n" + footer), kinds(forbidden))
            self.assertTrue(kinds(footer + " " + forbidden))

    def test_reports_line_numbers(self):
        found = check.scan("ok\n\nClaude-Session: x\n")
        self.assertEqual(found, [(3, "a Claude-Session trailer")])

    def test_attribution_block_allowed_only_at_the_top_of_a_body(self):
        self.assertEqual(kinds(ATTRIBUTION + "\n## What changes\n", allow_attribution=True), [])
        # In a commit message, or anywhere but the first two lines, it is found.
        self.assertIn("a project attribution marker", kinds(ATTRIBUTION))
        moved = "Intro\n" + ATTRIBUTION
        self.assertIn("a claude.ai link", kinds(moved, allow_attribution=True))
        # Anything after the block is still checked.
        self.assertEqual(
            kinds(ATTRIBUTION + "\nClaude-Session: x\n", allow_attribution=True), ["a Claude-Session trailer"]
        )


def _git(directory, *args):
    return subprocess.run(
        ["git", "-C", str(directory), *args], check=True, capture_output=True, text=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_AUTHOR_NAME": "t",
             "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
             "GIT_COMMITTER_EMAIL": "t@example.com"},
    ).stdout.strip()


@unittest.skipUnless(sys.executable, "needs python")
class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def _run(self, *args, **env):
        result = subprocess.run(
            [sys.executable, "-I", str(SCRIPT), *args], env={"PATH": os.environ["PATH"], **env}, cwd=self.dir,
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode, result.stdout + result.stderr

    def _git(self, *args):
        return _git(self.dir, *args)

    def test_never_prints_the_matched_text(self):
        body = self.dir / "body.md"
        body.write_text(
            "Draft for review.\nhttps://claude.ai/code/session_01ABCDEFGHIJKLMNOPQRSTUV\n"
            "Signed-off-by: Sam <sam@mailbox.test>\n"
        )
        code, out = self._run("--title=fix: inspect /Users/sam/project", f"--pr-body={body}")
        self.assertEqual(code, 1, out)
        self.assertIn("::error title=Public repository content::title, line 1: a local or project-storage path", out)
        self.assertIn("line 2: a claude.ai link", out)
        self.assertIn("line 3: an email address other than a noreply one", out)
        self.assertNotIn("/Users/sam", out)
        self.assertNotIn("session_01", out)
        self.assertNotIn("mailbox", out)

    def test_clean_text_passes(self):
        body = self.dir / "body.md"
        body.write_text(ATTRIBUTION + "\n## What changes\n\nNothing private.\n")
        code, out = self._run("--title=docs: say what changes", f"--pr-body={body}")
        self.assertEqual(code, 0, out)
        self.assertNotIn("::error", out)

    def test_public_footer_entrypoints(self):
        footer = "Signed-off-by: dependabot[bot] <support@github.com>"
        body = self.dir / "body.md"
        for ending in ("\n", "\r\n"):
            body.write_bytes(("update" + ending + footer + ending).encode())
            for option in ("--text", "--pr-body"):
                code, out = self._run(f"{option}={body}")
                self.assertEqual(code, 0, out)
            body.write_text(footer + "\nsam@mailbox.test\n")
            code, out = self._run(f"--pr-body={body}")
            self.assertEqual(code, 1, out)
            self.assertIn("line 2: an email address", out)
            self.assertNotIn("mailbox", out)
        body.unlink()
        self._git("init", "-q", "-b", "main")
        self._commit("chore: base")
        self._git("tag", "base")
        self._commit("build: update\n\n" + footer, {"notes.md": (footer + "\r\n").encode()})
        code, out = self._run("--range=base..main", "--files=base..main")
        self.assertEqual(code, 0, out)
        for suffix, expected in (("", 0), ("\r", 1), ("\v", 1), ("\u2028", 1)):
            content = (footer + suffix).encode()
            self._commit("test: line endings", {"notes.md": content})
            code, out = self._run("--files=HEAD^!")
            self.assertEqual(code, expected, out)
            body.write_bytes(content)
            for option in ("--text", "--pr-body"):
                code, out = self._run(f"{option}={body}")
                self.assertEqual(code, expected, out)
            body.unlink()
        self._commit("build: update\n\n" + footer + "\nsam@mailbox.test",
                     {"notes.md": footer + "\nsam@mailbox.test\n"})
        code, out = self._run("--range=HEAD^!", "--files=HEAD^!")
        self.assertEqual(code, 1, out)
        self.assertEqual(out.count("::error"), 2, out)
        self.assertNotIn("mailbox", out)

    def test_repository_references_pass_even_with_a_legacy_name_list(self):
        draft = "Example-project (bydradev/example-project#12, https://github.com/bydraio/example-project)."
        for env in ({}, {"PRIVATE_REPO_NAMES": "example-project"}):
            with self.subTest(env=env):
                code, out = self._run("--title", draft, **env)
                self.assertEqual(code, 0, out)
                self.assertNotIn("PRIVATE_REPO_NAMES", out)

    def test_needs_something_to_check(self):
        code, _ = self._run()
        self.assertEqual(code, 2)

    def test_checks_each_commit_in_a_range(self):
        self._git("init", "-q", "-b", "main")
        self._git("commit", "-q", "--allow-empty", "-m", "chore: base")
        self._git("tag", "base")
        self._git("commit", "-q", "--allow-empty", "-m", "fix: one\n\nClaude-Session: https://claude.ai/code/session_01ABCDEFGHIJKLMNOPQRSTUV")
        self._git("commit", "-q", "--allow-empty", "-m", "fix: two\n\nCo-Authored-By: A <a@example.com>")
        code, out = self._run("--range=base..main")
        self.assertEqual(code, 1, out)
        self.assertEqual(out.count("::error"), 3, out)  # trailer, link and ID, all on line 3 of one commit
        self.assertIn(", line 3: a Claude-Session trailer", out)
        self._git("commit", "-q", "--allow-empty", "-m", "fix: three")
        code, out = self._run("--range=main^!")
        self.assertEqual(code, 0, out)

    def _commit(self, message, files=(), remove=()):
        for name, content in dict(files).items():
            path = self.dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content) if isinstance(content, bytes) else path.write_text(content)
        for name in remove:
            self._git("rm", "-q", name)
        self._git("add", "-A")
        self._git("commit", "-q", "--allow-empty", "-m", message)

    def test_checks_the_lines_a_range_adds_to_files(self):
        self._git("init", "-q", "-b", "main")
        self._commit("chore: base", {"notes.md": "old\nfrom /home/alice/old\n", "gone.md": "/Users/sam/x\n"})
        self._git("tag", "base")
        self._commit("feat: add", {
            "notes.md": "old\nfrom /home/alice/old\nnew line\nsee /Users/sam/GitHub\n",
            "docs/sam@mailbox.test.md": "Signed-off-by: Sam <sam@mailbox.test>\n",
            "logo.png": b"\x89PNG\x00/Users/sam/x\n",
            # The check's own script and tests hold the patterns they find.
            ".github/scripts/check_public_content.py": "# /Users/sam/x\n",
            "tests/test_public_content.py": "# /Users/sam/x\n",
        }, remove=["gone.md"])
        code, out = self._run("--files=base..main")
        self.assertEqual(code, 1, out)
        commit = self._git("rev-parse", "--short=7", "main")
        self.assertIn(
            f"::error title=Public repository content::commit {commit}, file notes.md, line 4: "
            "a local or project-storage path", out
        )
        # A file whose name has a finding is not named but numbered as
        # `git show --name-only` lists it; its lines are still checked.
        self.assertIn(f"commit {commit}, changed file 2 (name not shown), name: an email address other than a noreply one", out)
        self.assertIn(
            f"commit {commit}, changed file 2 (name not shown), line 1: an email address other than a noreply one",
            out,
        )
        # Not the old line, the removed file, the image or the exempt files.
        self.assertEqual(out.count("::error"), 3, out)
        self.assertNotIn("mailbox.test", out)
        self.assertNotIn("sam", out.lower())

    def test_files_are_read_commit_by_commit(self):
        self._git("init", "-q", "-b", "main")
        self._commit("chore: base", {"a.md": "from /home/alice/x\n"})
        self._git("switch", "-q", "-c", "topic")
        self._commit("feat: rename", {"b.md": "from /home/alice/x\n"}, remove=["a.md"])
        self._commit("feat: clean line", {"c.md": "nothing private\n"})
        code, out = self._run("--files=main..topic")
        self.assertEqual(code, 0, out)  # a rename adds no lines
        self.assertIn("No private details found in 0 text(s) and 2 file change(s).", out)
        # A line one commit adds stays in that commit when a later one drops it.
        self._commit("feat: add a path", {"c.md": "nothing private\nin /Volumes/Work\n"})
        added = self._git("rev-parse", "--short=7", "HEAD")
        self._commit("fix: drop it", {"c.md": "nothing private\n"})
        code, out = self._run("--files=main..topic")
        self.assertEqual(code, 1, out)
        self.assertEqual(out.count("::error"), 1, out)
        self.assertIn(f"commit {added}, file c.md, line 2: a local or project-storage path", out)
        code, out = self._run("--files=topic^!")
        self.assertEqual(code, 0, out)

    def test_a_merge_is_read_for_lines_no_parent_has(self):
        self._git("init", "-q", "-b", "main")
        self._commit("chore: base", {"a.md": "one\ntwo\n"})
        self._git("switch", "-q", "-c", "topic")
        self._commit("feat: topic", {"a.md": "one\ntwo\ntopic\n"})
        self._git("switch", "-q", "main")
        self._commit("fix: main", {"a.md": "main /Users/sam/x\none\ntwo\n", "m.md": "/Users/sam/y\n"})
        self._git("switch", "-q", "topic")
        self._git("merge", "-q", "--no-commit", "main")
        # The merge brings main's lines, which main's own run checks, and
        # adds one that neither side has.
        (self.dir / "a.md").write_text("main /Users/sam/x\none\ntwo\ntopic\nby hand /Volumes/Work\n")
        self._commit("Merge branch 'main' into topic")
        merge = self._git("rev-parse", "--short=7", "HEAD")
        code, out = self._run("--files=main..topic")
        self.assertEqual(code, 1, out)
        self.assertEqual(out.count("::error"), 1, out)
        self.assertIn(f"commit {merge}, file a.md, line 5: a local or project-storage path", out)

    def test_a_merge_that_renames_a_file_is_read_to_the_end(self):
        self._git("init", "-q", "-b", "main")
        self._commit("chore: base", {"a.md": "one\ntwo\nthree\n", "z.md": "end\n"})
        self._git("switch", "-q", "-c", "topic")
        self._commit("feat: topic", {"a.md": "one\ntwo\nthree\ntopic\n"})
        self._git("switch", "-q", "main")
        self._commit("refactor: rename", {"b.md": "one\ntwo\nthree\n"}, remove=["a.md"])
        self._git("switch", "-q", "topic")
        self._git("merge", "-q", "--no-commit", "main")
        # The merge lists b.md with a letter per parent and one path, then z.md.
        self._commit("Merge branch 'main' into topic", {
            "b.md": "one\ntwo\nthree\ntopic\nby hand\n", "z.md": "end\nby hand /Volumes/Work\n"})
        merge = self._git("rev-parse", "--short=7", "HEAD")
        code, out = self._run("--files=main..topic")
        self.assertEqual(code, 1, out)
        self.assertEqual(out.count("::error"), 1, out)
        self.assertIn(f"commit {merge}, file z.md, line 2: a local or project-storage path", out)

    def test_files_needs_a_range(self):
        self._git("init", "-q", "-b", "main")
        self._commit("chore: base")
        code, out = self._run("--files=main")
        self.assertEqual(code, 2, out)


def _step(name):
    steps = yaml.safe_load(WORKFLOW.read_text())["jobs"]["public-content"]["steps"]
    return next(step["run"] for step in steps if step.get("name") == name)


@unittest.skipUnless(shutil.which("bash"), "needs bash")
class StepTests(unittest.TestCase):
    """The workflow's two steps, run with bash as GitHub runs them, in a scratch repository."""

    def _git(self, *args):
        return _git(self.dir, *args)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name) / "repo"
        self.dir.mkdir()
        (self.dir / ".github" / "scripts").mkdir(parents=True)
        shutil.copy(SCRIPT, self.dir / ".github" / "scripts" / SCRIPT.name)
        self._git("init", "-q", "-b", "main")
        self._git("commit", "-q", "--allow-empty", "-m", "chore: base")
        self.base = self._git("rev-parse", "HEAD")
        (self.dir / "notes.md").write_text("in /home/alice/x\n")
        self._git("add", "notes.md")
        self._git("commit", "-q", "-m", "fix: one\n\nClaude-Session: https://claude.ai/code/session_01ABCDEFGHIJKLMNOPQRSTUV")
        self._git("commit", "-q", "--allow-empty", "-m", "fix: two\n\nCo-Authored-By: A <a@example.com>")
        self.head = self._git("rev-parse", "HEAD")

    def _step(self, name, **env):
        result = subprocess.run(
            ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", _step(name)],
            env={"PATH": os.environ["PATH"], "RUNNER_TEMP": self._tmp.name, **env},
            cwd=self.dir, capture_output=True, text=True, timeout=30,
        )
        return result.returncode, result.stdout + result.stderr

    def _pr_step(self, title, body, base):
        # The step reads the title and body from the event file, not env.
        event = Path(self._tmp.name) / "event.json"
        event.write_text(json.dumps({"pull_request": {"title": title, "body": body}}), encoding="utf-8")
        return self._step("Check the pull request's title, body and commits",
                          GITHUB_EVENT_PATH=str(event), BASE=base, HEAD=self.head)

    @unittest.skipUnless(shutil.which("jq"), "needs jq")
    def test_pull_request_step(self):
        code, out = self._pr_step("fix: two", ATTRIBUTION + "\ncontact sam@mailbox.test\n", self.base)
        self.assertEqual(code, 1, out)
        self.assertIn("body, line 4: an email address other than a noreply one", out)
        self.assertRegex(out, r"commit [0-9a-f]{7}, line 3: a Claude-Session trailer")
        self.assertRegex(out, r"commit [0-9a-f]{7}, file notes\.md, line 1: a local or project-storage path")
        self.assertNotIn("mailbox.test", out)
        code, out = self._pr_step("fix: contact sam@mailbox.test", ATTRIBUTION, self.head)
        self.assertEqual(code, 1, out)
        self.assertIn("title, line 1: an email address other than a noreply one", out)
        self.assertNotIn("mailbox.test", out)
        code, out = self._pr_step("fix: two", ATTRIBUTION, self.head)
        self.assertEqual(code, 0, out)
        # A pull request opened with no description has a null body.
        code, out = self._pr_step("fix: two", None, self.head)
        self.assertEqual(code, 0, out)

    def test_push_step(self):
        name = "Check the pushed commits"
        code, out = self._step(name, BEFORE=self.base, AFTER=self.head)
        self.assertEqual(code, 1, out)
        self.assertIn("a Claude-Session trailer", out)
        self.assertRegex(out, r"commit [0-9a-f]{7}, file notes\.md, line 1: a local or project-storage path")
        code, out = self._step(name, BEFORE="0" * 40, AFTER=self.head)
        self.assertEqual(code, 0, out)
        code, out = self._step(name, BEFORE="0" * 40, AFTER=self.base)  # a root commit
        self.assertEqual(code, 0, out)


class WorkflowTests(unittest.TestCase):
    def test_workflow_runs_the_script_on_prs_and_main(self):
        workflow = yaml.safe_load(WORKFLOW.read_text())
        triggers = workflow[True] if True in workflow else workflow["on"]
        self.assertEqual(triggers["pull_request"]["types"], ["opened", "edited", "synchronize", "reopened"])
        self.assertEqual(triggers["push"]["branches"], ["main"])
        steps = workflow["jobs"]["public-content"]["steps"]
        runs = [step for step in steps if "run" in step]
        self.assertEqual(len(runs), 2)
        for step in runs:
            self.assertIn(".github/scripts/check_public_content.py", step["run"])
            self.assertRegex(step["run"], r'--files="\$(BASE\.\.\$HEAD|range)"')
            self.assertNotIn("PRIVATE_REPO_NAMES", step["env"])
        self.assertEqual(workflow["permissions"], {"contents": "read"})


class RepositoryTests(unittest.TestCase):
    """Every tracked file passes, so editing a line of one never trips the check."""

    def test_tracked_files_pass(self):
        try:
            listed = subprocess.run(
                ["git", "-C", str(ROOT), "ls-files", "-z"], check=True, capture_output=True, text=True
            ).stdout
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a git checkout")
        found = {}
        for name in filter(None, listed.split("\0")):
            path = ROOT / name
            if name in check.EXEMPT_FILES or path.is_symlink() or not path.is_file():
                continue
            data = path.read_bytes()
            if b"\0" in data:
                continue
            for number, kind in check.scan(name + "\n" + data.decode("utf-8", "replace")):
                found.setdefault(name, []).append((number - 1, kind))  # line 0 is the name
        self.assertEqual(found, {})
