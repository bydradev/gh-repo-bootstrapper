"""Tests for --check and --adopt against existing local repositories."""

import os
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

    def _git_init(self):
        _git(self.repo, "init", "-q")

    def _commit_all(self):
        _git(self.repo, "init", "-q")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "init")

    def _write(self, rel, text):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def _agents_missing_a_section(self, files):
        """A lossless-to-rebuild AGENTS.md: the template minus one generated section."""
        generated, owned = bootstrap._split_project_specifics(files["AGENTS.md"])
        start = generated.index("## Worktrees, verification copies, and scratch output")
        end = generated.index("## Definition of done")
        return generated[:start] + generated[end:] + owned

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
        original = self._agents_missing_a_section(files)
        self._write("AGENTS.md", original)
        # Not a git work tree: an existing AGENTS.md must not be modified.
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions["AGENTS.md"], "refused")
        # A git work tree with an uncommitted change to the file: also refused.
        self._commit_all()
        self._write("AGENTS.md", original + "\nUncommitted.\n")
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions["AGENTS.md"], "refused")
        self.assertEqual((self.repo / "AGENTS.md").read_text(), original + "\nUncommitted.\n")
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
        crlf = self._agents_missing_a_section(files).replace("\n", "\r\n").encode()
        (self.repo / "AGENTS.md").write_bytes(crlf)
        self._commit_all()
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions["AGENTS.md"], "refused")
        self.assertEqual((self.repo / "AGENTS.md").read_bytes(), crlf)
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

    def test_adopt_rewrites_through_a_new_inode(self):
        files = _render()
        outside = Path(self._tmp.name) / "linked-agents"
        outside.write_text(self._agents_missing_a_section(files))
        self._git_init()
        os.link(outside, self.repo / "AGENTS.md")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "init")
        bootstrap.adopt_repository(self.repo, files)
        self.assertEqual(outside.read_text(), self._agents_missing_a_section(files))
        self.assertEqual((self.repo / "AGENTS.md").read_text(), files["AGENTS.md"])
    def test_contained_headings_in_generated_sections_are_local(self):
        files = _render()
        generated, owned = bootstrap._split_project_specifics(files["AGENTS.md"])
        for container in ("> ## Local policy", "- ## Local policy", "1. ### Local policy"):
            edited = generated.replace(
                "## Definition of done\n\n", f"## Definition of done\n\n{container}\n\n", 1
            )
            rows = bootstrap.compare_agents(files["AGENTS.md"], edited + owned)
            self.assertIn(("local", f"## Definition of done › {container}"), rows)

    def test_contained_setext_headings_are_local(self):
        files = _render()
        generated, owned = bootstrap._split_project_specifics(files["AGENTS.md"])
        edited = generated.replace(
            "## Definition of done\n\n",
            "## Definition of done\n\n> Local policy\n> ------------\n>\n> Keep this.\n\n", 1,
        )
        rows = bootstrap.compare_agents(files["AGENTS.md"], edited + owned)
        self.assertIn(("local", "(setext heading: Local policy)"), rows)

    def test_replacement_requires_confirmation_when_a_confirmer_is_given(self):
        files = _render()
        edited = files["AGENTS.md"].replace("## Definition of done\n\n", "## Definition of done\n\nX.\n\n", 1)
        self._write("AGENTS.md", edited)
        self._commit_all()
        seen = []
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(
            self.repo, files, True, confirm=lambda sections: seen.append(sections) or False
        )}
        self.assertEqual(seen, [["## Definition of done"]])
        self.assertEqual(actions["AGENTS.md"], "refused")
        self.assertEqual((self.repo / "AGENTS.md").read_text(), edited)
        bootstrap.adopt_repository(self.repo, files, True, confirm=lambda sections: True)
        self.assertEqual((self.repo / "AGENTS.md").read_text(), files["AGENTS.md"])

    def test_ambiguity_in_repository_owned_text_is_ignored(self):
        files = _render()
        tail = "\nOur heading\n-----------\n\n```\nunclosed\n"
        self._write("AGENTS.md", files["AGENTS.md"] + tail)
        status, _ = bootstrap.compare_repository(self.repo, files)["AGENTS.md"]
        self.assertEqual(status, "same")

    def test_lone_carriage_returns_are_refused(self):
        files = _render()
        self._write("AGENTS.md", self._agents_missing_a_section(files).replace("\n", "\r", 3))
        self._commit_all()
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions["AGENTS.md"], "refused")
    def test_a_per_file_failure_does_not_abort_the_run(self):
        files = _render()
        original = bootstrap._adopt_file

        def flaky(repo_dir, rel, *args):
            if rel == "README.md":
                raise FileExistsError(17, "File exists")
            return original(repo_dir, rel, *args)

        bootstrap._adopt_file = flaky
        try:
            actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        finally:
            bootstrap._adopt_file = original
        self.assertEqual(actions["README.md"], "refused")
        self.assertEqual(actions["AGENTS.md"], "wrote")

    def test_directory_swapped_for_symlink_after_the_scan_is_refused(self):
        files = _render()
        outside = Path(self._tmp.name) / "elsewhere"
        outside.mkdir()
        report = bootstrap.compare_repository(self.repo, files)  # .github does not exist yet
        (self.repo / ".github").symlink_to(outside)
        original = bootstrap.compare_repository
        bootstrap.compare_repository = lambda repo_dir, files: report
        try:
            actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        finally:
            bootstrap.compare_repository = original
        self.assertEqual(actions[".github/workflows/pr-title-check.yml"], "refused")
        self.assertEqual(list(outside.iterdir()), [])
        self.assertEqual(actions["AGENTS.md"], "wrote")

    def test_failed_new_file_leaves_nothing_behind(self):
        files = {"deep/dir/new.txt": "content\n"}
        original = bootstrap._create_anchored

        def failing(parent, name, text, exact_mode=None):
            original(parent, name, text[:2], exact_mode)
            raise OSError(28, "No space left on device")

        bootstrap._create_anchored = failing
        try:
            actions = bootstrap.adopt_repository(self.repo, files)
        finally:
            bootstrap._create_anchored = original
        self.assertEqual(actions[0][0], "refused")
        self.assertEqual(list(self.repo.iterdir()), [])

    def test_rewrite_refused_when_the_file_changes_after_it_was_read(self):
        files = _render()
        self._write("AGENTS.md", self._agents_missing_a_section(files))
        self._commit_all()
        original = bootstrap._create_anchored
        edited = self._agents_missing_a_section(files) + "\nConcurrent edit.\n"

        def edit_then_create(parent, name, text, exact_mode=None):
            (self.repo / "AGENTS.md").write_text(edited)
            original(parent, name, text, exact_mode)

        bootstrap._create_anchored = edit_then_create
        try:
            actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(
                self.repo, {"AGENTS.md": files["AGENTS.md"]}
            )}
        finally:
            bootstrap._create_anchored = original
        self.assertEqual(actions["AGENTS.md"], "refused")
        self.assertEqual((self.repo / "AGENTS.md").read_text(), edited)
        self.assertEqual([p.name for p in self.repo.iterdir() if p.name.endswith(".tmp")], [])
    def test_unreadable_file_is_reported_and_the_run_continues(self):
        files = _render()
        self._write("README.md", "# Mine\n")
        (self.repo / "README.md").chmod(0)
        try:
            status, _ = bootstrap.compare_repository(self.repo, files)["README.md"]
            self.assertEqual(status, "unreadable")
            actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        finally:
            (self.repo / "README.md").chmod(0o644)
        self.assertEqual(actions["README.md"], "refused")
        self.assertEqual(actions["AGENTS.md"], "wrote")

    def test_reordered_generated_sections_are_drift(self):
        files = _render()
        preamble, sections = bootstrap._agents_sections(files["AGENTS.md"])
        titles = [title for title, _ in sections]
        a, b = titles.index("## Branches"), titles.index("## Commits")
        sections[a], sections[b] = sections[b], sections[a]
        swapped = preamble + "".join(body for _, body in sections)
        rows = bootstrap.compare_agents(files["AGENTS.md"], swapped)
        self.assertIn(("differs", "(order of generated sections)"), rows)
        self._write("AGENTS.md", swapped)
        self._commit_all()
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions["AGENTS.md"], "refused")

    def test_longer_fence_hides_inner_fence_and_headings(self):
        text = "## A\n\n````md\n```\n## Project specifics\n```\n````\n\n## B\n"
        _, sections = bootstrap._agents_sections(text)
        self.assertEqual([heading for heading, _ in sections], ["## A", "## B"])
        self.assertEqual(bootstrap._split_project_specifics(text), (text, None))
        self.assertIn("(code fence left open at end of file)", bootstrap._markdown_ambiguities("```\n## A\n"))

    def test_adopt_reports_missing_gitignore_entries_without_writing(self):
        files = _render()
        self._write(".gitignore", "node_modules/\n!.worktrees/keep\n")
        self._commit_all()
        actions = {rel: (action, detail) for action, rel, detail in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions[".gitignore"][0], "kept")
        self.assertIn(".worktrees/", actions[".gitignore"][1])
        self.assertEqual((self.repo / ".gitignore").read_text(), "node_modules/\n!.worktrees/keep\n")

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


class RepositoryNameTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.repo = self.root / "sample"
        self.repo.mkdir()
        (self.repo / "README.md").write_text("sample\n")
        _git(self.repo, "init", "-q")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "init")

    def tearDown(self):
        self._tmp.cleanup()

    def test_main_checkout_uses_its_directory_name(self):
        self.assertEqual(bootstrap.existing_repository_name(self.repo), "sample")

    def test_linked_worktree_uses_the_main_checkout_name(self):
        worktree = self.root / ".worktrees" / "sample" / "align"
        _git(self.repo, "worktree", "add", "-q", "--detach", str(worktree))
        self.assertEqual(bootstrap.existing_repository_name(worktree), "sample")

    def test_subdirectory_and_non_repository_keep_their_basename(self):
        nested = self.repo / "packages" / "web"
        nested.mkdir(parents=True)
        self.assertEqual(bootstrap.existing_repository_name(nested), "web")
        plain = self.root / "plain"
        plain.mkdir()
        self.assertEqual(bootstrap.existing_repository_name(plain), "plain")


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
