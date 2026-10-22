"""The interactive prompts, --configure-only and the create flow.

Each test drives gather_config() or main() with scripted answers and a
recording stand-in for gh and git, so nothing reaches GitHub or the network.
The recovery text matters most: it decides whether a user deletes a
half-created repository.
"""

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


class Answers:
    """Stands in for input(): returns each reply in turn, then reports end of input."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.questions = []

    def __call__(self, question=""):
        self.questions.append(question)
        if not self.replies:
            raise EOFError
        return self.replies.pop(0)


class Commands:
    """Stands in for subprocess.run: records every gh and git command and
    answers it as they would. A command for which fail() is true exits 1,
    with `stderr` as its error output."""

    def __init__(self, fail=None, stderr=b"", user="octocat", orgs=("acme",)):
        self.calls = []
        self.fail = fail or (lambda command: False)
        self.stderr = stderr
        self.user = user
        self.orgs = orgs

    def __call__(self, command, **kwargs):
        command = list(command)
        self.calls.append(command)
        failed = self.fail(command)
        if failed and kwargs.get("check"):
            raise subprocess.CalledProcessError(1, command, stderr=self.stderr)
        out = "" if failed else self._output(command)
        if kwargs.get("text"):
            return subprocess.CompletedProcess(command, int(failed), out, "")
        return subprocess.CompletedProcess(command, int(failed), out.encode(), self.stderr if failed else b"")

    def _output(self, command):
        if command[:3] == ["gh", "api", "user"]:
            return self.user + "\n"
        if command[:3] == ["gh", "org", "list"]:
            return "".join(org + "\n" for org in self.orgs)
        if command[:2] == ["gh", "api"] and command[-2:] == ["--jq", ".private"]:
            return "true\n"
        if command[:2] == ["gh", "api"] and len(command) == 3:
            return "{}"  # a read of the current settings
        return ""

    def ran(self, *prefix):
        return [command for command in self.calls if command[:len(prefix)] == list(prefix)]


class Session(unittest.TestCase):
    """Runs bootstrap in a scratch working directory with no credentials in the environment."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        cwd = os.getcwd()
        os.chdir(self.dir)
        self.addCleanup(os.chdir, cwd)

    def run_bootstrap(self, argv, answers=(), commands=None, call=None):
        """Run main() (or `call`) with argv; return (exit code, stdout, stderr, answers, commands)."""
        answers = Answers(*answers)
        commands = commands or Commands()
        out, err = io.StringIO(), io.StringIO()
        env = {"RELEASE_PLEASE_CLIENT_ID": "", "RELEASE_PLEASE_APP_KEY": ""}
        code = None
        with patch.object(sys, "argv", ["bootstrap.py", *argv]), patch.dict(os.environ, env), \
                patch("builtins.input", answers), patch.object(sys, "stdin", io.StringIO()), \
                patch.object(bootstrap.subprocess, "run", commands), \
                patch.object(bootstrap, "check_dependencies"), \
                patch.object(bootstrap.time, "sleep"), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                self.result = (call or bootstrap.main)()
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue(), answers, commands

    def gather(self, argv, answers=(), commands=None):
        return self.run_bootstrap(argv, answers, commands, call=lambda: bootstrap.gather_config(bootstrap.parse_args()))


class GatherConfigTests(Session):
    def test_a_nextjs_session_asks_every_question_and_repeats_a_bad_answer(self):
        code, out, _, answers, _ = self.gather([], [
            "Bad Name", "apps/my-app",   # name: refused, then a path
            "6", "one", "1",             # type: out of range, not a number, nextjs
            "2",                         # owner: the organization
            "maybe", "y",                # public: not y or n, then yes
            "y", "",                     # Postgres yes, screenshots by default no
            "client-id", "",             # client ID, key file skipped
        ])
        self.assertIsNone(code)
        cfg = self.result
        self.assertEqual((cfg["name"], cfg["repo_dir"], cfg["repo_type"]), ("my-app", Path("apps/my-app"), "nextjs"))
        self.assertEqual((cfg["owner"], cfg["private"], cfg["postgres"], cfg["screenshots"]),
                         ("acme", False, True, False))
        self.assertEqual((cfg["release_please_client_id"], cfg["release_please_app_key"]), ("client-id", ""))
        self.assertIn("Must be lowercase letters, digits, and hyphens only", out)
        self.assertEqual(out.count("Enter a number from 1 to 5."), 2)
        self.assertIn("  1. octocat\n  2. acme\n", out)
        self.assertIn("Please enter y or n.", out)
        self.assertIn("(skipped)", out)
        self.assertEqual(answers.replies, [])
        self.assertIn("\nMake repository public? [y/N]: ", answers.questions)

    def test_a_swift_session_asks_for_the_scheme_destination_and_xcodegen(self):
        code, _, _, _, commands = self.gather(
            ["--name", "ios-app", "--type", "swift", "--org", "octocat", "--private"],
            ["App", "3", "y", "n", "", ""],
        )
        self.assertIsNone(code)
        cfg = self.result
        self.assertEqual((cfg["scheme"], cfg["destination"], cfg["xcodegen"], cfg["screenshots"], cfg["private"]),
                         ("App", "macos", True, False, True))
        self.assertEqual(commands.calls, [], "an owner given with --org needs no lookup")

    def test_a_swift_session_without_a_scheme_stops(self):
        code, _, err, _, _ = self.gather(["--name", "ios-app", "--type", "swift", "--org", "octocat", "--private"], [""])
        self.assertEqual(code, 1)
        self.assertIn("Xcode scheme name is required for --type swift", err)

    def test_the_only_owner_is_taken_without_asking(self):
        code, out, _, answers, _ = self.gather(
            ["--name", "app", "--type", "simple", "--private"], ["", ""], Commands(orgs=()),
        )
        self.assertIsNone(code)
        self.assertEqual(self.result["owner"], "octocat")
        self.assertIn("GitHub owner: octocat", out)
        self.assertFalse(any("Select owner" in question for question in answers.questions))

    def test_with_no_owner_found_the_owner_is_typed_and_checked(self):
        nobody = dict(fail=lambda command: command[:3] == ["gh", "api", "user"], orgs=())
        argv = ["--name", "app", "--type", "simple", "--private"]
        code, _, _, _, _ = self.gather(argv, ["my-org", "", ""], Commands(**nobody))
        self.assertIsNone(code)
        self.assertEqual(self.result["owner"], "my-org")
        for typed, message in (("", "GitHub owner is required"), ("-flag", "GitHub owner: Must be letters")):
            with self.subTest(typed=typed):
                code, _, err, _, _ = self.gather(argv, [typed], Commands(**nobody))
                self.assertEqual(code, 1)
                self.assertIn(message, err)

    def test_a_dry_run_looks_nothing_up_and_asks_for_no_credentials(self):
        code, _, _, answers, commands = self.gather(["--dry-run", "--name", "app", "--type", "simple"], ["octocat", ""])
        self.assertIsNone(code)
        self.assertEqual(commands.calls, [])
        self.assertEqual(self.result["owner"], "octocat")
        self.assertTrue(self.result["private"])
        self.assertFalse(any("RELEASE_PLEASE" in question for question in answers.questions))

    def test_non_interactive_runs_name_what_is_missing(self):
        for argv, message in (
            (["--type", "simple"], "--name is required in --non-interactive mode"),
            (["--name", "app"], "--type is required in --non-interactive mode"),
            (["--name", "app", "--type", "swift", "--org", "o"], "--scheme is required for --type swift"),
        ):
            with self.subTest(message=message):
                code, _, err, _, _ = self.gather(["--non-interactive", *argv])
                self.assertEqual(code, 1)
                self.assertIn(message, err)
        code, _, err, _, _ = self.gather(["--non-interactive", "--name", "app", "--type", "simple"],
                                         commands=Commands(fail=lambda command: command[:3] == ["gh", "api", "user"]))
        self.assertEqual(code, 1)
        self.assertIn("could not determine GitHub user; pass --org", err)
        code, _, err, _, _ = self.gather(["--non-interactive", "--name", "Bad_Name", "--type", "simple"])
        self.assertEqual(code, 1)
        self.assertIn("error: Must be lowercase letters", err)

    def test_non_interactive_runs_take_the_signed_in_user_or_a_placeholder(self):
        self.gather(["--non-interactive", "--name", "app", "--type", "simple"])
        self.assertEqual(self.result["owner"], "octocat")
        _, _, _, _, commands = self.gather(["--non-interactive", "--dry-run", "--name", "app", "--type", "simple"])
        self.assertEqual(self.result["owner"], "example-org")
        self.assertEqual(commands.calls, [])

    def test_options_for_another_type_are_ignored_with_a_warning(self):
        for repo_type, flags, ignored in (
            ("python", ["--postgres", "--scheme", "S", "--destination", "ipad", "--xcodegen", "--screenshots"],
             ["--postgres", "--scheme", "--destination", "--xcodegen", "--screenshots"]),
            ("nextjs", ["--postgres", "--scheme", "S", "--destination", "ipad", "--xcodegen"],
             ["--scheme", "--destination", "--xcodegen"]),
            ("swift", ["--postgres", "--scheme", "S", "--destination", "ipad", "--xcodegen"], ["--postgres"]),
        ):
            with self.subTest(repo_type=repo_type):
                code, out, _, _, _ = self.gather(
                    ["--non-interactive", "--dry-run", "--name", "app", "--type", repo_type, "--org", "o", *flags])
                self.assertIsNone(code)
                warned = sorted(line.split()[1] for line in out.splitlines() if line.startswith("warning: "))
                self.assertEqual(warned, sorted(ignored))

    def test_configure_only_reads_the_visibility_from_github(self):
        code, out, _, _, commands = self.gather(
            ["--configure-only", "--non-interactive", "--name", "app", "--type", "simple", "--org", "octocat",
             "--public"])
        self.assertIsNone(code)
        self.assertIn("warning: --public/--private are ignored with --configure-only", out)
        self.assertEqual(commands.ran("gh", "api", "repos/octocat/app"), [["gh", "api", "repos/octocat/app", "--jq",
                                                                           ".private"]])
        self.assertTrue(self.result["private"])
        # A lookup that fails keeps the repository private rather than guessing public.
        self.gather(["--configure-only", "--non-interactive", "--name", "app", "--type", "simple", "--org", "octocat"],
                    commands=Commands(fail=lambda command: command[-1:] == [".private"]))
        self.assertTrue(self.result["private"])


class PromptHelperTests(Session):
    def test_every_prompt_stops_at_the_end_of_input(self):
        for name, ask in (
            ("prompt", lambda: bootstrap.prompt("Name")),
            ("prompt_validated", lambda: bootstrap.prompt_validated("Name", bootstrap.validate_name)),
            ("prompt_yn", lambda: bootstrap.prompt_yn("Proceed?")),
            ("prompt_choice", lambda: bootstrap.prompt_choice("Select", ["a", "b"])),
            ("_read_hidden", lambda: bootstrap._read_hidden("Key path")),
        ):
            with self.subTest(name):
                code, _, err, _, _ = self.run_bootstrap([], call=ask)
                self.assertEqual(code, 1)
                self.assertIn("error: unexpected end of input", err)

    def test_prompt_shows_and_returns_its_default(self):
        _, _, _, answers, _ = self.run_bootstrap([], ["  "], call=lambda: bootstrap.prompt("Owner", "octocat"))
        self.assertEqual(self.result, "octocat")
        self.assertEqual(answers.questions, ["Owner [octocat]: "])
        self.run_bootstrap([], [" acme "], call=lambda: bootstrap.prompt("Owner", "octocat"))
        self.assertEqual(self.result, "acme")

    def test_yes_and_no_answers(self):
        for reply, default, expected in (("", True, True), ("", False, False), ("YES", False, True), ("n", True, False)):
            with self.subTest(reply=reply, default=default):
                self.run_bootstrap([], [reply], call=lambda default=default: bootstrap.prompt_yn("Go?", default))
                self.assertIs(self.result, expected)


class CheckDependenciesTests(unittest.TestCase):
    def _check(self, missing=(), logged_in=True):
        err = io.StringIO()
        auth = subprocess.CompletedProcess(["gh", "auth", "status"], 0 if logged_in else 1)
        with patch.object(bootstrap.shutil, "which", lambda tool: None if tool in missing else f"/usr/bin/{tool}"), \
                patch.object(bootstrap.subprocess, "run", return_value=auth) as run, \
                contextlib.redirect_stderr(err):
            try:
                bootstrap.check_dependencies()
                code = None
            except SystemExit as exc:
                code = exc.code
        return code, err.getvalue(), run

    def test_each_missing_tool_is_named(self):
        for missing, logged_in, message in (
            (("gh",), True, "gh CLI not found"),
            (("git",), True, "git not found"),
            ((), False, "not logged in to GitHub CLI — run: gh auth login"),
        ):
            with self.subTest(message=message):
                code, err, _ = self._check(missing, logged_in)
                self.assertEqual(code, 1)
                self.assertIn(message, err)

    def test_a_logged_in_gh_passes(self):
        code, err, run = self._check()
        self.assertIsNone(code)
        self.assertEqual(err, "")
        self.assertEqual(run.call_args.args[0], ["gh", "auth", "status"])


class RetryTests(unittest.TestCase):
    def _retry(self, failures):
        calls, out = [], io.StringIO()

        def run(command, **kwargs):
            calls.append(command)
            if len(calls) <= failures:
                raise subprocess.CalledProcessError(1, command)

        with patch.object(bootstrap, "_run", run), patch.object(bootstrap.time, "sleep") as sleep, \
                contextlib.redirect_stdout(out):
            try:
                bootstrap._run_with_retry(["gh", "repo", "clone", "o/r", "/tmp/r"], delay=5)
                raised = None
            except subprocess.CalledProcessError as exc:
                raised = exc
        return calls, sleep, out.getvalue(), raised

    def test_a_clone_that_fails_twice_is_retried(self):
        calls, sleep, out, raised = self._retry(2)
        self.assertIsNone(raised)
        self.assertEqual(len(calls), 3)
        self.assertEqual([call.args for call in sleep.call_args_list], [(5,), (5,)])
        self.assertIn("clone failed (attempt 1/3), retrying…", out)
        self.assertIn("clone failed (attempt 2/3), retrying…", out)

    def test_a_clone_that_keeps_failing_gives_up_after_the_last_attempt(self):
        calls, sleep, out, raised = self._retry(3)
        self.assertIsInstance(raised, subprocess.CalledProcessError)
        self.assertEqual(len(calls), 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertNotIn("attempt 3/3", out)


class ConfigureOnlyTests(Session):
    ARGV = ["--configure-only", "--name", "app", "--type", "simple", "--org", "octocat"]

    def test_configure_only_cannot_be_a_dry_run(self):
        code, _, err, _, _ = self.run_bootstrap(self.ARGV + ["--dry-run"])
        self.assertEqual(code, 1)
        self.assertIn("--configure-only cannot be combined with --dry-run", err)

    def test_a_repository_that_is_not_there_stops_before_any_change(self):
        commands = Commands(fail=lambda command: command[:3] == ["gh", "repo", "view"])
        code, _, err, _, _ = self.run_bootstrap(self.ARGV + ["--non-interactive"], commands=commands)
        self.assertEqual(code, 1)
        self.assertIn("repository 'octocat/app' not found — verify the name and org", err)
        self.assertEqual(commands.ran("gh", "api", "repos/octocat/app", "--method"), [])

    def test_declining_to_proceed_changes_nothing(self):
        code, out, _, _, commands = self.run_bootstrap(self.ARGV, ["", "", "n"])
        self.assertIsNone(code)
        self.assertIn("About to configure: octocat/app (simple)", out)
        self.assertIn("Aborted.", out)
        self.assertFalse(any("--method" in command for command in commands.calls))

    def test_declined_actions_policy_changes_are_left_and_reported(self):
        code, out, _, answers, commands = self.run_bootstrap(self.ARGV, ["", "", "y", "n"])
        self.assertIsNone(code)
        self.assertIn("    Apply these Actions policy changes? [y/N]: ", answers.questions)
        self.assertIn("    left unchanged", out)
        self.assertEqual([command[2] for command in commands.ran("gh", "api") if "--method" in command],
                         ["repos/octocat/app"], "only the merge settings change")
        self.assertIn("https://github.com/octocat/app", out)
        self.assertIn("Actions policy (left unchanged; re-run --configure-only interactively to apply it)", out)
        self.assertIn("branch protection (main): left as is on an existing repository", out)

    def test_a_failed_setting_reports_what_was_applied(self):
        commands = Commands(fail=lambda command: "PATCH" in command)
        code, _, err, _, _ = self.run_bootstrap(self.ARGV + ["--non-interactive"], commands=commands)
        self.assertEqual(code, 1)
        self.assertIn("error: command failed: ['gh', 'api', 'repos/octocat/app', '--method', 'PATCH'", err)
        self.assertIn("Configuration stopped part-way", err)
        self.assertIn("Not applied: merge strategy", err)
        self.assertNotIn("gh repo delete", err)


class CreateFlowTests(Session):
    ARGV = ["--name", "app", "--type", "simple", "--org", "octocat", "--private", "--non-interactive"]

    def failing(self, *prefix, stderr=b""):
        return Commands(fail=lambda command: command[:len(prefix)] == list(prefix), stderr=stderr)

    def test_declining_to_proceed_creates_nothing(self):
        code, out, _, _, commands = self.run_bootstrap(self.ARGV[:-1], ["", "", "n"])
        self.assertIsNone(code)
        self.assertIn("About to create: octocat/app (simple, private)", out)
        self.assertIn("Aborted.", out)
        self.assertEqual(commands.calls, [])
        self.assertFalse((self.dir / "app").exists())

    def test_an_interactive_run_proceeds_on_yes(self):
        code, out, err, answers, commands = self.run_bootstrap(
            ["--name", "app", "--type", "nextjs", "--org", "octocat", "--public", "--postgres", "--screenshots"],
            ["", "", "y"])
        self.assertIsNone(code, err)
        self.assertIn("About to create: octocat/app (nextjs, public)", out)
        self.assertIn("  Extras: Postgres tests, screenshot review\n", out)
        self.assertEqual(answers.questions[-1], "\nProceed? [Y/n]: ")
        self.assertEqual(commands.calls[0], ["gh", "repo", "create", "octocat/app", "--public"])

    def test_a_complete_run_creates_pushes_configures_and_lists_what_is_left(self):
        code, out, err, _, commands = self.run_bootstrap(self.ARGV)
        self.assertIsNone(code, err)
        self.assertEqual(commands.calls[0], ["gh", "repo", "create", "octocat/app", "--private"])
        self.assertEqual(commands.calls[1], ["gh", "repo", "clone", "octocat/app", str((self.dir / "app").absolute())])
        self.assertEqual([command[3:5] for command in commands.ran("git")],
                         [["add", "."], ["commit", "-m"], ["push", "--set-upstream"]])
        self.assertTrue((self.dir / "app" / "AGENTS.md").is_file())
        self.assertTrue(commands.ran("gh", "api", "repos/octocat/app/branches/main/protection"))
        self.assertIn("https://github.com/octocat/app", out)
        self.assertIn("Still needs manual setup:\n    RELEASE_PLEASE_CLIENT_ID (variable)\n"
                      "    RELEASE_PLEASE_APP_KEY (secret)\n", out)
        self.assertEqual(err, "")

    def test_a_failed_create_names_the_likely_cause_and_no_cleanup(self):
        code, _, err, _, commands = self.run_bootstrap(self.ARGV, commands=self.failing("gh", "repo", "create"))
        self.assertEqual(code, 1)
        self.assertIn("failed to create 'octocat/app' — check it doesn't already exist", err)
        self.assertNotIn("gh repo delete", err)
        self.assertEqual(len(commands.calls), 1)

    def test_an_error_before_the_repository_exists_says_to_check_before_deleting(self):
        def gh_gone(command, **kwargs):
            raise FileNotFoundError(2, "No such file or directory", "gh")

        code, _, err, _, _ = self.run_bootstrap(self.ARGV, commands=gh_gone)
        self.assertEqual(code, 1)
        self.assertIn("error: [Errno 2] No such file or directory: 'gh'", err)
        self.assertIn("If the repository was created on GitHub, clean up with:\n  gh repo delete octocat/app\n", err)

    def test_a_failed_clone_is_retried_then_names_the_cleanup(self):
        commands = self.failing("gh", "repo", "clone")
        code, out, err, _, _ = self.run_bootstrap(self.ARGV, commands=commands)
        self.assertEqual(code, 1)
        self.assertEqual(len(commands.ran("gh", "repo", "clone")), 3)
        self.assertIn("clone failed (attempt 2/3), retrying…", out)
        self.assertIn("The repository was created on GitHub. Clean up with:\n  gh repo delete octocat/app\n", err)
        self.assertIn("failed to clone into 'app'", err)

    def test_a_failed_push_says_the_repository_exists_and_how_to_remove_it(self):
        code, _, err, _, commands = self.run_bootstrap(self.ARGV, commands=self.failing("git", "-C", "app", "push"))
        self.assertEqual(code, 1)
        self.assertIn("error: command failed: ['git', '-C', 'app', 'push'", err)
        self.assertIn("The GitHub repository was created, but local setup or push failed.\n"
                      "Inspect the cloned directory and retry, or clean up with:\n"
                      "  gh repo delete octocat/app\n", err)
        self.assertNotIn("Files were pushed", err)
        self.assertEqual(commands.ran("gh", "api"), [], "nothing is configured after a failed push")

    def test_a_failed_setting_after_the_push_keeps_the_repository(self):
        code, _, err, _, _ = self.run_bootstrap(self.ARGV, commands=self.failing("gh", "api", "repos/octocat/app",
                                                                                   "--method", "PATCH"))
        self.assertEqual(code, 1)
        self.assertIn("Files were pushed successfully.", err)
        self.assertIn("Configuration stopped part-way", err)
        self.assertIn("--configure-only --name app --type simple --org octocat", err)
        self.assertNotIn("gh repo delete", err)

    def test_branch_protection_needing_github_pro_is_reported_and_skipped(self):
        stderr = b"gh: Upgrade to GitHub Pro or make this repository public to enable this feature. (HTTP 403)"
        code, out, err, _, _ = self.run_bootstrap(
            self.ARGV, commands=self.failing("gh", "api", "repos/octocat/app/branches/main/protection",
                                             stderr=stderr))
        self.assertIsNone(code, err)
        self.assertIn("  warning: branch protection requires GitHub Pro for private repos; skipping.", out)
        self.assertNotIn("Upgrade to GitHub Pro or make", out)
        self.assertIn("    branch protection on main (requires GitHub Pro for private repos)\n", out)

    def test_another_branch_protection_failure_shows_the_error(self):
        code, out, err, _, _ = self.run_bootstrap(
            self.ARGV, commands=self.failing("gh", "api", "repos/octocat/app/branches/main/protection",
                                             stderr=b"gh: Validation Failed (HTTP 422)\n"))
        self.assertIsNone(code, err)
        self.assertIn("  warning: branch protection could not be set automatically.\n"
                      "    gh: Validation Failed (HTTP 422)\n", out)
        self.assertIn("    branch protection on main (failed — see warning above for details)\n", out)

    def test_a_folder_that_is_not_empty_is_refused_before_anything_is_created(self):
        (self.dir / "app").mkdir()
        (self.dir / "app" / "notes.txt").write_text("keep me\n")
        cfg = {"name": "app", "owner": "octocat", "repo_type": "simple", "private": True,
               "repo_dir": Path("app"), "postgres": False}
        code, _, err, _, commands = self.run_bootstrap(
            [], call=lambda: bootstrap.create_and_push(cfg, bootstrap.generate_files(cfg)))
        self.assertEqual(code, 1)
        self.assertIn("target directory 'app' already exists and is not empty", err)
        self.assertEqual(commands.calls, [])

    def test_success_with_everything_configured_lists_nothing_left(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            bootstrap.print_success({"name": "app", "owner": "octocat", "release_please_client_id": "id",
                                     "release_please_app_key": "key"})
        self.assertIn("  https://github.com/octocat/app\n", out.getvalue())
        self.assertNotIn("Still needs manual setup", out.getvalue())


if __name__ == "__main__":
    unittest.main()
