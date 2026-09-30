import { existsSync, readdirSync, readFileSync } from "node:fs";
import { relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseAdvisoryRows, parseLintRows } from "./baseline-table.mjs";

// fileURLToPath, not `.pathname`: a file URL percent-encodes characters that are
// legal in paths, so a checkout under "~/My Projects/app" yields
// "/Users/you/My%20Projects/app" and every resolve() and readFileSync() below
// silently misses. CI runners rarely have such a path; local clones do.
const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const lintBaselinePath = resolve(root, "docs/lint-baseline.md");
const advisoryBaselinePath = resolve(root, "docs/advisory-baseline.md");
const sourceExtensions = new Set([".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"]);
// Generated output is not source: coverage reports and Playwright's HTML report
// and results embed third-party JavaScript whose directives are not ours.
const excludedDirectories = new Set([
  ".git",
  "node_modules",
  ".next",
  "upstream",
  "coverage",
  "playwright-report",
  "test-results",
]);

function fail(message) {
  console.error(`Baseline verification error: ${message}`);
  process.exit(1);
}

function readBaseline(path, label) {
  try {
    return readFileSync(path, "utf8");
  } catch (error) {
    if (error.code === "ENOENT") fail(`${label} is missing`);
    throw error;
  }
}

function isIsoDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00.000Z`);
  return !Number.isNaN(date.valueOf()) && date.toISOString().slice(0, 10) === value;
}

function walk(directory) {
  const files = [];
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (!excludedDirectories.has(entry.name)) files.push(...walk(resolve(directory, entry.name)));
      continue;
    }
    if (sourceExtensions.has(entry.name.slice(entry.name.lastIndexOf("."))))
      files.push(resolve(directory, entry.name));
  }
  return files;
}

function rulesFromEslintDirective(text, file) {
  const rules = text.split("--", 1)[0].trim();
  if (!rules) fail(`suppression in ${file} does not name a rule`);
  return rules.split(/[\s,]+/).filter(Boolean);
}

// Splits text on commas outside quotes, brackets, and braces.
function topLevelEntries(text) {
  const entries = [];
  let depth = 0;
  let quote = "";
  let start = 0;
  for (let index = 0; index < text.length; index++) {
    const character = text[index];
    if (quote) {
      if (character === "\\") index++;
      else if (character === quote) quote = "";
    } else if (character === '"' || character === "'") quote = character;
    else if (character === "[" || character === "{") depth++;
    else if (character === "]" || character === "}") depth--;
    else if (character === "," && depth === 0) {
      entries.push(text.slice(start, index));
      start = index + 1;
    }
  }
  entries.push(text.slice(start));
  return entries;
}

// An `eslint` configuration block comment reconfigures rules for the whole
// file. Its value is a list of `rule: setting` entries, optionally followed by
// a description after ESLint's own separator (whitespace, two or more dashes,
// whitespace). A rule set to plain "error" or 2 is only switched on, and keeps
// its configured options (checked with ESLint 9.39.4's Linter, 2026-09-30), so
// it cannot weaken anything; every other setting — off, warn, or new options —
// needs a lint-baseline row.
function rulesFromEslintConfig(text) {
  const rules = [];
  for (const entry of topLevelEntries(text.split(/\s-{2,}\s/u, 1)[0])) {
    const match = /^\s*(?:"([^"]+)"|'([^']+)'|([^\s:"']+))\s*:([\s\S]*)$/u.exec(entry);
    if (!match) continue;
    const [, doubleQuoted, singleQuoted, bare, setting] = match;
    if (/^\s*(["']?)(?:error|2)\1\s*$/u.test(setting)) continue;
    rules.push(doubleQuoted ?? singleQuoted ?? bare);
  }
  return rules;
}

// Yields the body of each `eslint` configuration block comment. Rather than
// pairing every comment delimiter, which lets a string such as a
// "src/**/*.ts" glob open a phantom comment that swallows a real one, it
// reads from each opener followed by `eslint` to the next closing delimiter,
// which is where a real comment ends. Every opener is read independently, so
// configuration-shaped text before a real comment (in a line comment or a
// string) cannot hide it; such text is counted too, which errs on the side of
// requiring a row. The next closing delimiter is found once and reused, so the
// scan stays linear however many openers precede it.
function* eslintConfigComments(source) {
  const opener = /\/\*\s*eslint\s/gu;
  const close = "*" + "/";
  let end = -1;
  for (let match = opener.exec(source); match; match = opener.exec(source)) {
    if (end < opener.lastIndex) end = source.indexOf(close, opener.lastIndex);
    if (end === -1) return;
    yield source.slice(opener.lastIndex, end);
    opener.lastIndex = match.index + 1;
  }
}

function count(entries) {
  const counts = new Map();
  for (const entry of entries) counts.set(entry, (counts.get(entry) ?? 0) + 1);
  return counts;
}

const advisoryMarkdown = readBaseline(advisoryBaselinePath, "docs/advisory-baseline.md");
const lintMarkdown = readBaseline(lintBaselinePath, "docs/lint-baseline.md");

let advisoryRows;
let lintRows;
try {
  advisoryRows = parseAdvisoryRows(advisoryMarkdown);
  lintRows = parseLintRows(lintMarkdown);
} catch (error) {
  fail(error.message);
}

for (const row of advisoryRows) {
  if (!isIsoDate(row.reviewDate))
    fail(`invalid ISO review date ${JSON.stringify(row.reviewDate)} for ${row.ghsa}`);
}

for (const row of lintRows) {
  if (!isIsoDate(row.reviewDate))
    fail(
      `invalid ISO review date ${JSON.stringify(row.reviewDate)} for ${row.rule} in ${row.file}`,
    );
}

const documented = [];
for (const row of lintRows) {
  if (!row.rule) fail("lint-baseline row does not name a rule");
  const sourcePath = resolve(root, row.file);
  if (!existsSync(sourcePath)) fail(`lint-baseline file does not exist: ${row.file}`);
  documented.push(`${row.file}\u0000${row.rule}`);
}

const suppressions = [];
for (const sourcePath of walk(root)) {
  const relativePath = relative(root, sourcePath);
  const source = readFileSync(sourcePath, "utf8");
  const directives = source.matchAll(
    /(?:\/\/|\/\*)\s*(eslint-disable(?:-next-line|-line)?|@ts-(?:ignore|expect-error|nocheck))(?=\s|:|\*|$)([^\n*]*)/g,
  );
  for (const [, directive, remainder] of directives) {
    const rules = directive.startsWith("@ts-")
      ? [directive]
      : rulesFromEslintDirective(remainder, relativePath);
    for (const rule of rules) suppressions.push(`${relativePath}\u0000${rule}`);
  }
  // ESLint honours rule configuration only in block comments; a line comment
  // may carry only eslint-disable-line and eslint-disable-next-line (checked
  // against ESLint 9.39.4's SourceCode#getInlineConfigNodes and Linter,
  // 2026-09-30).
  for (const config of eslintConfigComments(source))
    for (const rule of rulesFromEslintConfig(config))
      suppressions.push(`${relativePath}\u0000${rule}`);
}

const documentedCounts = count(documented);
const suppressionCounts = count(suppressions);
const missingRows = [];
const orphanedRows = [];
for (const [entry, occurrences] of suppressionCounts)
  if ((documentedCounts.get(entry) ?? 0) < occurrences)
    missingRows.push(entry.replace("\u0000", " — "));
for (const [entry, occurrences] of documentedCounts)
  if ((suppressionCounts.get(entry) ?? 0) < occurrences)
    orphanedRows.push(entry.replace("\u0000", " — "));

if (missingRows.length || orphanedRows.length) {
  if (missingRows.length)
    console.error(`Undocumented suppressions:\n- ${missingRows.join("\n- ")}`);
  if (orphanedRows.length)
    console.error(`Orphaned lint-baseline rows:\n- ${orphanedRows.join("\n- ")}`);
  process.exit(1);
}

console.log(
  `Baseline verification passed: ${suppressions.length} suppression(s), ${advisoryRows.length} advisory row(s).`,
);
