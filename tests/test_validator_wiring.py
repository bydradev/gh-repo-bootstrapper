"""validate_templates.main() must keep running every check it was built with."""

import contextlib
import io
import unittest
from unittest.mock import patch

import validate_templates

# Every check main() calls. Removing a call from main() leaves the validator
# printing OK, so each name here must still reach the output when it fails.
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
# Called once per rendered configuration; "python" is one configuration's label.
PER_CONFIGURATION = set(CHECKS) - {
    "run_self_tests", "check_npm_script_assumptions",
    "check_runbook_copy_matches_template", "check_legacy_digests",
}


class ValidatorWiringTests(unittest.TestCase):
    def _main(self, failing=None, fixtures_run=1):
        with contextlib.ExitStack() as stack:
            for name in CHECKS:
                def fake(*args, _name=name, **kwargs):
                    label = args[0] if args and isinstance(args[0], str) else ""
                    return [f"SENTINEL {_name} [{label}]"] if _name == failing else []
                stack.enter_context(patch.object(validate_templates, name, side_effect=fake))
            stack.enter_context(patch.object(validate_templates, "STRUCTURE_FIXTURES_RUN", [fixtures_run]))
            out = io.StringIO()
            stack.enter_context(contextlib.redirect_stdout(out))
            code = validate_templates.main()
        return code, out.getvalue()

    def test_every_check_can_fail_the_run(self):
        code, out = self._main()
        self.assertEqual(code, 0, out)
        for name in CHECKS:
            with self.subTest(check=name):
                code, out = self._main(failing=name)
                self.assertEqual(code, 1, out)
                self.assertIn(f"SENTINEL {name}", out)
                if name in PER_CONFIGURATION:
                    self.assertIn(f"SENTINEL {name} [python]", out)

    def test_a_run_without_self_test_fixtures_fails(self):
        code, out = self._main(fixtures_run=0)
        self.assertEqual(code, 1)
        self.assertIn("no hub/skill/stamp self-test fixture ran", out)


if __name__ == "__main__":
    unittest.main()
