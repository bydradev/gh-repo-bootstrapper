import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { chmodSync, copyFileSync, mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const scriptsDirectory = dirname(fileURLToPath(import.meta.url));
const advisoryHeader = [
  "## Accepted advisories",
  "",
  "| GHSA | Package | Severity | Scope (runtime/dev) | Why not fixed | Re-check trigger | Review date |",
  "| ---- | ------- | -------- | ------------------- | ------------- | ---------------- | ----------- |",
].join("\n");
const advisoryUrl = "https://github.com/advisories/GHSA-aaaa-bbbb-cccc";
const vulnerableReport = {
  metadata: { vulnerabilities: { high: 1, total: 1 } },
  vulnerabilities: { example: { via: [{ url: advisoryUrl }] } },
};

// Runs the audit script in a scratch copy with a fake `npm` on PATH that prints
// the given report, so no test depends on the registry or the real tree.
function runAudit(report, rows = []) {
  const root = mkdtempSync(join(tmpdir(), "audit-production-"));
  try {
    for (const directory of ["scripts", "docs", "bin"]) mkdirSync(join(root, directory));
    for (const name of ["audit-production.mjs", "baseline-table.mjs"])
      copyFileSync(join(scriptsDirectory, name), join(root, "scripts", name));
    writeFileSync(join(root, "docs/advisory-baseline.md"), [advisoryHeader, ...rows].join("\n"));
    const npm = join(root, "bin/npm");
    writeFileSync(npm, "#!/usr/bin/env node\nprocess.stdout.write(process.env.FAKE_AUDIT_JSON);\n");
    chmodSync(npm, 0o755);
    return spawnSync(process.execPath, [join(root, "scripts/audit-production.mjs")], {
      cwd: root,
      encoding: "utf8",
      env: {
        ...process.env,
        PATH: `${join(root, "bin")}:${process.env.PATH}`,
        FAKE_AUDIT_JSON: JSON.stringify(report),
      },
    });
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

test("a clean production audit passes", () => {
  const result = runAudit({ metadata: { vulnerabilities: { total: 0 } }, vulnerabilities: {} });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /No production dependency vulnerabilities found/);
});

test("an unapproved runtime advisory fails", () => {
  const result = runAudit(vulnerableReport);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Unapproved production vulnerabilities: example/);
});

test("a documented runtime advisory passes", () => {
  const row =
    "| GHSA-aaaa-bbbb-cccc | example | high | runtime | No fixed release | Upstream fix | 2099-01-01 |";
  const result = runAudit(vulnerableReport, [row]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /only documented runtime exceptions/);
});

test("a dev-scope row does not approve a runtime advisory", () => {
  const row =
    "| GHSA-aaaa-bbbb-cccc | example | high | dev | Tooling only | Upstream fix | 2099-01-01 |";
  const result = runAudit(vulnerableReport, [row]);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Unapproved production vulnerabilities/);
});

test("an audit error response fails closed", () => {
  const result = runAudit({ error: { code: "ENOTFOUND", summary: "request failed" } });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /incomplete or error response/);
});

test("a report without a vulnerability map fails closed", () => {
  const result = runAudit({ metadata: { vulnerabilities: { total: 0 } } });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /incomplete or error response/);
});

test("a report without vulnerability counts fails closed", () => {
  const result = runAudit({ metadata: { vulnerabilities: {} }, vulnerabilities: {} });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /incomplete or error response/);
});
