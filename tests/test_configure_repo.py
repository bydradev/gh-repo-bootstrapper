"""Regression tests for provider-free generated repository configuration."""

import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

import bootstrap


class ConfigureRepoTests(unittest.TestCase):
    def _config(self):
        return {
            "name": "example",
            "owner": "octocat",
            "repo_type": "nextjs",
            "private": False,
            "postgres": False,
            "release_please_client_id": "client-id",
            "release_please_app_key": "private-key",
        }

    def test_configure_repo_writes_only_release_please_credentials(self):
        calls = []

        def run(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0)

        with patch.object(bootstrap.subprocess, "run", side_effect=run):
            bootstrap.configure_repo(self._config())

        variable_names = [
            command[3] for command, _kwargs in calls if command[:3] == ["gh", "variable", "set"]
        ]
        secret_names = [
            command[3] for command, _kwargs in calls if command[:3] == ["gh", "secret", "set"]
        ]
        self.assertEqual(variable_names, ["RELEASE_PLEASE_CLIENT_ID"])
        self.assertEqual(secret_names, ["RELEASE_PLEASE_APP_KEY"])

    def test_creation_commands_ignore_an_inherited_index_override(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        other, target = Path(tmp.name) / "other", Path(tmp.name) / "target"
        for repo in (other, target):
            subprocess.run(["git", "init", "-q", str(repo)], check=True, env=bootstrap._git_env())
        (target / "generated.txt").write_text("x\n")
        with patch.dict(os.environ, {"GIT_INDEX_FILE": str(other / ".git" / "index")}):
            bootstrap._run(["git", "-C", str(target), "add", "."])

        def tracked(repo):
            return subprocess.run(
                ["git", "-C", str(repo), "ls-files"],
                capture_output=True, text=True, check=True, env=bootstrap._git_env(),
            ).stdout

        self.assertEqual(tracked(target), "generated.txt\n")
        self.assertEqual(tracked(other), "")

    def test_selected_actions_excludes_provider_actions(self):
        rust_only = ["dtolnay/rust-toolchain@*", "Swatinem/rust-cache@*"]
        for repo_type in ("simple", "python", "nextjs", "swift", "rust"):
            with self.subTest(repo_type=repo_type):
                calls = []

                def run(command, **kwargs):
                    calls.append((command, kwargs))
                    return subprocess.CompletedProcess(command, 0)

                with patch.object(bootstrap.subprocess, "run", side_effect=run):
                    bootstrap.configure_repo({**self._config(), "repo_type": repo_type})

                command, kwargs = next(
                    (command, kwargs)
                    for command, kwargs in calls
                    if command[2] == "repos/octocat/example/actions/permissions/selected-actions"
                )
                payload = json.loads(kwargs["input"].decode())
                self.assertEqual(
                    payload["patterns_allowed"],
                    ["amannn/action-semantic-pull-request@*"] + (rust_only if repo_type == "rust" else []),
                )

    def test_rust_allowlist_covers_every_third_party_action_it_renders(self):
        files = bootstrap.generate_files({**self._config(), "repo_type": "rust", "name": "sample"})
        used = set()
        for path, text in files.items():
            if path.startswith(".github/workflows/"):
                used |= set(re.findall(r"uses:\s*([\w.-]+/[\w.-]+)@", text))
        third_party = {action for action in used if not action.startswith("actions/")}
        allowed = {p.removesuffix("@*") for p in bootstrap.selected_action_patterns("rust")}
        self.assertIn("Swatinem/rust-cache", third_party)
        # googleapis is a Marketplace verified creator; everything else needs a pattern.
        self.assertEqual(third_party - {"googleapis/release-please-action"}, allowed)

    def test_nextjs_render_is_provider_free_and_preserves_postgres(self):
        files = bootstrap.generate_files({**self._config(), "name": "sample", "postgres": True})
        rendered = "\n".join(
            content for path, content in files.items() if path != ".gitignore"
        ).lower()
        self.assertNotIn("vercel", rendered)
        self.assertNotIn("cloudflare", rendered)
        self.assertNotIn("wrangler", rendered)
        self.assertNotIn("wrangler.jsonc", files)
        self.assertIn(".vercel/", files[".gitignore"])
        self.assertIn(".wrangler/", files[".gitignore"])
        self.assertIn("postgres", files[".github/workflows/test.yml"].lower())
        self.assertNotIn("deployments: write", files[".github/workflows/release-please.yml"])

    def test_gather_config_has_no_provider_keys(self):
        with patch.object(
            sys,
            "argv",
            [
                "bootstrap.py",
                "--name",
                "sample",
                "--type",
                "nextjs",
                "--org",
                "octocat",
                "--non-interactive",
                "--dry-run",
            ],
        ):
            config = bootstrap.gather_config(bootstrap.parse_args())

        self.assertFalse({"vercel", "cloudflare", "vercel_token", "cloudflare_api_token"} & config.keys())

    def test_retired_provider_flags_are_rejected(self):
        for flag in ("--vercel", "--no-vercel", "--cloudflare", "--no-cloudflare"):
            with self.subTest(flag=flag), patch.object(sys, "argv", ["bootstrap.py", flag]):
                with self.assertRaises(SystemExit) as error:
                    bootstrap.parse_args()
            self.assertEqual(error.exception.code, 2)


class ConfigureExistingRepositoryTests(unittest.TestCase):
    """--configure-only on a repository that already exists."""

    REPO = "repos/octocat/example"
    # An existing Rust repository with its own checks and a looser Actions policy.
    CURRENT = {
        f"{REPO}/actions/permissions": {"enabled": True, "allowed_actions": "all", "sha_pinning_required": False},
        f"{REPO}/actions/permissions/workflow": {
            "default_workflow_permissions": "write", "can_approve_pull_request_reviews": False,
        },
        f"{REPO}/branches/main/protection": {
            "required_status_checks": {"strict": True, "contexts": ["Linux (default push CI)"]},
        },
    }

    def _configure(self, current, confirm, configure_only=True):
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            if command[:2] == ["gh", "api"] and "--method" not in command:
                body = current.get(command[2])
                if body is None:
                    return subprocess.CompletedProcess(command, 1, b"", b"Not Found")
                return subprocess.CompletedProcess(command, 0, json.dumps(body).encode(), b"")
            return subprocess.CompletedProcess(command, 0)

        cfg = {
            "name": "example", "owner": "octocat", "repo_type": "rust", "private": False,
            "configure_only": configure_only,
            "release_please_client_id": "client-id", "release_please_app_key": "private-key",
        }
        out = io.StringIO()
        with patch.object(bootstrap.subprocess, "run", side_effect=run), contextlib.redirect_stdout(out):
            bootstrap.configure_repo(cfg, confirm=confirm)
        writes = [command[2] for command in calls if command[:2] == ["gh", "api"] and "--method" in command]
        return writes, out.getvalue(), cfg

    def test_existing_protection_is_never_replaced(self):
        for confirm in (None, lambda: False, lambda: True):
            with self.subTest(confirm=confirm):
                writes, out, _ = self._configure(self.CURRENT, confirm)
                self.assertNotIn(f"{self.REPO}/branches/main/protection", writes)
                self.assertIn("Linux (default push CI)", out)
                self.assertIn("docs/branch-protection-runbook.md", out)

    def test_actions_policy_changes_are_listed_and_need_a_yes(self):
        actions = [endpoint for endpoint, _ in bootstrap.actions_policy_requests(
            {"owner": "octocat", "name": "example", "repo_type": "rust", "private": False}
        )]
        for confirm in (None, lambda: False):
            with self.subTest(confirm=confirm):
                writes, out, cfg = self._configure(self.CURRENT, confirm)
                self.assertEqual(writes, [self.REPO])
                self.assertIn('allowed_actions: "all" -> "selected"', out)
                self.assertIn('default_workflow_permissions: "write" -> "read"', out)
                self.assertTrue(cfg["actions_policy_unchanged"])
        writes, _, cfg = self._configure(self.CURRENT, lambda: True)
        self.assertEqual(writes, [self.REPO, *actions])
        self.assertNotIn("actions_policy_unchanged", cfg)

    def test_matching_actions_policy_asks_nothing(self):
        requests = bootstrap.actions_policy_requests(
            {"owner": "octocat", "name": "example", "repo_type": "rust", "private": False}
        )
        current = {**self.CURRENT, **dict(requests)}

        def never():
            raise AssertionError("asked to confirm an unchanged policy")

        writes, out, _ = self._configure(current, never)
        self.assertEqual(writes, [self.REPO])
        self.assertIn("already matches the generated policy", out)

    def test_security_settings_are_pinned(self):
        calls = []

        def run(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0)

        cfg = {
            "name": "example", "owner": "octocat", "repo_type": "python", "private": True,
            "release_please_client_id": "", "release_please_app_key": "",
        }
        with patch.object(bootstrap.subprocess, "run", side_effect=run), contextlib.redirect_stdout(io.StringIO()):
            bootstrap.configure_repo(cfg)
        payloads = {
            command[2]: json.loads(kwargs["input"].decode())
            for command, kwargs in calls if command[:2] == ["gh", "api"]
        }
        self.assertEqual(payloads[self.REPO], {
            "allow_squash_merge": True, "allow_merge_commit": False, "allow_rebase_merge": False,
            "delete_branch_on_merge": True, "squash_merge_commit_title": "PR_TITLE",
            "squash_merge_commit_message": "PR_BODY", "allow_update_branch": True, "has_projects": True,
        })
        self.assertEqual(payloads[f"{self.REPO}/actions/permissions"], {
            "enabled": True, "allowed_actions": "selected", "sha_pinning_required": True,
        })
        self.assertEqual(payloads[f"{self.REPO}/actions/permissions/selected-actions"], {
            "github_owned_allowed": True, "verified_allowed": True,
            "patterns_allowed": ["amannn/action-semantic-pull-request@*"],
        })
        self.assertEqual(payloads[f"{self.REPO}/actions/permissions/workflow"], {
            "default_workflow_permissions": "read", "can_approve_pull_request_reviews": False,
        })
        self.assertEqual(payloads[f"{self.REPO}/actions/permissions/fork-pr-workflows-private-repos"], {
            "run_workflows_from_fork_pull_requests": False, "send_write_tokens_to_workflows": False,
            "send_secrets_and_variables": False, "require_approval_for_fork_pr_workflows": False,
        })
        self.assertEqual(payloads[f"{self.REPO}/branches/main/protection"], {
            "required_status_checks": {"strict": False, "contexts": ["validate-title", "test / test"]},
            "enforce_admins": True,
            "required_pull_request_reviews": {
                "dismiss_stale_reviews": False, "require_code_owner_reviews": False,
                "required_approving_review_count": 0,
            },
            "restrictions": None,
        })

    def test_new_repository_still_gets_policy_and_protection(self):
        writes, _, _ = self._configure({}, None, configure_only=False)
        self.assertIn(f"{self.REPO}/actions/permissions", writes)
        self.assertIn(f"{self.REPO}/branches/main/protection", writes)


class ReleaseGateGuardTests(unittest.TestCase):
    """The gated release workflows refuse to tag a release merge they did not test."""

    GUARD = "Refuse to tag an untested release merge"

    def _steps(self, repo_type):
        files = bootstrap.generate_files(
            {"name": "sample", "repo_type": repo_type, "postgres": False, "scheme": "App"}
        )
        workflow = yaml.safe_load(files[".github/workflows/release-please.yml"])
        return workflow["jobs"]["release-please"]["steps"]

    def test_guard_runs_after_the_app_token_and_before_release_please(self):
        for repo_type in ("nextjs", "python", "swift", "rust"):
            with self.subTest(repo_type=repo_type):
                steps = self._steps(repo_type)
                names = [step.get("name") or step.get("uses", "") for step in steps]
                guard = names.index(self.GUARD)
                self.assertEqual(steps[guard - 1].get("id"), "app-token")
                self.assertTrue(names[guard + 1].startswith("googleapis/release-please-action@"))
                # release-please may tag only on the run the guard cleared.
                self.assertEqual(
                    steps[guard + 1]["with"]["skip-github-release"],
                    "${{ steps.guard.outputs.release != 'true' }}",
                )

    def test_guard_refuses_only_a_pending_merge_it_did_not_test(self):
        expected_argv = [
            "pr", "list", "--repo", "octocat/sample", "--state", "merged",
            "--label", "autorelease: pending", "--json", "number,mergeCommit",
            "--jq", '.[] | "\\(.number) \\(.mergeCommit.oid)"',
        ]
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        argv_file = Path(tmp.name) / "gh-argv"
        fake_gh = Path(tmp.name) / "gh"
        # Records each call's arguments; answers the compare call with how the
        # pending merge relates to TESTED_SHA (abc123).
        fake_gh.write_text(
            "#!/bin/sh\n"
            'printf "%s\\0" "$@" >> "$ARGV_FILE"; printf "\\n" >> "$ARGV_FILE"\n'
            '[ -z "$FAKE_FAIL" ] || exit 1\n'
            'if [ "$1" = api ]; then\n'
            '  cat > /dev/null\n'  # would swallow the guard's remaining rows without </dev/null
            '  [ -z "$FAKE_COMPARE_FAIL" ] || exit 1\n'
            '  case "$2" in\n'
            '    */compare/abc123...fff999) echo ahead ;;\n'
            '    */compare/abc123...def456) echo behind ;;\n'
            '    */compare/abc123...0dd000) echo diverged ;;\n'
            '    *) echo "unexpected compare: $2" >&2; exit 3 ;;\n'
            '  esac\n'
            'else\n'
            '  printf "%s" "$FAKE_PENDING"\n'
            'fi\n'
        )
        fake_gh.chmod(0o755)
        output = Path(tmp.name) / "github-output"
        # (pending rows, gh fails, exit code, release output or None when the step
        # fails before it, commits compared, message expected in the log)
        cases = {
            "no pending release": ("", False, 0, "false", [], None),
            "pending release is this commit": ("71 abc123", False, 0, "true", [], None),
            "pending release is an older commit": (
                "71 def456", False, 1, "false", ["def456"], "::error::Release PR #71 merged as def456"),
            "pending release merged after this commit": (
                "71 fff999", False, 0, "false", ["fff999"], "::notice::Release PR #71 merged as fff999"),
            "pending release on a diverged history": (
                "71 0dd000", False, 1, "false", ["0dd000"], "::error::Release PR #71 merged as 0dd000"),
            "this commit and an older one": (
                "71 abc123\n72 def456", False, 1, "true", ["def456"], "::error::Release PR #72 merged as def456"),
            "a newer merge, then an older one": (
                "71 fff999\n72 def456", False, 1, "false", ["fff999", "def456"],
                "::error::Release PR #72 merged as def456"),
            "this commit and a newer one": (
                "71 abc123\n72 fff999", False, 1, "false", ["fff999"], "::error::More than one release PR is pending"),
            "a newer one and this commit": (
                "71 fff999\n72 abc123", False, 1, "false", ["fff999"], "::error::More than one release PR is pending"),
            "the gh query fails": ("", True, 1, None, [], None),
            "the compare call fails": ("71 def456", "compare", 1, None, ["def456"], None),
        }
        for repo_type in ("python", "nextjs"):
            guard = next(step for step in self._steps(repo_type) if step.get("name") == self.GUARD)
            self.assertEqual(guard.get("id"), "guard")
            for label, (pending, fail, code, release, compared, message) in cases.items():
                with self.subTest(repo_type=repo_type, case=label):
                    output.write_text("")
                    argv_file.write_text("")
                    # GitHub runs a bash step as `bash --noprofile --norc -eo pipefail {0}`.
                    result = subprocess.run(
                        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", guard["run"]],
                        capture_output=True, text=True,
                        env={
                            "PATH": f"{tmp.name}:/usr/bin:/bin", "ARGV_FILE": str(argv_file),
                            "FAKE_PENDING": pending, "FAKE_FAIL": "1" if fail is True else "",
                            "FAKE_COMPARE_FAIL": "1" if fail == "compare" else "",
                            "REPO": "octocat/sample", "TESTED_SHA": "abc123",
                            "GITHUB_OUTPUT": str(output),
                        },
                    )
                    self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                    calls = [line.split("\0")[:-1] for line in argv_file.read_text().split("\n") if line]
                    self.assertEqual(calls, [expected_argv] + [
                        ["api", f"repos/octocat/sample/compare/abc123...{oid}", "--jq", ".status"]
                        for oid in compared
                    ])
                    if message:
                        self.assertIn(message, result.stdout)
                    expected_output = "" if release is None else f"release={release}\n"
                    self.assertEqual(output.read_text(), expected_output)


class PythonToolInstallTests(unittest.TestCase):
    """The generated Python suite installs pinned tools only when the project has none."""

    def test_pinned_fallbacks_install_only_missing_tools(self):
        files = bootstrap.generate_files({"name": "sample", "repo_type": "python", "postgres": False})
        steps = yaml.safe_load(files[".github/workflows/test.yml"])["jobs"]["test"]["steps"]
        script = next(step["run"] for step in steps if step.get("name") == "Install dependencies")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        log = Path(tmp.name) / "pip-log"
        fake_pip = Path(tmp.name) / "bin" / "pip"
        fake_pip.parent.mkdir()
        fake_pip.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = show ]; then case " $INSTALLED " in *" $2 "*) exit 0 ;; *) exit 1 ;; esac; fi\n'
            'echo "$*" >> "$PIP_LOG"\n'
            'exit "${PIP_FAIL:-0}"\n'
        )
        fake_pip.chmod(0o755)
        work = Path(tmp.name) / "project"
        work.mkdir()
        cases = {
            "nothing installed": ("", "", 0, ["install ruff==0.16.10", "install mypy==2.4.0", "install pytest==9.1.1"]),
            "the project pins ruff and pytest": ("ruff pytest", "", 0, ["install mypy==2.4.0"]),
            "an install fails": ("", "1", 1, ["install ruff==0.16.10"]),
        }
        for label, (installed, fail, code, installs) in cases.items():
            with self.subTest(label):
                log.write_text("")
                result = subprocess.run(
                    ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script],
                    cwd=work, capture_output=True, text=True,
                    env={"PATH": f"{fake_pip.parent}:/usr/bin:/bin", "PIP_LOG": str(log),
                         "INSTALLED": installed, "PIP_FAIL": fail},
                )
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                self.assertEqual(log.read_text().splitlines(), installs)


if __name__ == "__main__":
    unittest.main()
