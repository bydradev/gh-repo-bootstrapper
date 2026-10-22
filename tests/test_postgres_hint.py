"""The --check line on whether test.yml and the render carry the Postgres service."""

import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import bootstrap

TEST_YML = ".github/workflows/test.yml"


def _render(repo_type="nextjs", postgres=False):
    return bootstrap.generate_files(
        {"name": "sample", "repo_type": repo_type, "postgres": postgres, "scheme": "App",
         "screenshots": False}
    )


def _git(repo: Path, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def _workflow(services: str) -> str:
    return (
        "name: test\non:\n  workflow_call:\njobs:\n  lint:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - run: npm ci\n  build:\n    runs-on: ubuntu-latest\n"
        + services
        + "    steps:\n      - run: npm test\n"
    )


class PostgresServiceTests(unittest.TestCase):
    def test_reads_the_service_from_the_render(self):
        self.assertIs(bootstrap._has_postgres_service(_render(postgres=True)[TEST_YML]), True)
        self.assertIs(bootstrap._has_postgres_service(_render(postgres=False)[TEST_YML]), False)

    def test_names_and_images(self):
        cases = {
            "named postgres": ("    services:\n      postgres:\n        image: postgres:16\n", True),
            "named postgres, no image": ("    services:\n      postgres:\n", True),
            "another name, postgres image": ("    services:\n      db:\n        image: postgres:16\n", True),
            "quoted image": ("    services:\n      db:\n        image: \"postgres:17-alpine\"\n", True),
            "registry path": ("    services:\n      db:\n        image: docker.io/library/postgres:16\n", True),
            "digest": ("    services:\n      db:\n        image: postgres@sha256:abc\n", True),
            "another database": ("    services:\n      db:\n        image: mysql:8\n", False),
            "an image named like it": ("    services:\n      db:\n        image: postgres-exporter:1\n", False),
            "no services": ("", False),
        }
        for label, (services, found) in cases.items():
            with self.subTest(label):
                self.assertIs(bootstrap._has_postgres_service(_workflow(services)), found)
        self.assertIs(bootstrap._has_postgres_service("name: test\non: push\n"), False)

    def test_unreadable_yaml_is_not_guessed(self):
        # An anchor is outside the reader's subset.
        text = _workflow("    services:\n      db: &db\n        image: postgres:16\n")
        self.assertIsNone(bootstrap._has_postgres_service(text))
        self.assertEqual(
            bootstrap._postgres_hint(_render(postgres=True)[TEST_YML], text),
            "Postgres service: cannot read this file to tell; compare it with the render by hand",
        )

    def test_an_image_the_reader_cannot_see_into_is_not_guessed(self):
        # Valid YAML the reader admits but does not read inside: the image may
        # still be postgres, so the answer is "cannot tell", not "no".
        cases = {
            "block scalar image": "    services:\n      db:\n        image: >-\n          postgres:16\n",
            "literal image": "    services:\n      db:\n        image: |\n          postgres:16\n",
            "expression image": "    services:\n      db:\n        image: ${{ matrix.db }}\n",
            "flow container": "    services:\n      db: {image: postgres}\n",
            "flow services": "    services: {db: {image: postgres}}\n",
        }
        for label, services in cases.items():
            with self.subTest(label):
                self.assertIsNone(bootstrap._has_postgres_service(_workflow(services)))
        self.assertIsNone(bootstrap._has_postgres_service(
            "on: push\njobs:\n  build: {runs-on: ubuntu-latest}\n"))

    def test_a_postgres_service_found_outranks_one_it_cannot_read(self):
        services = ("    services:\n      cache:\n        image: ${{ matrix.cache }}\n"
                    "      postgres:\n        image: postgres:16\n")
        self.assertIs(bootstrap._has_postgres_service(_workflow(services)), True)

    def test_hint_for_each_combination(self):
        with_pg, without = _render(postgres=True)[TEST_YML], _render(postgres=False)[TEST_YML]
        cases = {
            (True, True): "Postgres service: in this file and in the render (--postgres)",
            (True, False): "Postgres service: in this file, not in the render; "
                           "pass --postgres if the repository uses it",
            (False, True): "Postgres service: in the render (--postgres), not in this file; "
                           "drop --postgres if the repository does not use it",
            (False, False): "Postgres service: in neither this file nor the render",
        }
        for (local, render), hint in cases.items():
            with self.subTest(local=local, render=render):
                actual = (with_pg if local else without) + "# edited\n"
                self.assertEqual(bootstrap._postgres_hint(with_pg if render else without, actual), hint)


class CheckReportHintTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name) / "sample"
        self.repo.mkdir()
        _git(self.repo, "init", "-q")

    def _adopt(self, files):
        bootstrap.adopt_repository(self.repo, files)
        (self.repo / TEST_YML).write_text((self.repo / TEST_YML).read_text() + "# Ours.\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "adopt")

    def test_an_edited_test_yml_names_a_wrong_postgres(self):
        self._adopt(_render(postgres=False))
        before = sorted(p.relative_to(self.repo) for p in self.repo.rglob("*") if ".git" not in p.parts)
        for postgres, hint in (
            (True, "Postgres service: in the render (--postgres), not in this file; "
                   "drop --postgres if the repository does not use it"),
            (False, "Postgres service: in neither this file nor the render"),
        ):
            with self.subTest(postgres=postgres):
                report = bootstrap.compare_repository(self.repo, _render(postgres=postgres))
                self.assertEqual(report[TEST_YML], ("differs", hint))
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    bootstrap.print_repository_report(self.repo, {"repo_type": "nextjs"}, report)
                row = f"  {'differs':<{bootstrap.REPORT_STATUS_WIDTH}} {TEST_YML}\n      {hint}\n"
                self.assertIn(row, output.getvalue())
        after = sorted(p.relative_to(self.repo) for p in self.repo.rglob("*") if ".git" not in p.parts)
        self.assertEqual(before, after)
        self.assertEqual(subprocess.run(["git", "-C", str(self.repo), "status", "--porcelain"],
                                        capture_output=True, text=True).stdout, "")

    def test_an_unedited_test_yml_has_no_hint(self):
        files = _render(postgres=True)
        bootstrap.adopt_repository(self.repo, files)
        self.assertEqual(bootstrap.compare_repository(self.repo, files)[TEST_YML], ("same", None))

    def test_other_types_get_no_hint(self):
        # Only nextjs renders --postgres, so another type's edited test.yml
        # keeps the plain row.
        files = _render("python")
        bootstrap.adopt_repository(self.repo, files)
        (self.repo / TEST_YML).write_text(files[TEST_YML] + "# Ours.\n")
        self.assertEqual(bootstrap.compare_repository(self.repo, files)[TEST_YML], ("differs", None))


if __name__ == "__main__":
    unittest.main()
