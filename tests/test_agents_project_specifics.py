"""An AGENTS.md whose `## Project specifics` comes before generated sections is refused, not split."""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import bootstrap

EARLY = "## Project specifics\n\nAn early rule, kept as written.\n\n"
LATE = "\n## Project specifics\n\nA second copy at the end.\n"


def _files(repo_type):
    return bootstrap.generate_files(
        {"name": "sample", "repo_type": repo_type, "postgres": False, "scheme": "App", "screenshots": False}
    )


def _git(repo: Path, *args):
    subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"},
    )


class EarlyProjectSpecificsTests(unittest.TestCase):
    repo_type = "python"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name) / "sample"
        self.repo.mkdir()
        self.files = _files(self.repo_type)
        self.expected = self.files["AGENTS.md"]
        self.generated, self.owned = bootstrap._split_project_specifics(self.expected)

    def _headings_from(self, start):
        """The generated headings from `start` to the end of the generated part."""
        _, sections = bootstrap._agents_sections(self.generated)
        headings = [heading for heading, _ in sections]
        return headings[headings.index(start):]

    def _early(self, before="## Branches", late=True):
        """The template with an extra `## Project specifics` before `before`."""
        at = 0 if self.generated.startswith(f"{before}\n") else self.generated.index(f"\n{before}\n") + 1
        agents = self.generated[:at] + EARLY + self.generated[at:] + self.owned
        return agents + LATE if late else agents

    def _commit(self, agents):
        (self.repo / "AGENTS.md").write_text(agents)
        _git(self.repo, "init", "-q")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "init")

    def _rows(self, agents):
        return bootstrap.compare_agents(self.expected, agents)

    def _adopt_agents(self, **kwargs):
        actions = bootstrap.adopt_repository(self.repo, self.files, confirm=lambda _: True, **kwargs)
        return next(a for a in actions if a[1] == "AGENTS.md")

    def _assert_refused(self, agents, after):
        rows = self._rows(agents)
        local = [heading for status, heading in rows if status == "local"]
        self.assertEqual(local, [f"(generated heading after ## Project specifics: {h})" for h in after])
        self.assertFalse([row for row in rows if row[0] == "missing"], rows)
        self._commit(agents)
        for replace_generated in (False, True):
            with self.subTest(replace_generated=replace_generated), \
                    unittest.mock.patch.object(bootstrap, "rebuild_agents", side_effect=AssertionError("rebuilt")):
                actions = bootstrap.adopt_repository(
                    self.repo, self.files, replace_generated=replace_generated, confirm=lambda _: True,
                )
                action, _, detail = next(a for a in actions if a[1] == "AGENTS.md")
                self.assertEqual(action, "refused")
                self.assertTrue(detail.startswith(
                    "keep one ## Project specifics heading, after every generated section, or rename a section"
                    " of the repository's own that shares a generated name, first; "
                ), detail)
                self.assertIn(f"(generated heading after ## Project specifics: {after[0]})", detail)
                self.assertEqual((self.repo / "AGENTS.md").read_text(), agents)

    def test_an_early_duplicate_among_the_generated_sections_is_refused(self):
        self._assert_refused(self._early("## Branches"), self._headings_from("## Branches"))

    def test_an_early_duplicate_before_every_generated_section_is_refused(self):
        _, sections = bootstrap._agents_sections(self.generated)
        first = sections[0][0]
        self._assert_refused(self._early(first), self._headings_from(first))

    def test_a_single_project_specifics_among_the_generated_sections_is_refused(self):
        # The template's own heading moved up: the file has one copy, above
        # ## Skills, and the repository's text after it.
        heading = "## Project specifics\n"
        self.assertTrue(self.owned.startswith(heading))
        early = self._early("## Skills", late=False)
        self.assertTrue(early.endswith(self.owned))
        agents = early[: -len(self.owned)] + self.owned[len(heading):].lstrip("\n")
        self.assertEqual([line for line in agents.splitlines() if line == heading.strip()], [heading.strip()])
        self._assert_refused(agents, self._headings_from("## Skills"))

    def test_rebuild_agents_alone_still_splits_the_file(self):
        # What the refusal guards against: rebuild_agents itself is unchanged,
        # so the sections after the early heading would come back above it and
        # stay below it too.
        rebuilt = bootstrap.rebuild_agents(self.expected, self._early("## Branches"))
        self.assertEqual(rebuilt.count("\n## Branches\n"), 2)

    def test_check_reports_the_rows_with_a_hint_and_writes_nothing(self):
        agents = self._early("## Skills")
        self._commit(agents)
        report = bootstrap.compare_repository(self.repo, self.files)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            aligned = bootstrap.print_repository_report(self.repo, {"repo_type": "python"}, report)
        self.assertFalse(aligned)
        self.assertIn(
            "      local    (generated heading after ## Project specifics: ## Skills)"
            "  → keep one ## Project specifics heading, after every generated section,"
            " or rename the repository's own section\n",
            output.getvalue(),
        )
        self.assertEqual((self.repo / "AGENTS.md").read_text(), agents)

    def test_command_line_adopt_exits_1_and_keeps_the_file_byte_for_byte(self):
        agents = self._early("## Branches")
        self._commit(agents)
        for flags in ((), ("--replace-generated-sections",)):
            with self.subTest(flags=flags):
                result = subprocess.run(
                    [sys.executable, str(Path(bootstrap.__file__)), "--adopt", str(self.repo),
                     "--type", "python", "--non-interactive", *flags],
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("refused  AGENTS.md", result.stdout)
                self.assertNotIn("updated  AGENTS.md", result.stdout)
                self.assertEqual((self.repo / "AGENTS.md").read_bytes(), agents.encode())

    def test_a_late_duplicate_still_rebuilds_and_keeps_both_copies(self):
        # Both copies after every generated section: nothing generated is
        # repository-owned, so the rebuild runs and keeps the text as written.
        start = self.generated.index("## Preservation and destructive operations")
        end = self.generated.index("## Definition of done")
        agents = self.generated[:start] + self.generated[end:] + self.owned + LATE
        self.assertFalse([row for row in self._rows(agents) if row[0] == "local"])
        self._commit(agents)
        actions = bootstrap.adopt_repository(self.repo, self.files)
        self.assertEqual(next(a for a in actions if a[1] == "AGENTS.md")[0], "updated")
        self.assertEqual((self.repo / "AGENTS.md").read_text(), self.expected + LATE)

    def test_a_generated_heading_repeated_under_project_specifics_is_not_flagged(self):
        # The generated part has the section too, so a rebuild adds nothing twice.
        agents = self.expected + "\n## Skills\n\nOur own skills list.\n"
        self.assertEqual({status for status, _ in self._rows(agents)}, {"same"})

    def test_an_early_duplicate_after_a_reordered_section_is_refused(self):
        # The template's last section moved up: the cut-off is the last
        # generated section above the early heading in the file, not the
        # template's last section.
        _, sections = bootstrap._agents_sections(self.generated)
        last = sections[-1][0]
        start = self.generated.index(f"\n{last}\n") + 1
        moved = self.generated[start:]
        rest = self.generated[:start]
        at = rest.index("\n## Development workflow\n") + 1
        rest = rest[:at] + moved + rest[at:]
        branches = rest.index("\n## Branches\n") + 1
        agents = rest[:branches] + EARLY + rest[branches:] + self.owned + LATE
        expected = [h for h in self._headings_from("## Branches") if h != last]
        self._assert_refused(agents, expected)

    def test_a_repository_section_sharing_an_earlier_generated_name_stays_missing(self):
        # The file lacks the generated ## Branches but has its own under its
        # one, late ## Project specifics: --adopt adds the generated section
        # and keeps the repository's, as before.
        start = self.generated.index("## Branches\n")
        end = self.generated.index("## Commits\n")
        own = "\n## Branches\n\nOur own branch rules.\n"
        agents = self.generated[:start] + self.generated[end:] + self.owned + own
        rows = self._rows(agents)
        self.assertIn(("missing", "## Branches"), rows)
        self.assertFalse([row for row in rows if "after ## Project specifics" in row[1]], rows)
        self._commit(agents)
        self.assertEqual(self._adopt_agents()[0], "updated")
        self.assertEqual((self.repo / "AGENTS.md").read_text(), self.expected + own)

    def test_a_section_another_type_lacks_is_missing_not_after_project_specifics(self):
        # A simple repository's AGENTS.md with its own ## Tooling, compared as
        # python, which generates ## Tooling before ## Skills.
        simple = _files("simple")["AGENTS.md"] + "\n## Tooling\n\nOur own commands.\n"
        rows = self._rows(simple)
        self.assertIn(("missing", "## Tooling"), rows)
        self.assertFalse([row for row in rows if "after ## Project specifics" in row[1]], rows)

    def test_other_structure_rows_are_named_in_the_refusal_too(self):
        # An HTML comment hides an early heading from a reader, not from the
        # line scan, which also reports the HTML block.
        at = self.generated.index("\n## Branches\n") + 1
        agents = self.generated[:at] + "<!--\n## Project specifics\n-->\n\n" + self.generated[at:] + self.owned
        local = [heading for status, heading in self._rows(agents) if status == "local"]
        structure = [heading for heading in local if not heading.startswith(bootstrap.AFTER_PROJECT_SPECIFICS)]
        self.assertTrue(structure, local)
        self._commit(agents)
        action, _, detail = self._adopt_agents()
        self.assertEqual(action, "refused")
        self.assertIn("(generated heading after ## Project specifics: ## Branches)", detail)
        self.assertIn(f"; also fix this structure first: {'; '.join(structure)}", detail)
        self.assertEqual((self.repo / "AGENTS.md").read_text(), agents)

    def test_a_heading_inside_a_fence_after_project_specifics_is_not_flagged(self):
        at = self.generated.index("\n## Skills\n") + 1
        agents = (self.generated[:at] + "```md\n## Project specifics\n```\n\n" + self.generated[at:] + self.owned)
        self.assertFalse([row for row in self._rows(agents) if "after ## Project specifics" in row[1]])


class NextjsEarlyProjectSpecificsTests(EarlyProjectSpecificsTests):
    """The same cases with the `next dev` block and the App Router headings."""

    repo_type = "nextjs"

    def test_an_early_duplicate_before_every_generated_section_is_refused(self):
        # The first sections sit in the `next dev` block, which a heading above
        # it would move (refused on its own); the first one after it.
        self._assert_refused(self._early("# This project uses the App Router"),
                             self._headings_from("# This project uses the App Router"))


if __name__ == "__main__":
    unittest.main()
