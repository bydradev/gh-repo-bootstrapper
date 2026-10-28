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

None of the fixes below may become a persistent change: no shell-profile,
OS file-limit, watcher, sandbox-policy, CI or Playwright-configuration
change made only to get a local run through or a trace, and no change to
the default E2E command, CI parallelism or coverage. When a fix does not work, keep the
exact output and report the limitation instead of claiming the run passed.

- **Browser launch fails before navigation** (for example macOS
  `MachPortRendezvousServer` / `bootstrap_check_in ... Permission denied`):
  an environment failure, not a test failure. Ask for the narrowest
  elevation for that exact command; if it is unavailable or denied, use
  hosted CI evidence where it exists.
- **macOS and `next dev`:** prefix any command that starts `next dev`,
  including a Playwright `webServer` that runs it (check
  `playwright.config.ts`), with `ulimit -n 10240 &&` in the same shell. An
  E2E suite that serves a production build does not need it. `next dev`
  locks the build directory, so stop a manually started `next dev` before
  an E2E suite that starts its own, and follow the repository's own docs on
  ports and server lifecycle.
- **`EMFILE: too many open files, watch`** despite the raised limit: run
  `npm run test:e2e:local` when that script is available, otherwise
  `npx playwright test --workers=1`. Check existing listeners on the E2E
  ports first and never stop a process you cannot identify; keep
  `.next/dev/logs/next-development.log` if present.

Before re-running a failed local Playwright test, check `trace` and
`retries` in `playwright.config.ts`. With `trace: "on-first-retry"` and no
local retries, a common setup, a local failure records nothing, so re-run
with `--trace=retain-on-failure` (from the start when the first failure
must be diagnosable) rather than `--retries=1`, which traces only the
retry. Playwright clears `test-results/` at the start of every run: copy
what you need first. On CI, a test that fails and then passes on a retry is
reported as `flaky`, not failed, and the run stays green unless
`failOnFlakyTests` is set: read the flaky count.

## Agent browser checks

To look at a running page yourself when `@playwright/test` is installed, use
the CLI it ships, `npx --no-install playwright cli`. Read its commands in
`node_modules/playwright-core/lib/tools/skills/playwright-cli/SKILL.md`,
which matches the installed version; `--help` prints that path only under
Claude Code or Copilot CLI. Older versions, such as 1.60, ship no such skill:
when the file is missing or `npx --no-install playwright cli --help` fails,
report that instead of installing or upgrading a package to follow this
section. Do not install `@playwright/cli`, and do not copy or link that skill
into `.agents/skills`: a fresh checkout has no `node_modules`, and `--adopt`
deletes a `.claude/skills` link to a skill folder that is missing.

- Name a session of your own with `-s=<name>` on `open` and every later
  command. Without it, every agent in the checkout shares the `default`
  session, and a second `open` replaces the browser another agent is using.
- Pass `--browser=chromium` to `open`, which `--help` does not list but the
  CLI accepts as Playwright's own Chromium. The default is the branded Chrome
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
  credentials are needed. Stop the run when you are done: it keeps the
  suite's server, and any `next dev` lock, alive.
- The CLI writes snapshots, console logs, screenshots, and traces to
  `.playwright-cli/`, which `.gitignore` excludes because they can hold
  session data. Leave out `--filename`, or start it with `.playwright-cli/`:
  a named file is written relative to the repository root, outside that
  folder. Never commit them. Attach a screenshot to a pull request or
  issue only as the screenshot rules in `AGENTS.md` allow, after their privacy
  review, never because the skill suggests `gh --attach`.
- Do not run `npx playwright init-agents`, `init-skills`, or
  `playwright cli install`. The healer agent that `init-agents` writes marks
  failing tests `test.fixme()` and is told not to ask questions, and all three
  write agent, skill, or MCP files outside this repository's layout.

## CI validation tiers

As generated, CI validates in three tiers. This repository owns
`.github/workflows/ci.yml` and `test.yml`, so check them, and the `test.yml`
call in `release-please.yml`, for its current tiers:

- **Pull requests (`ci.yml`):** fast validation (the `build` job only: production advisory audit, baseline verification, lint, format check, typecheck, unit tests, production build) with browser E2E skipped.
- **Push to `main` (`release-please.yml`):** the build suite plus a slim desktop-only Chromium E2E pass (`--project=chromium`).
- **Release Please PR merge (`chore(main): release`) or a manual dispatch of `release-please.yml`:** the full validation suite, including every Playwright project.

`test.yml` runs `npm run lint` as the scaffold defines it, and the lint baseline
requires the `lint` script in `package.json` to run `eslint --max-warnings=0`
with unused disable directives reported (the default from ESLint 9; ESLint 8
needs `--report-unused-disable-directives`, and a configuration that turns the
option off reports none), over every file `scripts/verify-baselines.mjs`
scans. Otherwise a stale baseline row keeps passing until its review date.
`create-next-app` writes a plain `eslint` script, so check the script and the
configuration, and add the flag in `package.json`, which local runs and CI
both read.

## Worktrees

A worktree starts without `node_modules`, `.next`, or test output. Install
dependencies in it with `npm ci`, which reuses the shared npm cache, only when
a check needs them, and remove them with the worktree. Never copy
`node_modules`, `.next`, `test-results`, or `playwright-report` into a
verification copy.

## Sources

- `next dev` build-directory lock: Next.js 16.4.2 `dist/build/lockfile.js`,
  checked 2026-10-22.
- Playwright CLI commands, flags, sessions and output paths: `@playwright/test`
  and `playwright-core` 1.64.0 help output, source and runs, checked 2026-10-22.
- Trace modes, `outputDir`, flaky status and `failOnFlakyTests`: Playwright
  1.64.1 `playwright test --help` and type docs, checked 2026-10-22.
- The `lint` script `create-next-app` writes: `create-next-app` 16.4.2,
  checked 2026-10-22.
- `--max-warnings` and the unused-directive default: ESLint v9 docs and v9.0.0
  release post, and ESLint 10.13.0's default config, checked 2026-10-22.
