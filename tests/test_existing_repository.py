"""Tests for --check and --adopt against existing local repositories."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import bootstrap


def _render(repo_type="python", name="sample"):
    return bootstrap.generate_files(
        {"name": name, "repo_type": repo_type, "postgres": False, "scheme": "App"}
    )


def _git(repo: Path, *args):
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
             "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"},
    )


class ExistingRepositoryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "sample"
        self.repo.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def _commit_all(self):
        _git(self.repo, "init", "-q")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "init")

    def _write(self, rel, text):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def test_check_reports_missing_files_and_never_writes(self):
        files = _render()
        report = bootstrap.compare_repository(self.repo, files)
        self.assertTrue(all(status == "missing" for status, _ in report.values()))
        self.assertEqual(list(self.repo.iterdir()), [])

    def test_adopt_into_empty_directory_then_check_is_aligned(self):
        files = _render()
        actions = bootstrap.adopt_repository(self.repo, files)
        self.assertEqual({a for a, _, _ in actions}, {"wrote"})
        report = bootstrap.compare_repository(self.repo, files)
        self.assertTrue(all(status == "same" for status, _ in report.values()), report)

    def test_adopt_keeps_existing_non_agents_files(self):
        files = _render()
        self._write("README.md", "# Mine\n")
        actions = bootstrap.adopt_repository(self.repo, files)
        self.assertIn(("kept", "README.md", "differs from the template; not overwritten"), actions)
        self.assertEqual((self.repo / "README.md").read_text(), "# Mine\n")

    def test_adopt_rebuilds_agents_keeping_project_specifics(self):
        files = _render()
        agents = files["AGENTS.md"]
        mine = "## Project specifics\n\n- Never touch the billing module.\n\n## Local notes\n\nKeep.\n"
        generated = agents.split(bootstrap.PROJECT_SPECIFICS)[0]
        # A generated section the repository lacks, plus a repository-owned
        # tail: rebuilding is lossless, so no opt-in is needed.
        start = generated.index("## Worktrees, verification copies, and scratch output")
        end = generated.index("## Definition of done")
        self._write("AGENTS.md", generated[:start] + generated[end:] + mine)
        rows = bootstrap.compare_agents(agents, (self.repo / "AGENTS.md").read_text())
        self.assertIn(("missing", "## Worktrees, verification copies, and scratch output"), rows)
        self._commit_all()
        actions = bootstrap.adopt_repository(self.repo, files)
        self.assertNotIn("refused", {a for a, _, _ in actions}, actions)
        result = (self.repo / "AGENTS.md").read_text()
        self.assertTrue(result.endswith(mine))
        self.assertEqual(result.split(bootstrap.PROJECT_SPECIFICS)[0], agents.split(bootstrap.PROJECT_SPECIFICS)[0])

    def test_adopt_refuses_local_sections_outside_project_specifics(self):
        files = _render()
        original = "## Prime directives\n\nOnly ours.\n\n" + files["AGENTS.md"]
        self._write("AGENTS.md", original)
        self._commit_all()
        actions = bootstrap.adopt_repository(self.repo, files)
        refused = [a for a in actions if a[1] == "AGENTS.md"]
        self.assertEqual(refused[0][0], "refused")
        self.assertIn("## Prime directives", refused[0][2])
        self.assertEqual((self.repo / "AGENTS.md").read_text(), original)

    def test_adopt_refuses_differing_generated_sections_unless_asked(self):
        files = _render()
        edited = files["AGENTS.md"].replace(
            "## Definition of done\n\n", "## Definition of done\n\nLocal edit.\n\n", 1
        )
        self.assertNotEqual(edited, files["AGENTS.md"])
        self._write("AGENTS.md", edited)
        self._commit_all()
        actions = bootstrap.adopt_repository(self.repo, files)
        row = next(a for a in actions if a[1] == "AGENTS.md")
        self.assertEqual(row[0], "refused")
        self.assertIn("## Definition of done", row[2])
        self.assertEqual((self.repo / "AGENTS.md").read_text(), edited)

        actions = bootstrap.adopt_repository(self.repo, files, replace_generated=True)
        row = next(a for a in actions if a[1] == "AGENTS.md")
        self.assertEqual(row[0], "updated")
        self.assertIn("replaced: ## Definition of done", row[2])
        self.assertEqual((self.repo / "AGENTS.md").read_text(), files["AGENTS.md"])

    def test_adopt_refuses_to_modify_files_outside_a_clean_git_tree(self):
        files = _render()
        self._write("AGENTS.md", files["AGENTS.md"].split(bootstrap.PROJECT_SPECIFICS)[0])
        self._write(".gitignore", "node_modules/\n")
        # Not a git work tree: existing files must not be modified.
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions["AGENTS.md"], "refused")
        self.assertEqual(actions[".gitignore"], "refused")
        # A git work tree with an uncommitted change to the file: also refused.
        self._commit_all()
        self._write(".gitignore", "node_modules/\ndist/\n")
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions[".gitignore"], "refused")
        self.assertEqual((self.repo / ".gitignore").read_text(), "node_modules/\ndist/\n")

    def test_adopt_prepends_only_missing_gitignore_entries(self):
        files = _render()
        self._write(".gitignore", "node_modules/\n.venv/\n")
        self._commit_all()
        bootstrap.adopt_repository(self.repo, files)
        text = (self.repo / ".gitignore").read_text()
        self.assertTrue(text.endswith("node_modules/\n.venv/\n"))
        self.assertEqual(text.count(".venv/\n"), 1)
        self.assertIn(".worktrees/", text.splitlines())
        status, detail = bootstrap.compare_repository(self.repo, files)[".gitignore"]
        self.assertEqual((status, detail), ("same", None))

    def test_adopt_keeps_repository_gitignore_exceptions(self):
        files = _render()
        self._write(".gitignore", "*.log\n!keep.log\n")
        self._write("keep.log", "x\n")
        self._commit_all()
        bootstrap.adopt_repository(self.repo, files)
        ignored = subprocess.run(
            ["git", "-C", str(self.repo), "check-ignore", "-q", "keep.log"], capture_output=True
        )
        self.assertEqual(ignored.returncode, 1, "keep.log became ignored")

    def test_adopt_never_writes_through_symlinks(self):
        files = _render()
        outside = Path(self._tmp.name) / "outside.md"
        (self.repo / "README.md").symlink_to(outside)  # dangling
        (self.repo / "docs").symlink_to(Path(self._tmp.name))
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions["README.md"], "refused")
        self.assertEqual(actions["docs/branch-protection-runbook.md"], "refused")
        self.assertFalse(outside.exists())
        self.assertFalse((Path(self._tmp.name) / "branch-protection-runbook.md").exists())

    def test_adopt_refuses_ignored_untracked_agents(self):
        files = _render()
        self._write(".gitignore", "AGENTS.md\n")
        self._commit_all()
        original = files["AGENTS.md"].replace("## Definition of done\n\n", "## Definition of done\n\nX.\n\n", 1)
        self._write("AGENTS.md", original)
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files, True)}
        self.assertEqual(actions["AGENTS.md"], "refused")
        self.assertEqual((self.repo / "AGENTS.md").read_text(), original)

    def test_adopt_refuses_crlf_files(self):
        files = _render()
        self._write(".gitignore", "node_modules/\r\n")
        self._commit_all()
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions[".gitignore"], "refused")
        self.assertEqual((self.repo / ".gitignore").read_bytes(), b"node_modules/\r\n")

    def test_check_treats_project_specifics_as_repository_owned(self):
        files = _render()
        self._write("AGENTS.md", files["AGENTS.md"] + "\n- Only ours.\n\n## Local notes\n\nMore.\n")
        status, _ = bootstrap.compare_repository(self.repo, files)["AGENTS.md"]
        self.assertEqual(status, "same")

    def test_ambiguous_structure_is_local(self):
        files = _render()
        generated, owned = bootstrap._split_project_specifics(files["AGENTS.md"])
        setext = generated.replace("## Definition of done\n\n", "## Definition of done\n\nOur rules\n---------\n\n", 1)
        rows = bootstrap.compare_agents(files["AGENTS.md"], setext + owned)
        self.assertIn(("local", "(setext heading: Our rules)"), rows)
        subsection = generated.replace("## Definition of done\n\n", "## Definition of done\n\n### Ours\n\nX.\n\n", 1)
        rows = bootstrap.compare_agents(files["AGENTS.md"], subsection + owned)
        self.assertIn(("local", "## Definition of done › ### Ours"), rows)

    def test_longer_fence_hides_inner_fence_and_headings(self):
        text = "## A\n\n````md\n```\n## Project specifics\n```\n````\n\n## B\n"
        _, sections = bootstrap._agents_sections(text)
        self.assertEqual([heading for heading, _ in sections], ["## A", "## B"])
        self.assertEqual(bootstrap._split_project_specifics(text), (text, None))
        self.assertIn("(code fence left open at end of file)", bootstrap._markdown_ambiguities("```\n## A\n"))

    def test_nextjs_block_is_kept_and_not_compared(self):
        files = _render("nextjs")
        repo_block = (
            "<!-- BEGIN:nextjs-agent-rules -->\n\n# Newer Next.js text\n\n<!-- END:nextjs-agent-rules -->"
        )
        template_block = bootstrap._nextjs_rules_block(files["AGENTS.md"])
        mine = files["AGENTS.md"].replace(template_block, repo_block, 1)
        rows = bootstrap.compare_agents(files["AGENTS.md"], mine)
        self.assertTrue(all(status == "same" for status, _ in rows), rows)
        rebuilt = bootstrap.rebuild_agents(files["AGENTS.md"], mine)
        self.assertIn("# Newer Next.js text", rebuilt)

    def test_headings_inside_code_fences_are_not_sections(self):
        text = "## Tooling\n\n```sh\n# 1. Format check\ncargo fmt\n```\n\n## Next\n"
        _, sections = bootstrap._agents_sections(text)
        self.assertEqual([heading for heading, _ in sections], ["## Tooling", "## Next"])

    def test_claude_md_without_import_is_reported(self):
        files = _render()
        self._write("CLAUDE.md", "Follow AGENTS.md for all project instructions.\n")
        status, detail = bootstrap.compare_repository(self.repo, files)["CLAUDE.md"]
        self.assertEqual(status, "differs")
        self.assertIn("does not import AGENTS.md", detail)


class CommandLineTests(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(Path(bootstrap.__file__)), *args], capture_output=True, text=True
        )

    def test_empty_path_is_rejected_before_any_other_flow(self):
        for flag in ("--check", "--adopt"):
            result = self._run(flag, "", "--type", "simple", "--non-interactive", "--name", "x")
            self.assertEqual(result.returncode, 1)
            self.assertIn("non-empty PATH", result.stderr)

    def test_adopt_exits_nonzero_when_it_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "AGENTS.md").write_text("## Ours\n")  # not in git: refused
            result = self._run("--adopt", tmp, "--type", "simple")
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("refused  AGENTS.md", result.stdout)


if __name__ == "__main__":
    unittest.main()
