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

// Reads the rules an `eslint` configuration comment sets. ESLint parses the
// text before its description separator (whitespace, two or more dashes,
// whitespace) as a levn object, which takes an optional outer pair of braces
// and entries separated by commas or only by whitespace; so a rule here is any
// quoted or bare name followed by `:` outside quotes, brackets, and braces,
// and its setting runs to the next rule. A rule set to plain "error" or 2 is
// only switched on, and keeps its configured options (checked with ESLint
// 9.39.4's Linter, 2026-09-30), so it cannot weaken anything; every other
// setting — off, warn, or new options — needs a lint-baseline row. Any value
// ESLint accepts has at least one such key, so text with none sets no rule.
function rulesFromEslintConfig(text) {
  let body = text.split(/\s-{2,}\s/u, 1)[0].trim();
  if (body.startsWith("{") && body.endsWith("}")) body = body.slice(1, -1);
  const keys = [];
  let depth = 0;
  for (let index = 0; index < body.length;) {
    const character = body[index];
    let end = index + 1;
    let name;
    if (character === '"' || character === "'") {
      while (end < body.length && body[end] !== character) end += body[end] === "\\" ? 2 : 1;
      name = body.slice(index + 1, end);
      end += 1;
    } else if (character === "[" || character === "{") depth++;
    else if (character === "]" || character === "}") depth--;
    else if (!/[\s:,]/u.test(character)) {
      end = index + /^[^\s:,"'[\]{}]+/u.exec(body.slice(index))[0].length;
      name = body.slice(index, end);
    }
    const colon = end + /^\s*/u.exec(body.slice(end))[0].length;
    if (name !== undefined && depth === 0 && body[colon] === ":") {
      keys.push({ name, start: index, valueStart: colon + 1 });
      end = colon + 1;
    }
    index = end;
  }
  return keys
    .filter(({ valueStart }, position) => {
      const setting = body
        .slice(valueStart, keys[position + 1]?.start ?? body.length)
        .trim()
        .replace(/,$/u, "")
        .trim();
      return !/^(["']?)(?:error|2)\1$/u.test(setting);
    })
    .map(({ name }) => name);
}

// Yields the body of each `eslint` configuration block comment. Rather than
// pairing every comment delimiter, which lets a string such as a
// "src/**/*.ts" glob open a phantom comment that swallows a real one, it
// reads from each opener followed by `eslint` through to the next closing
// delimiter, which is where a real comment ends. Every opener is read in full
// and independently, so no real comment can be hidden or cut short by
// opener-shaped text before or inside it; such text is counted too, which errs
// on the side of requiring a row. Openers sharing one closing delimiter reread
// the same text, so more than maxOpenersPerSpan of them fails closed rather
// than letting a pathological file make the scan quadratic.
const maxOpenersPerSpan = 64;
function* eslintConfigComments(source) {
  const opener = /\/\*\s*eslint\s/gu;
  const close = "*" + "/";
  let end = -1;
  let openersInSpan = 0;
  for (let match = opener.exec(source); match; match = opener.exec(source)) {
    const start = opener.lastIndex;
    if (end < start) {
      end = source.indexOf(close, start);
      openersInSpan = 0;
    }
    if (end === -1) return;
    if (++openersInSpan > maxOpenersPerSpan)
      throw new Error(
        `more than ${maxOpenersPerSpan} eslint configuration openers before one closing delimiter`,
      );
    yield source.slice(start, end);
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
  try {
    for (const config of eslintConfigComments(source))
      for (const rule of rulesFromEslintConfig(config))
        suppressions.push(`${relativePath}\u0000${rule}`);
  } catch (error) {
    fail(`${relativePath}: ${error.message}`);
  }
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
