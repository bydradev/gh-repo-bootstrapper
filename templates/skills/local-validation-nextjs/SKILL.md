---
name: local-validation-nextjs
description: Use before local Next.js checks, builds, dev servers, Playwright E2E or browser inspection.
---

# Local validation for Next.js

If `## Project specifics` in `AGENTS.md` names a repository-owned validation
skill, load it first; where it is narrower, it governs.

Find pre-push commands under `## Tooling` in
`AGENTS.md`. For `robots.txt`, the sitemap, `noindex`, or
canonical hostnames, load `public-site-indexing` instead.

## Local browser-validation constraints

Keep workarounds local to the command. Leave shell profiles, OS limits, watchers,
sandbox policy, Playwright config, default E2E commands, CI configuration
(including parallelism) and coverage intact. If blocked, report the exact error.

- **Launch denied before navigation.** For sandbox errors such as
  `MachPortRendezvousServer` permission denied, request the narrowest elevation for the
  exact browser command. If unavailable or denied, use equivalent hosted CI
  evidence where available and report the local launch failure.
- **Starting `next dev` on macOS.** Prefix the command with
  `ulimit -n 10240 &&` in the same shell, including when Playwright starts
  `next dev` via `webServer` in `playwright.config.ts`. Production builds
  need no prefix. Follow the repository's port and server instructions and
  stop a manually started `next dev` before the suite starts its own.
- **Still seeing `EMFILE: too many open files, watch`?** Check E2E port
  listeners first. Never stop an unidentified process. Keep
  `.next/dev/logs/next-development.log` if present. Run
  `npm run test:e2e:local` when that script is available, otherwise
  `npx playwright test --workers=1`.
- **Need a trace of a failure?** Before rerunning, save relevant artifacts
  from Playwright's output directory (default `test-results/`), which the
  next run clears. Check `trace` and `retries` in `playwright.config.ts`.
  With `on-first-retry`, zero retries gives no trace and `--retries=1`
  traces only the retry. Use `--trace=retain-on-failure` from the first
  attempt you need to diagnose.
- **Passed on retry in CI?** The test is reported as `flaky`, not failed.
  Check the flaky count even on a green run. `failOnFlakyTests` makes these
  results fail the run.

## Agent browser checks

With `@playwright/test` installed, use the CLI it ships, `npx --no-install playwright cli`.
Read `node_modules/playwright-core/lib/tools/skills/playwright-cli/SKILL.md`.
If it is missing or `npx --no-install playwright cli --help` fails, report
the limitation. Do not install or upgrade packages for this, including
`@playwright/cli`. Keep the installed skill out of `.agents/skills`, including
symlinks. A fresh checkout lacks dependencies and adoption removes dangling
skill mirrors.

- Open only a local server started from this repository with fixture or test
  data. Exclude hosted URLs, live or private data and real browser profiles
  (`--persistent`, `--profile`, `attach --cdp`, `attach --extension`).
- Name a session of your own with `-s=<name>` on `open` and every later
  command to avoid replacing another browser. Pass `--browser=chromium` to
  `open` for the suite's Chromium.
- To inspect a failing test, run it in the background with `--debug=cli`.
  When it pauses, use `npx --no-install playwright cli attach <name>` with
  the printed name, then `-s=<name>` for later commands. Attaching reuses the
  test's session without a separate sign-in. Stop the test afterward to release
  its server and any dev lock.
- Keep snapshots, console logs, screenshots and traces in the ignored
  `.playwright-cli/` directory. Omit `--filename` or prefix its value with
  `.playwright-cli/`. Never commit them. Attach screenshots only when the
  rules in `AGENTS.md` allow it and privacy review has passed, even if the
  CLI suggests `gh --attach`.
- Do not run `npx playwright init-agents`, `init-skills`, or
  `playwright cli install`. They write agent or tool configuration outside
  the repository's layout.

## CI validation tiers

Check the repository-owned `.github/workflows/ci.yml` and
`.github/workflows/test.yml`, and the caller in `release-please.yml`.
As generated:

- **PR or ordinary push to `main`.** Only `build` runs the production audit,
  baseline verification, lint, format check, typecheck, unit tests and production
  build. Browser E2E is skipped. A newer ordinary push cancels the prior
  ordinary push's tests.
- **Release merge on `main` (`chore(main): release`) or manual dispatch of
  `release-please.yml`.** Run `build` and every Playwright project. Later pushes
  do not cancel this run.

The baseline requires the `lint` script in `package.json` to run `eslint --max-warnings=0`
with unused disable directives reported across every file
`scripts/verify-baselines.mjs` scans. Check the scaffold's script and ESLint
config. For ESLint 8, add `--report-unused-disable-directives`.

## Worktrees

Run `npm ci` in the worktree when a check needs dependencies. It reuses the
shared npm cache. Remove the installation with the worktree.
Never copy `node_modules`, `.next`, `test-results`, or `playwright-report`
into a verification copy.

## Sources

- `next dev` build-directory lock: Next.js 16.4.2 `dist/build/lockfile.js`,
  checked 2026-10-22.
- Playwright CLI commands, flags, sessions and output paths: `@playwright/test`
  and `playwright-core` 1.64.0 help output, source and runs, checked 2026-10-22.
- The CLI's skill file: absent from `playwright-core` 1.58.2 and 1.60.0
  (no `lib/tools/skills/`), present from 1.62.0, checked 2026-10-22.
- Trace modes, `outputDir`, flaky status and `failOnFlakyTests`: Playwright
  1.64.1 `playwright test --help` and type docs, checked 2026-10-22.
- The `lint` script `create-next-app` writes: `create-next-app` 16.4.2,
  checked 2026-10-22.
- `--max-warnings` and the unused-directive default: ESLint v9 docs and v9.0.0
  release post, and ESLint 10.13.0's default config, checked 2026-10-22.
