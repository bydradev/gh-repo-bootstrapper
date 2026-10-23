"""Layout of the --check report."""

import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import bootstrap


def _render(repo_type):
    return bootstrap.generate_files(
        {"name": "sample", "repo_type": repo_type, "postgres": False, "scheme": "App",
         "screenshots": False}
    )


def _git(repo: Path, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


class CheckReportColumnTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name) / "sample"
        self.repo.mkdir()
        _git(self.repo, "init", "-q")

    def _report_rows(self, report):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            bootstrap.print_repository_report(self.repo, {"repo_type": "simple"}, report)
        # File rows are indented two spaces; detail lines six or more.
        return [line for line in output.getvalue().splitlines()
                if line.startswith("  ") and not line.startswith("   ")]

    def test_every_path_starts_in_the_same_column(self):
        # A nextjs repository checked as simple prints other-type rows, and an
        # edited template skill prints local-modified: the two longest states.
        bootstrap.adopt_repository(self.repo, _render("nextjs"))
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "adopt")
        with (self.repo / ".agents/skills/pull-requests/SKILL.md").open("a") as skill:
            skill.write("Edited.\n")
        report = bootstrap.compare_repository(self.repo, _render("simple"))
        rows = self._report_rows(report)
        statuses = {line.split()[0] for line in rows}
        self.assertLessEqual({"other-type", "local-modified", "same", "differs"}, statuses)
        column = 2 + bootstrap.REPORT_STATUS_WIDTH + 1
        for line in rows:
            with self.subTest(line):
                status, rel = line.split()[:2]
                self.assertEqual(line.index(rel, len(status) + 2), column)
                self.assertEqual(line[2:column].rstrip(), status)

    def test_width_fits_every_file_state(self):
        # Every state the report prints for a file, as the README lists them.
        states = ("same", "stale", "local-modified", "missing", "shadowed", "ignored",
                  "dangling", "orphaned", "other-type", "differs", "symlink",
                  "unreadable", "own")
        self.assertEqual(bootstrap.REPORT_STATUS_WIDTH, max(map(len, states)))
        rows = self._report_rows({f"path/{state}": (state, None) for state in states})
        self.assertEqual({line.index("path/") for line in rows}, {2 + bootstrap.REPORT_STATUS_WIDTH + 1})


if __name__ == "__main__":
    unittest.main()
