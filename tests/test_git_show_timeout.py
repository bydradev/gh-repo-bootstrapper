"""--check and --adopt stop waiting on a `git show` that does not answer."""

import contextlib
import io
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path

import bootstrap

PR_TITLE = ".github/workflows/pr-title-check.yml"
RUNBOOK = "docs/branch-protection-runbook.md"


def _git(repo: Path, *args):
    subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"},
    )


@unittest.skipIf(os.name == "nt", "the fake git is a POSIX shell script")
class GitShowTimeoutTests(unittest.TestCase):
    def setUp(self):
        if not bootstrap._workflow_diff_tags() or not bootstrap._legacy_tags():
            self.skipTest("release tags unavailable")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)
        self.repo = tmp / "sample"
        self.repo.mkdir()
        self.files = bootstrap.generate_files(
            {"name": "sample", "repo_type": "simple", "postgres": False, "scheme": "", "screenshots": False}
        )
        # Unstamped, locally edited copies: the workflow diff and the legacy
        # docs diff each read release tags with git show.
        fork = re.sub(r"(?m)^( +- name: .+)$", r"\1 (ours)", bootstrap.read_stamp(self.files[PR_TITLE], True)[1], count=1)
        runbook = bootstrap.read_stamp(self.files[RUNBOOK])[1] + "\nOur own note.\n"
        for rel, body in ((PR_TITLE, fork), (RUNBOOK, runbook)):
            path = self.repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        _git(self.repo, "init", "-q")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "fork")
        # A git whose `show` hangs, as one waiting on a credential prompt, a
        # filter or fsmonitor would. The sleep is a child that keeps the
        # pipes open after the shell is killed, as a hung helper would.
        fake = tmp / "bin"
        fake.mkdir()
        script = fake / "git"
        script.write_text(
            "#!/bin/sh\n"
            'case " $* " in *" show "*) echo "$*" >> "$0.log"; sleep 30 ;; esac\n'
            f'exec "{shutil.which("git")}" "$@"\n'
        )
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        self.log = fake / "git.log"
        self.path = f"{fake}{os.pathsep}{os.environ['PATH']}"

    def _compare(self):
        errors = io.StringIO()
        with unittest.mock.patch.dict(os.environ, {"PATH": self.path}), \
                unittest.mock.patch.object(bootstrap, "GIT_SHOW_TIMEOUT", 0.5), \
                contextlib.redirect_stderr(errors):
            start = time.monotonic()
            report = bootstrap.compare_repository(self.repo, self.files)
            elapsed = time.monotonic() - start
        return report, errors.getvalue(), elapsed

    def test_one_hung_read_skips_both_diffs_with_one_notice(self):
        report, errors, elapsed = self._compare()
        self.assertEqual(report[PR_TITLE], ("local-modified", None))
        self.assertEqual(report[RUNBOOK], ("local-modified", None))
        notices = errors.splitlines()
        self.assertEqual(len(notices), 1, errors)
        self.assertRegex(notices[0], r"^notice: git show v\d+\.\d+\.\d+:templates/\S+ did not answer within 0\.5 s in ")
        self.assertIn("skipped the diff against legacy template docs or workflows", notices[0])
        # Only the first read waited: git show was not started again.
        self.assertEqual(len(self.log.read_text().splitlines()), 1)
        self.assertLess(elapsed, 10)

    def test_the_same_repository_diffs_when_git_answers(self):
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            report = bootstrap.compare_repository(self.repo, self.files)
        self.assertEqual(errors.getvalue(), "")
        for rel in (PR_TITLE, RUNBOOK):
            status, detail = report[rel]
            self.assertEqual(status, "local-modified")
            self.assertTrue(detail and detail.startswith("--- "), detail)

    def test_check_and_adopt_end_with_the_notice_and_no_traceback(self):
        env = {**os.environ, "PATH": self.path}
        # GIT_SHOW_TIMEOUT is a module constant; shorten it in the child run.
        prelude = (
            "import sys; import bootstrap; bootstrap.GIT_SHOW_TIMEOUT = 0.5; "
            "sys.argv = ['bootstrap.py', *sys.argv[1:]]; bootstrap.main()"
        )
        for flag in ("--check", "--adopt"):
            with self.subTest(flag=flag):
                result = subprocess.run(
                    [sys.executable, "-c", prelude, flag, str(self.repo), "--type", "simple"],
                    capture_output=True, text=True, env=env, cwd=Path(bootstrap.__file__).parent, timeout=60,
                )
                self.assertNotIn("Traceback", result.stderr)
                self.assertIn("did not answer within 0.5 s", result.stderr)
                self.assertEqual(result.stderr.count("notice:"), 1, result.stderr)
                self.assertIn(PR_TITLE, result.stdout)


if __name__ == "__main__":
    unittest.main()
