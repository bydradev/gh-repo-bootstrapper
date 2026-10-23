"""--check and --adopt read releases without fetching from a partial clone's remote."""

import contextlib
import io
import os
import stat
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import bootstrap
import validate_templates
from test_git_show_timeout import PR_TITLE, RUNBOOK, _fork_repository

# What git 2.43.0 and git 2.55.0 print for a release read a partial clone has
# not fetched, with lazy fetch off.
MISS = b"warning: lazy fetching disabled; some objects may not be available\nfatal: could not fetch 0123abcd from promisor remote\n"
BAD_OBJECT = b"fatal: bad object v0.1.0:templates/x.yml\n"


class NoLazyFetchTests(unittest.TestCase):
    def test_git_show_runs_git_with_lazy_fetch_off(self):
        result = bootstrap._git_show(["sh", "-c", 'printf %s "$GIT_NO_LAZY_FETCH"'])
        self.assertEqual(result.stdout, b"1")

    def test_git_show_keeps_git_messages_untranslated(self):
        # A translated "from promisor remote" would not be recognised.
        with unittest.mock.patch.dict(os.environ, {"LANG": "de_DE.UTF-8", "LC_ALL": "de_DE.UTF-8"}):
            result = bootstrap._git_show(["sh", "-c", 'printf %s "$LC_ALL"'])
        self.assertEqual(result.stdout, b"C")


class MissingObjectTests(unittest.TestCase):
    """A read that needs an object the partial clone has not fetched ends the
    run's reads like a timeout: one notice, and no diff built from the
    releases read before it."""

    def setUp(self):
        _fork_repository(self)

    def _compare(self, stop, stderr=MISS):
        """compare_repository where a read fails for a missing object, with
        `stderr`, once stop(the arguments of the reads that answered) is
        true."""
        real, answered, failed = bootstrap._git_show, [], []

        def show(args, *rest, **kwargs):
            if stop(answered):
                failed.append(args[-1])
                return subprocess.CompletedProcess(args, 128, b"", stderr)
            answered.append(args[-1])
            return real(args, *rest, **kwargs)

        errors = io.StringIO()
        with unittest.mock.patch.object(bootstrap, "_git_show", show), contextlib.redirect_stderr(errors):
            report = bootstrap.compare_repository(self.repo, self.files)
        return report, errors.getvalue(), failed

    def test_a_missing_object_skips_both_diffs_with_one_notice(self):
        for stderr in (MISS, BAD_OBJECT):
            with self.subTest(stderr=stderr):
                self._assert_one_notice(stderr)

    def _assert_one_notice(self, stderr):
        report, errors, failed = self._compare(lambda answered: True, stderr)
        self.assertEqual(report[PR_TITLE], ("local-modified", None))
        self.assertEqual(report[RUNBOOK], ("local-modified", None))
        notices = errors.splitlines()
        self.assertEqual(len(notices), 1, errors)
        self.assertRegex(notices[0], r"^notice: git show v\d+\.\d+\.\d+:templates/\S+ needs an object this partial clone ")
        # git show was not started again after the first failure.
        self.assertEqual(len(failed), 1)

    def test_a_missing_object_after_others_answered_skips_the_diff_it_was_building(self):
        for name, stop, diffed in (
            ("workflow reads", lambda answered: len(answered) == 1, None),
            ("legacy reads", lambda answered: any(a.endswith("docs-branch-protection-runbook.md") for a in answered),
             PR_TITLE),
        ):
            with self.subTest(name):
                report, errors, _ = self._compare(stop)
                self.assertEqual(len(errors.splitlines()), 1, errors)
                self.assertIn("needs an object this partial clone", errors)
                self.assertEqual(report[RUNBOOK], ("local-modified", None))
                status, detail = report[PR_TITLE]
                self.assertEqual(status, "local-modified")
                if diffed:
                    self.assertTrue(detail and detail.startswith("--- "), detail)
                else:
                    self.assertIsNone(detail)

    def test_the_validator_does_not_rebuild_the_legacy_table_from_a_partial_clone(self):
        def show(args, *rest, **kwargs):
            return subprocess.CompletedProcess(args, 128, b"", MISS)

        with unittest.mock.patch.object(bootstrap, "_git_show", show), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(OSError):
                bootstrap.compute_legacy_digests()
            errors = validate_templates.check_legacy_digests()
        self.assertEqual(len(errors), 1)
        self.assertIn("could not be checked: ", errors[0])
        self.assertIn("partial clone has not fetched", errors[0])


def _git(*args, cwd=None):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"},
    )


@unittest.skipIf(os.name == "nt", "the logging upload-pack is a POSIX shell script")
class PartialCloneTests(unittest.TestCase):
    """A real partial clone whose remote logs every fetch."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)
        source = tmp / "source"
        (source / "templates").mkdir(parents=True)
        (source / "templates" / "x.yml").write_text("old\n")
        _git("init", "-q", str(source))
        _git("-C", str(source), "config", "uploadpack.allowFilter", "true")
        _git("-C", str(source), "add", "-A")
        _git("-C", str(source), "commit", "-q", "-m", "old")
        _git("-C", str(source), "tag", "v0.1.0")
        (source / "templates" / "x.yml").write_text("new\n")
        _git("-C", str(source), "commit", "-q", "-am", "new")
        self.clone = tmp / "clone"
        _git("clone", "-q", "--no-local", "--filter=blob:none", str(source), str(self.clone))
        # From here on, every fetch from the remote leaves a line in the log.
        self.log = tmp / "fetches.log"
        upload = tmp / "upload-pack"
        upload.write_text(f'#!/bin/sh\necho fetch >> "{self.log}"\nexec git upload-pack "$@"\n')
        upload.chmod(upload.stat().st_mode | stat.S_IXUSR)
        _git("-C", str(self.clone), "config", "remote.origin.uploadpack", str(upload))

    def test_a_release_read_does_not_fetch_and_ends_the_reads(self):
        probe = subprocess.run(
            ["git", "-C", str(self.clone), "show", "v0.1.0:templates/x.yml"], capture_output=True,
            env={**os.environ, "GIT_NO_LAZY_FETCH": "1"},
        )
        if probe.returncode == 0 or self.log.exists():
            self.skipTest("this git predates GIT_NO_LAZY_FETCH and fetched the object")
        reads = bootstrap._ReleaseReads()
        errors = io.StringIO()
        with unittest.mock.patch.object(bootstrap, "TEMPLATES_DIR", self.clone / "templates"), \
                contextlib.redirect_stderr(errors):
            self.assertIsNone(reads.template("v0.1.0", "x.yml"))
        self.assertFalse(self.log.exists(), "git show fetched from the remote")
        self.assertTrue(reads.missing_objects)
        self.assertIn("needs an object this partial clone", errors.getvalue())
        # A tag or path the release lacks is not a missing object.
        absent = bootstrap._ReleaseReads()
        with unittest.mock.patch.object(bootstrap, "TEMPLATES_DIR", self.clone / "templates"):
            self.assertIsNone(absent.template("v0.1.0", "nope.yml"))
            self.assertIsNone(absent.template("v9.9.9", "x.yml"))
        self.assertFalse(absent.incomplete)
        # The blob a checkout fetched is still read: only missing ones stop.
        fresh = bootstrap._ReleaseReads()
        with unittest.mock.patch.object(bootstrap, "TEMPLATES_DIR", self.clone / "templates"):
            self.assertEqual(fresh.template("HEAD", "x.yml"), b"new\n")
        self.assertFalse(fresh.incomplete)


if __name__ == "__main__":
    unittest.main()
