"""Tests for the generated-Markdown checks in validate_templates.py."""

import tempfile
import unittest
from pathlib import Path

import validate_templates


class MarkdownBlankLinesTest(unittest.TestCase):
    def test_every_configuration_is_free_of_blank_line_runs(self):
        for label, cfg in validate_templates.configurations():
            files = validate_templates.bootstrap.generate_files(cfg)
            with self.subTest(label=label):
                self.assertEqual(validate_templates.check_markdown_blank_lines(label, files), [])

    def test_reports_a_blank_line_run_with_its_line(self):
        files = {"AGENTS.md": "# Title\n\n## A\n\n\n## B\n", "ci.yml": "a:\n\n\nb: 1\n"}
        self.assertEqual(
            validate_templates.check_markdown_blank_lines("x", files),
            ["[x] AGENTS.md:4: multiple consecutive blank lines"],
        )


class RunbookTest(unittest.TestCase):
    path = validate_templates.BRANCH_PROTECTION_RUNBOOK

    def test_every_configuration_carries_the_runbook_rules(self):
        for label, cfg in validate_templates.configurations():
            files = validate_templates.bootstrap.generate_files(cfg)
            with self.subTest(label=label):
                self.assertEqual(validate_templates.check_runbook(label, files), [])

    def test_incident_run_ids_and_shas_are_reported(self):
        files = validate_templates.bootstrap.generate_files(next(
            cfg for _, cfg in validate_templates.configurations() if cfg["repo_type"] == "simple"))
        files[self.path] += "\nRun 30244655509 fetched `d975919`; `main` was `4d583c5`.\n"
        errors = validate_templates.check_runbook("x", files)
        for evidence in ("30244655509", "`d975919`", "`4d583c5`"):
            self.assertTrue(any(repr(evidence) in error for error in errors), errors)
        self.assertEqual(len(errors), 3, errors)

    def test_the_stamp_digest_is_not_incident_evidence(self):
        # A digest of 64 digits would match the run-ID pattern if the stamp
        # line were scanned; only the body is.
        stamp_line = f"{validate_templates.bootstrap.STAMP_PREFIX}{'1' * 64} -->\n"
        body = "# Runbook\n\n" + "\n".join(validate_templates.RUNBOOK_REQUIRED_PHRASES) + "\n"
        content = stamp_line + body
        self.assertEqual(validate_templates.bootstrap.read_stamp(content)[1], body)
        self.assertEqual(validate_templates.check_runbook("x", {self.path: content}), [])
        self.assertEqual(len(validate_templates.check_runbook("x", {self.path: body + stamp_line[4:]})), 1)

    def test_the_cited_incident_archive_exists(self):
        root = Path(validate_templates.__file__).parent
        template = (root / validate_templates.TEMPLATE_RUNBOOK).read_text(encoding="utf-8")
        archive = validate_templates.RUNBOOK_INCIDENT_ARCHIVE
        self.assertIn(archive, template)
        self.assertTrue((root / archive).is_file())


class RenderMarkdownTest(unittest.TestCase):
    def test_writes_each_configurations_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(validate_templates.render_markdown(Path(tmp)), 0)
            agents = sorted(p.parent.name for p in Path(tmp).glob("*/AGENTS.md"))
            self.assertEqual(len(agents), len(list(validate_templates.configurations())))
            self.assertIn("simple", agents)
            self.assertFalse(list(Path(tmp).rglob("*.yml")))

    def test_writes_skills_and_reviewer_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            validate_templates.render_markdown(Path(tmp))
            simple = Path(tmp) / "simple"
            self.assertTrue((simple / ".agents/skills/pull-requests/SKILL.md").is_file())
            self.assertTrue((simple / ".claude/agents/fresh-eyes-reviewer.md").is_file())
            self.assertTrue((simple / ".opencode/agents/fresh-eyes-reviewer.md").is_file())


if __name__ == "__main__":
    unittest.main()
