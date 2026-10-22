"""The title check reads the body as GitHub's default squash commit ends it.

GitHub's default squash commit can add a line of dashes and the commits'
Signed-off-by and Co-authored-by trailers after the body, which ends the
body's trailing footers. Each case was checked against release-please
17.6.0's parseConventionalCommits on 2026-10-22, with and without that block.
"""

import shutil
import unittest
from pathlib import Path

import test_user_visible_line as base

ROOT = Path(__file__).resolve().parent.parent
LOST = "but only while that footer ends the squash commit"


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

    def test_both_copies_of_the_workflow_carry_the_check(self):
        template = (ROOT / "templates" / "pr-title-check.yml").read_bytes()
        self.assertEqual((ROOT / ".github" / "workflows" / "pr-title-check.yml").read_bytes(), template)
        self.assertIn(b'CO_AUTHORS = "\\n\\n---------\\n\\nCo-authored-by: A <a@example.com>"', template)


if __name__ == "__main__":
    unittest.main()
