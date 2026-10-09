"""validate_templates.main() must keep running every check it was built with."""

import contextlib
import inspect
import io
import re
import unittest
from unittest.mock import patch

import validate_templates

# Every check main() calls, listed by hand: a list derived from main() would
# shrink along with it, and a dropped call leaves the validator printing OK.
CHECKS = (
    "run_self_tests",
    "check_npm_script_assumptions",
    "check_syntax",
    "check_nextjs_provider_free",
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
    "check_reusable_workflow_inputs",
    "check_release_full_suite_contract",
    "check_rust_suite",
    "check_release_please_config",
    "check_baseline_documents",
    "check_readme",
    "check_branch_protection_payload",
    "check_runbook",
    "check_runbook_copy_matches_template",
    "check_legacy_digests",
)
RUN_ONCE = {
    "run_self_tests", "check_npm_script_assumptions",
    "check_runbook_copy_matches_template", "check_legacy_digests",
}
OWN_WORKFLOWS = "bootstrapper own workflows"
ALSO_ON_OWN_WORKFLOWS = {"check_sha_pinned_actions", "check_workflow_gates"}
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


if __name__ == "__main__":
    unittest.main()
