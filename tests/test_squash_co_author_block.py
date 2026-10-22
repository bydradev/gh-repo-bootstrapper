"""The title check reads the body as GitHub's default squash commit ends it.

GitHub's default squash commit can add a line of dashes and the commits'
Signed-off-by and Co-authored-by trailers after the body, which ends the
body's trailing footers and can give a breaking-change token a note it lacks.
Each case was checked against release-please 17.6.0's parseConventionalCommits
on 2026-10-22, with and without that block.
"""

import shutil
import unittest
from pathlib import Path

import test_user_visible_line as base

ROOT = Path(__file__).resolve().parent.parent
LOST = "which it reads as a footer only while it ends the squash commit"


@unittest.skipUnless(shutil.which("bash") and shutil.which("python3"), "needs bash and python3")
class SquashCoAuthorBlockTests(unittest.TestCase):
    SCRIPT = base.UserVisibleLineTests.SCRIPT
    _run = base.UserVisibleLineTests._run
    assertPasses = base.UserVisibleLineTests.assertPasses
    assertFails = base.UserVisibleLineTests.assertFails

    def _override(self, title, body):
        return f"BEGIN_COMMIT_OVERRIDE\n{title}\n\n{body}\nEND_COMMIT_OVERRIDE"

    def test_a_release_only_a_trailing_footer_makes_fails_either_answer(self):
        for body, reason in (
            ("Release-As: 1.0.0", "the body has a Release-As footer"),
            ("Prose.\n\nFix: also y", "the body has a fix entry"),
            ("Prose.\n\nci!: drop a job", "the body has a commit marked breaking"),
            ("BREAKING CHANGE #12", "the body has a breaking-change note"),
        ):
            for answer in ("yes", "no"):
                with self.subTest(body=body, answer=answer):
                    self.assertFails("chore: release 1.0.0", f"{body}\n\nUser-visible: {answer}", LOST)
                    self.assertFails("chore: release 1.0.0", f"{body}\n\nUser-visible: {answer}", reason)

    def test_the_same_footer_in_an_override_releases(self):
        for body in ("Release-As: 1.0.0", "Prose.\n\nFix: also y", "BREAKING CHANGE #12"):
            with self.subTest(body=body):
                self.assertPasses("chore: release 1.0.0", self._override("chore: release 1.0.0", body)
                                  + "\n\nUser-visible: yes")

    def test_a_release_the_block_cannot_reach_passes(self):
        # The title, an extra entry that opens a paragraph, and a
        # BREAKING CHANGE: note all survive the block.
        for title, body in (
            ("fix: stop crashing", "Prose."),
            ("chore: tidy", "Prose.\n\nfix: also y"),
            ("docs: x", "Prose.\n\nBREAKING CHANGE: drops x"),
        ):
            with self.subTest(title=title, body=body):
                self.assertPasses(title, f"{body}\n\nUser-visible: yes")

    def test_a_release_as_version_only_a_trailing_footer_carries_fails(self):
        # The title still releases, but at the version Release Please
        # would propose without the footer.
        self.assertFails("feat: add a flag", "Release-As: 1.0.0\n\nUser-visible: yes",
                         "releases this change as 1.0.0 because of its Release-As footer, " + LOST)
        self.assertPasses("feat: add a flag",
                          self._override("feat: add a flag", "Release-As: 1.0.0") + "\n\nUser-visible: yes")

    def test_a_lost_release_as_points_only_to_the_override(self):
        # The title, an extra entry or a note would release the change but
        # still lose the version, so the message names only the override.
        override = "Put the whole commit message with its Release-As footer in a BEGIN_COMMIT_OVERRIDE block"
        for answer in ("yes", "no"):
            with self.subTest(answer=answer):
                code, out = self._run("chore: release 1.0.0", f"Release-As: 1.0.0\n\nUser-visible: {answer}")
                self.assertNotEqual(code, 0, out)
                self.assertIn(override, out)
                self.assertNotIn("Give the release to the title", out)
        self.assertFails("fix: release 1.0.0", "Release-As: 1.0.0\n\nUser-visible: yes", override)
        self.assertFails("chore: x", "Release-As: 1.0.0\n\nFix: also y\n\nUser-visible: yes", override)

    def test_the_block_making_a_release_fails_either_answer(self):
        # An empty BREAKING CHANGE: footer gives no note until the block
        # follows it (release-please 17.6.0, checked 2026-10-22).
        for body in ("Prose.\n\nUser-visible: {}\nBREAKING CHANGE:", "Prose.\n\nBREAKING CHANGE:\n\nUser-visible: {}"):
            for answer in ("yes", "no"):
                with self.subTest(body=body, answer=answer):
                    self.assertFails("docs: x", body.format(answer), "because the body has a "
                                     "breaking-change note only once GitHub's default squash commit adds")

    def test_a_version_the_block_changes_fails(self):
        # Without the block the title's own footer sets 1.0.0; after it,
        # the nested commit's 2.0.0 is the first Release-As note.
        nested = "Release-As: 1.0.0\n\nBEGIN_NESTED_COMMIT\nchore: y\n\nRelease-As: 2.0.0\nEND_NESTED_COMMIT"
        self.assertFails("feat: x", f"{nested}\n\nUser-visible: yes", "proposes another version")

    def test_the_messages_print_no_footer_text_but_the_version(self):
        body = "Release-As: 1.0.0 <b>arbitrary PR text</b>\n\nUser-visible: yes"
        for title, version in (("feat: x", "as 1.0.0 because"), ("chore: x", "Release-As footer")):
            with self.subTest(title=title):
                code, out = self._run(title, body)
                self.assertNotEqual(code, 0, out)
                self.assertIn(version, out)
                self.assertNotIn("arbitrary", out)

    def test_both_copies_of_the_workflow_carry_the_check(self):
        template = (ROOT / "templates" / "pr-title-check.yml").read_bytes()
        self.assertEqual((ROOT / ".github" / "workflows" / "pr-title-check.yml").read_bytes(), template)
        self.assertIn(b'CO_AUTHORS = "\\n\\n---------\\n\\nCo-authored-by: A <a@example.com>"', template)


if __name__ == "__main__":
    unittest.main()
