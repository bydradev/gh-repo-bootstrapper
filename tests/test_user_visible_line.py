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


def _bash_major():
    if not shutil.which("bash"):
        return 0
    result = subprocess.run(["bash", "-c", "echo ${BASH_VERSINFO[0]}"], capture_output=True, text=True)
    return int(result.stdout.strip() or 0)


def _script(text):
    job = yaml.safe_load(text)["jobs"]["validate-title"]
    return next(step["run"] for step in job["steps"] if step.get("name") == validate_templates.USER_VISIBLE_STEP)


# The script lowercases with ${var,,}, which needs bash 4, as on GitHub's
# Ubuntu runners; macOS ships bash 3.2.
@unittest.skipUnless(_bash_major() >= 4, "needs bash 4 or newer")
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

    def test_an_answer_that_agrees_with_the_title_type_passes(self):
        for title in ("feat: add a flag", "fix(cli): stop crashing", "perf: cache renders", "revert: drop the flag"):
            self.assertPasses(title, "Prose.\n\nUser-visible: yes\n")
        for title in ("docs: fix a typo", "chore: tidy", "refactor(core): split a module",
                      "test: cover x", "build: bump a tool", "ci: cache"):
            self.assertPasses(title, "Prose.\n\nUser-visible: no\n")

    def test_an_answer_that_disagrees_with_the_title_type_fails(self):
        self.assertFails("chore: tidy", "User-visible: yes", "the title type is chore")
        self.assertFails("docs: fix a typo", "User-visible: yes", "retitle it feat, fix, perf or revert")
        self.assertFails("fix: stop crashing", "User-visible: no", "because the title type is fix")

    def test_a_breaking_change_releases_whatever_its_type(self):
        self.assertPasses("chore!: drop the old flag", "User-visible: yes")
        self.assertFails("refactor(api)!: rename", "User-visible: no", "the title marks a breaking change")
        self.assertFails("docs: x", "Prose.\n\nBREAKING CHANGE: the flag is gone\n\nUser-visible: no",
                         "breaking-change footer")
        self.assertFails("docs: x", "BREAKING-CHANGE: gone\nUser-visible: no", "breaking-change footer")
        self.assertFails("docs: x", "ci!: drop a job\n\nUser-visible: no", "entry line marked breaking")

    def test_extra_entries_at_column_0_count(self):
        self.assertPasses("docs: x", "Prose.\n\nfix: also stop crashing\n\nUser-visible: yes")
        self.assertPasses("docs: x", "Prose.\n\nfeature(cli): add a flag\n\nUser-visible: yes")
        # Release Please matches types in any case.
        self.assertFails("docs: x", "Fix: also y\n\nUser-visible: no", "the body has a fix entry line")
        # Indented, hidden-type or footer lines are not releasable entries.
        self.assertPasses("docs: x", "Prose.\n\n  fix: indented\n\nchore: also\n\nFixes: #12\n\nUser-visible: no")

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
        self.assertFails("docs: x", "Prose.\r\n\r\nfix: y\r\n\r\nUser-visible: no\r\n", "fix entry line")

    def test_body_text_is_neither_run_nor_echoed(self):
        body = "$(touch pwned) `touch pwned2` ${IFS}\n::warning::injected\nUser-visible: yes\n"
        code, out = self._run("feat: x", body)
        self.assertEqual(code, 0, out)
        self.assertNotIn("injected", out)
        code, out = self._run("chore: x", "fix: ::warning::injected\nUser-visible: no\n")
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
        start = text.index("      # Release Please releases")
        moved = text[:start].rstrip("\n") + "\n"
        step = text[start:]
        moved = moved.replace("    steps:\n", "    steps:\n" + step + "\n", 1)
        errors = validate_templates.check_user_visible_step("t", {".github/workflows/pr-title-check.yml": moved})
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("must come after 'Validate PR title'", errors[0])

    def test_a_changed_step_fails(self):
        for edit, needle in (
            (lambda t: t.replace("Check the user-visible line", "Check the body", 1), "exactly once"),
            (lambda t: t.replace('<<< "$BODY"', '<<< "${{ github.event.pull_request.body }}"', 1),
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
