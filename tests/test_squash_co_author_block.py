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

    def test_the_block_making_a_released_change_breaking_fails_either_answer(self):
        # Under a title that releases on its own, a bare marker gives no
        # note as the body stands, but after the block the release is a
        # breaking one (release-please 17.6.0, checked 2026-11-16 for each
        # of these titles, both spellings, and prose that ends in the
        # hyphenated token).
        needle = "reads this change as breaking only once GitHub's default squash commit adds"
        for title in ("fix: x", "feat: x", "perf: x", "revert: x"):
            for marker in ("BREAKING CHANGE", "BREAKING-CHANGE"):
                for body in (
                    f"Prose.\n\n{marker}:\n\nUser-visible: {{}}",
                    f"Prose.\n\n{marker}:\nRefs: #1\n\nUser-visible: {{}}",
                    f"Prose.\n\nUser-visible: {{}}\n{marker}:",
                ):
                    for answer in ("yes", "no"):
                        with self.subTest(title=title, body=body, answer=answer):
                            self.assertFails(title, body.format(answer), needle)
            with self.subTest(title=title, body="prose ending in the token"):
                self.assertFails(title, "Prose ending BREAKING-CHANGE:\n\nUser-visible: yes", needle)

    def test_a_bare_marker_after_a_breaking_title_fails_either_answer(self):
        # "!" makes the subject the note, but a bare footer marker replaces
        # it with nothing, so the commit is not breaking as written and is
        # once the block follows (release-please 17.6.0, checked
        # 2026-11-16). Under docs!, which then releases nothing, the
        # existing message for a release only the block makes applies.
        for title, needle in (
            ("fix!: x", "reads this change as breaking only once"),
            ("feat!: x", "reads this change as breaking only once"),
            ("docs!: x", "only once GitHub's default squash commit adds"),
        ):
            for body in ("Prose.\n\nBREAKING CHANGE:", "Prose.\n\nBREAKING-CHANGE:\nRefs: #1"):
                for answer in ("yes", "no"):
                    with self.subTest(title=title, body=body, answer=answer):
                        self.assertFails(title, f"{body}\n\nUser-visible: {answer}", needle)

    def test_a_breaking_change_the_block_leaves_alone_passes(self):
        # A note after the colon, or "!" on the title with no empty marker
        # to erase its subject note, is breaking with or without the block,
        # and an override, which no block follows, keeps a bare marker an
        # empty footer.
        for title, body in (
            ("fix!: x", "Prose."),
            ("docs!: x", "Prose.\n\nRefs: #1"),
            ("fix: x", "Prose.\n\nBREAKING CHANGE: drops x"),
            ("feat: x", "Prose.\n\nBREAKING-CHANGE: drops x\nRefs: #1"),
            ("fix: x", self._override("fix: x", "Prose.\n\nBREAKING CHANGE:")),
            ("perf: x", self._override("perf: x", "Prose.\n\nBREAKING-CHANGE:\nRefs: #1")),
        ):
            with self.subTest(title=title, body=body):
                self.assertPasses(title, f"{body}\n\nUser-visible: yes")

    def test_a_breaking_change_only_a_trailing_footer_gives_fails_either_answer(self):
        # An entry with a type and "!", or a breaking-change marker with a
        # hash, among the trailing footers makes a breaking commit while it
        # ends the squash commit and is body text once the block follows:
        # the release is a plain one (release-please 17.6.0, checked
        # 2026-11-17 for each of these titles and bodies).
        needle = "reads this change as breaking only while the body's trailing footers end the squash commit"
        for title in ("fix: x", "feat: x", "perf: x", "revert: x"):
            for body in (
                "Prose.\n\nfeat!: y\n\nUser-visible: {}",
                "Prose.\n\nfeat!: y\nUser-visible: {}",
                "Prose.\n\nUser-visible: {}\nfix(api)!: y",
                "Prose.\n\nBREAKING CHANGE #12\n\nUser-visible: {}",
                "Prose.\n\nUser-visible: {}\nBREAKING CHANGE #12",
            ):
                for answer in ("yes", "no"):
                    with self.subTest(title=title, body=body, answer=answer):
                        self.assertFails(title, body.format(answer), needle)

    def test_a_breaking_change_the_block_keeps_passes(self):
        # A BREAKING CHANGE: note, on its own or after an entry it then
        # marks, "!" on the title, and an override all keep the release a
        # breaking one after the block (release-please 17.6.0, checked
        # 2026-11-17). A "!" entry that is not among the trailing footers is
        # not read at all, as written or after the block, so the title's
        # plain release passes.
        for title, body in (
            ("fix: x", "Prose.\n\nfeat: y\n\nBREAKING CHANGE: drops z"),
            ("fix: x", "Prose.\n\nBREAKING CHANGE: drops y"),
            ("fix!: x", "Prose."),
            ("feat!: x", "Prose.\n\nfeat: y\n\nBREAKING CHANGE: drops z"),
            ("fix: x", self._override("fix: x", "Prose.\n\nfeat!: y")),
            ("fix: x", "Prose.\n\nfeat!: y\n\nMore prose."),
        ):
            with self.subTest(title=title, body=body):
                self.assertPasses(title, f"{body}\n\nUser-visible: yes")

    def test_an_entry_only_a_trailing_footer_gives_fails_either_answer(self):
        # Under a title that releases on its own, an extra entry of a
        # released type that only the body's trailing footers give is
        # body text once the block follows, so it drops out of the
        # changelog, and a feat's bump with it (release-please 17.6.0,
        # checked 2026-11-17 for each of these titles and bodies).
        for title, body, kinds in (
            ("fix: x", "Prose.\n\nUser-visible: {}\nfeat: y", "feat entry as an extra changelog entry"),
            ("fix: x", "Prose.\n\nFeat: y\n\nUser-visible: {}", "Feat entry as an extra changelog entry"),
            ("fix!: x", "Prose.\n\nfeat!: y\n\nUser-visible: {}", "feat! entry as an extra changelog entry"),
            ("feat!: x", "Prose.\n\nfeat!: y\n\nUser-visible: {}", "feat! entry as an extra changelog entry"),
            ("fix: x", "Prose.\n\nfeat!:\n\nUser-visible: {}", "feat! entry as an extra changelog entry"),
            ("fix: x", "Prose.\n\nfeature: y\n\nUser-visible: {}", "feature entry as an extra changelog entry"),
            ("fix!: x", "Prose.\n\nchore!: y\n\nUser-visible: {}", "breaking entry as an extra changelog entry"),
            ("perf: x", "Prose.\n\nUser-visible: {}\nfeat: y\nfix(api): z",
             "feat and fix entries as extra changelog entries"),
            ("perf: x", "Prose.\n\nUser-visible: {}\nfeat: y\nfix: z\nrevert: w",
             "feat, fix and revert entries as extra changelog entries"),
        ):
            for answer in ("yes", "no"):
                with self.subTest(title=title, body=body, answer=answer):
                    self.assertFails(title, body.format(answer), f"Release Please reads the body's {kinds} only while")

    def test_the_dropped_entry_message_fits_the_entry(self):
        # A feat's bump is named only when a feat entry drops, and a
        # breaking change lost with its entry is not told to move to the
        # title, where the entry would still drop.
        tail = "Give each entry a paragraph of its own"
        self.assertFails("fix: x", "Prose.\n\nUser-visible: yes\nfeat: y", "and a feat entry's bump out of the version")
        code, out = self._run("perf: x", "Prose.\n\nUser-visible: yes\nfix: y")
        self.assertIn(tail, out)
        self.assertNotIn("bump", out)
        code, out = self._run("fix: x", "Prose.\n\nUser-visible: yes\nfeat!: y")
        self.assertIn("reads this change as breaking only while", out)
        self.assertNotIn("mark the title", out)
        self.assertIn("mark the title with !", self._run("fix: x", "Prose.\n\nBREAKING CHANGE #12\n\nUser-visible: yes")[1])
        # Under a feat title the bump stays; two entries of one type are
        # still plural.
        code, out = self._run("feat: x", "Prose.\n\nUser-visible: yes\nfeat: y")
        self.assertIn("the body's feat entry as an extra changelog entry", out)
        self.assertNotIn("bump", out)
        self.assertFails("fix: x", "Prose.\n\nUser-visible: yes\nfeat: a\nfeat: b",
                         "the body's feat entries as extra changelog entries")

    def test_an_entry_the_rewrap_makes_names_the_rewrap(self):
        # GitHub refills the long line, starting a line with "fix:", which
        # is an entry only while it ends the squash commit (release-please
        # 17.6.0 on the refilled text, checked 2026-11-17).
        line = "The parser change keeps the old behaviour for every caller that passes fix: the docs say so"
        self.assertFails("fix: x", f"Prose.\n\n{line}\n\nUser-visible: yes",
                         "GitHub's 72-column rewrap for the squash commit starts a line of the body with a fix entry")
        # A footer's indented continuation, read again as an entry, is the
        # author's own line, not the rewrap's.
        code, out = self._run("fix: x", "Prose.\n\nExample:\n\n    feat(api): add the endpoint\n\nUser-visible: yes")
        self.assertIn("Release Please reads the body's feat entry as an extra changelog entry", out)
        self.assertNotIn("rewrap", out)
        # With an entry the author wrote, the rewrap is still named.
        self.assertFails("fix: x", f"Prose.\n\n{line}\n\nUser-visible: yes\nfeat: z",
                         "GitHub's 72-column rewrap starts a line with the fix one: break the long line")

    def test_an_entry_the_block_keeps_passes(self):
        # An entry that opens a paragraph with a lowercase type is a commit
        # of its own wherever it stands, and a nested commit block, an
        # override and a footer of another type read the same either way
        # (release-please 17.6.0, checked 2026-11-17).
        for title, body in (
            ("fix: x", "Prose.\n\nfix: also y"),
            ("fix: x", "Prose.\n\nfeat: y\n\nMore prose."),
            ("fix!: x", "Prose.\n\nfeat: y\n\nBREAKING CHANGE: drops z"),
            ("fix!: x", "Prose.\n\nchore: y\n\nBREAKING CHANGE: drops z"),
            ("fix: x", "Prose.\n\nBEGIN_NESTED_COMMIT\nfeat: y\nEND_NESTED_COMMIT"),
            ("fix: x", "Prose.\n\nBEGIN_NESTED_COMMIT\nfeat!: y\nEND_NESTED_COMMIT"),
            ("fix: x", self._override("fix: x", "Prose.\n\nfeat: y")),
            ("fix: x", "Prose.\n\nchore: y"),
            ("fix: x", "Prose.\n\nRefs: #1"),
        ):
            with self.subTest(title=title, body=body):
                self.assertPasses(title, f"{body}\n\nUser-visible: yes")

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
