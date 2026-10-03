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
