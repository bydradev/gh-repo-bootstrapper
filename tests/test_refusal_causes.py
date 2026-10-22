"""--adopt and --check name the real cause when git or the file system refuses a read."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import bootstrap

SKILL = ".agents/skills/pull-requests/SKILL.md"
# Git's own test knob (git 2.35.2 and later, t/t0033-safe-directory.sh): git
# treats every repository as owned by another user, as when a checkout is
# shared between accounts, without changing any owner on disk.
DIFFERENT_OWNER = {
    "GIT_TEST_ASSUME_DIFFERENT_OWNER": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


def _git(repo: Path, *args):
    subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"},
    )


class GitRefusalTests(unittest.TestCase):
    """When git cannot read the repository at all, every file looks dirty, so
    the refusal must name git's cause rather than uncommitted changes."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name) / "sample"
        self.repo.mkdir()
        self.files = bootstrap.generate_files(
            {"name": "sample", "repo_type": "python", "postgres": False, "scheme": "App", "screenshots": False}
        )
        _git(self.repo, "init", "-q")
        bootstrap.adopt_repository(self.repo, self.files)
        # A stale copy: an earlier body under a valid stamp of its own.
        path = self.repo / SKILL
        path.write_text(bootstrap.stamp(path.read_text().replace("# Pull requests", "# Pull requests (older)")))
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "init")

    def _adopt(self, env=None):
        return subprocess.run(
            [sys.executable, str(Path(bootstrap.__file__)), "--adopt", str(self.repo), "--type", "python"],
            capture_output=True, text=True, env={**os.environ, **(env or {})},
        )

    def _refusal(self, result):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        rows = [line for line in result.stdout.splitlines() if line.startswith("  refused")]
        self.assertEqual(len(rows), 1, result.stdout)
        self.assertIn(SKILL, rows[0])
        return rows[0]

    def test_a_clean_stale_file_is_still_updated(self):
        result = self._adopt()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"updated  {SKILL}", result.stdout)

    def test_the_ownership_check_is_named_instead_of_uncommitted_changes(self):
        probe = subprocess.run(
            ["git", "-C", str(self.repo), "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, env={**os.environ, **DIFFERENT_OWNER},
        )
        if probe.returncode == 0:
            self.skipTest("this git has no GIT_TEST_ASSUME_DIFFERENT_OWNER")
        row = self._refusal(self._adopt(DIFFERENT_OWNER))
        self.assertIn("git cannot read this repository (detected dubious ownership in repository at", row)
        self.assertIn(str(self.repo), row)
        self.assertIn("fix that, then re-run --adopt", row)
        self.assertNotIn("uncommitted", row)

    def test_a_broken_git_directory_is_named_with_the_repository(self):
        (self.repo / ".git" / "HEAD").write_text("not a ref\n")
        row = self._refusal(self._adopt())
        self.assertIn(f"git cannot read the repository at {self.repo} (not a git repository", row)
        self.assertNotIn("uncommitted", row)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root ignores directory permissions")
    def test_an_unreadable_git_directory_is_named_with_the_repository(self):
        git_dir = self.repo / ".git"
        git_dir.chmod(0o000)
        self.addCleanup(git_dir.chmod, 0o755)
        row = self._refusal(self._adopt())
        self.assertIn(f"git cannot read the repository at {self.repo} (", row)
        self.assertNotIn("uncommitted", row)

    def test_an_uncommitted_change_keeps_its_own_reason(self):
        _git(self.repo, "rm", "-q", "--cached", SKILL)  # a staged deletion; the file stays on disk
        row = self._refusal(self._adopt())
        self.assertIn("needs the file tracked by git with no uncommitted changes", row)
        self.assertNotIn("git cannot read", row)

    def test_git_that_cannot_be_run_is_named(self):
        with unittest.mock.patch.object(bootstrap.subprocess, "run", side_effect=FileNotFoundError(2, "No such file")):
            reason = bootstrap._unclean_reason(self.repo, "fallback")
        self.assertIn("git could not be run (No such file)", reason)
        self.assertIn(str(self.repo), reason)

    def test_no_repository_keeps_the_file_reason(self):
        outside = Path(self._tmp.name) / "plain"
        outside.mkdir()
        if bootstrap._has_git_marker(outside):
            self.skipTest("the temporary directory is inside a git repository")
        self.assertEqual(bootstrap._unclean_reason(outside, "fallback"), "fallback")


class UnlistableDirectoryTests(unittest.TestCase):
    """A folder that cannot be listed is named in the report, with the cause."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name) / "sample"
        (self.repo / ".github").mkdir(parents=True)
        (self.repo / ".github" / "pull_request_template.md").write_text("x\n")

    def test_the_folder_and_the_cause_are_named(self):
        real = os.listdir

        def listdir(path):
            if Path(path) == self.repo / ".github":
                raise PermissionError(13, "Permission denied", str(path))
            return real(path)

        with unittest.mock.patch.object(bootstrap.os, "listdir", side_effect=listdir):
            with self.assertRaises(PermissionError) as raised:
                bootstrap._exact_path_exists(self.repo, ".github/pull_request_template.md")
        self.assertEqual(str(raised.exception), "[Errno 13] Permission denied: .github")
        self.assertEqual(raised.exception.strerror, "Permission denied: .github")

    def test_the_repository_itself_is_named_as_dot(self):
        with unittest.mock.patch.object(bootstrap.os, "listdir", side_effect=PermissionError(13, "Permission denied")):
            with self.assertRaises(PermissionError) as raised:
                bootstrap._exact_path_exists(self.repo, ".github")
        self.assertEqual(raised.exception.strerror, "Permission denied: .")

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root ignores directory permissions")
    def test_check_names_a_github_folder_it_can_search_but_not_list(self):
        files = bootstrap.generate_files(
            {"name": "sample", "repo_type": "python", "postgres": False, "scheme": "App", "screenshots": False}
        )
        shutil.rmtree(self.repo)
        self.repo.mkdir()
        _git(self.repo, "init", "-q")
        bootstrap.adopt_repository(self.repo, files)
        folder = self.repo / ".github"
        folder.chmod(0o311)  # search, no read
        self.addCleanup(folder.chmod, 0o755)
        state = bootstrap.compare_repository(self.repo, files)[bootstrap.PR_TEMPLATE]
        self.assertEqual(state, ("unreadable", "PermissionError: Permission denied: .github"))


if __name__ == "__main__":
    unittest.main()
