import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { copyFileSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
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
      // A scan that is not linear takes minutes on the 50,000-opener fixtures;
      // killing it here fails the test without timing a busy host.
      timeout: 30_000,
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

test("reads TypeScript directives from the last line of a block comment", () => {
  const open = "/" + "*";
  const close = "*" + "/";
  for (const source of [
    `${open}* @ts-ignore ${close}\nconst answer: number = "wrong";\n`,
    `${open}\n * @ts-expect-error ${close}\nconst answer: number = "wrong";\n`,
    `export const ok = 1; ${open} @ts-ignore ${close}\n`,
    `${open} @ts-ignore: reason ${close}\nconst answer: number = "wrong";\n`,
    `${open}* @ts-expect-error(reason) ${close}\nconst answer: number = "wrong";\n`,
  ])
    assert.match(runFixture(source), /sample\.ts: @ts-(ignore|expect-error)\n/);
  // TypeScript reads only the last line, so a directive above it suppresses nothing.
  assert.match(
    runFixture(`${open}\n * @ts-ignore\n ${close}\nexport const ok = 1;\n`),
    /Baseline verification passed/,
  );
});

test("counts a line TypeScript directive with nothing after its name", () => {
  for (const directive of ["@ts-ignore(reason)", "@ts-expect-error."])
    assert.match(
      runFixture("/" + `/ ${directive}\nconst answer: number = "wrong";\n`),
      /sample\.ts: @ts-(ignore|expect-error)\n/,
    );
});

test("counts a line directive followed by a glob once", () => {
  const source = "/" + "/ @ts-ignore see src/**" + '/*.ts\nconst answer: number = "wrong";\n';
  const row = "| 1 | @ts-ignore | sample.ts | fixture | 2099-01-01 |";
  assert.match(
    runFixture(source, { "docs/lint-baseline.md": `${lintHeader}\n${row}\n` }),
    /Baseline verification passed: 1 suppression/,
  );
});

test("scans long lines of block comments in linear time", () => {
  const comment = "/" + "* pure *" + "/";
  const source = `export const bundle = [${Array(50_000).fill(`${comment}f()`).join(",")}];\n`;
  assert.match(runFixture(source), /Baseline verification passed/);
});

test("scans .mts and .cts sources", () => {
  const directive = "/" + "/ eslint-disable-next-line no-console -- fixture\n";
  for (const file of ["src/module.mts", "src/common.cts"])
    assert.match(
      runFixture("export const ok = 1;\n", { [file]: directive }),
      /Undocumented suppressions/,
    );
});

test("records every rule in a block eslint-disable list that wraps onto another line", () => {
  const output = runFixture(
    "/" + "* eslint-disable-next-line no-console,\n   no-alert *" + "/\nconsole.log(alert(1));\n",
  );
  for (const rule of ["no-console", "no-alert"])
    assert.match(output, new RegExp(`sample\\.ts: ${rule}\\n`));
});

test("does not count a JSDoc-style eslint-disable comment, which ESLint ignores", () => {
  assert.match(
    runFixture("/" + "** eslint-disable-next-line no-console *" + "/\nexport const ok = 1;\n"),
    /Baseline verification passed/,
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

test("counts every rule an inline ESLint configuration comment weakens", () => {
  const output = runFixture(
    "/" +
      '* eslint no-console: "off", "example/rule-one": \'warn\',\n' +
      '   max-len: ["error", { code: 120, ignoreUrls: true }] */\n',
  );
  assert.match(output, /Undocumented suppressions/);
  for (const rule of ["no-console", "example/rule-one", "max-len"])
    assert.match(output, new RegExp(`sample\\.ts: ${rule}\\n`));
  assert.doesNotMatch(output, /: (code|ignoreUrls)$/m);
});

test("does not count a rule that is only switched on", () => {
  assert.match(
    runFixture("/" + '* eslint no-console: "error", eqeqeq: 2 */\nexport const ok = 1;\n'),
    /Baseline verification passed: 0 suppression/,
  );
});

test("reads the rules before an ESLint description, not dashes inside a setting", () => {
  const output = runFixture(
    "/" +
      '* eslint no-restricted-syntax: ["error", "a--b"], no-console: "off" -- local logging */\n',
  );
  assert.match(output, /sample\.ts: no-restricted-syntax\n/);
  assert.match(output, /sample\.ts: no-console\n/);
  assert.doesNotMatch(output, /local logging/);
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

test("scans many unterminated comment openers in linear time", () => {
  const source = ("/" + "* eslint ").repeat(50_000) + "\n";
  assert.equal(source.split("/" + "*").length - 1, 50_000);
  assert.match(runFixture(source), /Baseline verification passed/);
});

test("scans many unterminated directive openers in linear time", () => {
  for (const opener of ["/" + "* eslint-disable no-console ", "/" + "* @ts-ignore "])
    assert.match(
      runFixture(`export const text = \`${opener.repeat(50_000)}\`;\n`),
      /Baseline verification passed/,
    );
});

test("fails closed on too many eslint-disable openers before one closing delimiter", () => {
  const source = ("/" + "* eslint-disable no-console ").repeat(65) + "*" + "/\n";
  assert.match(runFixture(source), /more than 64 eslint-disable openers/);
});

test("scans its own source to the end", () => {
  const source = readFileSync(join(scriptsDirectory, "verify-baselines.mjs"), "utf8");
  const output = runFixture(source + "\n/" + '* eslint no-console: "off" */\n');
  assert.match(output, /sample\.ts: no-console\n/);
  assert.equal(output.match(/^- /gm)?.length, 1, output);
});

test("finds a configuration comment wherever comment-shaped code precedes it", () => {
  const output = runFixture(
    [
      'const globs = ["src/**/*.ts", "/' + '*"];',
      "const url = /https?:\\/\\//; /" + '* eslint no-console: "off" */',
      "const value = `${input /" + '* eslint eqeqeq: "off" */}`;',
      "export const title = <p>Don't stop</p>; /" + '* eslint no-alert: "warn" */',
    ].join("\n"),
  );
  for (const rule of ["no-console", "eqeqeq", "no-alert"])
    assert.match(output, new RegExp(`sample\\.ts: ${rule}\\n`));
});

test("counts configuration-shaped text in a string, erring towards a row", () => {
  assert.match(
    runFixture('const text = "/' + "* eslint eqeqeq: 'off' */\";\n"),
    /sample\.ts: eqeqeq\n/,
  );
});

test("reads a real configuration comment after configuration-shaped text", () => {
  for (const prefix of ["/" + "/ /" + "* eslint", 'const text = "/' + '* eslint";'])
    assert.match(
      runFixture(`${prefix}\n/` + '* eslint no-console: "off" */\n'),
      /sample\.ts: no-console\n/,
    );
});

test("fails closed on too many openers before one closing delimiter", () => {
  const output = runFixture(("/" + "* eslint ").repeat(50_000) + "*" + "/\n");
  assert.match(output, /more than 64 eslint configuration openers before one closing delimiter/);
});
test("parses a whole configuration comment even when a setting quotes opener text", () => {
  const output = runFixture(
    "/" +
      '* eslint no-warning-comments: ["warn", { terms: ["/' +
      '* eslint marker"] }], no-console: "off" */\n',
  );
  assert.match(output, /sample\.ts: no-warning-comments\n/);
  assert.match(output, /sample\.ts: no-console\n/);
});

test("reads a real configuration comment in full after opener-shaped text", () => {
  const output = runFixture(
    'const label = "/' +
      '* eslint ";\n/' +
      '* eslint no-warning-comments: ["warn", { terms: ["/' +
      '* eslint marker"] }], no-console: "off" */\n',
  );
  assert.match(output, /sample\.ts: no-warning-comments\n/);
  assert.match(output, /sample\.ts: no-console\n/);
});

test("reads a braced configuration comment", () => {
  const output = runFixture(
    "/" + '* eslint {"no-console":"off", "eqeqeq": 2} *' + "/\nconsole.log(1);\n",
  );
  assert.match(output, /sample\.ts: no-console\n/);
  assert.doesNotMatch(output, /eqeqeq/);
});

test("reads configuration entries separated only by whitespace", () => {
  const output = runFixture("/" + "* eslint no-alert: 2 no-console: 0 *" + "/\nconsole.log(1);\n");
  assert.match(output, /sample\.ts: no-console\n/);
  assert.doesNotMatch(output, /no-alert/);
});
