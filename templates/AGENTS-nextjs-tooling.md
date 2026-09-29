
## Local browser-validation constraints

When a local Playwright suite is present, treat a browser-launch failure before
navigation — for example, macOS `MachPortRendezvousServer` /
`bootstrap_check_in ... Permission denied` — as an environment or
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

The limit concerns `next dev`'s file watching. When the repository's E2E
suite serves a production build instead of `next dev`, it is not an E2E
requirement.

This is a non-persistent per-shell setting. Do not add it to shell profiles,
change system limits, change CI, or alter Playwright configuration. A generated
repository owns its server lifecycle, ports, and test scripts, so follow its
local documentation before combining a manual dev server with browser tests.
`next dev` takes a lock in the project's build directory and refuses to start
a second server for the same project, so stop a manually started `next dev`
before running an E2E suite that starts its own (checked against Next.js
16.3.5's `dist/build/lockfile.js` and `setup-dev-bundler.js`, 2026-09-29).
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

Check the trace settings before re-running a failed local Playwright test. A
common configuration — `trace: "on-first-retry"` with no retries outside CI —
records nothing for a local failure, because only a retry is traced, so the
attempt that already failed cannot be recovered. Re-run with
`--trace=retain-on-failure` so the next failure is traced rather than lost too,
and run with it from the start when a failure must be diagnosable the first
time. Prefer it to `--retries=1` for intermittent failures: `on-first-retry`
traces the retry, not the attempt that failed. Do not change the Playwright
configuration merely to obtain a trace (trace modes checked against the
`--trace` choices in Playwright 1.63.0's `playwright test --help`, 2026-09-29).

Playwright clears its output directory (`test-results/` by default) at the
start of every run, so copy any failure output you need before re-running.
When CI retries failed tests, a test that fails and then passes on a retry is
reported as `flaky`, not failed, and the run stays green unless it is
configured to fail on flaky tests (`failOnFlakyTests`); read the report's flaky
count instead of treating a green run as proof nothing failed (checked against
Playwright 1.63.0's `outputDir`, test-status, and `failOnFlakyTests`
documentation, 2026-09-29).

## Tooling
Run all checks before pushing:

```sh
npm run lint          # ESLint
npm run format:check  # Prettier
npm run typecheck     # TypeScript
npm test              # unit/integration tests
npm run audit:production  # runtime advisory floor; requires network access
npm run verify:baselines  # lint/advisory baseline parity
npm run build         # Next.js production build
npm run test:e2e      # Playwright e2e
```

`npm run lint:fix` auto-fixes ESLint violations; `npm run format` auto-fixes
Prettier formatting issues.

In CI, automated validation runs in three tiers:
- **Pull requests (`ci.yml`):** Runs fast validation (`build` only: lint, format, typecheck, unit tests, verify baselines, production build) with browser E2E skipped for rapid feedback (< 2 mins).
- **Push to `main` (`release-please.yml`):** Runs the build suite plus a slim desktop-only Chromium E2E pass (`--project=chromium`).
- **Release Please PR merge (`chore(main): release`):** Runs the full validation suite, including the complete browser E2E matrix and any configured production/runtime checks.

Always run the relevant checks locally before pushing. For changes that alter browser-facing UI or user interactions, run `npm run test:e2e` locally (or `npm run test:e2e:local` when that script is available) before opening or updating a PR.

A worktree starts without `node_modules`, `.next`, or test output. Install
dependencies in it with `npm ci`, which reuses the shared npm cache, only when
a check needs them, and remove them with the worktree. Never copy
`node_modules`, `.next`, `test-results`, or `playwright-report` into a
verification copy.
