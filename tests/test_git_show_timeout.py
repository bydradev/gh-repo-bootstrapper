"""--check and --adopt stop waiting on a `git show` that does not answer."""

import contextlib
import io
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path

import bootstrap
import validate_templates
from test_existing_repository import _skip_without_tags

PR_TITLE = ".github/workflows/pr-title-check.yml"
RUNBOOK = "docs/branch-protection-runbook.md"


def _git(repo: Path, *args):
    subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"},
    )


def _fork_repository(test):
    """Give `test` a committed repository at test.repo whose pr-title-check.yml
    and branch-protection runbook are unstamped, locally edited copies, so the
    workflow diff and the legacy docs diff each read release tags with git
    show; test.files is its render. Skips, or fails in GitHub Actions, without
    the release tags."""
    if not bootstrap._workflow_diff_tags() or not bootstrap._legacy_tags():
        _skip_without_tags(test)
    test._tmp = tempfile.TemporaryDirectory()
    test.addCleanup(test._tmp.cleanup)
    test.repo = Path(test._tmp.name) / "sample"
    test.repo.mkdir()
    test.files = bootstrap.generate_files(
        {"name": "sample", "repo_type": "simple", "postgres": False, "scheme": "", "screenshots": False}
    )
    fork = re.sub(r"(?m)^( +- name: .+)$", r"\1 (ours)", bootstrap.read_stamp(test.files[PR_TITLE], True)[1], count=1)
    runbook = bootstrap.read_stamp(test.files[RUNBOOK])[1] + "\nOur own note.\n"
    for rel, body in ((PR_TITLE, fork), (RUNBOOK, runbook)):
        path = test.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    _git(test.repo, "init", "-q")
    _git(test.repo, "add", "-A")
    _git(test.repo, "commit", "-q", "-m", "fork")


def _gone(pid: int) -> bool:
    """Whether `pid` has exited (a zombie no one has reaped yet counts)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] == "Z"
    except OSError:
        return False


@unittest.skipIf(os.name == "nt", "the fake git is a POSIX shell script")
class GitShowTimeoutTests(unittest.TestCase):
    def setUp(self):
        _fork_repository(self)
        tmp = Path(self._tmp.name)
        # A git whose `show` hangs, as one fetching a missing object in a
        # partial clone from a remote that does not answer would. The sleep
        # stands for the `git fetch` that git starts: a child that keeps the
        # pipes open, and would outlive the shell if only the shell were killed.
        fake = tmp / "bin"
        fake.mkdir()
        script = fake / "git"
        script.write_text(
            "#!/bin/sh\n"
            'case " $* " in *" show "*) echo "$*" >> "$0.log"; sleep 30 & echo $! >> "$0.pids"; wait; exit 1 ;; esac\n'
            f'exec "{shutil.which("git")}" "$@"\n'
        )
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        self.log = fake / "git.log"
        self.pids = fake / "git.pids"
        self.path = f"{fake}{os.pathsep}{os.environ['PATH']}"

    def _hung(self):
        """The fake git on PATH, and reads that give up after half a second."""
        stack = contextlib.ExitStack()
        stack.enter_context(unittest.mock.patch.dict(os.environ, {"PATH": self.path}))
        stack.enter_context(unittest.mock.patch.object(bootstrap, "GIT_SHOW_TIMEOUT", 0.5))
        return stack

    def _compare(self):
        errors = io.StringIO()
        with self._hung(), contextlib.redirect_stderr(errors):
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

    def test_a_timeout_stops_the_fetch_git_started(self):
        self._compare()
        pids = [int(line) for line in self.pids.read_text().split()]
        self.assertEqual(len(pids), 1)
        deadline = time.monotonic() + 5
        while not _gone(pids[0]) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(_gone(pids[0]), f"the hung git's child {pids[0]} is still running")

    def test_ctrl_c_during_a_hung_read_stops_the_fetch_too(self):
        # A terminal's Ctrl-C signals its foreground process group: here the
        # harness's own, which git's process group is not part of.
        prelude = (
            "import sys; import bootstrap; from pathlib import Path; "
            "bootstrap.GIT_SHOW_TIMEOUT = 60; "
            "bootstrap.compare_repository(Path(sys.argv[1]), bootstrap.generate_files({'name': 'sample', "
            "'repo_type': 'simple', 'postgres': False, 'scheme': '', 'screenshots': False}))"
        )
        harness = subprocess.Popen(
            [sys.executable, "-c", prelude, str(self.repo)], cwd=Path(bootstrap.__file__).parent,
            env={**os.environ, "PATH": self.path}, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            start_new_session=True,
        )
        self.addCleanup(lambda: harness.poll() is None and harness.kill())
        deadline = time.monotonic() + 20
        while not (self.pids.exists() and self.pids.read_text().strip()) and time.monotonic() < deadline:
            time.sleep(0.05)
        pids = [int(line) for line in self.pids.read_text().split()]
        os.killpg(harness.pid, signal.SIGINT)
        _, errors = harness.communicate(timeout=20)
        self.assertNotEqual(harness.returncode, 0)
        self.assertIn("KeyboardInterrupt", errors.decode())
        deadline = time.monotonic() + 5
        while not _gone(pids[0]) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(_gone(pids[0]), f"the hung git's child {pids[0]} is still running")

    def test_a_timeout_after_the_missing_tags_notice_still_names_the_read(self):
        # The workflow diff finds no usable tags and says so; the legacy docs
        # then read a release, which hangs: the second notice names that.
        with unittest.mock.patch.object(bootstrap, "_workflow_diff_tags", return_value=[]):
            report, errors, _ = self._compare()
        notices = errors.splitlines()
        self.assertEqual(len(notices), 2, errors)
        self.assertTrue(notices[0].startswith("notice: no usable git release tags"), errors)
        self.assertIn("did not answer within 0.5 s", notices[1])
        self.assertEqual(report[RUNBOOK], ("local-modified", None))

    def test_the_validator_does_not_rebuild_the_legacy_table_from_a_partial_read(self):
        with self._hung(), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(TimeoutError):
                bootstrap.compute_legacy_digests()
            errors = validate_templates.check_legacy_digests()
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("bootstrap.LEGACY_TEMPLATE_DIGESTS could not be checked: "), errors)
        self.assertIn("did not answer within 0.5 s", errors[0])
        prelude = (
            "import sys; import bootstrap; bootstrap.GIT_SHOW_TIMEOUT = 0.5; "
            "sys.argv = ['validate_templates.py', '--regenerate-legacy-digests']; "
            "import runpy; runpy.run_path('validate_templates.py', run_name='__main__')"
        )
        result = subprocess.run(
            [sys.executable, "-c", prelude], capture_output=True, text=True,
            env={**os.environ, "PATH": self.path}, cwd=Path(bootstrap.__file__).parent, timeout=60,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("error: LEGACY_TEMPLATE_DIGESTS not regenerated: ", result.stderr)

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


class PartialReadTests(unittest.TestCase):
    """A read that times out after others answered: the diff it was building
    is skipped rather than built from the releases read so far, which would
    name the wrong nearest release."""

    def setUp(self):
        _fork_repository(self)

    def _compare(self, stop):
        """compare_repository where a git show read times out once
        stop(the arguments of the reads that answered) is true."""
        real, answered = bootstrap._git_show, []

        def show(args, *rest, **kwargs):
            if stop(answered):
                raise subprocess.TimeoutExpired(args, bootstrap.GIT_SHOW_TIMEOUT)
            answered.append(args[-1])
            return real(args, *rest, **kwargs)

        errors = io.StringIO()
        with unittest.mock.patch.object(bootstrap, "_git_show", show), contextlib.redirect_stderr(errors):
            report = bootstrap.compare_repository(self.repo, self.files)
        return report, errors.getvalue()

    def test_a_timeout_inside_the_workflow_reads_skips_the_workflow_diff(self):
        # The first release answers, the second does not.
        report, errors = self._compare(lambda answered: len(answered) == 1)
        self.assertEqual(report[PR_TITLE], ("local-modified", None))
        self.assertEqual(report[RUNBOOK], ("local-modified", None))
        self.assertEqual(len(errors.splitlines()), 1, errors)
        self.assertIn("did not answer within", errors)

    def test_a_timeout_inside_the_legacy_reads_skips_the_docs_diff(self):
        # The workflow diff reads first and gets every release; the legacy
        # docs read one release's runbook and then time out.
        runbook = "templates/docs-branch-protection-runbook.md"
        report, errors = self._compare(lambda answered: any(arg.endswith(runbook) for arg in answered))
        status, detail = report[PR_TITLE]
        self.assertEqual(status, "local-modified")
        self.assertTrue(detail and detail.startswith("--- "), detail)
        self.assertEqual(report[RUNBOOK], ("local-modified", None))
        self.assertEqual(len(errors.splitlines()), 1, errors)
        self.assertIn("did not answer within", errors)


if __name__ == "__main__":
    unittest.main()
