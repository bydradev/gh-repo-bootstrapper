---
name: local-validation-nextjs
description: "Use before running local validation in this Next.js repository: lint, format, typecheck, unit tests, the production build, `next dev`, Playwright E2E, or driving a browser against a local server. Covers browser-launch sandbox failures, the macOS descriptor limit for `next dev` and when it applies, `EMFILE` fallbacks, Playwright traces and flaky results, the Playwright CLI for agent browser checks, the CI validation tiers as generated and where to check them, and how a worktree gets its dependencies."
---

# Local validation for Next.js

If `## Project specifics` in `AGENTS.md` names a repository-owned validation
skill, load it first; where it is narrower, it governs.

The commands to run before pushing are in the `## Tooling` section of
`AGENTS.md`. This skill covers what to do when they misbehave locally, and how
CI runs them as generated. For `robots.txt`, the sitemap, `noindex`, or
canonical hostnames, load `public-site-indexing` instead.

## Local browser-validation constraints

When a local Playwright suite is present, treat a browser-launch failure before
navigation (for example, macOS `MachPortRendezvousServer` /
`bootstrap_check_in ... Permission denied`) as an environment or
process-launch failure, not an application test failure. Preserve the exact
output. Request the narrowest available permission elevation for the exact
browser-test command; do not weaken agent-wide sandbox or host-execution policy.
If elevation is unavailable or denied, report the constraint and use equivalent
hosted CI evidence where available.

On macOS, use a temporary per-shell descriptor limit when starting a local
Next.js development server:

```sh
ulimit -n 10240 && npm run dev
```

The limit concerns `next dev`'s file watching, so it applies to any command
that starts `next dev`, including a Playwright `webServer` that runs it (check
`playwright.config.ts`), for example `ulimit -n 10240 && npx playwright test`.
An E2E suite that serves a production build does not need it.

This is a non-persistent per-shell setting. Do not add it to shell profiles,
change system limits, change CI, or alter Playwright configuration. A generated
repository owns its server lifecycle, ports, and test scripts, so follow its
local documentation before combining a manual dev server with browser tests.
`next dev` takes a lock in the project's build directory and refuses to start
a second server for the same project, so stop a manually started `next dev`
before running an E2E suite that starts its own.
If Next.js or Watchpack still reports `EMFILE: too many open files, watch`,
treat it as local host resource exhaustion. Run `npm run test:e2e:local` when that script is available.
Otherwise, run the project's normal Playwright suite with one worker, for
example `npx playwright test --workers=1`. Do not replace the default E2E
command, disable parallel CI, reduce test coverage, or alter
`playwright.config.ts` merely to accommodate a constrained host. Before
retrying, inspect any existing local listeners on the E2E ports; do not
terminate processes you cannot identify. If the raised limit does not resolve
the failure, preserve the exact output and, if present,
`.next/dev/logs/next-development.log` rather than claiming browser validation
passed.

Do not make persistent OS file-limit, watcher, or global sandbox-policy changes
solely to resolve a local validation failure. If the serial command still fails,
record the exact error and report the limitation rather than claiming the
validation passed.

Before re-running a failed local Playwright test, check `trace` and `retries`
in `playwright.config.ts`. With `trace: "on-first-retry"` and no retries
outside CI, a common setup, a local failure records nothing, because only a
retry is traced, so the attempt that already failed cannot be recovered. Re-run
with `--trace=retain-on-failure` so the next failure is traced rather than lost
too, and run with it from the start when a failure must be diagnosable the
first time. Prefer it to `--retries=1` for intermittent failures:
`on-first-retry` traces the retry, not the attempt that failed. Do not change
the Playwright configuration merely to obtain a trace.

Playwright clears its output directory (`test-results/` by default) at the
start of every run, so copy any failure output you need before re-running.
When CI retries failed tests, a test that fails and then passes on a retry is
reported as `flaky`, not failed, and the run stays green unless it is
configured to fail on flaky tests (`failOnFlakyTests`); read the report's flaky
count instead of treating a green run as proof nothing failed.

## Agent browser checks

To look at a running page yourself when `@playwright/test` is installed, use
the CLI it ships, `npx --no-install playwright cli`. Its `--help` names its
skill file under `node_modules`, which matches the installed version; read
that file for the commands. Do not install `@playwright/cli`, and do not copy
or link that skill into `.agents/skills`: a fresh checkout has no
`node_modules`, and `--adopt` deletes a `.claude/skills` link to a skill
folder that is missing.

- Pass `--browser=chromium` to `open`. The default is the branded Chrome
  channel, which the E2E setup does not install, and where Chrome is installed
  it tests a different browser than the suite does.
- Open only a local server started from this repository with its fixture or
  test data. Never a hosted or production URL, live or private data, or a real
  browser profile (`--persistent`, `--profile`, `attach --cdp`, or
  `attach --extension`).
- To inspect a failing E2E test, run it with `--debug=cli` in the background.
  It pauses the test and prints `playwright-cli attach <name>`; run that
  through `npx --no-install playwright cli`, then pass `-s=<name>` to later
  commands. The page uses the suite's own servers and sign-in, so no
  credentials are needed.
- The CLI writes snapshots, console logs, screenshots, and traces to
  `.playwright-cli/`, which `.gitignore` excludes. They are temporary
  diagnostics under the screenshot rules in `AGENTS.md`: never commit them or
  attach them to a pull request or issue, whatever the skill says about
  `gh --attach`.
- Do not run `npx playwright init-agents` or `init-skills`. The healer agent
  that `init-agents` writes marks failing tests `test.fixme()` and is told not
  to ask questions, and both write agent, skill, or MCP files outside this
  repository's layout.

## CI validation tiers

As generated, CI validates in three tiers. This repository owns
`.github/workflows/ci.yml` and `test.yml`, so check them, and the `test.yml`
call in `release-please.yml`, for its current tiers:

- **Pull requests (`ci.yml`):** fast validation (the `build` job only: production advisory audit, baseline verification, lint, format check, typecheck, unit tests, production build) with browser E2E skipped.
- **Push to `main` (`release-please.yml`):** the build suite plus a slim desktop-only Chromium E2E pass (`--project=chromium`).
- **Release Please PR merge (`chore(main): release`) or a manual dispatch of `release-please.yml`:** the full validation suite, including every Playwright project.

`test.yml` runs `npm run lint` as the scaffold defines it, and the lint baseline
requires the `lint` script in `package.json` to run `eslint --max-warnings=0`
with unused disable directives reported, which is the default since ESLint 9
(`reportUnusedDisableDirectives: "warn"`). ESLint 8 reports them only when
asked, such as with `--report-unused-disable-directives`, and a configuration
that sets the option to `"off"` reports none. Without the flag, a warning does not fail lint locally
or in CI, and without the reporting, an unused `eslint-disable` directive is no
warning at all; either way a stale baseline row only surfaces at its review
date. `create-next-app` generates a plain `eslint` script for its ESLint
option, so check the script and the ESLint configuration before treating a green
lint run as proof that no stale directive remains, and add the flag to the
script in `package.json`, the one place both local runs and CI read. Keep the
script's file target wide enough to cover every file
`scripts/verify-baselines.mjs` scans (the JavaScript and TypeScript files
outside `node_modules`, `.next` and the other directories it excludes); a
narrowed target such as `eslint src` leaves a stale directive elsewhere
unreported while its baseline row keeps passing.

## Worktrees

A worktree starts without `node_modules`, `.next`, or test output. Install
dependencies in it with `npm ci`, which reuses the shared npm cache, only when
a check needs them, and remove them with the worktree. Never copy
`node_modules`, `.next`, `test-results`, or `playwright-report` into a
verification copy.

## Sources

- `next dev` build-directory lock: Next.js 16.3.5 `dist/build/lockfile.js` and
  `setup-dev-bundler.js`, checked 2026-09-29.
- Playwright CLI: `@playwright/test` 1.64.0's `playwright cli --help`,
  `cli open --help` (`--browser`, `--persistent`, `--profile`), `cli attach
  --help` (`--cdp`, `--extension`), and `playwright test --help`
  (`--debug` modes `inspector` and `cli`); a run on 2026-10-22 where `open`
  without `--browser` looked for Google Chrome and output landed in
  `.playwright-cli/`; and `playwright-core` 1.64.0's
  `lib/tools/skills/playwright-cli/SKILL.md` (`gh --attach`) and
  `playwright` 1.64.0's `lib/agents/playwright-test-healer.agent.md`
  (`test.fixme()`), checked 2026-10-22.
- Trace modes: the `--trace` choices in Playwright 1.63.0's
  `playwright test --help`, checked 2026-09-29.
- Output directory, flaky status, and `failOnFlakyTests`: Playwright 1.63.0's
  `outputDir`, test-status, and `failOnFlakyTests` documentation, checked
  2026-09-29.
- `lint` script of a new project: `create-next-app` 16.4.2 (npm `latest`,
  published 2026-10-15), `dist/index.js`, which writes `lint: "eslint"` for the
  ESLint option, checked 2026-10-22.
- `--max-warnings` and the unused-directive default: the ESLint v9.x
  command-line reference (`--max-warnings` exits with an error status above
  the threshold) and rules reference (`reportUnusedDisableDirectives` defaults
  to `"warn"`), eslint.org/docs/v9.x, and the ESLint v9.0.0 release post
  ("Unused disable directives cause warnings by default", so earlier versions
  did not), eslint.org/blog/2024/04/eslint-v9.0.0-released, and ESLint
  10.13.0's `lib/config/default-config.js` (`reportUnusedDisableDirectives: 1`,
  that is `"warn"`), checked 2026-10-22.
