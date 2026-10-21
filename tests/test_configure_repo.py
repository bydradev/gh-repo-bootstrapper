"""Regression tests for provider-free generated repository configuration."""

import base64
import contextlib
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import yaml

import bootstrap


class ConfigureRepoTests(unittest.TestCase):
    def _config(self):
        return {
            "name": "example",
            "owner": "octocat",
            "repo_type": "nextjs",
            "private": False,
            "postgres": False,
            "release_please_client_id": "client-id",
            "release_please_app_key": "private-key",
        }

    def test_configure_repo_writes_only_release_please_credentials(self):
        calls = []

        def run(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0)

        with patch.object(bootstrap.subprocess, "run", side_effect=run):
            bootstrap.configure_repo(self._config())

        variable_names = [
            command[3] for command, _kwargs in calls if command[:3] == ["gh", "variable", "set"]
        ]
        secret_names = [
            command[3] for command, _kwargs in calls if command[:3] == ["gh", "secret", "set"]
        ]
        self.assertEqual(variable_names, ["RELEASE_PLEASE_CLIENT_ID"])
        self.assertEqual(secret_names, ["RELEASE_PLEASE_APP_KEY"])

    def test_a_failed_allowlist_reports_what_was_applied_and_how_to_finish(self):
        def run(command, **kwargs):
            if command[:3] == ["gh", "api", "repos/octocat/example/actions/permissions/selected-actions"]:
                raise subprocess.CalledProcessError(1, command)
            return subprocess.CompletedProcess(command, 0)

        cfg = self._config()
        with patch.object(bootstrap.subprocess, "run", side_effect=run), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(subprocess.CalledProcessError):
            bootstrap.configure_repo(cfg)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            bootstrap.print_configuration_progress(cfg)
        report = err.getvalue()
        self.assertIn("Applied:     RELEASE_PLEASE_CLIENT_ID variable, RELEASE_PLEASE_APP_KEY secret, "
                      "merge strategy, Actions policy (selected actions, SHA pinning)", report)
        self.assertIn("Not applied: Actions allowlist, default workflow token permissions, "
                      "branch protection on main", report)
        self.assertIn("without its allowlist", report)
        script = str(Path(bootstrap.__file__).resolve())
        self.assertIn(f"{sys.executable} {script} --configure-only --name example --type nextjs --org octocat",
                      report)
        self.assertIn("docs/branch-protection-runbook.md", report)
        self.assertNotIn("private-key", report)

    def test_an_early_failure_still_lists_every_later_setting(self):
        def run(command, **kwargs):
            if "PATCH" in command:
                raise subprocess.CalledProcessError(1, command)
            return subprocess.CompletedProcess(command, 0)

        cfg = self._config()
        with patch.object(bootstrap.subprocess, "run", side_effect=run), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(subprocess.CalledProcessError):
            bootstrap.configure_repo(cfg)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            bootstrap.print_configuration_progress(cfg)
        self.assertIn("Not applied: merge strategy, Actions policy (selected actions, SHA pinning), "
                      "Actions allowlist, default workflow token permissions, branch protection on main",
                      err.getvalue())
        self.assertIn("docs/branch-protection-runbook.md", err.getvalue())

    def test_a_completed_configuration_records_every_step(self):
        cfg = self._config()
        with patch.object(bootstrap.subprocess, "run",
                          side_effect=lambda command, **kwargs: subprocess.CompletedProcess(command, 0)), \
                contextlib.redirect_stdout(io.StringIO()):
            bootstrap.configure_repo(cfg)
        self.assertEqual(cfg["configured"], cfg["configure_plan"])

    def test_creation_commands_ignore_an_inherited_index_override(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        other, target = Path(tmp.name) / "other", Path(tmp.name) / "target"
        for repo in (other, target):
            subprocess.run(["git", "init", "-q", str(repo)], check=True, env=bootstrap._git_env())
        (target / "generated.txt").write_text("x\n")
        with patch.dict(os.environ, {"GIT_INDEX_FILE": str(other / ".git" / "index")}):
            bootstrap._run(["git", "-C", str(target), "add", "."])

        def tracked(repo):
            return subprocess.run(
                ["git", "-C", str(repo), "ls-files"],
                capture_output=True, text=True, check=True, env=bootstrap._git_env(),
            ).stdout

        self.assertEqual(tracked(target), "generated.txt\n")
        self.assertEqual(tracked(other), "")

    def test_selected_actions_excludes_provider_actions(self):
        rust_only = ["dtolnay/rust-toolchain@*", "Swatinem/rust-cache@*"]
        for repo_type in ("simple", "python", "nextjs", "swift", "rust"):
            with self.subTest(repo_type=repo_type):
                calls = []

                def run(command, **kwargs):
                    calls.append((command, kwargs))
                    return subprocess.CompletedProcess(command, 0)

                with patch.object(bootstrap.subprocess, "run", side_effect=run):
                    bootstrap.configure_repo({**self._config(), "repo_type": repo_type})

                command, kwargs = next(
                    (command, kwargs)
                    for command, kwargs in calls
                    if command[2] == "repos/octocat/example/actions/permissions/selected-actions"
                )
                payload = json.loads(kwargs["input"].decode())
                self.assertEqual(
                    payload["patterns_allowed"],
                    ["amannn/action-semantic-pull-request@*"] + (rust_only if repo_type == "rust" else []),
                )

    def test_rust_allowlist_covers_every_third_party_action_it_renders(self):
        files = bootstrap.generate_files({**self._config(), "repo_type": "rust", "name": "sample"})
        used = set()
        for path, text in files.items():
            if path.startswith(".github/workflows/"):
                used |= set(re.findall(r"uses:\s*([\w.-]+/[\w.-]+)@", text))
        third_party = {action for action in used if not action.startswith("actions/")}
        allowed = {p.removesuffix("@*") for p in bootstrap.selected_action_patterns("rust")}
        self.assertIn("Swatinem/rust-cache", third_party)
        # googleapis is a Marketplace verified creator; everything else needs a pattern.
        self.assertEqual(third_party - {"googleapis/release-please-action"}, allowed)

    def test_nextjs_render_is_provider_free_and_preserves_postgres(self):
        files = bootstrap.generate_files({**self._config(), "name": "sample", "postgres": True})
        rendered = "\n".join(
            content for path, content in files.items() if path != ".gitignore"
        ).lower()
        self.assertNotIn("vercel", rendered)
        self.assertNotIn("cloudflare", rendered)
        self.assertNotIn("wrangler", rendered)
        self.assertNotIn("wrangler.jsonc", files)
        self.assertIn(".vercel/", files[".gitignore"])
        self.assertIn(".wrangler/", files[".gitignore"])
        self.assertIn("postgres", files[".github/workflows/test.yml"].lower())
        self.assertNotIn("deployments: write", files[".github/workflows/release-please.yml"])

    def test_gather_config_has_no_provider_keys(self):
        with patch.object(
            sys,
            "argv",
            [
                "bootstrap.py",
                "--name",
                "sample",
                "--type",
                "nextjs",
                "--org",
                "octocat",
                "--non-interactive",
                "--dry-run",
            ],
        ):
            config = bootstrap.gather_config(bootstrap.parse_args())

        self.assertFalse({"vercel", "cloudflare", "vercel_token", "cloudflare_api_token"} & config.keys())

    def test_screenshots_flag_is_used_for_nextjs_and_swift_only(self):
        base = ["bootstrap.py", "--name", "sample", "--org", "octocat", "--non-interactive", "--dry-run"]
        cases = {
            ("nextjs",): False,
            ("nextjs", "--screenshots"): True,
            ("swift", "--scheme", "App"): False,
            ("swift", "--scheme", "App", "--screenshots"): True,
            ("python", "--screenshots"): False,
            ("simple", "--screenshots"): False,
        }
        for (repo_type, *flags), expected in cases.items():
            with self.subTest(repo_type=repo_type, flags=flags):
                out = io.StringIO()
                with patch.object(sys, "argv", base + ["--type", repo_type, *flags]), \
                        contextlib.redirect_stdout(out):
                    config = bootstrap.gather_config(bootstrap.parse_args())
                self.assertIs(config["screenshots"], expected)
                ignored = "--screenshots is only used with --type nextjs or swift; ignoring"
                self.assertEqual(ignored in out.getvalue(), repo_type not in ("nextjs", "swift"))

    def test_interactive_runs_ask_about_screenshots_with_no_as_the_default(self):
        for repo_type, flags in (("nextjs", []), ("swift", ["--scheme", "App", "--destination", "macos"])):
            with self.subTest(repo_type=repo_type):
                asked = {}

                def answer(question, default=True):
                    asked[question] = default
                    return False

                argv = ["bootstrap.py", "--name", "sample", "--type", repo_type, "--org", "octocat",
                        "--private", "--dry-run", *flags]
                with patch.object(sys, "argv", argv), patch.object(bootstrap, "prompt_yn", answer), \
                        contextlib.redirect_stdout(io.StringIO()):
                    config = bootstrap.gather_config(bootstrap.parse_args())
                self.assertIs(asked[bootstrap.SCREENSHOTS_QUESTION], False)
                self.assertFalse(config["screenshots"])
                asked.clear()
                with patch.object(sys, "argv", argv + ["--screenshots"]), patch.object(bootstrap, "prompt_yn", answer), \
                        contextlib.redirect_stdout(io.StringIO()):
                    config = bootstrap.gather_config(bootstrap.parse_args())
                self.assertNotIn(bootstrap.SCREENSHOTS_QUESTION, asked)
                self.assertTrue(config["screenshots"])

    def test_dry_run_and_summary_show_screenshot_review(self):
        cfg = {"name": "sample", "owner": "octocat", "repo_type": "nextjs", "private": True,
               "repo_dir": "sample", "postgres": False, "screenshots": False}
        for screenshots in (False, True):
            with self.subTest(screenshots=screenshots):
                cfg["screenshots"] = screenshots
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    bootstrap.print_dry_run(cfg, bootstrap.generate_files(cfg))
                self.assertIn(f"Screenshot review: {screenshots}", out.getvalue())
                self.assertEqual(".claude/skills/screenshot-review ->" in out.getvalue(), screenshots)
                argv = ["bootstrap.py", "--name", "sample", "--type", "nextjs", "--org", "octocat",
                        "--non-interactive"] + (["--screenshots"] if screenshots else [])
                out = io.StringIO()
                env = {"RELEASE_PLEASE_APP_KEY": "", "RELEASE_PLEASE_CLIENT_ID": ""}
                with patch.object(sys, "argv", argv), patch.dict(os.environ, env), \
                        patch.object(bootstrap, "check_dependencies"), \
                        patch.object(bootstrap, "create_and_push", side_effect=OSError("stop")), \
                        contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()), \
                        self.assertRaises(SystemExit):
                    bootstrap.main()
                self.assertEqual("Extras: screenshot review" in out.getvalue(), screenshots)

    def test_owner_must_be_a_plain_github_name(self):
        for owner in ("octocat", "my-org", "A1", "x" * 39, "mona-cat_octo"):
            self.assertEqual(bootstrap.validate_owner(owner), "", owner)
        for owner in ("-flag", "_lead", "../evil", "a/b", "has space", "dot.name", "x" * 101, ""):
            self.assertNotEqual(bootstrap.validate_owner(owner), "", owner)
        argv = ["bootstrap.py", "--name", "sample", "--type", "simple", "--org", "../evil",
                "--non-interactive", "--dry-run"]
        with patch.object(sys, "argv", argv), contextlib.redirect_stderr(io.StringIO()) as err:
            with self.assertRaises(SystemExit):
                bootstrap.gather_config(bootstrap.parse_args())
        self.assertIn("--org", err.getvalue())

    def test_retired_provider_flags_are_rejected(self):
        for flag in ("--vercel", "--no-vercel", "--cloudflare", "--no-cloudflare"):
            with self.subTest(flag=flag), patch.object(sys, "argv", ["bootstrap.py", flag]):
                with self.assertRaises(SystemExit) as error:
                    bootstrap.parse_args()
            self.assertEqual(error.exception.code, 2)


def _der(tag, content):
    """One DER element: tag, definite length, content."""
    length = len(content)
    if length < 0x80:
        return bytes([tag, length]) + content
    size = (length.bit_length() + 7) // 8
    return bytes([tag, 0x80 | size]) + length.to_bytes(size, "big") + content


def _der_int(value):
    return _der(0x02, value.to_bytes(value.bit_length() // 8 + 1, "big"))


def _pem(label, der):
    body = base64.b64encode(der).decode()
    lines = [body[i:i + 64] for i in range(0, len(body), 64)]
    return "\n".join([f"-----BEGIN {label}-----", *lines, f"-----END {label}-----"]) + "\n"


def _test_rsa_key(qinv_offset=0, e_offset=0, d_offset=0):
    """A complete, consistent PKCS#1 RSA key built from two public Mersenne
    primes. It is far too small to protect anything; it exists so the
    validator sees real key structure without a secret in the repository."""
    p, q, e = 2**127 - 1, 2**107 - 1, 65537
    d = pow(e, -1, (p - 1) * (q - 1)) + d_offset
    numbers = (0, p * q, e + e_offset, d, p, q, d % (p - 1), d % (q - 1), pow(q, -1, p) + qinv_offset)
    return _der(0x30, b"".join(_der_int(n) for n in numbers))


_TEST_RSA_DER = _test_rsa_key()


def _der_sequence_body_after_version():
    """The test key's eight INTEGERs after its version, for re-encoding."""
    body = _TEST_RSA_DER[2:] if _TEST_RSA_DER[1] < 0x80 else _TEST_RSA_DER[2 + (_TEST_RSA_DER[1] & 0x7F):]
    return body[3:]  # drop 02 01 00


_TEST_PUBLIC_KEY = b"\x00" + _der(0x30, _der_int((2**127 - 1) * (2**107 - 1)) + _der_int(65537))


def _pkcs8_with_public_key(public_key):
    """The test key as version-1 PKCS#8, carrying public_key as its [1] field."""
    return _pem("PRIVATE KEY", _der(0x30, _der_int(1) + _der(0x30, bytes.fromhex(
        "06092a864886f70d010101") + b"\x05\x00") + _der(0x04, _TEST_RSA_DER) + _der(0x81, public_key)))


def _pkcs8_with_attributes(attributes):
    """The test key as version-0 PKCS#8, carrying attributes as its [0] field."""
    return _pem("PRIVATE KEY", _der(0x30, _der_int(0) + _der(0x30, bytes.fromhex(
        "06092a864886f70d010101") + b"\x05\x00") + _der(0x04, _TEST_RSA_DER) + _der(0xA0, attributes)))


# A friendlyName attribute (PKCS#9, 1.2.840.113549.1.9.20) holding a BMPString.
_TEST_ATTRIBUTE = _der(0x30, bytes.fromhex("060a2a864886f70d01091401") + _der(0x31, _der(0x1E, "key".encode("utf-16-be"))))


class ReleasePleaseAppKeyTests(unittest.TestCase):
    """The App key is a multi-line PEM block and must arrive whole."""

    KEY = _pem("RSA PRIVATE KEY", _TEST_RSA_DER)
    PKCS8_KEY = _pem("PRIVATE KEY", _der(0x30, _der_int(0) + _der(0x30, bytes.fromhex(
        "06092a864886f70d010101") + b"\x05\x00") + _der(0x04, _TEST_RSA_DER)))
    FIRST_LINE = "-----BEGIN RSA PRIVATE KEY-----"
    BODY_LINE = KEY.splitlines()[1]

    def _key_file(self, text):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "app-key.pem"
        path.write_text(text, encoding="utf-8")
        return path

    def test_app_key_error_accepts_only_a_complete_pem_block(self):
        self.assertGreaterEqual(len(self.KEY.splitlines()), 5, "the fixture needs several body lines")
        self.assertEqual(bootstrap.app_key_error(self.KEY), "")
        self.assertEqual(bootstrap.app_key_error(self.PKCS8_KEY), "")
        self.assertEqual(bootstrap.app_key_error(_pkcs8_with_public_key(_TEST_PUBLIC_KEY)), "")
        self.assertEqual(bootstrap.app_key_error(self.KEY.rstrip("\n")), "")
        self.assertIn("incomplete", bootstrap.app_key_error(self.FIRST_LINE))
        self.assertIn("incomplete", bootstrap.app_key_error(self.KEY.split("-----END")[0]))
        end_first = "-----END RSA PRIVATE KEY-----\n" + self.FIRST_LINE + "\n"
        self.assertIn("incomplete", bootstrap.app_key_error(end_first))
        self.assertIn("not a PEM private key", bootstrap.app_key_error("private-key"))

    def test_app_key_error_refuses_key_data_that_is_cut_or_corrupted(self):
        lines = self.KEY.splitlines(keepends=True)
        flipped = list(self.BODY_LINE)
        flipped[10] = "A" if flipped[10] != "A" else "B"
        cases = {
            "only the first body line": lines[0] + lines[1] + lines[-1],
            "a middle line dropped": "".join(lines[:2] + lines[3:]),
            "the last body line dropped": "".join(lines[:-2] + lines[-1:]),
            "one character changed": self.KEY.replace(self.BODY_LINE, "".join(flipped)),
            "not base64": self.KEY.replace(self.BODY_LINE, "not key material!"),
            # Python's base64 skips these too, but a PEM reader does not.
            "a vertical tab inside a line": self.KEY.replace(self.BODY_LINE, self.BODY_LINE[:20] + "\v" + self.BODY_LINE[20:]),
            "a form feed inside a line": self.KEY.replace(self.BODY_LINE, self.BODY_LINE[:20] + "\f" + self.BODY_LINE[20:]),
            "a no-break space inside a line": self.KEY.replace(
                self.BODY_LINE, self.BODY_LINE[:20] + "\u00a0" + self.BODY_LINE[20:]),
            "PKCS#1 data under a PKCS#8 label": self.KEY.replace("RSA PRIVATE", "PRIVATE"),
            "PKCS#8 data under a PKCS#1 label": self.PKCS8_KEY.replace("PRIVATE KEY", "RSA PRIVATE KEY"),
            "a PKCS#8 version of 2": _pem("PRIVATE KEY", _der(0x30, _der_int(2) + _der(0x30, bytes.fromhex(
                "06092a864886f70d010101") + b"\x05\x00") + _der(0x04, _TEST_RSA_DER))),
            "a PKCS#8 key with a trailing NULL": _pem("PRIVATE KEY", _der(0x30, _der_int(0) + _der(0x30, bytes.fromhex(
                "06092a864886f70d010101") + b"\x05\x00") + _der(0x04, _TEST_RSA_DER) + b"\x05\x00")),
            "a PKCS#8 public key under version 0": _pem("PRIVATE KEY", _der(0x30, _der_int(0) + _der(0x30, bytes.fromhex(
                "06092a864886f70d010101") + b"\x05\x00") + _der(0x04, _TEST_RSA_DER) + _der(0x81, b"\x00"))),
            # Node and OpenSSL refuse an unused-bit count over 7 (X.690, 8.6.2.2).
            "a PKCS#8 public key with 8 unused bits": _pkcs8_with_public_key(b"\x08"),
            "a PKCS#8 public key with unused bits": _pkcs8_with_public_key(b"\x01" + _TEST_PUBLIC_KEY[1:]),
            "an empty PKCS#8 public key": _pkcs8_with_public_key(b"\x00"),
            "a PKCS#8 public key for another modulus": _pkcs8_with_public_key(
                b"\x00" + _der(0x30, _der_int((2**127 - 1) * (2**89 - 1)) + _der_int(65537))),
            # Congruent modulo p - 1 and q - 1, but not below n, so it signs wrongly.
            "a public exponent past the modulus": _pem("RSA PRIVATE KEY", _test_rsa_key(
                e_offset=1000 * math.lcm(2**127 - 2, 2**107 - 2))),
            # Congruent modulo p - 1 and q - 1, but not below n, so Node
            # refuses to sign with it (RFC 8017, 3.2: d < n).
            "a private exponent past the modulus": _pem("RSA PRIVATE KEY", _test_rsa_key(
                d_offset=1000 * math.lcm(2**127 - 2, 2**107 - 2))),
            "a PKCS#1 version encoded in two bytes": _pem("RSA PRIVATE KEY", _der(
                0x30, b"\x02\x02\x00\x00" + _der_sequence_body_after_version())),
            "a long-form length for a short element": _pem("RSA PRIVATE KEY", _der(
                0x30, b"\x02\x81\x01\x00" + _der_sequence_body_after_version())),
            # Congruent, but outside 0 < qInv < p, so signing fails.
            "a CRT coefficient of qInv + p": _pem("RSA PRIVATE KEY", _test_rsa_key(qinv_offset=2**127 - 1)),
            "PKCS#8 parameters that are not NULL": _pem("PRIVATE KEY", _der(0x30, _der_int(0) + _der(
                0x30, bytes.fromhex("06092a864886f70d010101") + b"\x02\x01\x00") + _der(0x04, _TEST_RSA_DER))),
        }
        for label, value in cases.items():
            with self.subTest(label):
                error = bootstrap.app_key_error(value)
                self.assertIn("is incomplete or damaged", error)
                self.assertNotIn(self.BODY_LINE, error)

    def test_app_key_error_refuses_pkcs8_attributes(self):
        # Valid or not, attributes are refused: GitHub never adds them, and
        # Node fails to load a key whose attribute values do not decode.
        for attributes in (_TEST_ATTRIBUTE, b"\xff", _der(0x30, bytes.fromhex("060180") + _der(0x31, b"\x05\x01\x00"))):
            with self.subTest(attributes.hex()):
                error = bootstrap.app_key_error(_pkcs8_with_attributes(attributes))
                self.assertIn("carries PKCS#8 attributes", error)

    def test_app_key_error_refuses_a_pkcs8_key_that_is_not_rsa(self):
        # The EC P-256 algorithm identifier with an empty key: the algorithm
        # is refused before the key is read.
        ec = _pem("PRIVATE KEY", _der(0x30, _der_int(0) + _der(0x30, bytes.fromhex(
            "06072a8648ce3d020106082a8648ce3d030107")) + _der(0x04, b"")))
        self.assertIn("is not an RSA key", bootstrap.app_key_error(ec))

    @unittest.skipUnless(shutil.which("openssl"), "openssl is not installed")
    def test_app_key_error_accepts_keys_openssl_generates(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        pkcs8 = Path(tmp.name) / "pkcs8.pem"
        pkcs1 = Path(tmp.name) / "pkcs1.pem"
        made = [subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048",
                                "-out", str(pkcs8)], capture_output=True)]
        # -traditional is OpenSSL 3; 1.1 and LibreSSL already write PKCS#1.
        made.append(subprocess.run(["openssl", "rsa", "-traditional", "-in", str(pkcs8), "-out", str(pkcs1)],
                                   capture_output=True))
        if made[-1].returncode:
            made.append(subprocess.run(["openssl", "rsa", "-in", str(pkcs8), "-out", str(pkcs1)],
                                       capture_output=True))
        if made[0].returncode or made[-1].returncode or "BEGIN RSA PRIVATE KEY" not in pkcs1.read_text():
            self.skipTest("this openssl cannot write both PKCS#8 and PKCS#1 keys")
        for path in (pkcs8, pkcs1):
            with self.subTest(path.name):
                text = path.read_text()
                self.assertEqual(bootstrap.app_key_error(text), "")
                lines = text.splitlines(keepends=True)
                self.assertIn("is incomplete or damaged",
                              bootstrap.app_key_error(lines[0] + lines[1] + lines[-1]))

    def test_app_key_error_tolerates_crlf_and_trailing_spaces(self):
        self.assertEqual(bootstrap.app_key_error(self.KEY.replace("\n", "\r\n")), "")
        self.assertEqual(bootstrap.app_key_error(self.KEY.replace("-----\n", "-----  \n")), "")

    def test_app_key_error_names_malformed_keys_without_quoting_them(self):
        cases = {
            "encrypted": self.KEY.replace("RSA PRIVATE", "ENCRYPTED PRIVATE"),
            "different key types": self.KEY.replace("END RSA", "END EC"),
            "no key data": self.FIRST_LINE + "\n-----END RSA PRIVATE KEY-----\n",
            "OPENSSH PRIVATE KEY format": self.KEY.replace("RSA PRIVATE", "OPENSSH PRIVATE"),
        }
        for expected, value in cases.items():
            with self.subTest(expected):
                error = bootstrap.app_key_error(value)
                self.assertIn(expected, error)
                self.assertNotIn(self.BODY_LINE, error)

    def test_app_key_error_refuses_a_traditionally_encrypted_key(self):
        encrypted = self.KEY.replace(
            "KEY-----\n", "KEY-----\nProc-Type: 4,ENCRYPTED\nDEK-Info: AES-128-CBC,00\n\n", 1)
        self.assertIn("encrypted", bootstrap.app_key_error(encrypted))

    def test_escaped_newlines_are_turned_back_into_lines(self):
        escaped = self.KEY.replace("\n", "\\n")
        self.assertEqual(bootstrap.normalize_app_key(escaped), self.KEY)
        self.assertEqual(bootstrap.normalize_app_key(self.KEY), self.KEY)
        argv = ["bootstrap.py", "--name", "sample", "--type", "simple", "--org", "octocat",
                "--non-interactive", "--dry-run"]
        env = {"RELEASE_PLEASE_APP_KEY": escaped, "RELEASE_PLEASE_CLIENT_ID": "id"}
        with patch.object(sys, "argv", argv), patch.dict(os.environ, env), \
                contextlib.redirect_stdout(io.StringIO()):
            config = bootstrap.gather_config(bootstrap.parse_args())
        self.assertEqual(config["release_please_app_key"], self.KEY)

    def test_prompt_hides_the_path_on_a_terminal(self):
        path = self._key_file(self.KEY)
        with patch.object(sys.stdin, "isatty", return_value=True), \
                patch.object(bootstrap.getpass, "getpass", return_value=str(path)) as hidden, \
                patch("builtins.input", side_effect=AssertionError("echoed prompt used")), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(bootstrap.prompt_app_key_file(), self.KEY)
        hidden.assert_called_once()

    def test_prompt_reads_the_whole_key_from_a_file(self):
        path = self._key_file(self.KEY)
        with patch("builtins.input", return_value=str(path)), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(bootstrap.prompt_app_key_file(), self.KEY)

    def test_prompt_refuses_a_truncated_or_unreadable_file_and_asks_again(self):
        truncated = self._key_file(self.FIRST_LINE + "\n")
        missing = truncated.with_name("missing.pem")
        good = self._key_file(self.KEY)
        answers = iter([str(truncated), str(missing), str(good)])
        with patch("builtins.input", side_effect=lambda _q: next(answers)), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(bootstrap.prompt_app_key_file(), self.KEY)
        self.assertIn("is incomplete", out.getvalue())
        self.assertIn("cannot read", out.getvalue())
        self.assertNotIn(self.BODY_LINE, out.getvalue())

    def test_prompt_never_prints_back_a_key_pasted_in_place_of_a_path(self):
        good = self._key_file(self.KEY)
        answers = iter(self.KEY.splitlines() + [str(good)])
        with patch("builtins.input", side_effect=lambda _q: next(answers)), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(bootstrap.prompt_app_key_file(), self.KEY)
        self.assertIn("enter the path to the .pem file instead", out.getvalue())
        self.assertNotIn(self.BODY_LINE, out.getvalue())
        self.assertNotIn("RSA PRIVATE KEY", out.getvalue())

    def test_prompt_reads_a_bom_prefixed_key_from_a_home_relative_path(self):
        path = self._key_file("﻿" + self.KEY)
        with patch.dict(os.environ, {"HOME": str(path.parent)}), \
                patch("builtins.input", return_value="~/app-key.pem"), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(bootstrap.prompt_app_key_file(), self.KEY)

    def test_prompt_can_be_skipped(self):
        with patch("builtins.input", return_value=""), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(bootstrap.prompt_app_key_file(), "")
        self.assertIn("(skipped)", out.getvalue())

    def test_non_interactive_refuses_a_truncated_key_from_the_environment(self):
        argv = ["bootstrap.py", "--name", "sample", "--type", "simple", "--org", "octocat",
                "--non-interactive"]
        env = {"RELEASE_PLEASE_APP_KEY": self.FIRST_LINE, "RELEASE_PLEASE_CLIENT_ID": "id"}
        with patch.object(sys, "argv", argv), patch.dict(os.environ, env), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            with self.assertRaises(SystemExit):
                bootstrap.gather_config(bootstrap.parse_args())
        self.assertIn("RELEASE_PLEASE_APP_KEY is incomplete", err.getvalue())
        self.assertNotIn(self.FIRST_LINE, err.getvalue())

        env["RELEASE_PLEASE_APP_KEY"] = "\ufeff" + self.KEY
        with patch.object(sys, "argv", argv), patch.dict(os.environ, env), \
                contextlib.redirect_stdout(io.StringIO()):
            config = bootstrap.gather_config(bootstrap.parse_args())
        self.assertEqual(config["release_please_app_key"], self.KEY)

    def test_dry_run_does_not_check_the_key(self):
        argv = ["bootstrap.py", "--name", "sample", "--type", "simple", "--org", "octocat",
                "--non-interactive", "--dry-run"]
        env = {"RELEASE_PLEASE_APP_KEY": self.FIRST_LINE, "RELEASE_PLEASE_CLIENT_ID": "id"}
        with patch.object(sys, "argv", argv), patch.dict(os.environ, env), \
                contextlib.redirect_stdout(io.StringIO()):
            bootstrap.gather_config(bootstrap.parse_args())


class ConfigureExistingRepositoryTests(unittest.TestCase):
    """--configure-only on a repository that already exists."""

    REPO = "repos/octocat/example"
    # An existing Rust repository with its own checks and a looser Actions policy.
    CURRENT = {
        f"{REPO}/actions/permissions": {"enabled": True, "allowed_actions": "all", "sha_pinning_required": False},
        f"{REPO}/actions/permissions/workflow": {
            "default_workflow_permissions": "write", "can_approve_pull_request_reviews": False,
        },
        f"{REPO}/branches/main/protection": {
            "required_status_checks": {"strict": True, "contexts": ["Linux (default push CI)"]},
        },
    }

    def _configure(self, current, confirm, configure_only=True):
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            if command[:2] == ["gh", "api"] and "--method" not in command:
                body = current.get(command[2])
                if body is None:
                    return subprocess.CompletedProcess(command, 1, b"", b"Not Found")
                return subprocess.CompletedProcess(command, 0, json.dumps(body).encode(), b"")
            return subprocess.CompletedProcess(command, 0)

        cfg = {
            "name": "example", "owner": "octocat", "repo_type": "rust", "private": False,
            "configure_only": configure_only,
            "release_please_client_id": "client-id", "release_please_app_key": "private-key",
        }
        out = io.StringIO()
        with patch.object(bootstrap.subprocess, "run", side_effect=run), contextlib.redirect_stdout(out):
            bootstrap.configure_repo(cfg, confirm=confirm)
        writes = [command[2] for command in calls if command[:2] == ["gh", "api"] and "--method" in command]
        return writes, out.getvalue(), cfg

    def test_progress_bookkeeping_for_an_existing_repository(self):
        for confirm, applied in ((lambda: False, False), (lambda: True, True)):
            with self.subTest(applied=applied):
                _, _, cfg = self._configure(self.CURRENT, confirm)
                self.assertEqual(cfg["configured"], cfg["configure_plan"])
                self.assertNotIn("branch protection on main", cfg["configure_plan"])
                self.assertEqual("Actions allowlist" in cfg["configure_plan"], applied)

    def test_existing_protection_is_never_replaced(self):
        for confirm in (None, lambda: False, lambda: True):
            with self.subTest(confirm=confirm):
                writes, out, _ = self._configure(self.CURRENT, confirm)
                self.assertNotIn(f"{self.REPO}/branches/main/protection", writes)
                self.assertIn("Linux (default push CI)", out)
                self.assertIn("docs/branch-protection-runbook.md", out)

    def test_actions_policy_changes_are_listed_and_need_a_yes(self):
        actions = [endpoint for endpoint, _ in bootstrap.actions_policy_requests(
            {"owner": "octocat", "name": "example", "repo_type": "rust", "private": False}
        )]
        for confirm in (None, lambda: False):
            with self.subTest(confirm=confirm):
                writes, out, cfg = self._configure(self.CURRENT, confirm)
                self.assertEqual(writes, [self.REPO])
                self.assertIn('allowed_actions: "all" -> "selected"', out)
                self.assertIn('default_workflow_permissions: "write" -> "read"', out)
                self.assertTrue(cfg["actions_policy_unchanged"])
        writes, _, cfg = self._configure(self.CURRENT, lambda: True)
        self.assertEqual(writes, [self.REPO, *actions])
        self.assertNotIn("actions_policy_unchanged", cfg)

    def test_matching_actions_policy_asks_nothing(self):
        requests = bootstrap.actions_policy_requests(
            {"owner": "octocat", "name": "example", "repo_type": "rust", "private": False}
        )
        current = {**self.CURRENT, **dict(requests)}

        def never():
            raise AssertionError("asked to confirm an unchanged policy")

        writes, out, _ = self._configure(current, never)
        self.assertEqual(writes, [self.REPO])
        self.assertIn("already matches the generated policy", out)

    def test_security_settings_are_pinned(self):
        calls = []

        def run(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0)

        cfg = {
            "name": "example", "owner": "octocat", "repo_type": "python", "private": True,
            "release_please_client_id": "", "release_please_app_key": "",
        }
        with patch.object(bootstrap.subprocess, "run", side_effect=run), contextlib.redirect_stdout(io.StringIO()):
            bootstrap.configure_repo(cfg)
        payloads = {
            command[2]: json.loads(kwargs["input"].decode())
            for command, kwargs in calls if command[:2] == ["gh", "api"]
        }
        self.assertEqual(payloads[self.REPO], {
            "allow_squash_merge": True, "allow_merge_commit": False, "allow_rebase_merge": False,
            "delete_branch_on_merge": True, "squash_merge_commit_title": "PR_TITLE",
            "squash_merge_commit_message": "PR_BODY", "allow_update_branch": True, "has_projects": True,
        })
        self.assertEqual(payloads[f"{self.REPO}/actions/permissions"], {
            "enabled": True, "allowed_actions": "selected", "sha_pinning_required": True,
        })
        self.assertEqual(payloads[f"{self.REPO}/actions/permissions/selected-actions"], {
            "github_owned_allowed": True, "verified_allowed": True,
            "patterns_allowed": ["amannn/action-semantic-pull-request@*"],
        })
        self.assertEqual(payloads[f"{self.REPO}/actions/permissions/workflow"], {
            "default_workflow_permissions": "read", "can_approve_pull_request_reviews": False,
        })
        self.assertEqual(payloads[f"{self.REPO}/actions/permissions/fork-pr-workflows-private-repos"], {
            "run_workflows_from_fork_pull_requests": False, "send_write_tokens_to_workflows": False,
            "send_secrets_and_variables": False, "require_approval_for_fork_pr_workflows": False,
        })
        self.assertEqual(payloads[f"{self.REPO}/branches/main/protection"], {
            "required_status_checks": {"strict": False, "contexts": ["validate-title", "test / test"]},
            "enforce_admins": True,
            "required_pull_request_reviews": {
                "dismiss_stale_reviews": False, "require_code_owner_reviews": False,
                "required_approving_review_count": 0,
            },
            "restrictions": None,
        })

    def test_new_repository_still_gets_policy_and_protection(self):
        writes, _, _ = self._configure({}, None, configure_only=False)
        self.assertIn(f"{self.REPO}/actions/permissions", writes)
        self.assertIn(f"{self.REPO}/branches/main/protection", writes)


class ReleaseGateGuardTests(unittest.TestCase):
    """The gated release workflows refuse to tag a release merge they did not test."""

    GUARD = "Refuse to tag an untested release merge"

    def _steps(self, repo_type):
        files = bootstrap.generate_files(
            {"name": "sample", "repo_type": repo_type, "postgres": False, "scheme": "App"}
        )
        workflow = yaml.safe_load(files[".github/workflows/release-please.yml"])
        return workflow["jobs"]["release-please"]["steps"]

    def test_guard_runs_after_the_app_token_and_before_release_please(self):
        for repo_type in ("nextjs", "python", "swift", "rust"):
            with self.subTest(repo_type=repo_type):
                steps = self._steps(repo_type)
                names = [step.get("name") or step.get("uses", "") for step in steps]
                guard = names.index(self.GUARD)
                self.assertEqual(steps[guard - 1].get("id"), "app-token")
                self.assertTrue(names[guard + 1].startswith("googleapis/release-please-action@"))
                # release-please may tag only on the run the guard cleared.
                self.assertEqual(
                    steps[guard + 1]["with"]["skip-github-release"],
                    "${{ steps.guard.outputs.release != 'true' }}",
                )

    def test_guard_refuses_only_a_pending_merge_it_did_not_test(self):
        expected_argv = [
            "pr", "list", "--repo", "octocat/sample", "--state", "merged",
            "--label", "autorelease: pending", "--json", "number,mergeCommit",
            "--jq", '.[] | "\\(.number) \\(.mergeCommit.oid)"',
        ]
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        argv_file = Path(tmp.name) / "gh-argv"
        fake_gh = Path(tmp.name) / "gh"
        # Records each call's arguments; answers the compare call with how the
        # pending merge relates to TESTED_SHA (abc123).
        fake_gh.write_text(
            "#!/bin/sh\n"
            'printf "%s\\0" "$@" >> "$ARGV_FILE"; printf "\\n" >> "$ARGV_FILE"\n'
            '[ -z "$FAKE_FAIL" ] || exit 1\n'
            'if [ "$1" = api ]; then\n'
            '  cat > /dev/null\n'  # would swallow the guard's remaining rows without </dev/null
            '  [ -z "$FAKE_COMPARE_FAIL" ] || exit 1\n'
            '  case "$2" in\n'
            '    */compare/abc123...fff999) echo ahead ;;\n'
            '    */compare/abc123...def456) echo behind ;;\n'
            '    */compare/abc123...0dd000) echo diverged ;;\n'
            '    *) echo "unexpected compare: $2" >&2; exit 3 ;;\n'
            '  esac\n'
            'else\n'
            '  printf "%s" "$FAKE_PENDING"\n'
            'fi\n'
        )
        fake_gh.chmod(0o755)
        output = Path(tmp.name) / "github-output"
        # (pending rows, gh fails, exit code, release output or None when the step
        # fails before it, commits compared, message expected in the log)
        cases = {
            "no pending release": ("", False, 0, "false", [], None),
            "pending release is this commit": ("71 abc123", False, 0, "true", [], None),
            "pending release is an older commit": (
                "71 def456", False, 1, "false", ["def456"], "::error::Release PR #71 merged as def456"),
            "pending release merged after this commit": (
                "71 fff999", False, 0, "false", ["fff999"], "::notice::Release PR #71 merged as fff999"),
            "pending release on a diverged history": (
                "71 0dd000", False, 1, "false", ["0dd000"], "::error::Release PR #71 merged as 0dd000"),
            "this commit and an older one": (
                "71 abc123\n72 def456", False, 1, "true", ["def456"], "::error::Release PR #72 merged as def456"),
            "a newer merge, then an older one": (
                "71 fff999\n72 def456", False, 1, "false", ["fff999", "def456"],
                "::error::Release PR #72 merged as def456"),
            "this commit and a newer one": (
                "71 abc123\n72 fff999", False, 1, "false", ["fff999"], "::error::More than one release PR is pending"),
            "a newer one and this commit": (
                "71 fff999\n72 abc123", False, 1, "false", ["fff999"], "::error::More than one release PR is pending"),
            "the gh query fails": ("", True, 1, None, [], None),
            "the compare call fails": ("71 def456", "compare", 1, None, ["def456"], None),
        }
        for repo_type in ("python", "nextjs"):
            guard = next(step for step in self._steps(repo_type) if step.get("name") == self.GUARD)
            self.assertEqual(guard.get("id"), "guard")
            for label, (pending, fail, code, release, compared, message) in cases.items():
                with self.subTest(repo_type=repo_type, case=label):
                    output.write_text("")
                    argv_file.write_text("")
                    # GitHub runs a bash step as `bash --noprofile --norc -eo pipefail {0}`.
                    result = subprocess.run(
                        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", guard["run"]],
                        capture_output=True, text=True,
                        env={
                            "PATH": f"{tmp.name}:/usr/bin:/bin", "ARGV_FILE": str(argv_file),
                            "FAKE_PENDING": pending, "FAKE_FAIL": "1" if fail is True else "",
                            "FAKE_COMPARE_FAIL": "1" if fail == "compare" else "",
                            "REPO": "octocat/sample", "TESTED_SHA": "abc123",
                            "GITHUB_OUTPUT": str(output),
                        },
                    )
                    self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                    calls = [line.split("\0")[:-1] for line in argv_file.read_text().split("\n") if line]
                    self.assertEqual(calls, [expected_argv] + [
                        ["api", f"repos/octocat/sample/compare/abc123...{oid}", "--jq", ".status"]
                        for oid in compared
                    ])
                    if message:
                        self.assertIn(message, result.stdout)
                    expected_output = "" if release is None else f"release={release}\n"
                    self.assertEqual(output.read_text(), expected_output)


class ReleaseCredentialsGuardTests(unittest.TestCase):
    """Without the Release Please App credentials, the release is skipped with a warning."""

    CONDITION = "steps.credentials.outputs.configured == 'true'"
    WARNING = (
        "::warning::Release Please is not configured, or its credentials are not available to this run, "
        "so releases are skipped until the RELEASE_PLEASE_CLIENT_ID variable and the "
        "RELEASE_PLEASE_APP_KEY secret are both set."
    )
    # The bootstrapper's own release workflow carries the same check.
    OWN_WORKFLOW = Path(bootstrap.__file__).parent / ".github" / "workflows" / "release-please.yml"

    def _workflow(self, repo_type):
        files = bootstrap.generate_files(
            {"name": "sample", "repo_type": repo_type, "postgres": False, "scheme": "App"}
        )
        return yaml.safe_load(files[".github/workflows/release-please.yml"])

    def test_every_release_step_after_the_check_needs_both_credentials(self):
        for repo_type in ("nextjs", "python", "swift", "rust", "simple"):
            with self.subTest(repo_type=repo_type):
                workflow = self._workflow(repo_type)
                job = workflow["jobs"]["release-please"]
                check, *rest = job["steps"]
                self.assertEqual(check["id"], "credentials")
                self.assertNotIn("if", check)
                # Only whether each one is set reaches the step, never the key.
                self.assertEqual(check["env"], {
                    "HAS_CLIENT_ID": "${{ vars.RELEASE_PLEASE_CLIENT_ID != '' }}",
                    "HAS_APP_KEY": "${{ secrets.RELEASE_PLEASE_APP_KEY != '' }}",
                })
                self.assertEqual(rest[0]["id"], "app-token")
                self.assertTrue(rest[-1]["uses"].startswith("googleapis/release-please-action@"))
                for step in rest:
                    self.assertEqual(step.get("if"), self.CONDITION, step.get("name") or step.get("uses"))
                # The job itself stays unconditional, and the test job still gates it.
                self.assertNotIn("if", job)
                if repo_type != "simple":
                    self.assertEqual(job["needs"], "test")
                    self.assertNotIn("if", workflow["jobs"]["test"])

    def test_check_warns_and_skips_until_both_credentials_are_set(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        output = Path(tmp.name) / "github-output"
        # GitHub renders each `!= ''` comparison in the step env as true or false.
        cases = {
            "both set": ("true", "true", "true"),
            "no app key": ("true", "false", "false"),
            "no client id": ("false", "true", "false"),
            "neither set": ("false", "false", "false"),
        }
        workflows = {repo_type: self._workflow(repo_type) for repo_type in ("nextjs", "python", "simple")}
        workflows["bootstrapper own"] = yaml.safe_load(self.OWN_WORKFLOW.read_text())
        for source, workflow in workflows.items():
            check = workflow["jobs"]["release-please"]["steps"][0]
            self.assertEqual(check.get("id"), "credentials", source)
            self.assertEqual(check.get("shell"), "bash")
            for label, (client_id, app_key, configured) in cases.items():
                with self.subTest(source=source, case=label):
                    output.write_text("")
                    # GitHub runs a bash step as `bash --noprofile --norc -eo pipefail {0}`.
                    result = subprocess.run(
                        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", check["run"]],
                        capture_output=True, text=True,
                        env={"PATH": "/usr/bin:/bin", "GITHUB_OUTPUT": str(output),
                             "HAS_CLIENT_ID": client_id, "HAS_APP_KEY": app_key},
                    )
                    # A missing credential never fails the run; it warns instead.
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual(output.read_text(), f"configured={configured}\n")
                    if configured == "true":
                        self.assertEqual(result.stdout, "")
                    else:
                        self.assertEqual(result.stdout, self.WARNING + "\n")


class PythonToolInstallTests(unittest.TestCase):
    """The generated Python suite installs pinned tools only when the project has none."""

    def test_pinned_fallbacks_install_only_missing_tools(self):
        files = bootstrap.generate_files({"name": "sample", "repo_type": "python", "postgres": False})
        steps = yaml.safe_load(files[".github/workflows/test.yml"])["jobs"]["test"]["steps"]
        script = next(step["run"] for step in steps if step.get("name") == "Install dependencies")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        log = Path(tmp.name) / "pip-log"
        fake_pip = Path(tmp.name) / "bin" / "pip"
        fake_pip.parent.mkdir()
        fake_pip.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = show ]; then case " $INSTALLED " in *" $2 "*) exit 0 ;; *) exit 1 ;; esac; fi\n'
            'echo "$*" >> "$PIP_LOG"\n'
            'exit "${PIP_FAIL:-0}"\n'
        )
        fake_pip.chmod(0o755)
        work = Path(tmp.name) / "project"
        work.mkdir()
        cases = {
            "nothing installed": ("", "", 0, ["install ruff==0.16.10", "install mypy==2.4.0", "install pytest==9.1.1"]),
            "the project pins ruff and pytest": ("ruff pytest", "", 0, ["install mypy==2.4.0"]),
            "an install fails": ("", "1", 1, ["install ruff==0.16.10"]),
        }
        for label, (installed, fail, code, installs) in cases.items():
            with self.subTest(label):
                log.write_text("")
                result = subprocess.run(
                    ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script],
                    cwd=work, capture_output=True, text=True,
                    env={"PATH": f"{fake_pip.parent}:/usr/bin:/bin", "PIP_LOG": str(log),
                         "INSTALLED": installed, "PIP_FAIL": fail},
                )
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                self.assertEqual(log.read_text().splitlines(), installs)

    def test_installs_the_dependency_set_the_project_declares(self):
        files = bootstrap.generate_files({"name": "sample", "repo_type": "python", "postgres": False})
        steps = yaml.safe_load(files[".github/workflows/test.yml"])["jobs"]["test"]["steps"]
        script = next(step["run"] for step in steps if step.get("name") == "Install dependencies")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        log = Path(tmp.name) / "log"
        bin_dir = Path(tmp.name) / "bin"
        bin_dir.mkdir()
        # Fake pip and uv log each install and report every tool but ruff as
        # present, so the log holds the project's own installs and one fallback.
        for name, show in (("pip", '"$1" = show'), ("uv", '"$1 $2" = "pip show"')):
            fake = bin_dir / name
            fake.write_text(
                "#!/bin/sh\n"
                f'if [ {show} ]; then case "$*" in *ruff*) exit 1 ;; esac; exit 0; fi\n'
                f'echo "{name} $*" >> "$LOG"\n'
            )
            fake.chmod(0o755)
        # The step's python3 must be one that can import packaging, as the
        # workflow's (which has pip) can; this interpreter has pytest's.
        python = bin_dir / "python3"
        python.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
        python.chmod(0o755)
        app = ("[project]\nname = \"sample\"\nversion = \"0.1.0\"\n"
               "dependencies = [\"idna>=3\", \"six; python_version >= '3'\", \"never; python_version < '3'\"]\n")
        project = "[build-system]\nrequires = [\"setuptools\"]\nbuild-backend = \"setuptools.build_meta\"\n" + app
        extra = "[project.optional-dependencies]\ndev = [\"pytest\"]\n"
        group = "[dependency-groups]\ndev = [\"pytest\"]\n"
        build = "[build-system]\nrequires = [\"poetry-core\"]\nbuild-backend = \"poetry.core.masonry.api\"\n"
        cases = {
            "uv.lock": ({"pyproject.toml": project + group, "uv.lock": ""},
                        ["pip install uv==0.12.24", "uv sync --locked --group dev",
                         "uv pip install ruff==0.16.10"]),
            "uv.lock with a dev extra": ({"pyproject.toml": project + extra, "uv.lock": ""},
                                         ["pip install uv==0.12.24", "uv sync --locked --extra dev",
                                          "uv pip install ruff==0.16.10"]),
            "requirements-dev.txt": ({"requirements-dev.txt": "", "pyproject.toml": project + group},
                                     ["pip install -r requirements-dev.txt", "pip install ruff==0.16.10"]),
            "a dev dependency group": ({"pyproject.toml": project + group},
                                       ["pip install --upgrade pip>=25.1", "pip install -e . --group dev",
                                        "pip install ruff==0.16.10"]),
            "a dev extra and group": ({"pyproject.toml": project + extra + group},
                                      ["pip install --upgrade pip>=25.1", "pip install -e .[dev] --group dev",
                                       "pip install ruff==0.16.10"]),
            "a dev extra": ({"pyproject.toml": project + extra}, ["pip install -e .[dev]", "pip install ruff==0.16.10"]),
            "no dev dependencies": ({"pyproject.toml": project}, ["pip install -e .", "pip install ruff==0.16.10"]),
            "a dev group in a scripts repository": ({"pyproject.toml": group},
                                                    ["pip install pytest", "pip install ruff==0.16.10"]),
            "a build backend without [project]": ({"pyproject.toml": build},
                                                  ["pip install -e .", "pip install ruff==0.16.10"]),
            "tool settings only": ({"pyproject.toml": "[tool.ruff]\nline-length = 100\n"},
                                   ["pip install ruff==0.16.10"]),
            "tool settings and setup.py": ({"pyproject.toml": "[tool.ruff]\nline-length = 100\n", "setup.py": ""},
                                           ["pip install -e .", "pip install ruff==0.16.10"]),
            "a uv init --no-package app with a dev group": ({"pyproject.toml": app + group},
                                               ["pip install idna>=3 six pytest", "pip install ruff==0.16.10"]),
            "a uv init --no-package app with a dev extra": ({"pyproject.toml": app + extra},
                                               ["pip install idna>=3 six pytest", "pip install ruff==0.16.10"]),
            "an app with [tool.uv] package = true": ({"pyproject.toml": app + "[tool.uv]\npackage = true\n"},
                                                     ["pip install -e .", "pip install ruff==0.16.10"]),
            "a package with [tool.uv] package = false": ({"pyproject.toml": project + "[tool.uv]\npackage = false\n"},
                                                         ["pip install idna>=3 six", "pip install ruff==0.16.10"]),
            "an app whose dev extra names itself": (
                {"pyproject.toml": app + "[project.optional-dependencies]\ndev = [\"Sample[test,lint]\", \"mypy\"]\n"
                                         "test = [\"pytest\", \"sample[lint]\"]\nlint = [\"ruff\"]\n"},
                ["pip install idna>=3 six mypy ruff pytest", "pip install ruff==0.16.10"]),
            "markers, a cycle and extra markers": (
                {"pyproject.toml": app + "[project.optional-dependencies]\n"
                                         "dev = [\"sample[test]; python_version >= '3'\", \"skip; python_version < '3'\","
                                         " \"helper; extra == 'dev'\", \"at; platform_release != '@'\"]\n"
                                         "test = [\"sample[dev]\", \"pytest; extra == 'test'\", \"nope; extra == 'dev'\","
                                         " \"url @ https://example.com/pkg;a.whl ; python_version >= '3'\"]\n"},
                ["pip install idna>=3 six helper at pytest url @ https://example.com/pkg;a.whl",
                 "pip install ruff==0.16.10"]),
            "a self-reference its own version does not satisfy": (
                {"pyproject.toml": app + "[project.optional-dependencies]\ndev = [\"sample[test]>=2\"]\ntest = [\"pytest\"]\n"},
                "excludes this project's own version"),
            "a requires-python this interpreter is outside": (
                {"pyproject.toml": app.replace("[project]\n", "[project]\nrequires-python = \"<3\"\n")},
                "requires-python '<3' excludes Python"),
            "a dependency marked for the dev extra": (
                {"pyproject.toml": app.replace("\"idna>=3\"", "\"idna>=3\", \"helper; extra == 'dev'\"") + extra},
                ["pip install idna>=3 helper six pytest", "pip install ruff==0.16.10"]),
            "a dependency marked for an extra not requested": (
                {"pyproject.toml": app.replace("\"idna>=3\"", "\"idna>=3\", \"helper; extra == 'docs'\"") + extra},
                ["pip install idna>=3 six pytest", "pip install ruff==0.16.10"]),
            "an app with no dependencies": ({"pyproject.toml": "[project]\nname = \"sample\"\nversion = \"0.1.0\"\n"},
                                            ["pip install ruff==0.16.10"]),
            "only setup.py": ({"setup.py": ""}, ["pip install -e .", "pip install ruff==0.16.10"]),
            # pip installs a directory only with a pyproject.toml or setup.py.
            "only setup.cfg": ({"setup.cfg": ""}, ["pip install ruff==0.16.10"]),
            "setup.cfg metadata with tool settings": (
                {"setup.cfg": "[metadata]\nname = sample\n", "pyproject.toml": "[tool.ruff]\nline-length = 100\n"},
                ["pip install -e .", "pip install ruff==0.16.10"]),
            "a flake8-only setup.cfg next to an app": (
                {"setup.cfg": "[flake8]\nmax-line-length = 100\n", "pyproject.toml": app},
                ["pip install idna>=3 six", "pip install ruff==0.16.10"]),
            "a dev group that includes a group and names the app's extra": (
                {"pyproject.toml": app + "[project.optional-dependencies]\ntest = [\"helper\"]\n"
                                         "[dependency-groups]\ndev = [{include-group = \"Lint\"}, \"sample[test]\"]\n"
                                         "lint = [\"ruff\"]\n"},
                ["pip install idna>=3 six helper ruff", "pip install ruff==0.16.10"]),
            "a dev group that includes a missing group": (
                {"pyproject.toml": app + "[dependency-groups]\ndev = [{include-group = \"missing\"}]\n"},
                "includes 'missing', which is not defined"),
            "an app with its own platform.py and requires-python": (
                {"pyproject.toml": app.replace("[project]\n", "[project]\nrequires-python = \">=3.11\"\n"),
                 "platform.py": "raise SystemExit('the project platform.py was imported')\n"},
                ["pip install idna>=3 six", "pip install ruff==0.16.10"]),
            "a package with a Dev extra and DEV group": (
                {"pyproject.toml": project + "[project.optional-dependencies]\nDev = [\"pytest\"]\n"
                                             "[dependency-groups]\nDEV = [\"pytest\"]\n"},
                ["pip install --upgrade pip>=25.1", "pip install -e .[dev] --group dev",
                 "pip install ruff==0.16.10"]),
            "an app with a Dev group": ({"pyproject.toml": app + "[dependency-groups]\nDev = [\"pytest\"]\n"},
                                        ["pip install idna>=3 six pytest", "pip install ruff==0.16.10"]),
            "a dev group that is a string": (
                {"pyproject.toml": app + "[dependency-groups]\ndev = \"pytest\"\n"},
                "dependency group 'dev' is not a list"),
            # pip installs the base requirements alongside an extra's, so a
            # marker that holds without the extra keeps the dependency.
            "a dependency excluded from the dev extra": (
                {"pyproject.toml": app.replace("\"idna>=3\"", "\"idna>=3\", \"helper; extra != 'dev'\"") + extra},
                ["pip install idna>=3 helper six pytest", "pip install ruff==0.16.10"]),
            "a dependency excluded from an extra not requested": (
                {"pyproject.toml": app.replace("\"idna>=3\"", "\"idna>=3\", \"helper; extra != 'dev'\"")},
                ["pip install idna>=3 helper six", "pip install ruff==0.16.10"]),
            "a malformed requirement in an extra not installed": (
                {"pyproject.toml": app + extra + "docs = [\"not a req ???\"]\n"},
                "'not a req ???' in project.optional-dependencies.docs is not a valid requirement"),
            "a requirement that is not a string": (
                {"pyproject.toml": app.replace("\"idna>=3\"", "\"idna>=3\", 3")},
                "3 in project.dependencies is not a valid requirement"),
            "a tool.uv package value that is a string": (
                {"pyproject.toml": app + "[tool.uv]\npackage = \"false\"\n"},
                "tool.uv.package must be true or false, not 'false'"),
            "two groups that normalize alike": (
                {"pyproject.toml": app + "[dependency-groups]\ndev = [\"pytest\"]\nDev = [\"mypy\"]\n"},
                "duplicate dependency group name 'Dev'"),
            "two extras that normalize alike": (
                {"pyproject.toml": app + "[project.optional-dependencies]\ndev = [\"pytest\"]\nDEV = [\"mypy\"]\n"},
                "duplicate extra name 'DEV'"),
            "an indented setup.cfg [metadata] next to an app": (
                {"setup.cfg": "  [metadata]\n  name = sample\n", "pyproject.toml": app},
                ["pip install -e .", "pip install ruff==0.16.10"]),
            "a dev group include with an extra key": (
                {"pyproject.toml": app + "[dependency-groups]\ndev = [{include-group = \"lint\", typo = \"x\"}]\n"
                                         "lint = [\"ruff\"]\n"},
                "has a table that is not exactly"),
            "dependencies that are a string": (
                {"pyproject.toml": "[project]\nname = \"sample\"\nversion = \"0.1.0\"\ndependencies = \"pytest\"\n"},
                "project.dependencies is not a list"),
            "a dev extra that is a string": (
                {"pyproject.toml": app + "[project.optional-dependencies]\ndev = \"pytest\"\n"},
                "project.optional-dependencies.dev is not a list"),
            "a dev group that includes itself": (
                {"pyproject.toml": app + "[dependency-groups]\ndev = [{include-group = \"dev\"}]\n"},
                "dependency group 'dev' includes itself"),
            "a self-reference to a URL": (
                {"pyproject.toml": app + "[project.optional-dependencies]\ndev = [\"sample @ file:///tmp/sample-2.0.whl\"]\n"},
                "installs this project from a URL"),
        }
        for label, (project_files, installs) in cases.items():
            with self.subTest(label):
                work = Path(tempfile.mkdtemp(dir=tmp.name))
                for name, content in project_files.items():
                    (work / name).write_text(content)
                log.write_text("")
                result = subprocess.run(
                    ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script],
                    cwd=work, capture_output=True, text=True,
                    env={"PATH": f"{bin_dir}:/usr/bin:/bin", "LOG": str(log),
                         "GITHUB_PATH": str(Path(tmp.name) / "github-path")},
                )
                if isinstance(installs, str):
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(installs, result.stderr)
                    continue
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                # packaging writes a direct reference as "name@ url" or
                # "name @ url" depending on its version.
                self.assertEqual(log.read_text().replace("@ ", " @ ").replace("  @", " @").splitlines(), installs)

    @staticmethod
    def _write_wheel(directory, name, version, metadata=""):
        """Write an empty but valid wheel, so pip can install it offline."""
        dist_info = f"{name}-{version}.dist-info"
        files = {
            f"{dist_info}/METADATA": f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n{metadata}",
            f"{dist_info}/WHEEL": "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        }
        record = []
        for path, text in files.items():
            digest = base64.urlsafe_b64encode(hashlib.sha256(text.encode()).digest()).rstrip(b"=").decode()
            record.append(f"{path},sha256={digest},{len(text.encode())}")
        files[f"{dist_info}/RECORD"] = "\n".join(record + [f"{dist_info}/RECORD,,"]) + "\n"
        with zipfile.ZipFile(Path(directory) / f"{name}-{version}-py3-none-any.whl", "w") as wheel:
            for path, text in files.items():
                wheel.writestr(path, text)

    def _real_pip(self):
        """(install step script, temporary directory, pip argv) with pip 25.1+."""
        files = bootstrap.generate_files({"name": "sample", "repo_type": "python", "postgres": False})
        steps = yaml.safe_load(files[".github/workflows/test.yml"])["jobs"]["test"]["steps"]
        script = next(step["run"] for step in steps if step.get("name") == "Install dependencies")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        venv = Path(tmp.name) / "venv"
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True, capture_output=True)
        pip = [str(venv / "bin" / "python"), "-m", "pip"]
        def pip_version():
            version = subprocess.run(pip + ["--version"], capture_output=True, text=True, check=True).stdout.split()[1]
            return version, tuple(int(part) for part in re.findall(r"\d+", version)[:2])

        version, parsed = pip_version()
        if parsed < (25, 1):
            # Python 3.11 bundles an older pip; upgrade it when the index is
            # reachable, as the workflow itself does.
            with contextlib.suppress(subprocess.TimeoutExpired):
                subprocess.run(pip + ["install", "--quiet", "--timeout", "15", "--disable-pip-version-check",
                                      "--upgrade", "pip>=25.1"], capture_output=True, timeout=120)
            version, parsed = pip_version()
        if parsed < (25, 1):
            self.skipTest(f"pip {version} predates --group (25.1) and could not be upgraded")
        return script, tmp, venv, pip

    def _run_step(self, script, work, tmp, venv, wheels):
        return subprocess.run(
            ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script],
            cwd=work, capture_output=True, text=True,
            env={"PATH": f"{venv / 'bin'}:/usr/bin:/bin", "HOME": tmp.name,
                 "PIP_NO_INDEX": "1", "PIP_FIND_LINKS": str(wheels),
                 "PIP_DISABLE_PIP_VERSION_CHECK": "1"},
        )

    def test_tests_import_a_project_that_is_not_installed(self):
        # A project the step does not build (and one uv sync leaves
        # uninstalled) is importable only from the repository root, which
        # the test step must put on sys.path itself.
        files = bootstrap.generate_files({"name": "sample", "repo_type": "python", "postgres": False})
        steps = yaml.safe_load(files[".github/workflows/test.yml"])["jobs"]["test"]["steps"]
        command = next(step["run"] for step in steps
                       if "pytest" in step.get("run", "") and step.get("name") != "Install dependencies")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        bin_dir = Path(tmp.name) / "bin"
        bin_dir.mkdir()
        # `python` keeps this interpreter (and its environment); `pytest` is
        # what pip writes as the console script.
        (bin_dir / "python").write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
        (bin_dir / "pytest").write_text(
            f"#!{sys.executable}\nimport sys\nimport pytest\nsys.exit(pytest.main())\n")
        for script in bin_dir.iterdir():
            script.chmod(0o755)
        test = "def test_it():\n    from {} import value\n    assert value == 1\n"
        layouts = {
            "a scripts repository": ({"main.py": "value = 1\n", "helper.py": ""}, "main"),
            "a flat package": ({"mypkg/__init__.py": "value = 1\n"}, "mypkg"),
        }
        for label, (sources, module) in layouts.items():
            with self.subTest(label):
                work = Path(tempfile.mkdtemp(dir=tmp.name))
                (work / "pyproject.toml").write_text("[project]\nname = \"app\"\nversion = \"0.1.0\"\n")
                for name, content in {**sources, "tests/test_it.py": test.format(module)}.items():
                    (work / name).parent.mkdir(parents=True, exist_ok=True)
                    (work / name).write_text(content)
                result = subprocess.run(
                    ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", command],
                    cwd=work, capture_output=True, text=True,
                    env={"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": tmp.name},
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_project_that_is_not_a_package_installs_with_real_pip(self):
        # The editable install a package gets would fail here: setuptools
        # cannot discover a package among several top-level modules.
        script, tmp, venv, pip = self._real_pip()
        wheels = Path(tmp.name) / "wheels"
        wheels.mkdir()
        for name, pinned in (("devdep", "1.0"), ("ruff", "0.16.10"), ("mypy", "2.4.0"), ("pytest", "9.1.1")):
            self._write_wheel(wheels, name, pinned)
        self._write_wheel(wheels, "appdep", "1.0")
        group = "[dependency-groups]\ndev = [\"devdep==1.0\"]\n"
        layouts = {
            "only a dev group": (group, ["devdep"]),
            # What `uv init --no-package` writes: [project] without a [build-system].
            "a uv init app": ("[project]\nname = \"app\"\nversion = \"0.1.0\"\n"
                              "dependencies = [\"appdep==1.0\"]\n" + group, ["appdep", "devdep"]),
        }
        for label, (pyproject, installed) in layouts.items():
            with self.subTest(label):
                subprocess.run(pip + ["uninstall", "--yes", "--quiet", "devdep", "appdep"], capture_output=True)
                work = Path(tempfile.mkdtemp(dir=tmp.name))
                (work / "pyproject.toml").write_text(pyproject)
                (work / "main.py").write_text("")
                (work / "helper.py").write_text("")
                result = self._run_step(script, work, tmp, venv, wheels)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                for name in installed:
                    shown = subprocess.run(pip + ["show", name], capture_output=True, text=True)
                    self.assertEqual(shown.returncode, 0, f"{name} not installed")

    def test_dependency_markers_select_what_real_pip_selects(self):
        # The step reads markers itself for a project it does not build, so
        # it must pick the same dependencies pip picks from the metadata a
        # build would write for the same pyproject.toml.
        script, tmp, venv, pip = self._real_pip()
        wheels = Path(tmp.name) / "wheels"
        wheels.mkdir()
        candidates = ("always", "baseonly", "withdev", "devonly", "neverdev")
        for name, pinned in [(name, "1.0") for name in candidates] + [
                ("ruff", "0.16.10"), ("mypy", "2.4.0"), ("pytest", "9.1.1")]:
            self._write_wheel(wheels, name, pinned)
        dependencies = ["always", "baseonly; extra != 'dev'", "withdev; extra == 'dev'"]
        dev = ["devonly", "neverdev; extra != 'dev'"]
        # What a build backend writes: an optional dependency's marker is
        # joined with its extra.
        self._write_wheel(wheels, "sample", "0.1.0", "Provides-Extra: dev\n" + "".join(
            [f"Requires-Dist: {r}\n" for r in dependencies]
            + [f"Requires-Dist: {r.split(';')[0].strip()} ; ({r.split(';')[1].strip()}) and extra == \"dev\"\n"
               if ";" in r else f"Requires-Dist: {r} ; extra == \"dev\"\n" for r in dev]))
        report = Path(tmp.name) / "report.json"
        subprocess.run(pip + ["install", "--dry-run", "--ignore-installed", "--quiet", "--report", str(report),
                              "--no-index", "--find-links", str(wheels), "sample[dev]"],
                       check=True, capture_output=True)
        expected = {item["metadata"]["name"] for item in json.loads(report.read_text())["install"]} - {"sample"}
        self.assertEqual(expected, {"always", "baseonly", "withdev", "devonly"})
        work = Path(tempfile.mkdtemp(dir=tmp.name))
        (work / "pyproject.toml").write_text(
            "[project]\nname = \"sample\"\nversion = \"0.1.0\"\n"
            f"dependencies = {json.dumps(dependencies)}\n"
            f"[project.optional-dependencies]\ndev = {json.dumps(dev)}\n")
        result = self._run_step(script, work, tmp, venv, wheels)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        installed = {name for name in candidates
                     if subprocess.run(pip + ["show", name], capture_output=True).returncode == 0}
        self.assertEqual(installed, expected)


class ReleasePleaseConfigTests(unittest.TestCase):
    """A generated repository starts at 0.1.0, so its first breaking change must not propose 1.0.0."""

    OWN_CONFIG = Path(bootstrap.__file__).parent / "release-please-config.json"

    def _files(self, repo_type):
        return bootstrap.generate_files(
            {"name": "sample", "repo_type": repo_type, "postgres": False, "scheme": "App"}
        )

    def _config(self, repo_type):
        return json.loads(self._files(repo_type)["release-please-config.json"])

    def test_every_type_bumps_the_minor_for_a_breaking_change_before_1_0_0(self):
        for repo_type in ("nextjs", "python", "swift", "rust", "simple"):
            with self.subTest(repo_type=repo_type):
                config = self._config(repo_type)
                self.assertIs(config["bump-minor-pre-major"], True)
                # Top level only: a package-level value would override it.
                self.assertNotIn("bump-minor-pre-major", config["packages"]["."])

    def test_the_option_sits_beside_include_component_in_tag(self):
        keys = list(self._config("simple"))
        self.assertEqual(keys[keys.index("include-component-in-tag") + 1], "bump-minor-pre-major")

    def test_generated_config_agrees_with_this_repositorys_own(self):
        own = json.loads(self.OWN_CONFIG.read_text(encoding="utf-8"))
        for repo_type in ("nextjs", "simple"):
            with self.subTest(repo_type=repo_type):
                config = self._config(repo_type)
                for key in ("include-component-in-tag", "bump-minor-pre-major"):
                    self.assertEqual(config[key], own[key])

    def test_the_manifest_still_seeds_0_1_0(self):
        # The option only means something while the version is below 1.0.0.
        manifest = self._files("simple")[".release-please-manifest.json"]
        self.assertEqual(json.loads(manifest), {".": "0.1.0"})


class ReleaseGuardTokenTests(unittest.TestCase):
    """The untested-merge guard reads with the workflow token; the App token goes only to release-please."""

    GUARD = "Refuse to tag an untested release merge"
    WORKFLOW = ".github/workflows/release-please.yml"
    APP_TOKEN = "steps.app-token.outputs.token"

    def _workflow(self, repo_type):
        files = bootstrap.generate_files(
            {"name": "sample", "repo_type": repo_type, "postgres": False, "scheme": "App"}
        )
        return yaml.safe_load(files[self.WORKFLOW])

    def test_the_guard_reads_with_the_workflow_token(self):
        for repo_type in ("nextjs", "python", "swift", "rust"):
            with self.subTest(repo_type=repo_type):
                steps = self._workflow(repo_type)["jobs"]["release-please"]["steps"]
                guard = next(step for step in steps if step.get("name") == self.GUARD)
                self.assertEqual(guard["env"]["GH_TOKEN"], "${{ github.token }}")

    def test_only_release_please_gets_the_app_token(self):
        for repo_type in ("nextjs", "python", "swift", "rust", "simple"):
            with self.subTest(repo_type=repo_type):
                steps = self._workflow(repo_type)["jobs"]["release-please"]["steps"]
                users = [step for step in steps if self.APP_TOKEN in json.dumps(step)]
                self.assertEqual(len(users), 1, users)
                self.assertTrue(users[0]["uses"].startswith("googleapis/release-please-action@"))
                self.assertEqual(users[0]["with"]["token"], "${{ " + self.APP_TOKEN + " }}")

    def test_the_job_declares_the_reads_the_guard_needs_and_nothing_more(self):
        for repo_type in ("nextjs", "python", "swift", "rust", "simple"):
            with self.subTest(repo_type=repo_type):
                workflow = self._workflow(repo_type)
                job = workflow["jobs"]["release-please"]
                # A job-level block replaces the workflow's, so it repeats contents: read.
                self.assertEqual(workflow["permissions"], {"contents": "read"})
                if repo_type == "simple":
                    self.assertNotIn("permissions", job)
                else:
                    self.assertEqual(job["permissions"], {"contents": "read", "pull-requests": "read"})


if __name__ == "__main__":
    unittest.main()
