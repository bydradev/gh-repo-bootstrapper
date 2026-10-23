"""The target folder is checked before the other questions, and the
interactive destination question has the default --help names."""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bootstrap


class TargetAndDestinationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        cwd = os.getcwd()
        os.chdir(self.dir)
        self.addCleanup(os.chdir, cwd)
        (self.dir / "taken").mkdir()
        (self.dir / "taken" / "notes.txt").write_text("keep me\n")

    def gather(self, argv, replies=()):
        """Run gather_config with argv and scripted answers; gh and git only record.

        Returns (exit code, config, stdout, stderr, questions asked, commands run).
        """
        replies, questions, commands = list(replies), [], []

        def answer(question=""):
            questions.append(question)
            if not replies:
                raise EOFError
            return replies.pop(0)

        def run(command, **kwargs):
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, "true\n" if kwargs.get("text") else b"", "")

        out, err = io.StringIO(), io.StringIO()
        env = {"RELEASE_PLEASE_CLIENT_ID": "", "RELEASE_PLEASE_APP_KEY": ""}
        code = cfg = None
        with patch.object(sys, "argv", ["bootstrap.py", *argv]), patch.dict(os.environ, env), \
                patch("builtins.input", answer), patch.object(sys, "stdin", io.StringIO()), \
                patch.object(bootstrap.subprocess, "run", run), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                cfg = bootstrap.gather_config(bootstrap.parse_args())
            except SystemExit as exc:
                code = exc.code
        return code, cfg, out.getvalue(), err.getvalue(), questions, commands

    def test_a_typed_name_for_a_folder_in_use_is_asked_again(self):
        code, cfg, out, _, questions, _ = self.gather(
            ["--type", "simple", "--org", "octocat", "--private"], ["taken", "fresh", "", ""])
        self.assertIsNone(code)
        self.assertEqual(cfg["name"], "fresh")
        self.assertIn("  target directory 'taken' already exists and is not empty\n", out)
        self.assertEqual(questions[:2], ["Repository name: ", "Repository name: "])

    def test_a_name_flag_for_a_folder_in_use_stops_before_any_question(self):
        for extra in ([], ["--non-interactive"]):
            with self.subTest(extra=extra):
                code, _, _, err, questions, commands = self.gather(
                    ["--name", "taken", "--type", "simple", "--org", "octocat", "--private", *extra])
                self.assertEqual(code, 1)
                self.assertIn("error: target directory 'taken' already exists and is not empty", err)
                self.assertEqual((questions, commands), ([], []))

    def test_a_file_at_the_target_is_refused(self):
        (self.dir / "file").write_text("x\n")
        code, _, _, err, _, _ = self.gather(
            ["--name", "file", "--type", "simple", "--org", "octocat", "--non-interactive"])
        self.assertEqual(code, 1)
        self.assertIn("error: target directory 'file' cannot be used: Not a directory", err)

    def test_paths_git_clone_cannot_create_are_refused(self):
        (self.dir / "file").write_text("x\n")
        (self.dir / "dangling").symlink_to("nowhere")
        (self.dir / "loop").symlink_to("loop")
        (self.dir / "to-file").symlink_to("file")
        for name, reason in (
            ("dangling", "'dangling' is a link that leads nowhere"),
            ("loop/repo", "'loop' is a link that leads nowhere"),
            ("to-file/repo", "'to-file' is not a directory"),
            ("dangling/repo", "'dangling' is a link that leads nowhere"),
            ("file/repo", "'file' is not a directory"),
            ("file/deeper/repo", "'file' is not a directory"),
        ):
            with self.subTest(name=name):
                code, _, _, err, _, commands = self.gather(
                    ["--name", name, "--type", "simple", "--org", "octocat", "--non-interactive"])
                self.assertEqual(code, 1)
                self.assertIn(f"error: target directory '{name}' cannot be used: {reason}", err)
                self.assertEqual(commands, [])

    def test_paths_git_clone_can_create_are_accepted(self):
        (self.dir / "empty").mkdir()
        (self.dir / "link").symlink_to("empty")
        for name in ("link", "missing/deeper/repo", str(self.dir.resolve() / "absolute")):
            with self.subTest(name=name):
                code, cfg, _, err, _, _ = self.gather(
                    ["--name", name, "--type", "simple", "--org", "octocat", "--non-interactive"])
                self.assertIsNone(code, err)
                self.assertEqual(cfg["repo_dir"], Path(name))

    def test_runs_that_create_nothing_locally_do_not_check_the_folder(self):
        for extra in (["--dry-run"], ["--configure-only"]):
            with self.subTest(extra=extra):
                code, cfg, _, err, _, _ = self.gather(
                    ["--name", "taken", "--type", "simple", "--org", "octocat", "--non-interactive", *extra])
                self.assertIsNone(code, err)
                self.assertEqual(cfg["name"], "taken")

    def test_an_empty_folder_is_accepted(self):
        (self.dir / "empty").mkdir()
        code, cfg, _, err, _, _ = self.gather(
            ["--name", "empty", "--type", "simple", "--org", "octocat", "--non-interactive"])
        self.assertIsNone(code, err)
        self.assertEqual(cfg["repo_dir"], Path("empty"))

    def test_create_and_push_still_refuses_a_folder_filled_after_the_questions(self):
        cfg = {"name": "taken", "owner": "octocat", "repo_type": "simple", "private": True,
               "repo_dir": Path("taken"), "postgres": False}
        calls, err = [], io.StringIO()
        with patch.object(bootstrap, "_run", lambda command, **kwargs: calls.append(command)), \
                contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
            bootstrap.create_and_push(cfg, bootstrap.generate_files(cfg))
        self.assertIn("target directory 'taken' already exists and is not empty", err.getvalue())
        self.assertEqual(calls, [])

    def test_an_empty_destination_answer_takes_iphone(self):
        code, cfg, _, _, questions, _ = self.gather(
            ["--name", "ios-app", "--type", "swift", "--scheme", "App", "--org", "octocat", "--private"],
            ["", "", "", "", ""])
        self.assertIsNone(code)
        self.assertEqual(cfg["destination"], "iphone")
        self.assertIn("Select destination (1-3) [1]: ", questions)

    def test_a_choice_without_a_default_still_needs_a_number(self):
        code, cfg, out, _, questions, _ = self.gather(
            ["--name", "app", "--org", "octocat", "--private"], ["", "5", "", ""])
        self.assertIsNone(code)
        self.assertEqual(cfg["repo_type"], "simple")
        self.assertIn("Enter a number from 1 to 5.", out)
        self.assertEqual(questions[:2], ["Select type (1-5): ", "Select type (1-5): "])


if __name__ == "__main__":
    unittest.main()
