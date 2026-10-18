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
# parseConventionalCommits and DefaultChangelogNotes on 2026-10-18.
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
        self.assertReleases("docs: x", "Prose.\n\nci!: drop a job", "the body has a commit marked breaking")

    def test_extra_entries_count_where_release_please_reads_them(self):
        # A paragraph that opens with a lowercase standard type is a commit.
        self.assertReleases("docs: x", "Prose.\n\nfix: also stop crashing\n\nMore prose.", "the body has a fix entry")
        self.assertReleases("docs: x", "Prose.\n\nperf(cli): also y\ndetail", "the body has a perf entry")
        self.assertReleases("docs: x", "Prose.\n\n```\n\nfix: keep the key\n```\n\nMore.", "the body has a fix entry")
        # So is a trailing footer of a released type, in any case.
        self.assertReleases("docs: x", "Prose.\n\nFix: also y", "the body has a fix entry")
        self.assertReleases("docs: x", "Prose.\n\nfeature(cli): add a flag", "the body has a feature entry")
        self.assertReleases("docs: x", "Note: this matters.\nFeat: y\n  continued", "the body has a feat entry")
        # Elsewhere such lines are prose.
        for body in (
            "Prose.\n\nFix: also y\n\nMore prose.",
            "Prose.\n\nfeature: y\n\nMore prose.",
            "Prose.\nfix: no blank line before\n\nMore prose.",
            "Prose.\n\n```\nfix: keep the key\n```\n\nMore prose.",
            "Prose.\n\n  fix: indented\n\nchore: also\n\nstyle: too\n\nFixes: #12",
            "Prose.\n\n- fix: a bullet\n\n> fix: quoted",
            "Prose.\n\nFeat: y\n  continued\nnot a footer",
        ):
            with self.subTest(body=body):
                self.assertDoesNotRelease("docs: x", body)
        code, out = self._run("chore: x", "Prose.\n\nfeat(cli)!: y\n\nMore prose.\n\nUser-visible: yes")
        self.assertIn("will not release this change", out)

    def test_a_release_as_footer_releases(self):
        self.assertReleases("chore: release 1.0.0", "Release-As: 1.0.0", "the body has a Release-As footer")
        self.assertReleases("chore: release 1.0.0", "Prose.\n\nRelease-As: v1.0.0\nCo-Authored-By: A <a@b.c>",
                            "the body has a Release-As footer")
        self.assertDoesNotRelease("chore: release 1.0.0", "Release-As: 1.0.0\n\nThen prose.")

    def test_override_and_nested_commits_count(self):
        self.assertDoesNotRelease("feat: x", "BEGIN_COMMIT_OVERRIDE\ndocs: y\nEND_COMMIT_OVERRIDE")
        self.assertReleases("docs: x", "BEGIN_COMMIT_OVERRIDE\nfix: y\nEND_COMMIT_OVERRIDE",
                            "the commit override has a fix entry")
        self.assertReleases("docs: x", "Prose.\n\nBEGIN_NESTED_COMMIT\nfix: y\nEND_NESTED_COMMIT",
                            "the body has a fix entry")

    def test_the_line_is_required(self):
        for body in ("", "Prose with no answer.\n", "**User-visible:** yes", "- User-visible: yes",
                     " User-visible: yes", "User visible: yes"):
            self.assertFails("feat: x", body, "The body has no User-visible line")

    def test_the_answer_must_be_yes_or_no(self):
        for body in ("User-visible:", "User-visible: yes or no", "User-visible: maybe", "User-visible: y"):
            self.assertFails("feat: x", body, "must answer yes or no")

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
