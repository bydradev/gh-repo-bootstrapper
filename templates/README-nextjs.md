# __REPOSITORY_NAME__

> A Next.js project bootstrapped with GitHub Actions, Release Please, and
> Dependabot. Replace this sentence with the product’s purpose and intended users.

| Detail | Value |
|---|---|
| Status | Initial setup |
| Repository type | Next.js |

## Start here

The bootstrapper supplies repository automation but does not create or patch
`package.json`. Add the application scaffold and its project-specific setup
instructions before shipping.

The scaffold's `lint` script must run `eslint --max-warnings=0`, so that any
warning fails `npm run lint`, and ESLint must report unused disable directives,
which is the default since ESLint 9 (`reportUnusedDisableDirectives: "warn"`).
The [lint baseline](docs/lint-baseline.md) relies on both to fail CI on a stale
`eslint-disable` directive; without either, a stale baseline row only surfaces
at its review date. The script's file target must cover every file
`scripts/verify-baselines.mjs` scans (the JavaScript and TypeScript files
outside `node_modules`, `.next` and the other directories it excludes): a
narrowed target such as `eslint src` leaves a stale directive elsewhere
unreported.

## Local development

Once the application scaffold is in place, install its locked dependencies and
start the local server:

```sh
npm ci
npm run dev
```

On macOS, use a temporary per-shell descriptor limit before starting a Next.js
development server to avoid Watchpack `EMFILE` failures:

```sh
ulimit -n 10240 && npm run dev
```

Do not add this setting to a shell profile or make a persistent system-limit
change. Browser-test commands, ports, and server lifecycle are application
specific; document them with the application scaffold.

## Verification

Once the application scaffold is in place, install Chromium once per machine,
then run these checks locally before pushing:

```sh
npx playwright install chromium  # CI adds --with-deps for the bare Linux runner
npm run audit:production
npm run verify:baselines
npm run lint
npm run format:check
npm run typecheck
npm test
npm run build
npm run test:e2e
```

CI runs them in three tiers. Pull requests run every check above except the
browser suite. Ordinary pushes to `main` add the Chromium browser project. The
Release Please merge runs the full suite, including every Playwright project.
A green pull request therefore does not mean the browser suite passed; run
`npm run test:e2e` locally for changes to browser-facing UI or interactions.

`npm run lint:fix` and `npm run format` fix lint and formatting.

The generated `.prettierignore` keeps Prettier off the three workflows the
bootstrapper owns: `pr-title-check.yml`, `release-please.yml` and
`baseline-review.yml`. They must stay verbatim, because a reformatted copy
counts as a local edit and `--adopt` stops replacing it. `ci.yml` and
`test.yml` belong to this repository and stay formatted.

## Deployment

Deployment is application-owned. The generated `release-please.yml` only tests
and creates releases; add any provider-specific deployment workflow separately,
preferably as a release-triggered workflow after the application and provider
configuration have been reviewed.

## Quality baselines

The [lint baseline](docs/lint-baseline.md) records justified code suppressions; the
[advisory baseline](docs/advisory-baseline.md) records accepted dependency advisories with reasons
and review dates. Both are automatically enforced as blocking checks; see [AGENTS.md](AGENTS.md) for
the contribution process.

## Project guide

- `AGENTS.md`: branch, commit, pull-request, and validation workflow.
- `docs/branch-protection-runbook.md`: how to unblock required GitHub checks.
