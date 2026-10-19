"""The title check's user-visible step, run as GitHub runs it."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

import validate_templates

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "pr-title-check.yml"


def _script(text):
    job = yaml.safe_load(text)["jobs"]["validate-title"]
    return next(step["run"] for step in job["steps"] if step.get("name") == validate_templates.USER_VISIBLE_STEP)


# Each releasable case here was checked against release-please 17.6.0's own
# parseConventionalCommits and DefaultChangelogNotes, each Release-As version
# against its Version.parse, and each <details> case against its
# PullRequestBody, on 2026-10-18 or 2026-10-19.
@unittest.skipUnless(shutil.which("bash") and shutil.which("python3"), "needs bash and python3")
class UserVisibleLineTests(unittest.TestCase):
    SCRIPT = _script(TEMPLATE.read_text())

    def _run(self, title, body):
        # GitHub's default shell for a run step on Linux.
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", self.SCRIPT],
                env={"PATH": os.environ["PATH"], "TITLE": title, "BODY": body},
                cwd=tmp, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(os.listdir(tmp), [], "the script must not write files")
        return result.returncode, result.stdout + result.stderr

    def assertPasses(self, title, body):
        code, out = self._run(title, body)
        self.assertEqual(code, 0, out)
        self.assertNotIn("::error", out)

    def assertFails(self, title, body, needle):
        code, out = self._run(title, body)
        self.assertNotEqual(code, 0, out)
        self.assertIn("::error title=User-visible line::", out)
        self.assertIn(needle, out)

    def assertReleases(self, title, body, reason):
        self.assertFails(title, body + "\n\nUser-visible: no", f"because {reason}.")
        self.assertPasses(title, body + "\n\nUser-visible: yes")

    def assertDoesNotRelease(self, title, body):
        self.assertPasses(title, body + "\n\nUser-visible: no")
        self.assertFails(title, body + "\n\nUser-visible: yes", "will not release this change")

    def test_an_answer_that_agrees_with_the_title_type_passes(self):
        for title in ("feat: add a flag", "fix(cli): stop crashing", "perf: cache renders", "revert: drop the flag"):
            self.assertPasses(title, "Prose.\n\nUser-visible: yes\n")
        for title in ("docs: fix a typo", "chore: tidy", "refactor(core): split a module",
                      "test: cover x", "build: bump a tool", "ci: cache"):
            self.assertPasses(title, "Prose.\n\nUser-visible: no\n")

    def test_an_answer_that_disagrees_with_the_title_type_fails(self):
        self.assertFails("chore: tidy", "User-visible: yes", "neither the title nor the body")
        self.assertFails("docs: fix a typo", "User-visible: yes", "retitle it feat, fix, perf or revert")
        self.assertFails("fix: stop crashing", "User-visible: no", "because the title type is fix")

    def test_a_breaking_change_releases_whatever_its_type(self):
        self.assertReleases("chore!: drop the old flag", "Prose.", "the title marks a breaking change")
        self.assertReleases("refactor(api)!: rename", "", "the title marks a breaking change")
        note = "the body has a breaking-change note"
        self.assertReleases("docs: x", "Prose.\n\nBREAKING CHANGE: the flag is gone\n\nMore prose.", note)
        self.assertReleases("docs: x", "Prose.\n\nBREAKING CHANGE:\n- the flag is gone", note)
        self.assertReleases("docs: x", "Prose.\n\nBREAKING CHANGE #12", note)
        # Release Please finds this token anywhere in the body, quoted or not.
        self.assertReleases("docs: x", "The `BREAKING-CHANGE:` token is accepted.", note)
        self.assertReleases("docs: x", "Prose.\n\n    BREAKING-CHANGE: indented\n\nMore.", note)
        self.assertDoesNotRelease("docs: x", "Prose about a BREAKING CHANGE: inline.")
        # A footer note is its value or its last continuation line, and the
        # last marker's note replaces the earlier ones.
        self.assertReleases("docs: x", "Prose.\n\nBREAKING CHANGE:\n  the flag is gone", note)
        for body in (
            "Prose.\n\nBREAKING CHANGE:",
            "Prose.\n\nBREAKING CHANGE:\nRefs: #1",
            "Prose.\nBREAKING CHANGE: the flag is gone\n\nRefs: #1\nBREAKING CHANGE:",
            "Prose.\n\nRefs: the BREAKING-CHANGE: token",
            "Prose.\n\nBREAKING-CHANGES: none",
            "Prose.\n\nBREAKING CHANGES: none",
            "Prose ending BREAKING-CHANGE:",
            "Prose.\n\nBREAKING CHANGE: the flag is gone\n   \nRefs: #1",
        ):
            with self.subTest(body=body):
                self.assertDoesNotRelease("docs: x", body)
        self.assertReleases("docs: x", "Prose.\n\nci!: drop a job", "the body has a commit marked breaking")
        # With no subject, only a type of word characters is breaking.
        for body in ("Prose.\n\nBEGIN_NESTED_COMMIT\ndocs!:\nEND_NESTED_COMMIT",
                     "Prose.\n\nBEGIN_NESTED_COMMIT\nre-ref!: y\nEND_NESTED_COMMIT"):
            with self.subTest(body=body):
                self.assertReleases("docs: x", body, "the body has a commit marked breaking")
        for body in ("Prose.\n\nBEGIN_NESTED_COMMIT\nre-ref!:\nEND_NESTED_COMMIT", "Prose.\n\nRe-ref!:",
                     "Prose.\n\nBEGIN_NESTED_COMMIT\nd\u00f6cs!:\nEND_NESTED_COMMIT"):
            with self.subTest(body=body):
                self.assertDoesNotRelease("docs: x", body)
        # An empty footer marker after the header replaces the subject's
        # note, which the preset then restores only for a word type.
        for body in ("Prose.\n\nRe-ref!: x\n  BREAKING CHANGE:",
                     "Prose.\n\nBEGIN_NESTED_COMMIT\nRe-ref!: x\n\nBREAKING CHANGE:\nEND_NESTED_COMMIT",
                     ("BEGIN_COMMIT_OVERRIDE\nre-ref(api)!: x\n\nBREAKING CHANGE: y\nBREAKING CHANGE:\n"
                      "END_COMMIT_OVERRIDE")):
            with self.subTest(body=body):
                self.assertDoesNotRelease("docs: x", body)
        self.assertReleases("docs: x", "Prose.\n\nci!: x\n  BREAKING CHANGE:", "the body has a commit marked breaking")
        self.assertReleases("docs: x", "BEGIN_COMMIT_OVERRIDE\nre-ref!: x\n\nBREAKING CHANGE:\nBREAKING CHANGE: y\n"
                            "END_COMMIT_OVERRIDE", "the commit override has a commit marked breaking")
        # Release Please reads a footer and its continuation lines again as
        # a commit of their own.
        self.assertReleases("docs: x", "Prose.\n\nExample:\n\n    BREAKING CHANGE: the --foo flag is gone", note)
        self.assertReleases("docs: x", "Prose.\n\nRefs: #1\n  the BREAKING-CHANGE: token", note)

    def test_extra_entries_count_where_release_please_reads_them(self):
        # A paragraph that opens with a lowercase standard type is a commit.
        self.assertReleases("docs: x", "Prose.\n\nfix: also stop crashing\n\nMore prose.", "the body has a fix entry")
        self.assertReleases("docs: x", "Prose.\n\nperf(cli): also y\ndetail", "the body has a perf entry")
        self.assertReleases("docs: x", "Prose.\n\n```\n\nfix: keep the key\n```\n\nMore.", "the body has a fix entry")
        # So is a trailing footer of a released type, in any case.
        self.assertReleases("docs: x", "Prose.\n\nFix: also y", "the body has a fix entry")
        self.assertReleases("docs: x", "Prose.\n\nfeature(cli): add a flag", "the body has a feature entry")
        self.assertReleases("docs: x", "Note: this matters.\nFeat: y\n  continued", "the body has a feat entry")
        # Release Please reads each footer with its continuation lines, less
        # their indent, as a commit, unless it has no colon or such a line
        # makes the parser throw.
        self.assertReleases("docs: x", "Prose.\n\nExample:\n\n    feat(api): add the endpoint",
                            "the body has a feat entry")
        # Elsewhere such lines are prose.
        for body in (
            "Prose.\n\nFix: also y\n\nMore prose.",
            "Prose.\n\nfeature: y\n\nMore prose.",
            "Prose.\nfix: no blank line before\n\nMore prose.",
            "Prose.\n\n```\nfix: keep the key\n```\n\nMore prose.",
            "Prose.\n\n  fix: indented\n\nchore: also\n\nstyle: too\n\nFixes: #12",
            "Prose.\n\n- fix: a bullet\n\n> fix: quoted",
            "Prose.\n\nFeat: y\n  continued\nnot a footer",
            "Prose.\n\nFix #12",
            "Prose.\n\nRefs #12\n  feat: y",
            "Prose.\n\nFix: y\n  f(g(x))",
            "Prose.\n\nOutput:\n  fix: y\n\n  More output.",
            "Prose.\n\nFix: y\n  ok\n  f(g(x))",
            "Prose.\n\nBREAKING-CHANGE: x\n  feat: y\n   ",
        ):
            with self.subTest(body=body):
                self.assertDoesNotRelease("docs: x", body)
        # A footer with an empty scope is prose (a paragraph that opens with
        # one is a dropped entry, tested below); a "!" footer keeps the
        # footers together.
        self.assertDoesNotRelease("docs: x", "Prose.\n\nOther: x\nfix(): y")
        self.assertReleases("docs: x", "Prose.\n\nFeat: y\n!: x", "the body has a feat entry")
        code, out = self._run("chore: x", "Prose.\n\nfeat(cli)!: y\n\nMore prose.\n\nUser-visible: yes")
        self.assertIn("will not release this change", out)

    def test_a_release_as_footer_releases(self):
        self.assertReleases("chore: release 1.0.0", "Release-As: 1.0.0", "the body has a Release-As footer")
        self.assertReleases("chore: release 1.0.0", "Prose.\n\nRelease-As: v1.0.0\nCo-Authored-By: A <a@b.c>",
                            "the body has a Release-As footer")
        self.assertDoesNotRelease("chore: release 1.0.0", "Release-As: 1.0.0\n\nThen prose.")
        # The version is the footer's value or its last continuation line.
        for body in ("Release-As #1.0.0", "Release-As:\n  1.0.0", "Release-As: pkg@1.0.0",
                     "Release-As: 1.0.0\nRelease-As: next", "Prose.\n\nExample:\n  Release-As: 2.0.0",
                     "Release-As: 2.0.0\n\nchore: y\n\nRelease-As: next"):
            with self.subTest(body=body):
                self.assertReleases("chore: release 1.0.0", body, "the body has a Release-As footer")
        self.assertDoesNotRelease("chore: release 1.0.0", "Release-As: @scope/pkg@1.0.0")
        self.assertDoesNotRelease("chore: release 1.0.0", "Release-As: 1.2.x\n\nThen prose.")

    def test_a_release_as_version_release_please_cannot_read_fails(self):
        # Release Please reads the first Release-As footer's version before
        # it writes the changelog, and stops with an error when it cannot.
        for body in ("Release-As: 1.2.x", "Release-As: next", "Release-As:", "Release-As: 1.0.0\n  then words",
                     "Release-As: next\nRelease-As: 1.0.0", "Prose.\n\nExample:\n  Release-As: next",
                     "Release-As: 1.0.0\nRefs: x\n  Release-As: next", "release-as: next"):
            for title, answer in (("chore: release 1.0.0", "yes"), ("docs: x", "no"), ("feat: x", "yes")):
                with self.subTest(body=body, title=title):
                    self.assertFails(title, f"{body}\n\nUser-visible: {answer}",
                                     "cannot read the version in the Release-As footer")

    def test_override_and_nested_commits_count(self):
        self.assertDoesNotRelease("feat: x", "BEGIN_COMMIT_OVERRIDE\ndocs: y\nEND_COMMIT_OVERRIDE")
        self.assertReleases("docs: x", "BEGIN_COMMIT_OVERRIDE\nfix: y\nEND_COMMIT_OVERRIDE",
                            "the commit override has a fix entry")
        self.assertReleases("docs: x", "Prose.\n\nBEGIN_NESTED_COMMIT\nfix: y\nEND_NESTED_COMMIT",
                            "the body has a fix entry")
        # A commit's header may use " #" in place of ":".
        self.assertReleases("docs: x", "BEGIN_COMMIT_OVERRIDE\nfix #123 y\nEND_COMMIT_OVERRIDE",
                            "the commit override has a fix entry")
        self.assertReleases("docs: x", "Prose.\n\nBEGIN_NESTED_COMMIT\nfix #12 y\nEND_NESTED_COMMIT",
                            "the body has a fix entry")

    def test_a_line_release_please_cannot_parse_fails_when_it_drops_a_change(self):
        # Release Please drops the whole commit, so the title's entry is lost.
        for body in ("Prose.\n\nz.array(z.boolean())", "Prose.\n\n`f(g(x))`   ", "Prose.\n\nf(x\n\nMore."):
            with self.subTest(body=body):
                for answer in ("yes", "no"):
                    self.assertFails("feat: x", f"{body}\n\nUser-visible: {answer}",
                                     "Release Please cannot parse line 3 of the body")
        # Code in a pull request body is the usual source.
        for code in ("useEffect(() => {\n  load();\n}, []);", 'describe("x", () => {', "print(len(x))",
                     "subprocess.run(\n    [\"x\"],\n)"):
            with self.subTest(code=code):
                self.assertFails("fix: x", f"Prose.\n\n```\n{code}\n```\n\nUser-visible: yes", "cannot parse line 4")
        # A dropped entry part loses only that entry, which still fails.
        self.assertFails("feat: x", "Prose.\n\nfix: y\nf(a(b))\n\nUser-visible: yes", "cannot parse line 4")
        # The line named is the one that drops the change, not one like it.
        self.assertFails("fix: x", "Prose.\n\n```\ndef f():\n    print(len(x))\nprint(len(x))\n```\n\n"
                         "User-visible: yes", "cannot parse line 6")
        self.assertFails("docs: x", "Prose.\n\n```\nf(g(x))\n```\n\nfix: y\nf(g(x))\n\nUser-visible: yes",
                         "cannot parse line 8")
        self.assertFails("docs: x", "Intro.\n\nBEGIN_COMMIT_OVERRIDE\nfix: y\nf(g(x))\nEND_COMMIT_OVERRIDE\n\n"
                         "User-visible: yes", "cannot parse line 5")
        self.assertFails("docs: x", "User-visible: yes\n\n```\nfix: y\nf(g(x))\n```\n\nfix: y\nf(g(x))",
                         "cannot parse line 9")
        self.assertFails("docs: x", "Prose.\n\nBEGIN_NESTED_COMMIT\nfix: y\nf(g(x))\nEND_NESTED_COMMIT\n\nfeat: z\n\n"
                         "User-visible: yes", "cannot parse line 5")
        self.assertFails("docs: x", "Prose.\n\n```\nfix: y\nf(g(x))\n```\n\nBEGIN_NESTED_COMMIT\nfix: y\nf(g(x))\n"
                         "END_NESTED_COMMIT\n\nfeat: z\n\nUser-visible: yes", "cannot parse line 10")
        self.assertFails("docs: x", "Prose.\n\nBEGIN_NESTED_COMMIT\ndocs: n\nEND_NESTED_COMMIT\n\nfix: y\nf(g(x))\n\n"
                         "User-visible: yes", "cannot parse line 8")
        self.assertFails("fix: x", "Prose.\nBEGIN_NESTED_COMMIT\ndocs: n\nEND_NESTED_COMMIT\nf(g(x))\n\nUser-visible: yes",
                         "cannot parse a line of the body")
        # Nothing that would release is lost, or the line parses.
        self.assertPasses("docs: x", "Prose.\n\n```\nf(a(b))\n```\n\nUser-visible: no")
        for line in ("  z.array(z.boolean())", "- f(g(x))", "f (g(x))", "f(x)(y)", "f()", "Prose ending f(g(x",
                     "BREAKING-CHANGE(x("):
            with self.subTest(line=line):
                self.assertPasses("feat: x", f"Prose.\n\n{line}\n\nUser-visible: yes")

    def test_an_entry_scope_release_please_cannot_parse_fails_when_it_drops_a_change(self):
        # Release Please drops the entry whole, with the change it carries.
        for body, line in (("Prose.\n\nfix(a(b)): y", 3), ("Prose.\n\nfix(): y", 3),
                           ("Prose.\n\nBEGIN_NESTED_COMMIT\nfix(a(b)): y\nEND_NESTED_COMMIT", 4),
                           ("Prose.\n\nBEGIN_NESTED_COMMIT\nFIX(a) (b): y\nEND_NESTED_COMMIT", 4),
                           ("Prose.\n\nBEGIN_NESTED_COMMIT\nfix(a(b)) #12 y\nEND_NESTED_COMMIT", 4),
                           ("Prose.\n\nBEGIN_NESTED_COMMIT\ndocs(a(b))!: y\nEND_NESTED_COMMIT", 4),
                           ("Prose.\n\nBEGIN_NESTED_COMMIT\ndocs(a(b)): y\n\nBREAKING CHANGE: z\nEND_NESTED_COMMIT", 4),
                           ("BEGIN_COMMIT_OVERRIDE\nfix(a(b)): y\n\nfeat: z\nEND_COMMIT_OVERRIDE", 2)):
            for title in ("fix: x", "docs: x"):
                for answer in ("yes", "no"):
                    with self.subTest(title=title, body=body, answer=answer):
                        self.assertFails(title, f"{body}\n\nUser-visible: {answer}",
                                         f"cannot parse line {line} of the body, so it would drop a change")
        # Nothing that would release is lost.
        self.assertReleases("fix: x", "Prose.\n\ndocs(a(b)): y", "the title type is fix")
        self.assertReleases("fix: x", "Prose.\n\nBEGIN_NESTED_COMMIT\nsee f(g(x)): y\nEND_NESTED_COMMIT",
                            "the title type is fix")
        self.assertDoesNotRelease("docs: x", "Prose.\n\nBEGIN_NESTED_COMMIT\nchore(): y\nEND_NESTED_COMMIT")

    def test_a_details_tag_the_changelog_keeps_as_html_fails(self):
        # node-html-parser reads it as a <details> element when Release Please
        # parses its release pull request's body, which then throws, or reads
        # it as the notes of another release.
        for title, body in (("fix: keep `<details>` open", "Prose."), ("fix: keep ``<DETAILS open>`` open", "Prose."),
                            ("fix: keep `<details/>` open", "Prose."),
                            ("fix: keep `<details><summary>x 1.2.3</summary>` open", "Prose."),
                            ("fix(<details>): x", "Prose."), ("docs!: drop <details> support", "Prose."),
                            ("fix: x", "BREAKING CHANGE: drop <details> support"),
                            ("fix: x", "BREAKING CHANGE: drop\n  <details> support"),
                            ("feat: x", "Prose about BREAKING-CHANGE: the <details> tag"),
                            ("feat: x", "Prose.\n\nBREAKING CHANGE: the <details> tag goes.\n\nMore."),
                            ("fix: x", "Prose.\n\nfix: keep `<details>` open"),
                            ("fix: x", "Prose.\n\nBEGIN_NESTED_COMMIT\nfix: keep `<details>` open\nEND_NESTED_COMMIT"),
                            ("fix: x", "Prose.\n\nRefs: #1\nfix(<details>): y"),
                            ("docs: x", "BEGIN_COMMIT_OVERRIDE\nfix: keep `<details>` open\nEND_COMMIT_OVERRIDE"),
                            ("chore: keep `<details>` open", "Release-As: 1.2.3")):
            for answer in ("yes", "no"):
                with self.subTest(title=title, body=body, answer=answer):
                    self.assertFails(title, f"{body}\n\nUser-visible: {answer}",
                                     "could not read back its release pull request")
        # Text the changelog escapes, leaves out, or that is not the tag.
        for title, body in (("fix: keep <details> open", "Prose."),
                            ("fix: keep `</details>` and `<detailsx>` open", "Prose."),
                            ("fix: keep `<details` open", "Prose."), ("fix(details): x", "Prose."),
                            ("fix: x", "Prose with `<details>` and <details> in the body."),
                            ("fix: x", "Prose.\n\ndocs: keep `<details>` open")):
            with self.subTest(title=title, body=body):
                self.assertReleases(title, body, "the title type is fix")
        self.assertReleases("fix: keep `<details>` open", "BEGIN_COMMIT_OVERRIDE\nfix: y\nEND_COMMIT_OVERRIDE",
                            "the commit override has a fix entry")
        self.assertDoesNotRelease("docs: keep `<details>` open", "Prose.")

    def test_a_title_release_please_cannot_parse_releases_nothing(self):
        for title in ("feat(): x", "feat(a(b)): x"):
            with self.subTest(title=title):
                self.assertFails(title, "Prose.\n\nUser-visible: yes", "cannot parse the title")
                self.assertPasses(title, "Prose.\n\nUser-visible: no")

    def test_the_line_is_required(self):
        for body in ("", "Prose with no answer.\n", "**User-visible:** yes", "- User-visible: yes",
                     " User-visible: yes", "User visible: yes"):
            self.assertFails("feat: x", body, "The body has no User-visible line")

    def test_the_answer_must_be_yes_or_no(self):
        for body in ("User-visible:", "User-visible: yes or no", "User-visible: maybe", "User-visible: y"):
            self.assertFails("feat: x", body, "must answer yes or no")

    def test_the_generated_pull_request_template_waits_for_an_answer(self):
        template = (ROOT / "templates" / "pull-request-template.md").read_text()
        for body in (template, template.replace("\n", "\r\n")):
            self.assertFails("feat: x", body, "must answer yes or no")
            self.assertPasses("feat: x", body.replace("User-visible: yes or no", "User-visible: yes"))
            self.assertPasses("docs: x", body.replace("User-visible: yes or no", "User-visible: no"))

    def test_conflicting_answers_fail_and_repeated_ones_pass(self):
        self.assertFails("docs: x", "User-visible: yes\nUser-visible: no", "Keep one")
        self.assertPasses("docs: x", "User-visible: no\n\nUser-visible: no")

    def test_case_trailing_spaces_and_crlf_bodies_are_accepted(self):
        self.assertPasses("feat: x", "Prose.\r\n\r\nuser-visible:YES  \r\n")
        self.assertPasses("docs: x", "Prose.\r\n\r\nUSER-VISIBLE: No\r\n")
        self.assertFails("docs: x", "Prose.\r\n\r\nfix: y\r\n\r\nUser-visible: no\r\n", "fix entry")

    def test_body_text_is_neither_run_nor_echoed(self):
        body = "$(touch pwned) `touch pwned2` ${IFS}\n::warning::injected\nUser-visible: yes\n"
        code, out = self._run("feat: x", body)
        self.assertEqual(code, 0, out)
        self.assertNotIn("injected", out)
        code, out = self._run("chore: x", "Prose.\n\nfix: ::warning::injected\n\nUser-visible: no\n")
        self.assertNotEqual(code, 0, out)
        self.assertNotIn("injected", out)
        code, out = self._run("docs: x", "BEGIN_COMMIT_OVERRIDE\n::warning::injected: y\nEND_COMMIT_OVERRIDE\n"
                                         "User-visible: yes\n")
        self.assertNotEqual(code, 0, out)
        self.assertNotIn("injected", out)


class OwnTitleCheckTests(unittest.TestCase):
    def test_this_repository_runs_the_template_title_check(self):
        own = ROOT / ".github" / "workflows" / "pr-title-check.yml"
        self.assertEqual(own.read_text(), TEMPLATE.read_text())


class UserVisibleStepCheckTests(unittest.TestCase):
    def _check(self, edit):
        text = edit(TEMPLATE.read_text())
        return validate_templates.check_user_visible_step("t", {".github/workflows/pr-title-check.yml": text})

    def test_the_template_passes_and_other_files_are_skipped(self):
        self.assertEqual(self._check(lambda t: t), [])
        self.assertEqual(validate_templates.check_user_visible_step("t", {}), [])

    def test_the_step_must_follow_the_title_step(self):
        text = TEMPLATE.read_text()
        start = text.index("\n      # Asking a yes/no question") + 1
        moved = text[:start].rstrip("\n") + "\n"
        step = text[start:]
        moved = moved.replace("    steps:\n", "    steps:\n" + step + "\n", 1)
        errors = validate_templates.check_user_visible_step("t", {".github/workflows/pr-title-check.yml": moved})
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("must come after 'Validate PR title'", errors[0])

    def test_a_changed_step_fails(self):
        for edit, needle in (
            (lambda t: t.replace("Check the user-visible line", "Check the body", 1), "exactly once"),
            (lambda t: t.replace('os.environ.get("BODY", "")', '"""${{ github.event.pull_request.body }}"""', 1),
             "without ${{ }} expressions"),
            (lambda t: t.replace("          TITLE: ${{ github.event.pull_request.title }}\n", "", 1),
             "must set exactly env"),
            (lambda t: t.replace("      - name: Check the user-visible line\n",
                                 "      - name: Check the user-visible line\n        shell: sh\n", 1),
             "must not set shell"),
        ):
            errors = self._check(edit)
            self.assertEqual(len(errors), 1, errors)
            self.assertIn(needle, errors[0])


if __name__ == "__main__":
    unittest.main()
