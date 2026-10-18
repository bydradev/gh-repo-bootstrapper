"""validate_templates.main() must keep running every check it was built with."""

import contextlib
import inspect
import io
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import validate_templates

# Every check main() calls, listed by hand: a list derived from main() would
# shrink along with it, and a dropped call leaves the validator printing OK.
CHECKS = (
    "run_self_tests",
    "check_npm_script_assumptions",
    "check_syntax",
    "check_nextjs_provider_free",
    "check_retired_lane_phrases",
    "check_markers",
    "check_markdown_blank_lines",
    "check_agents_guidance",
    "check_hub_budget",
    "check_no_at_imports",
    "check_skill_pointers",
    "check_skill_frontmatter",
    "check_markdown_links",
    "check_template_stamps",
    "check_reviewer_agents",
    "check_workspace_guidance",
    "check_screenshot_guidance",
    "check_workflow_job_consistency",
    "check_workflow_permissions",
    "check_sha_pinned_actions",
    "check_workflow_gates",
    "check_secrets_word",
    "check_release_step_names",
    "check_reusable_workflow_inputs",
    "check_release_full_suite_contract",
    "check_rust_suite",
    "check_release_please_config",
    "check_baseline_documents",
    "check_dependabot_cooldown",
    "check_readme",
    "check_branch_protection_payload",
    "check_runbook",
    "check_runbook_copy_matches_template",
    "check_own_template_copies",
    "check_legacy_digests",
    "check_bug_form",
)
RUN_ONCE = {
    "run_self_tests", "check_npm_script_assumptions",
    "check_runbook_copy_matches_template", "check_own_template_copies", "check_legacy_digests",
    "check_bug_form",
}
OWN_WORKFLOWS = "bootstrapper own workflows"
ALSO_ON_OWN_WORKFLOWS = {"check_sha_pinned_actions", "check_workflow_gates", "check_secrets_word"}
LABELS = [label for label, _ in validate_templates.configurations()]


class ValidatorWiringTests(unittest.TestCase):
    def _main(self, failing=None, fixtures_per_run=1):
        with contextlib.ExitStack() as stack:
            for name in CHECKS:
                def fake(*args, _name=name, **kwargs):
                    if _name == "run_self_tests":
                        validate_templates.STRUCTURE_FIXTURES_RUN[0] += fixtures_per_run
                    label = args[0] if args and isinstance(args[0], str) else ""
                    return [f"SENTINEL {_name} [{label}]"] if _name == failing else []
                stack.enter_context(patch.object(validate_templates, name, side_effect=fake))
            out = io.StringIO()
            stack.enter_context(contextlib.redirect_stdout(out))
            code = validate_templates.main()
        return code, out.getvalue()

    def test_the_inventory_lists_every_check_main_calls(self):
        called = set(re.findall(r"\b((?:check|run)_\w+)\(", inspect.getsource(validate_templates.main)))
        self.assertEqual(called, set(CHECKS))

    def test_every_check_can_fail_the_run(self):
        code, out = self._main()
        self.assertEqual(code, 0, out)
        for name in CHECKS:
            with self.subTest(check=name):
                code, out = self._main(failing=name)
                self.assertEqual(code, 1, out)
                self.assertIn(f"SENTINEL {name}", out)
                if name not in RUN_ONCE:
                    for label in LABELS:
                        self.assertIn(f"SENTINEL {name} [{label}]", out)
                if name in ALSO_ON_OWN_WORKFLOWS:
                    self.assertIn(f"SENTINEL {name} [{OWN_WORKFLOWS}]", out)

    def test_protection_contexts_are_pinned_independently(self):
        reduced = lambda repo_type: ["validate-title", "test / build"]
        with patch.object(validate_templates.bootstrap, "required_status_checks", side_effect=reduced):
            errors = validate_templates.check_branch_protection_payload("probe", "nextjs")
        self.assertTrue(any("do not match" in error for error in errors), errors)

    def test_rewrapped_runbook_passes_the_whole_validator(self):
        original = validate_templates.bootstrap.generate_files
        path = validate_templates.BRANCH_PROTECTION_RUNBOOK

        def rewrapped(cfg):
            files = original(cfg)
            body = validate_templates.bootstrap.read_stamp(files[path])[1]
            for phrase in validate_templates.RUNBOOK_REQUIRED_PHRASES:
                body = body.replace(phrase, phrase.replace(" ", "\n"))
            # A real template rewrap is re-stamped, so the stamp check still holds.
            files[path] = validate_templates.bootstrap.stamp(body)
            return files

        out = io.StringIO()
        with patch.object(validate_templates.bootstrap, "generate_files", side_effect=rewrapped), \
                contextlib.redirect_stdout(out):
            code = validate_templates.main()
        self.assertEqual(code, 0, out.getvalue())

    def test_invalid_yaml_is_reported_without_crashing(self):
        original = validate_templates.bootstrap.generate_files

        def broken(cfg):
            files = original(cfg)
            if cfg["repo_type"] == "python":
                files[".github/workflows/test.yml"] = "jobs: [\n"
            return files

        out = io.StringIO()
        # The real self-tests run too: they parse renders before any check does.
        with patch.object(validate_templates.bootstrap, "generate_files", side_effect=broken), \
                contextlib.redirect_stdout(out):
            code = validate_templates.main()
        self.assertEqual(code, 1)
        syntax = [line for line in out.getvalue().splitlines() if "[python]" in line]
        self.assertTrue(syntax and all("test.yml" in line for line in syntax), out.getvalue())

    def test_a_run_without_self_test_fixtures_fails_every_time(self):
        self.assertEqual(self._main()[0], 0)
        for _ in range(2):
            code, out = self._main(fixtures_per_run=0)
            self.assertEqual(code, 1)
            self.assertIn("no hub/skill/stamp self-test fixture ran", out)


class OwnTemplateCopyTests(unittest.TestCase):
    # Listed by hand, like CHECKS: lists derived from the check's own
    # constants would shrink along with them.
    COVERED = (
        "AGENTS.md", "CLAUDE.md", ".agents/skills/x/SKILL.md", ".claude/skills/x",
        ".claude/agents/x.md", ".opencode/agents/x.md",
    )
    FAILING = (
        "stale", "local-modified", "missing", "differs", "orphaned", "dangling", "other-type",
        "shadowed", "symlink", "ignored", "unreadable",
    )

    def _check(self, report):
        with patch.object(validate_templates.bootstrap, "compare_repository", return_value=report), \
                tempfile.TemporaryDirectory() as tmp:
            return validate_templates.check_own_template_copies("t", Path(tmp))

    def test_main_checks_the_validator_s_own_directory(self):
        roots = []

        def record(label, repo_dir):
            if label == "bootstrapper self":  # not the self-tests' temporary copies
                roots.append(Path(repo_dir).resolve())
            return []
        # From another directory, so a path relative to the working directory fails.
        with tempfile.TemporaryDirectory() as tmp, contextlib.chdir(tmp), \
                patch.object(validate_templates, "check_own_template_copies", side_effect=record), \
                contextlib.redirect_stdout(io.StringIO()):
            validate_templates.main()
        self.assertEqual(roots, [Path(validate_templates.__file__).resolve().parent])

    def test_every_status_but_same_fails_in_every_covered_path(self):
        for rel in self.COVERED:
            self.assertEqual(self._check({rel: ("same", None)}), [], rel)
            for status in self.FAILING:
                with self.subTest(rel=rel, status=status):
                    errors = self._check({rel: (status, None)})
                    self.assertEqual(len(errors), 1, errors)
                    self.assertIn(f"{rel} does not match this repository's `--type simple` render: {status}", errors[0])

    def test_files_outside_the_agent_files_are_not_checked(self):
        for rel in ("README.md", ".github/workflows/pr-title-check.yml", "docs/current-work.md", "(--type)"):
            self.assertEqual(self._check({rel: ("local-modified", None)}), [], rel)

    def test_a_bare_shadowed_skill_says_how_to_restore_it(self):
        errors = self._check({".agents/skills/x/SKILL.md": ("shadowed", None)})
        self.assertIn("shadowed, an unstamped file at a template skill's path; move any change", errors[0])
        self.assertIn("then delete it and run `./bootstrap.py --adopt . --type simple --non-interactive`", errors[0])
        detailed = self._check({".agents/skills/x/SKILL.md": ("shadowed", "frontmatter name collides")})
        self.assertTrue(detailed[0].endswith("shadowed, frontmatter name collides"), detailed)


class StalePinTests(unittest.TestCase):
    TEMPLATES = {
        "test.yml": "steps:\n  # Pinned fallbacks (PyPI, 2026-01-01), so the suite holds\n",
        "other.yml": "# pinned to the same framework version, no date here\n",
    }

    def test_a_pin_inside_the_age_limit_is_quiet(self):
        today = validate_templates.datetime.date(2026, 3, 31)
        self.assertEqual(validate_templates.stale_pin_warnings(self.TEMPLATES, today), [])

    def test_an_old_pin_names_its_file_line_and_source(self):
        today = validate_templates.datetime.date(2026, 4, 2)
        warnings = validate_templates.stale_pin_warnings(self.TEMPLATES, today)
        self.assertEqual(len(warnings), 1)
        self.assertIn("templates/test.yml:2", warnings[0])
        self.assertIn("PyPI on 2026-01-01 (91 days ago)", warnings[0])

    def test_an_impossible_date_is_reported_instead_of_crashing(self):
        templates = {"t.yml": "# Pinned (PyPI, 2026-02-30)\n"}
        self.assertIn("not a valid date", validate_templates.stale_pin_warnings(templates)[0])

    def test_a_future_date_is_reported_instead_of_hiding_the_pin(self):
        today = validate_templates.datetime.date(2026, 1, 1)
        templates = {"t.yml": "# Pinned (PyPI, 2096-10-15)\n"}
        self.assertIn("in the future", validate_templates.stale_pin_warnings(templates, today)[0])

    def test_the_shipped_templates_carry_dated_pins(self):
        # An empty match set would make the warning silently useless.
        far_future = validate_templates.datetime.date(2100, 1, 1)
        warnings = validate_templates.stale_pin_warnings(today=far_future)
        for name in ("test-python.yml", "test-swift-xcodegen.yml"):
            self.assertTrue(any(f"templates/{name}:" in w for w in warnings), warnings)

    def test_a_stale_pin_warns_without_failing_the_run(self):
        out = io.StringIO()
        # Outside GitHub Actions, even when this suite itself runs there.
        with patch.object(validate_templates, "stale_pin_warnings", return_value=["templates/x.yml:1: old"]), \
                patch.dict(validate_templates.os.environ, {"GITHUB_ACTIONS": "false"}), \
                contextlib.redirect_stdout(out):
            code = validate_templates.main()
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("WARNING: templates/x.yml:1: old", out.getvalue())
        self.assertNotIn("::warning", out.getvalue())

    def test_a_stale_pin_is_annotated_in_github_actions(self):
        out = io.StringIO()
        with patch.object(validate_templates, "stale_pin_warnings", return_value=["templates/x.yml:12: old 50%"]), \
                patch.dict(validate_templates.os.environ, {"GITHUB_ACTIONS": "true"}), \
                contextlib.redirect_stdout(out):
            code = validate_templates.main()
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("::warning file=templates/x.yml,line=12::old 50%25\n", out.getvalue())

    def test_annotation_values_are_escaped(self):
        warn = validate_templates.github_warning
        self.assertEqual(warn("templates/a,b.yml:3: x"), "::warning file=templates/a%2Cb.yml,line=3::x")
        self.assertEqual(warn("no location 5%\nhere"), "::warning::no location 5%25%0Ahere")


class ReleaseQueueTests(unittest.TestCase):
    def _files(self, concurrency):
        body = validate_templates.yaml.safe_dump(
            {"on": {"push": {"branches": ["main"]}}, "concurrency": concurrency, "jobs": {}}
        )
        return {".github/workflows/release-please.yml": body}

    def test_the_release_group_must_keep_every_pending_run(self):
        queued = {"group": "release-please", "cancel-in-progress": False, "queue": "max"}
        self.assertEqual(validate_templates._workflow_hardening("t", self._files(queued)), [])
        for missing in ({**queued, "queue": "single"}, {k: v for k, v in queued.items() if k != "queue"}):
            errors = validate_templates._workflow_hardening("t", self._files(missing))
            self.assertEqual(len(errors), 1, (missing, errors))
            self.assertIn("queue: max", errors[0])

    def test_dropping_the_concurrency_block_fails(self):
        body = validate_templates.yaml.safe_dump({"on": {"push": {"branches": ["main"]}}, "jobs": {}})
        files = {".github/workflows/release-please.yml": body}
        errors = validate_templates._workflow_hardening("t", files)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("queue: max", errors[0])


class SecretsWordTests(unittest.TestCase):
    PATH = ".github/workflows/release-please.yml"

    def _check(self, body, path=PATH):
        return validate_templates.check_secrets_word("t", {path: body})

    def test_static_references_and_mapping_keys_pass(self):
        body = (
            "jobs:\n"
            "  test:\n"
            "    uses: ./.github/workflows/test.yml\n"
            "    secrets:\n"
            "      APP_KEY: ${{ secrets.RELEASE_PLEASE_APP_KEY }}\n"
            "  release:\n"
            "    steps:\n"
            "      # A secret cannot be read in an `if:`; Secrets.GITHUB_TOKEN is static.\n"
            "      - env:\n"
            "          HAS_APP_KEY: ${{ secrets.RELEASE_PLEASE_APP_KEY != '' }}\n"
            "          TOKEN: ${{secrets.GITHUB_TOKEN}}\n"
            "          NOTE: secretsless, mysecrets and secrets_store are other words\n"
        )
        self.assertEqual(self._check(body), [])

    def test_the_word_anywhere_else_fails_with_its_line(self):
        for line in (
            '# Source: "Using secrets in GitHub Actions"',
            "# https://docs.github.com/en/actions/how-tos/use-secrets",
            "# SECRETS are set in the settings",
            "ALL: ${{ toJSON(secrets) }}",
            "KEY: ${{ secrets['RELEASE_PLEASE_APP_KEY'] }}",
            "KEY: ${{ secrets . RELEASE_PLEASE_APP_KEY }}",
            "secrets: inherit",
            "secrets:\nAPP_KEY: x",
        ):
            with self.subTest(line):
                errors = self._check("name: release-please\n" + line + "\n")
                self.assertEqual(len(errors), 1, errors)
                self.assertIn(f"{self.PATH}:2 uses the word", errors[0])

    def test_only_workflows_are_checked(self):
        self.assertEqual(self._check("# Using secrets\n", path="docs/notes.yml"), [])
        self.assertEqual(len(self._check("# Using secrets\n", path=".github/workflows/ci.yaml")), 1)

    def test_the_shipped_release_workflows_pass(self):
        for template in ("release-please-gated.yml", "release-please-nextjs.yml", "release-please-simple.yml"):
            with self.subTest(template):
                text = (Path(validate_templates.__file__).parent / "templates" / template).read_text()
                self.assertEqual(self._check(text), [])



class ReleaseStepNameTests(unittest.TestCase):
    SCRIPT = (
        'const releaseCredentialsStep = "Check Release Please credentials";\n'
        'const releaseTokenStep = "Generate GitHub App token";\n'
    )
    WORKFLOW = (
        "jobs:\n"
        "  release-please:\n"
        "    steps:\n"
        "      - name: Check Release Please credentials\n"
        "        id: credentials\n"
        "      - name: Generate GitHub App token\n"
        "        id: app-token\n"
    )

    def _check(self, script=SCRIPT, workflow=WORKFLOW):
        files = {".github/workflows/release-please.yml": workflow}
        if script is not None:
            files["scripts/review-baselines.mjs"] = script
        return validate_templates.check_release_step_names("t", files)

    def test_matching_names_pass_and_repos_without_the_review_are_skipped(self):
        self.assertEqual(self._check(), [])
        self.assertEqual(self._check(script=None, workflow="jobs: {}\n"), [])

    def test_a_name_changed_on_one_side_fails(self):
        for script, workflow, needle in (
            (self.SCRIPT, self.WORKFLOW.replace("Check Release Please credentials", "Check credentials"),
             "step id 'credentials' is named ['Check credentials']"),
            (self.SCRIPT.replace("Generate GitHub App token", "Mint token"), self.WORKFLOW,
             "reads it as 'Mint token'"),
            (self.SCRIPT, self.WORKFLOW.replace("id: app-token", "id: token"), "'app-token' is named nowhere"),
            (self.SCRIPT, self.WORKFLOW + "      - name: Generate GitHub App token\n        id: app-token\n",
             "is named ['Generate GitHub App token', 'Generate GitHub App token']"),
            (self.SCRIPT.replace("const releaseTokenStep", "let releaseTokenStep"), self.WORKFLOW,
             "no longer defines releaseTokenStep"),
            (self.SCRIPT, "jobs: [\n", "'credentials' is named nowhere"),
        ):
            with self.subTest(needle):
                errors = self._check(script, workflow)
                self.assertTrue(any(needle in error for error in errors), errors)

    def test_the_shipped_templates_agree(self):
        root = Path(validate_templates.__file__).parent / "templates"
        self.assertEqual(
            self._check(
                (root / "review-baselines.mjs").read_text(), (root / "release-please-nextjs.yml").read_text()
            ),
            [],
        )

class DependabotCooldownTests(unittest.TestCase):
    def test_every_update_entry_needs_a_cooldown(self):
        good = "version: 2\nupdates:\n  - package-ecosystem: pip\n    cooldown:\n      default-days: 7\n"
        bad = good + "  - package-ecosystem: github-actions\n    directory: /\n"
        check = validate_templates.check_dependabot_cooldown
        self.assertEqual(check("t", {".github/dependabot.yml": good}), [])
        errors = check("t", {".github/dependabot.yml": bad})
        self.assertEqual(len(errors), 1)
        self.assertIn("github-actions", errors[0])
        self.assertTrue(check("t", {}))
        for days in ("0", "91", "true", "seven"):
            body = good.replace("default-days: 7", f"default-days: {days}")
            self.assertEqual(len(check("t", {".github/dependabot.yml": body})), 1, days)

    def test_a_cooldown_cannot_be_switched_off_or_use_unsupported_keys(self):
        check = validate_templates.check_dependabot_cooldown

        def entry(ecosystem, extra):
            return {".github/dependabot.yml": f"version: 2\nupdates:\n  - package-ecosystem: {ecosystem}\n"
                    f"    cooldown:\n      default-days: 7\n{extra}"}
        self.assertEqual(check("t", entry("npm", "      exclude: ['@types/*']\n      semver-major-days: 30\n")), [])
        for ecosystem, extra in (
            ("npm", "      exclude: ['*']\n"),
            ("npm", "      exclude: ['**']\n"),
            ("npm", "      exclude: '*'\n"),
            ("npm", "      exclude: ''\n"),
            ("github-actions", "      exclude: ['*/*']\n"),
            ("npm", "      include: ['left-pad']\n"),
            ("github-actions", "      semver-major-days: 30\n"),
        ):
            with self.subTest(extra):
                self.assertEqual(len(check("t", entry(ecosystem, extra))), 1)


if __name__ == "__main__":
    unittest.main()
