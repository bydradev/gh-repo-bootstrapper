"""Tests for the Android repository type (Packages B1 and B2)."""

import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

import bootstrap
import validate_templates


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

        # Supply minimal application scaffold: executable gradlew supporting all lanes
        gradlew = fixture_repo / "gradlew"
        gradlew.write_text(
            """#!/bin/sh
case "$*" in
  "check")
    echo "FULL VALIDATION SUCCESSFUL"
    exit 0
    ;;
  "spotlessCheck lintDebug testDebugUnitTest")
    echo "FAST CHECKS SUCCESSFUL"
    exit 0
    ;;
  "connectedCheck")
    echo "DEVICE CHECKS SUCCESSFUL"
    exit 0
    ;;
  *)
    echo "unknown arguments: $*" >&2
    exit 1
    ;;
esac
""",
            encoding="utf-8",
        )
        gradlew.chmod(0o755)

        steps = self._extract_workflow_steps()
        guard_step = next(
            s for s in steps if s.get("name") == "Require an executable Gradle wrapper"
        )
        guard_script = guard_step["run"]

        fast_step = next(s for s in steps if s.get("name") == "Run fast checks")
        fast_cmd = fast_step["run"]
        self.assertEqual(fast_cmd, "./gradlew spotlessCheck lintDebug testDebugUnitTest")

        full_step = next(s for s in steps if s.get("name") == "Run full validation")
        full_cmd = full_step["run"]
        self.assertEqual(full_cmd, "./gradlew check")

        device_step = next(s for s in steps if s.get("name") == "Run device checks")
        device_cmd = device_step["run"]
        self.assertEqual(device_cmd, "./gradlew connectedCheck")

        # Execute extracted guard step
        guard_proc = subprocess.run(
            ["sh", "-c", guard_script],
            cwd=str(fixture_repo),
            capture_output=True,
            text=True,
        )
        self.assertEqual(guard_proc.returncode, 0)

        # Execute extracted fast checks step
        fast_proc = subprocess.run(
            ["sh", "-c", fast_cmd],
            cwd=str(fixture_repo),
            capture_output=True,
            text=True,
        )
        self.assertEqual(fast_proc.returncode, 0)
        self.assertIn("FAST CHECKS SUCCESSFUL", fast_proc.stdout)

        # Execute extracted full validation step
        full_proc = subprocess.run(
            ["sh", "-c", full_cmd],
            cwd=str(fixture_repo),
            capture_output=True,
            text=True,
        )
        self.assertEqual(full_proc.returncode, 0)
        self.assertIn("FULL VALIDATION SUCCESSFUL", full_proc.stdout)

        # Execute extracted device checks step
        device_proc = subprocess.run(
            ["sh", "-c", device_cmd],
            cwd=str(fixture_repo),
            capture_output=True,
            text=True,
        )
        self.assertEqual(device_proc.returncode, 0)
        self.assertIn("DEVICE CHECKS SUCCESSFUL", device_proc.stdout)


class AndroidB2HubAndValidationSkillTests(unittest.TestCase):
    def test_b2_ac1_hub_byte_budget_with_and_without_screenshots(self):
        # Without screenshots
        files_no_shots = bootstrap.generate_files({
            "name": "sample-android",
            "repo_type": "android",
            "postgres": False,
            "scheme": "",
            "destination": "",
            "screenshots": False,
        })
        hub_no = files_no_shots["AGENTS.md"]
        size_no = len(validate_templates._hub_generated_part(hub_no).encode())
        self.assertLessEqual(size_no, validate_templates.HUB_BUDGET_BYTES)
        budget_errors_no = validate_templates.check_hub_budget("android-no-shots", files_no_shots)
        self.assertEqual(budget_errors_no, [])

        # With screenshots
        files_shots = bootstrap.generate_files({
            "name": "sample-android",
            "repo_type": "android",
            "postgres": False,
            "scheme": "",
            "destination": "",
            "screenshots": True,
        })
        hub_shots = files_shots["AGENTS.md"]
        size_shots = len(validate_templates._hub_generated_part(hub_shots).encode())
        self.assertLessEqual(size_shots, validate_templates.HUB_BUDGET_BYTES)
        budget_errors_shots = validate_templates.check_hub_budget("android-shots", files_shots)
        self.assertEqual(budget_errors_shots, [])

    def test_b2_ac1_local_validation_android_skill_content_and_guidance(self):
        files = _render_android("sample-android")
        skill_path = ".agents/skills/local-validation-android/SKILL.md"
        self.assertIn(skill_path, files)
        content = files[skill_path]

        # Valid frontmatter
        data, err = validate_templates._frontmatter(content)
        self.assertIsNone(err)
        self.assertEqual(data["name"], "local-validation-android")
        self.assertTrue(data["description"])

        # Tooling commands covered
        for cmd in ("spotlessCheck", "lintDebug", "test", "check", "connectedCheck"):
            self.assertIn(cmd, content)

        # CI tiers covered
        self.assertIn("CI validation tiers", content)
        self.assertIn("fast checks", content)
        self.assertIn("full validation", content)
        self.assertIn("device checks", content)

        # Safeguards covered: lifecycle, cancellation, state, persistence, permissions, API 35–37
        for topic in (
            "Lifecycle and state",
            "Structured concurrency and cancellation",
            "Persistence and storage",
            "Runtime permissions and privacy",
            "API 35–37 verification",
        ):
            self.assertIn(topic, content)

        # Compose Preview workaround under AGP 9.5.1
        self.assertIn("android.onlyEnableUnitTestForTheTestedBuildType=false", content)
        self.assertIn("testOptions.unitTests.isIncludeAndroidResources = true", content)
        self.assertIn("AGP 9.5.1", content)

        # Symlink mirror for Claude Code
        cfg = {
            "name": "sample-android",
            "repo_type": "android",
            "postgres": False,
            "scheme": "",
            "destination": "",
            "screenshots": False,
        }
        links = bootstrap.generate_links(cfg)
        self.assertIn(".claude/skills/local-validation-android", links)
        self.assertEqual(
            links[".claude/skills/local-validation-android"],
            "../../.agents/skills/local-validation-android",
        )

    def test_b2_ac1_review_guidelines_stack_section_coverage(self):
        files = _render_android("sample-android")
        review_skill = files[".agents/skills/review-guidelines/SKILL.md"]
        self.assertIn("### Android", review_skill)
        for req in (
            "Lifecycle and state",
            "Concurrency",
            "cancellation",
            "Persistence and storage",
            "KeyStore",
            "Permissions and privacy",
            "Compatibility and API verification",
            "API 35, 36",
            "37 targets",
        ):
            self.assertIn(req, review_skill)


class AndroidB2WorkflowRoutingContractTests(unittest.TestCase):
    def test_b2_ac2_routing_structure_and_gate_conditions(self):
        files = _render_android("sample-android")
        test_yml = yaml.safe_load(files[".github/workflows/test.yml"])
        steps = test_yml["jobs"]["test"]["steps"]

        # Wrapper guard: unconditional and blocking
        wrapper_step = next(s for s in steps if s.get("name") == "Require an executable Gradle wrapper")
        self.assertNotIn("if", wrapper_step)
        self.assertFalse(wrapper_step.get("continue-on-error", False))

        # Setup Java: unconditional and blocking
        java_step = next(s for s in steps if str(s.get("uses", "")).startswith("actions/setup-java@"))
        self.assertNotIn("if", java_step)
        self.assertFalse(java_step.get("continue-on-error", False))

        # Fast checks: runs on !inputs.full
        fast_step = next(s for s in steps if s.get("name") == "Run fast checks")
        self.assertEqual(fast_step["run"], "./gradlew spotlessCheck lintDebug testDebugUnitTest")
        self.assertEqual(fast_step["if"], "${{ !inputs.full }}")
        self.assertFalse(fast_step.get("continue-on-error", False))

        # Full validation: runs on inputs.full
        full_step = next(s for s in steps if s.get("name") == "Run full validation")
        self.assertEqual(full_step["run"], "./gradlew check")
        self.assertEqual(full_step["if"], "${{ inputs.full }}")
        self.assertFalse(full_step.get("continue-on-error", False))

        # Device checks: runs on inputs.device
        device_step = next(s for s in steps if s.get("name") == "Run device checks")
        self.assertEqual(device_step["run"], "./gradlew connectedCheck")
        self.assertEqual(device_step["if"], "${{ inputs.device }}")
        self.assertFalse(device_step.get("continue-on-error", False))

        # Caller contracts
        ci_yml = yaml.safe_load(files[".github/workflows/ci.yml"])
        self.assertEqual(ci_yml["jobs"]["test"]["with"]["full"], False)

        rp_yml = yaml.safe_load(files[".github/workflows/release-please.yml"])
        self.assertEqual(
            rp_yml["jobs"]["test"]["with"]["full"],
            validate_templates.RELEASE_FULL_SUITE_EXPRESSION,
        )
        self.assertEqual(rp_yml["jobs"]["release-please"]["needs"], "test")

        # Required status check context
        self.assertEqual(
            bootstrap.required_status_checks("android"),
            ["validate-title", "test / test"],
        )

    def test_b2_ac2_negative_workflow_routing_contract_failures(self):
        # 1. Dropping condition on fast checks step fails check_workflow_gates
        files1 = _render_android("sample-android")
        test1 = yaml.safe_load(files1[".github/workflows/test.yml"])
        fast = next(s for s in test1["jobs"]["test"]["steps"] if "spotlessCheck" in str(s.get("run", "")))
        del fast["if"]
        files1[".github/workflows/test.yml"] = yaml.safe_dump(test1)
        errs1 = validate_templates.check_workflow_gates("test", "android", files1)
        self.assertTrue(any("must be gated on !inputs.full" in e for e in errs1))

        # 2. Dropping condition on full validation step fails check_workflow_gates
        files2 = _render_android("sample-android")
        test2 = yaml.safe_load(files2[".github/workflows/test.yml"])
        full = next(s for s in test2["jobs"]["test"]["steps"] if s.get("run") == "./gradlew check")
        del full["if"]
        files2[".github/workflows/test.yml"] = yaml.safe_dump(test2)
        errs2 = validate_templates.check_workflow_gates("test", "android", files2)
        self.assertTrue(any("must be gated on inputs.full" in e for e in errs2))

        # 3. Dropping condition on device checks step fails check_workflow_gates
        files3 = _render_android("sample-android")
        test3 = yaml.safe_load(files3[".github/workflows/test.yml"])
        dev = next(s for s in test3["jobs"]["test"]["steps"] if "connectedCheck" in str(s.get("run", "")))
        del dev["if"]
        files3[".github/workflows/test.yml"] = yaml.safe_dump(test3)
        errs3 = validate_templates.check_workflow_gates("test", "android", files3)
        self.assertTrue(any("must be gated on inputs.device" in e for e in errs3))

        # 4. Inverting fast check condition fails check_workflow_gates
        files4 = _render_android("sample-android")
        test4 = yaml.safe_load(files4[".github/workflows/test.yml"])
        fast4 = next(s for s in test4["jobs"]["test"]["steps"] if "spotlessCheck" in str(s.get("run", "")))
        fast4["if"] = "${{ inputs.full }}"
        files4[".github/workflows/test.yml"] = yaml.safe_dump(test4)
        errs4 = validate_templates.check_workflow_gates("test", "android", files4)
        self.assertTrue(any("must be gated on !inputs.full" in e for e in errs4))

        # 5. Making wrapper guard conditional fails check_workflow_gates
        files5 = _render_android("sample-android")
        test5 = yaml.safe_load(files5[".github/workflows/test.yml"])
        wrap = next(s for s in test5["jobs"]["test"]["steps"] if s.get("name") == "Require an executable Gradle wrapper")
        wrap["if"] = "${{ inputs.full }}"
        files5[".github/workflows/test.yml"] = yaml.safe_dump(test5)
        errs5 = validate_templates.check_workflow_gates("test", "android", files5)
        self.assertTrue(any("must be unconditional and blocking" in e for e in errs5))

        # 6. Altering release full suite expression fails check_release_full_suite_contract
        files6 = _render_android("sample-android")
        rp6 = yaml.safe_load(files6[".github/workflows/release-please.yml"])
        rp6["jobs"]["test"]["with"]["full"] = False
        files6[".github/workflows/release-please.yml"] = yaml.safe_dump(rp6)
        errs6 = validate_templates.check_release_full_suite_contract("test", "android", files6)
        self.assertTrue(any("must be" in e for e in errs6))

        # 7. Dropping needs: test on release-please fails check_workflow_gates
        files7 = _render_android("sample-android")
        rp7 = yaml.safe_load(files7[".github/workflows/release-please.yml"])
        del rp7["jobs"]["release-please"]["needs"]
        files7[".github/workflows/release-please.yml"] = yaml.safe_dump(rp7)
        errs7 = validate_templates.check_workflow_gates("test", "android", files7)
        self.assertTrue(any("must need 'test'" in e for e in errs7))


class AndroidB2ScreenshotOptionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_b2_ac3_generation_with_screenshots(self):
        cfg = {
            "name": "shot-android",
            "repo_type": "android",
            "postgres": False,
            "scheme": "",
            "destination": "",
            "screenshots": True,
        }
        files = bootstrap.generate_files(cfg)

        # docs/screenshot-review.md is generated
        self.assertIn("docs/screenshot-review.md", files)
        doc = files["docs/screenshot-review.md"]
        self.assertIn("## Android projects", doc)
        self.assertIn("Formatter:", doc)
        self.assertIn("Emulator selection:", doc)
        self.assertIn("Fixture isolation:", doc)
        self.assertIn("Artifact-review boundaries:", doc)

        # screenshot-review skill is generated
        skill_path = ".agents/skills/screenshot-review/SKILL.md"
        self.assertIn(skill_path, files)

        # Symlink mirror is generated
        links = bootstrap.generate_links(cfg)
        self.assertIn(".claude/skills/screenshot-review", links)

        # AGENTS.md points to screenshot-review skill
        agents = files["AGENTS.md"]
        self.assertIn("| change screenshots or captured views | `screenshot-review` |", agents)
        self.assertIn("Load `screenshot-review` for the full process.", agents)

    def test_b2_ac3_generation_without_screenshots(self):
        cfg = {
            "name": "noshot-android",
            "repo_type": "android",
            "postgres": False,
            "scheme": "",
            "destination": "",
            "screenshots": False,
        }
        files = bootstrap.generate_files(cfg)
        self.assertNotIn("docs/screenshot-review.md", files)
        self.assertNotIn(".agents/skills/screenshot-review/SKILL.md", files)
        links = bootstrap.generate_links(cfg)
        self.assertNotIn(".claude/skills/screenshot-review", links)
        agents = files["AGENTS.md"]
        self.assertNotIn("`screenshot-review`", agents)

    def test_b2_ac3_dry_run_with_screenshots(self):
        cfg = {
            "name": "dry-android",
            "repo_dir": self.root / "dry-repo",
            "repo_type": "android",
            "owner": "test-owner",
            "private": True,
            "postgres": False,
            "scheme": "",
            "destination": "",
            "screenshots": True,
        }
        files = bootstrap.generate_files(cfg)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            bootstrap.print_dry_run(cfg, files)
        output = out.getvalue()
        self.assertIn("Screenshot review: True", output)
        self.assertIn("docs/screenshot-review.md", output)
        self.assertIn(".agents/skills/screenshot-review/SKILL.md", output)

    def test_b2_ac3_adoption_with_screenshots(self):
        repo_dir = self.root / "adopt-shots-repo"
        repo_dir.mkdir()
        _git(repo_dir, "init", "-q")
        _git(repo_dir, "config", "user.name", "Test User")
        _git(repo_dir, "config", "user.email", "user@example.com")

        # Initial commit
        (repo_dir / "build.gradle.kts").write_text("// App build\n", encoding="utf-8")
        _git(repo_dir, "add", "-A")
        _git(repo_dir, "commit", "-q", "-m", "Initial")

        cfg = {
            "name": "adopt-shots-repo",
            "repo_dir": repo_dir,
            "repo_type": "android",
            "owner": "test-owner",
            "private": True,
            "postgres": False,
            "scheme": "",
            "destination": "",
            "screenshots": True,
        }
        files = bootstrap.generate_files(cfg)
        actions = bootstrap.adopt_repository(repo_dir, files)

        self.assertTrue((repo_dir / "docs" / "screenshot-review.md").is_file())
        self.assertTrue((repo_dir / ".agents" / "skills" / "screenshot-review" / "SKILL.md").is_file())
        self.assertTrue((repo_dir / ".agents" / "skills" / "local-validation-android" / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
