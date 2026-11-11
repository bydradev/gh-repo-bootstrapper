"""Tests for the Android repository type (Package B1)."""

import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

import bootstrap


def _git(repo: Path, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _render_android(name="sample-android"):
    return bootstrap.generate_files({
        "name": name,
        "repo_type": "android",
        "postgres": False,
        "scheme": "",
        "destination": "",
        "screenshots": False,
    })


class AndroidTypeGenerationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_b1_ac1_fresh_generation_and_stamps(self):
        cfg = {
            "name": "sample-android",
            "repo_type": "android",
            "owner": "example-owner",
            "private": True,
            "postgres": False,
            "scheme": "",
            "destination": "",
            "screenshots": False,
        }
        files = bootstrap.generate_files(cfg)

        # Expected infrastructure files
        expected_paths = {
            "README.md",
            "AGENTS.md",
            "CLAUDE.md",
            ".gitignore",
            "docs/current-work.md",
            "docs/branch-protection-runbook.md",
            ".github/pull_request_template.md",
            ".github/workflows/pr-title-check.yml",
            ".github/workflows/release-please.yml",
            ".github/workflows/ci.yml",
            ".github/workflows/test.yml",
            ".github/dependabot.yml",
            "release-please-config.json",
            ".release-please-manifest.json",
        }
        for path in expected_paths:
            self.assertIn(path, files, f"missing expected file {path}")

        # Stamped template-owned files
        for path in bootstrap.template_owned_paths(cfg):
            content = files[path]
            is_yaml = path.endswith((".yml", ".yaml"))
            digest, _ = bootstrap.read_stamp(content, is_yaml)
            self.assertIsNotNone(digest, f"file {path} must have a valid ownership stamp")

        # Gitignore contains Android SDK, build and signing outputs
        gitignore = files[".gitignore"]
        for entry in (".gradle/", "local.properties", "*.keystore", "*.jks", ".cxx/", "captures/"):
            self.assertIn(entry, gitignore, f".gitignore missing {entry}")

        # Required status checks include test / test
        self.assertEqual(
            bootstrap.required_status_checks("android"),
            ["validate-title", "test / test"],
        )

    def test_b1_ac1_dry_run_absence_of_writes(self):
        target_dir = self.root / "dry-run-repo"
        cfg = {
            "name": "dry-run-repo",
            "repo_dir": target_dir,
            "repo_type": "android",
            "owner": "example-owner",
            "private": True,
            "postgres": False,
            "scheme": "",
            "destination": "",
            "screenshots": False,
        }
        files = bootstrap.generate_files(cfg)

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            bootstrap.print_dry_run(cfg, files)

        output = out.getvalue()
        self.assertIn("DRY RUN — example-owner/dry-run-repo (android, private)", output)
        self.assertIn(".github/workflows/test.yml", output)
        self.assertIn("README.md", output)

        # Absence of writes: target directory was never created or written to
        self.assertFalse(target_dir.exists(), "dry-run must not create target directory")

    def test_b1_ac1_check_read_only_and_drift_detection(self):
        repo_dir = self.root / "check-repo"
        repo_dir.mkdir()
        _git(repo_dir, "init", "-q")
        _git(repo_dir, "config", "user.name", "Test User")
        _git(repo_dir, "config", "user.email", "user@example.com")

        cfg = {
            "name": "check-repo",
            "repo_dir": repo_dir,
            "repo_type": "android",
            "owner": "example-owner",
            "private": True,
            "postgres": False,
            "scheme": "",
            "destination": "",
            "screenshots": False,
        }
        files = bootstrap.generate_files(cfg)

        # On empty repository: compare_repository reports missing files
        report = bootstrap.compare_repository(repo_dir, files)
        self.assertIn("README.md", report)
        self.assertEqual(report["README.md"][0], "missing")
        self.assertIn(".github/workflows/test.yml", report)
        self.assertEqual(report[".github/workflows/test.yml"][0], "missing")

        # Write files, create mirror links, and commit
        for rel, content in files.items():
            path = repo_dir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        for rel, target in bootstrap.generate_links(cfg).items():
            link = repo_dir / rel
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(target)
        _git(repo_dir, "add", "-A")
        _git(repo_dir, "commit", "-q", "-m", "Initial commit")

        # Clean check reports aligned
        clean_report = bootstrap.compare_repository(repo_dir, files)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            aligned = bootstrap.print_repository_report(repo_dir, cfg, clean_report)
        self.assertTrue(aligned)
        self.assertIn("Aligned.", out.getvalue())


class AndroidTypeAdoptionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_b1_ac2_adoption_preserves_app_owned_files_and_project_specifics(self):
        repo_dir = self.root / "existing-android-app"
        repo_dir.mkdir()
        _git(repo_dir, "init", "-q")
        _git(repo_dir, "config", "user.name", "Test User")
        _git(repo_dir, "config", "user.email", "user@example.com")

        # Create app-owned files in the fixture
        build_gradle = "// Custom app build script\nplugins { id('com.android.application') }\n"
        settings_gradle = "rootProject.name = 'my-custom-app'\ninclude(':app')\n"
        gradlew_script = "#!/bin/sh\necho 'running custom gradlew'\n"
        app_source = "package com.example.app\nclass MainActivity {}\n"
        local_props = "sdk.dir=/path/to/local/sdk\n"
        gradle_props = "android.onlyEnableUnitTestForTheTestedBuildType=false\n"
        gitignore_content = "*.iml\n.gradle\n/build\nlocal.properties\n"

        (repo_dir / "build.gradle.kts").write_text(build_gradle, encoding="utf-8")
        (repo_dir / "settings.gradle.kts").write_text(settings_gradle, encoding="utf-8")
        gradlew_path = repo_dir / "gradlew"
        gradlew_path.write_text(gradlew_script, encoding="utf-8")
        gradlew_path.chmod(0o755)
        (repo_dir / "local.properties").write_text(local_props, encoding="utf-8")
        (repo_dir / "gradle.properties").write_text(gradle_props, encoding="utf-8")
        (repo_dir / ".gitignore").write_text(gitignore_content, encoding="utf-8")

        app_src_dir = repo_dir / "app" / "src" / "main" / "java" / "com" / "example" / "app"
        app_src_dir.mkdir(parents=True)
        (app_src_dir / "MainActivity.kt").write_text(app_source, encoding="utf-8")

        # Existing AGENTS.md with Project specifics
        existing_agents = (
            _render_android("existing-android-app")["AGENTS.md"]
            + "\n### Custom App Rule\n\nOnly the app team edits domain state.\n"
        )
        (repo_dir / "AGENTS.md").write_text(existing_agents, encoding="utf-8")

        _git(repo_dir, "add", "-A")
        _git(repo_dir, "commit", "-q", "-m", "Existing app project commit")

        # Perform adoption
        cfg = {
            "name": "existing-android-app",
            "repo_dir": repo_dir,
            "repo_type": "android",
            "owner": "example-owner",
            "private": True,
            "postgres": False,
            "scheme": "",
            "destination": "",
            "screenshots": False,
        }
        files = bootstrap.generate_files(cfg)
        actions = bootstrap.adopt_repository(repo_dir, files)

        # App-owned files are untouched
        self.assertEqual((repo_dir / "build.gradle.kts").read_text(encoding="utf-8"), build_gradle)
        self.assertEqual((repo_dir / "settings.gradle.kts").read_text(encoding="utf-8"), settings_gradle)
        self.assertEqual((repo_dir / "gradlew").read_text(encoding="utf-8"), gradlew_script)
        self.assertEqual((repo_dir / "local.properties").read_text(encoding="utf-8"), local_props)
        self.assertEqual((repo_dir / "gradle.properties").read_text(encoding="utf-8"), gradle_props)
        self.assertEqual((app_src_dir / "MainActivity.kt").read_text(encoding="utf-8"), app_source)

        # Project specifics are preserved in AGENTS.md
        adopted_agents = (repo_dir / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("### Custom App Rule", adopted_agents)
        self.assertIn("Only the app team edits domain state.", adopted_agents)

        # .gitignore has managed block added, preserving existing rules
        adopted_gitignore = (repo_dir / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("*.iml", adopted_gitignore)
        self.assertIn(bootstrap.MANAGED_BLOCK_BEGIN, adopted_gitignore)
        self.assertIn(bootstrap.MANAGED_BLOCK_END, adopted_gitignore)

        # Stamped workflows are installed
        self.assertTrue((repo_dir / ".github" / "workflows" / "pr-title-check.yml").is_file())
        self.assertTrue((repo_dir / ".github" / "workflows" / "release-please.yml").is_file())
        self.assertTrue((repo_dir / ".github" / "workflows" / "test.yml").is_file())

    def test_b1_ac2_symlink_protection_during_adoption(self):
        repo_dir = self.root / "symlink-repo"
        repo_dir.mkdir()
        _git(repo_dir, "init", "-q")
        _git(repo_dir, "config", "user.name", "Test User")
        _git(repo_dir, "config", "user.email", "user@example.com")

        # Create a symlink at docs/current-work.md pointing elsewhere
        outside_target = self.root / "outside.md"
        outside_target.write_text("outside text\n", encoding="utf-8")
        docs_dir = repo_dir / "docs"
        docs_dir.mkdir()
        (docs_dir / "current-work.md").symlink_to(outside_target)

        _git(repo_dir, "add", "-A")
        _git(repo_dir, "commit", "-q", "-m", "Symlink commit")

        files = _render_android("symlink-repo")

        report = bootstrap.compare_repository(repo_dir, files)
        self.assertEqual(report["docs/current-work.md"][0], "symlink")

        # adopt_repository must refuse or not overwrite the symlink target
        actions = bootstrap.adopt_repository(repo_dir, files)
        self.assertEqual(outside_target.read_text(encoding="utf-8"), "outside text\n")


class AndroidWorkflowScaffoldContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _extract_workflow_steps(self):
        files = _render_android("fixture-app")
        workflow = yaml.safe_load(files[".github/workflows/test.yml"])
        return workflow["jobs"]["test"]["steps"]

    def test_b1_ac3_workflow_fails_when_scaffold_absent(self):
        # In a repository without gradlew:
        # The scaffold guard step must fail clearly with an informative error message.
        empty_repo = self.root / "empty-android-repo"
        empty_repo.mkdir()

        steps = self._extract_workflow_steps()
        guard_step = next(
            s for s in steps if s.get("name") == "Require an executable Gradle wrapper"
        )
        guard_script = guard_step["run"]
        self.assertIn("No Gradle wrapper found (gradlew missing)", guard_script)

        # Run the extracted guard script in the empty directory (missing gradlew)
        proc = subprocess.run(
            ["sh", "-c", guard_script],
            cwd=str(empty_repo),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("No Gradle wrapper found (gradlew missing)", proc.stdout)

        # When gradlew exists but is not executable
        (empty_repo / "gradlew").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        (empty_repo / "gradlew").chmod(0o644)
        proc_not_exec = subprocess.run(
            ["sh", "-c", guard_script],
            cwd=str(empty_repo),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc_not_exec.returncode, 1)
        self.assertIn("Gradle wrapper gradlew is not executable", proc_not_exec.stdout)

    def test_b1_ac3_minimal_fixture_supplies_and_exercises_commands(self):
        fixture_repo = self.root / "fixture-android-repo"
        fixture_repo.mkdir()

        # Supply minimal application scaffold: executable gradlew supporting check
        gradlew = fixture_repo / "gradlew"
        gradlew.write_text(
            """#!/bin/sh
if [ "$1" = "check" ]; then
  echo "BUILD SUCCESSFUL"
  exit 0
fi
echo "unknown argument: $1" >&2
exit 1
""",
            encoding="utf-8",
        )
        gradlew.chmod(0o755)

        steps = self._extract_workflow_steps()
        guard_step = next(
            s for s in steps if s.get("name") == "Require an executable Gradle wrapper"
        )
        guard_script = guard_step["run"]

        check_step = next(s for s in steps if s.get("name") == "Run checks")
        check_cmd = check_step["run"]
        self.assertEqual(check_cmd, "./gradlew check")

        # Execute extracted guard step
        guard_proc = subprocess.run(
            ["sh", "-c", guard_script],
            cwd=str(fixture_repo),
            capture_output=True,
            text=True,
        )
        self.assertEqual(guard_proc.returncode, 0)

        # Execute extracted app-side check step
        check_proc = subprocess.run(
            ["sh", "-c", check_cmd],
            cwd=str(fixture_repo),
            capture_output=True,
            text=True,
        )
        self.assertEqual(check_proc.returncode, 0)
        self.assertIn("BUILD SUCCESSFUL", check_proc.stdout)


if __name__ == "__main__":
    unittest.main()
