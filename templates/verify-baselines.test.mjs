import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { copyFileSync, mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const scriptsDirectory = dirname(fileURLToPath(import.meta.url));
const lintHeader = [
  "## Accepted suppressions",
  "",
  "| # | Rule | File | Why this is accepted | Review date |",
  "| - | ---- | ---- | ------------------- | ----------- |",
].join("\n");
const advisoryHeader = [
  "## Accepted advisories",
  "",
  "| GHSA | Package | Severity | Scope (runtime/dev) | Why not fixed | Re-check trigger | Review date |",
  "| ---- | ------- | -------- | ------------------- | ------------- | ---------------- | ----------- |",
].join("\n");

function runFixture(source, extraFiles = {}) {
  const root = mkdtempSync(join(tmpdir(), "verify-baselines-"));
  try {
    mkdirSync(join(root, "scripts"));
    mkdirSync(join(root, "docs"));
    copyFileSync(
      join(scriptsDirectory, "baseline-table.mjs"),
      join(root, "scripts/baseline-table.mjs"),
    );
    copyFileSync(
      join(scriptsDirectory, "verify-baselines.mjs"),
      join(root, "scripts/verify-baselines.mjs"),
    );
    writeFileSync(join(root, "docs/lint-baseline.md"), lintHeader);
    writeFileSync(join(root, "docs/advisory-baseline.md"), advisoryHeader);
    writeFileSync(join(root, "sample.ts"), source);
    for (const [path, content] of Object.entries(extraFiles)) {
      mkdirSync(dirname(join(root, path)), { recursive: true });
      writeFileSync(join(root, path), content);
    }
    return execFileSync(process.execPath, [join(root, "scripts/verify-baselines.mjs")], {
      cwd: root,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (error) {
    return error.stderr?.toString() || error.stdout?.toString() || error.message;
  } finally {
    rmSync(root, { force: true, recursive: true });
  }
}

test("requires a lint-baseline row for TypeScript suppression directives", () => {
  for (const directive of ["@ts-ignore", "@ts-expect-error", "@ts-nocheck"])
    assert.match(
      runFixture(
        "/" + `/ ${directive} -- fixture suppression\nconst answer: number = \"wrong\";\n`,
      ),
      /Undocumented suppressions/,
    );
});

test("does not treat bare eslint-disable text as a suppression", () => {
  assert.match(
    runFixture('export const message = "use eslint-disable-next-line no-console to silence";\n'),
    /Baseline verification passed/,
  );
});

test("recognises block-comment ESLint suppressions", () => {
  assert.match(
    runFixture("/" + '* eslint-disable no-console */\nconsole.log("fixture");\n'),
    /Undocumented suppressions/,
  );
});

test("ignores suppression directives inside generated output directories", () => {
  const directive = "/" + "/ eslint-disable-next-line no-console -- vendored report code\n";
  const generated = {
    "coverage/lcov-report/sorter.js": directive,
    "playwright-report/trace/index.js": directive,
    "test-results/example/error-context.js": directive,
  };
  assert.match(runFixture("export const ok = 1;\n", generated), /Baseline verification passed/);
  assert.match(
    runFixture("export const ok = 1;\n", { "src/real.js": directive }),
    /Undocumented suppressions/,
  );
});

test("counts every rule an inline ESLint configuration comment sets", () => {
  const output = runFixture(
    "/" +
      '* eslint no-console: "off",\n   max-len: ["error", { code: 120, ignoreUrls: true }] */\n',
  );
  assert.match(output, /Undocumented suppressions/);
  assert.match(output, /sample\.ts — no-console/);
  assert.match(output, /sample\.ts — max-len/);
  assert.doesNotMatch(output, /— (code|ignoreUrls)/);
});

test("ignores ESLint rule configuration in a line comment, as ESLint does", () => {
  assert.match(
    runFixture("/" + '/ eslint no-console: "off"\nexport const ok = 1;\n'),
    /Baseline verification passed/,
  );
});

test("does not read eslint-env or eslint-disable as rule configuration", () => {
  assert.match(
    runFixture("/" + "* eslint-env node */\nexport const ok = 1;\n"),
    /Baseline verification passed: 0 suppression/,
  );
});
