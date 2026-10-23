"""A bootstrapper copy inside another repository ignores that repository's release tags."""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import bootstrap

PR_TITLE = ".github/workflows/pr-title-check.yml"
RUNBOOK = "docs/branch-protection-runbook.md"
NOTICE = "notice: no usable git release tags in "


def _git(repo: Path, *args):
    subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"},
    )


class ForeignReleaseTagTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)
        # Another project with release tags of its own, through and past the
        # bootstrapper's unstamped releases, and no templates/ folder.
        self.outer = tmp / "outer"
        self.outer.mkdir()
        _git(self.outer, "init", "-q")
        for tag in ("v0.1.0", "v0.5.0", "v0.8.1", "v0.12.0", "v1.0.0"):
            (self.outer / "VERSION").write_text(tag + "\n")
            _git(self.outer, "add", "-A")
            _git(self.outer, "commit", "-q", "-m", tag)
            _git(self.outer, "tag", tag)
        # A copy of the bootstrapper with no .git of its own, inside it.
        self.copy = self.outer / "tools" / "bootstrapper"
        source = Path(bootstrap.__file__).parent
        shutil.copytree(source / "templates", self.copy / "templates")
        shutil.copy2(source / "bootstrap.py", self.copy / "bootstrap.py")
        # A repository with an unstamped, locally edited workflow and doc.
        self.repo = tmp / "sample"
        self.repo.mkdir()
        files = bootstrap.generate_files(
            {"name": "sample", "repo_type": "simple", "postgres": False, "scheme": "", "screenshots": False}
        )
        fork = re.sub(r"(?m)^( +- name: .+)$", r"\1 (ours)", bootstrap.read_stamp(files[PR_TITLE], True)[1], count=1)
        runbook = bootstrap.read_stamp(files[RUNBOOK])[1] + "\nOur own note.\n"
        self.bodies = {PR_TITLE: fork, RUNBOOK: runbook}
        self.current = bootstrap.read_stamp(files[PR_TITLE], True)[1]

    def _check(self, *rels):
        for rel in rels:
            path = self.repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.bodies[rel], encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(self.copy / "bootstrap.py"), "--check", str(self.repo), "--type", "simple"],
            capture_output=True, text=True,
        )

    def test_the_copy_lists_the_other_repositorys_tags(self):
        listed = subprocess.run(
            ["git", "-C", str(self.copy), "tag", "--list", "v*"], capture_output=True, text=True, check=True
        )
        self.assertIn("v0.8.1", listed.stdout.split())

    def test_workflow_diff_takes_the_notice_path(self):
        result = self._check(PR_TITLE)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn(f"local-modified {PR_TITLE}", result.stdout)
        self.assertNotIn("--- current/", result.stdout)
        self.assertNotIn("+++ ", result.stdout)
        self.assertEqual(result.stderr.count(NOTICE), 1, result.stderr)
        self.assertIn("tags that hold no bootstrapper template", result.stderr)

    def test_legacy_doc_diff_takes_the_notice_path(self):
        result = self._check(RUNBOOK)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(f"local-modified {RUNBOOK}", result.stdout)
        self.assertNotIn("--- legacy/", result.stdout)
        self.assertEqual(result.stderr.count(NOTICE), 1, result.stderr)

    def test_both_together_print_one_notice(self):
        result = self._check(PR_TITLE, RUNBOOK)
        self.assertEqual(result.stderr.count(NOTICE), 1, result.stderr)
        self.assertNotIn("+++ ", result.stdout)

    def test_a_real_tag_still_gives_the_diff_its_bases(self):
        reads = bootstrap._ReleaseReads()
        reads.template = lambda tag, name: None  # no tag holds the template
        self.assertEqual(bootstrap._workflow_diff_bases(PR_TITLE, self.current, ["v0.14.0"], reads), [])
        shipped = b"shipped\n"
        reads.template = lambda tag, name: shipped if name == "pr-title-check.yml" else None
        bases = bootstrap._workflow_diff_bases(PR_TITLE, self.current, ["v0.14.0"], reads)
        self.assertEqual([label for label, _, _ in bases], [f"current/{PR_TITLE}", f"legacy/v0.14.0/{PR_TITLE}"])


if __name__ == "__main__":
    unittest.main()
