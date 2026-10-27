"""The own-workflow checks skip gh-agent-kit's workflows, and only those its lock lists."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import validate_templates

KIT_WORKFLOW = """name: kit
on: pull_request
permissions: {}
jobs:
  review:
    runs-on: ubuntu-latest
    # The kit reads its secrets from the settings job.
    timeout-minutes: ${{ fromJSON(needs.settings.outputs.timeout) }}
    steps:
      - run: echo kit
"""
OWN_WORKFLOW = KIT_WORKFLOW.replace("name: kit", "name: own")


class KitWorkflowTests(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        workflows = root / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "pr-review.yml").write_text(KIT_WORKFLOW)
        (workflows / "own.yml").write_text(OWN_WORKFLOW)
        self.lock = root / ".github" / "gh-agent-kit.lock"
        self.enterContext(patch.object(validate_templates, "OWN_WORKFLOWS_DIR", workflows))
        self.enterContext(patch.object(validate_templates, "KIT_LOCK_PATH", self.lock))

    def write_lock(self, **fields):
        lock = {
            "source": validate_templates.KIT_SOURCE,
            "seeds": [".github/security-review-instructions.md"],
            "paths": [".github/workflows/pr-review.yml", ".github/security-review-instructions.md"],
        }
        lock.update(fields)
        self.lock.write_text(json.dumps(lock))

    def own_errors(self):
        files = validate_templates._own_workflow_files()
        return (
            validate_templates.check_workflow_gates("own", "simple", files)
            + validate_templates.check_secrets_word("own", files)
        )

    def test_a_listed_workflow_is_skipped(self):
        self.write_lock()
        self.assertEqual(set(validate_templates._own_workflow_files()), {".github/workflows/own.yml"})
        errors = self.own_errors()
        self.assertTrue(errors)
        self.assertFalse([e for e in errors if "pr-review.yml" in e], errors)

    def test_the_pinned_action_check_still_reads_the_kit(self):
        self.write_lock()
        files = validate_templates._own_workflow_files(include_kit=True)
        self.assertEqual(set(files), {".github/workflows/own.yml", ".github/workflows/pr-review.yml"})

    def test_without_a_usable_lock_nothing_is_skipped(self):
        cases = {
            "absent": None,
            "not JSON": "{",
            "not an object": "[]",
            "another source": {"source": "github.com/example/other-kit"},
            "paths not a list": {"paths": ".github/workflows/pr-review.yml"},
            "a path not a string": {"paths": [1]},
        }
        for case, value in cases.items():
            with self.subTest(case=case):
                self.lock.unlink(missing_ok=True)
                if isinstance(value, str):
                    self.lock.write_text(value)
                elif value is not None:
                    self.write_lock(**value)
                self.assertIn(".github/workflows/pr-review.yml", validate_templates._own_workflow_files())
                self.assertTrue([e for e in self.own_errors() if "pr-review.yml" in e])

    def test_a_seed_is_checked_as_this_repository_own(self):
        self.write_lock(seeds=[".github/workflows/pr-review.yml"])
        self.assertIn(".github/workflows/pr-review.yml", validate_templates._own_workflow_files())


if __name__ == "__main__":
    unittest.main()
