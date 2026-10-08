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

    def test_guard_refuses_only_a_pending_merge_it_did_not_test(self):
        guard = next(step for step in self._steps("python") if step.get("name") == self.GUARD)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        fake_gh = Path(tmp.name) / "gh"
        fake_gh.write_text('#!/bin/sh\nprintf "%s" "$FAKE_PENDING"\n')
        fake_gh.chmod(0o755)
        cases = {
            "no pending release": ("", 0),
            "pending release is this commit": ("71 abc123", 0),
            "pending release is an older commit": ("71 def456", 1),
        }
        for label, (pending, expected) in cases.items():
            with self.subTest(label):
                result = subprocess.run(
                    ["bash", "-c", guard["run"]], capture_output=True, text=True,
                    env={"PATH": f"{tmp.name}:/usr/bin:/bin", "FAKE_PENDING": pending,
                         "REPO": "octocat/sample", "TESTED_SHA": "abc123"},
                )
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                if expected:
                    self.assertIn("::error::Release PR #71 merged as def456", result.stdout)


if __name__ == "__main__":
    unittest.main()
