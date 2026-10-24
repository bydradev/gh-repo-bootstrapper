# Repository types

Every type gets a type-specific `README.md` starter, `AGENTS.md` and
`CLAUDE.md` (contribution guidance), `docs/current-work.md` (dated status),
`.github/pull_request_template.md` (asks for the `User-visible:` line),
`.gitignore`, `release-please-config.json`, and
`.release-please-manifest.json` seeded at `0.1.0`. Every type also gets the
agent skills and reviewer agents ([Generated agent layout](agent-layout.md)),
`pr-title-check.yml`, `release-please.yml`, `dependabot.yml` and
`docs/branch-protection-runbook.md`. The per-type lists below highlight the
additional files and README guidance for that type.

| Type | For | CI | Options |
|---|---|---|---|
| [`nextjs`](#nextjs) | Next.js applications | production audit and baselines, lint, format, typecheck, unit tests, build, Playwright e2e | `--postgres`, `--screenshots` |
| [`python`](#python) | Python packages and tools | ruff format check, ruff, mypy, pytest | none |
| [`swift`](#swift) | Xcode apps | `swift-format` lint on every PR; `xcodebuild test` on release merges | `--scheme` (required), `--destination`, `--xcodegen`, `--screenshots` |
| [`rust`](#rust) | crates and workspaces | `cargo fmt --check`, clippy, `cargo test` | none |
| [`simple`](#simple) | scripts, docs, anything without a test suite | none: Release Please only | none |

`release-please-config.json` sets `bump-minor-pre-major`, so while a repository
is below 1.0.0 a breaking change (`feat!`, `chore!` or a `BREAKING CHANGE:`
footer) proposes the next minor, 0.2.0 from the seeded 0.1.0, and not 1.0.0,
which Release Please proposes without the option. To release 1.0.0 on purpose,
merge a commit with a `Release-As: 1.0.0` footer, in a `BEGIN_COMMIT_OVERRIDE`
block so that GitHub's squash trailers do not end it (see
[Upgrading to 0.19.1](upgrading.md#upgrading-to-0191)), or remove the line before the
breaking change merges. The repository owns the file, so `--adopt` writes
it only when it is missing and keeps an existing one (see
[Upgrading to 0.17.0](upgrading.md#upgrading-to-0170)).

The pull request template belongs to the repository. `--adopt` writes it only
when the repository has no template of its own where GitHub reads one, in
`.github/`, the root or `docs/`: a `pull_request_template` file in any case
and with any extension or none, since GitHub's names are not case sensitive
and can end in `.md` or `.txt`. A symlink at `.github/pull_request_template.md`
counts as the repository's own template too when it points to a file, and
`--adopt` refuses one that does not. A `PULL_REQUEST_TEMPLATE` folder does
not count: GitHub fills a pull request from its templates only when a link
names one with the `template` query parameter, so `--adopt` adds the generated
template beside it as the default. A template that git ignores does not
count, and when git ignores `.github/pull_request_template.md`, `--adopt`
refuses it, whether it is missing or an untracked file is already there,
since neither would reach the default branch. GitHub uses an account or
organization default from a `.github` repository only when a repository has
no template, so the generated one replaces such a default. To go on using the
default, copy it into the repository as its own template
([About issue and pull request templates](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/about-issue-and-pull-request-templates),
[Creating a pull request template for your repository](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository),
[Using query parameters to create a pull request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/using-query-parameters-to-create-a-pull-request)
and [Creating a default community health file](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file),
all checked 2026-10-19).

The generated `AGENTS.md` ends with a `## Project specifics` section. Put
repository-specific rules there, below every generated section, so later
template updates can be applied without overwriting them.

## `nextjs`

Full CI pipeline for Next.js applications.

- `pr-title-check.yml`: Conventional Commits validation on PR titles, and a
  `User-visible: yes` or `User-visible: no` line in PR bodies that must agree
  with the title (see [Upgrading to 0.14.0](upgrading.md#upgrading-to-0140))
- `release-please.yml`: test → release-please; deployment remains application-owned
- `ci.yml`: runs the suite on every PR without the browser e2e lane; pushes
  to `main` add Chromium, and the Release Please merge (or a manual dispatch of
  `release-please.yml`) runs every Playwright project
- `test.yml`: reusable suite (enforced production advisory audit and baseline verification, lint, format check, typecheck, unit tests, production build, Playwright e2e)
- `baseline-review.yml`: weekly, non-blocking summary of advisory review dates and Dependabot/document parity
- `dependabot.yml`: weekly npm + GitHub Actions updates
- `.nvmrc`, `.npmrc`, `.prettierrc.json`, `.prettierignore` (which keeps Prettier off
  the three template-owned workflows); `.nvmrc` names Node 24, in Maintenance
  LTS since 2026-10-20, while Node 26 becomes Active LTS on 2026-10-28
  (`nodejs/Release` `schedule.json`, read 2026-10-22)
- `docs/lint-baseline.md`: policy and an empty table for our own inline lint/type suppressions
- `docs/advisory-baseline.md`: policy and an empty table for accepted dependency advisories
- `docs/branch-protection-runbook.md`: operational runbook for PRs blocked by required status checks
- `scripts/baseline-table.mjs`, `scripts/verify-baselines.mjs`, and `scripts/audit-production.mjs`: shared parser plus fail-closed baseline and production-audit checkers
- `scripts/*-baselines.test.mjs` and `scripts/audit-production.test.mjs`: regression tests for the baseline verifier, scheduled review, and production audit
- `README.md` and `AGENTS.md`: project starter, quality-baseline pointers, and contribution guidance

Options:

- `--postgres`: adds a PostgreSQL 16 service container to the build job
- `--screenshots`: adds the `screenshot-review` skill and
  `docs/screenshot-review.md`, for an app with a screenshot capture lane

`ci.yml` and `release-please.yml` use the canonical light-PR/full-release
caller contract. `test.yml` is necessarily scaffold-general: it retains that
`full` input and adds the optional PostgreSQL service, while each generated
application supplies its own package scripts, which must include a `lint`
script that runs `eslint --max-warnings=0` (see
[Next.js npm-script assumptions](#nextjs-npm-script-assumptions)), and any
application-owned release-triggered deployment workflow.

The `next dev` block at the top of `AGENTS.md` is the text Next.js 16.4.0 to
16.4.2 writes, under `## This is NOT the Next.js you know`; 16.3.x writes the
same two paragraphs under a level-1 heading. It was compared byte for byte with
`buildAgentRulesBlock()` in `dist/server/lib/generate-agent-files.js` of the
published `next` package on 2026-10-22 (16.4.2 was `latest`). `next dev` rewrites
a block that differs from its own version's, but only when it detects an AI
coding agent, so a repository on 16.3.x gets a one-line change to commit the
next time `next dev` runs under one. Update the template's block from that file
when a release changes it.

### Next.js npm-script assumptions

The bootstrapper intentionally does not create or patch `package.json`; that
file belongs to the application scaffold. The Next.js templates therefore
assume the scaffold supplies `dev`, `lint`, `lint:fix`, `format`, `format:check`,
`typecheck`, `test`, `audit:production`, `verify:baselines`, `review:baselines`,
`build`, and `test:e2e` scripts. The canonical set is
`bootstrap.ASSUMED_NPM_SCRIPTS`, and `validate_templates.py` verifies that each
template `npm run <script>` / `npm test` reference is declared there and that
each declared assumption is documented by a template.

This is deliberately a self-consistency check between bootstrapper-owned
artefacts, not a claim that the generated repository's external scaffold
actually provides those scripts. Changing a scaffold's scripts still requires
checking that scaffold separately.

One assumption is about what a script does, not only its name: `lint` must run
`eslint --max-warnings=0`, with unused disable directives reported. The
generated `docs/lint-baseline.md` relies on both to fail CI on an unused
`eslint-disable` directive and calls the baseline mostly self-cleaning on that
condition; without either, a stale baseline row only surfaces at its review date.
Nothing the bootstrapper generates checks either: `test.yml` runs
`npm run lint` as the scaffold defines it, `scripts/verify-baselines.mjs` does
not read `package.json` or the ESLint configuration, and the generated
`README.md`, `docs/lint-baseline.md` and `local-validation-nextjs` skill state
them as requirements. `create-next-app` does not set the flag: its generated
`lint` script is `eslint` (`create-next-app` 16.4.2, `dist/index.js`, checked
2026-10-22), and ESLint exits with an error status on warnings only when
`--max-warnings` is given ([ESLint v9.x command-line reference](https://eslint.org/docs/v9.x/use/command-line-interface#--max-warnings),
checked 2026-10-22). Reporting unused directives is the default since ESLint 9
(`linterOptions.reportUnusedDisableDirectives` defaults to `"warn"`, [ESLint v9.x
rules reference](https://eslint.org/docs/v9.x/use/configure/rules#report-unused-eslint-disable-comments);
"Unused disable directives cause warnings by default" in the [ESLint v9.0.0
release post](https://eslint.org/blog/2024/04/eslint-v9.0.0-released/); ESLint
10.13.0's `lib/config/default-config.js` sets `reportUnusedDisableDirectives: 1`,
that is `"warn"`; all checked 2026-10-22), so it holds for a new
`create-next-app` project (`eslint@^9`, and its `eslint-config-next` accepts
`eslint >=9.0.0`). ESLint 8 reports unused directives only when asked, such as
with `--report-unused-disable-directives`, and a configuration that sets the
option to `"off"` reports none. Add the flag to the scaffold's `lint` script and keep the
reporting on.

The e2e job in `test.yml` also assumes two things of the scaffold's Playwright
configuration: a project named `chromium`, which ordinary `main` pushes run
alone (`--project=chromium`), and the HTML reporter enabled in CI, which
writes the `playwright-report/` directory the job uploads. Without the HTML
reporter the upload finds nothing and is skipped silently.

## `python`

CI pipeline for Python projects.

- `pr-title-check.yml`
- `release-please.yml`: test gate → release-please (no deploy); refuses to
  tag a release merge whose own test run failed
- `ci.yml`: runs the test suite on every PR
- `test.yml`: ruff format check, ruff (lint), mypy (type check), pytest;
  fails with a clear error until the repository has a `pyproject.toml`, a
  `requirements*.txt` or a `uv.lock`, the files its pip cache hashes; installs
  a uv project from `uv.lock` with `uv sync --locked`, and otherwise
  auto-detects `requirements-dev.txt`, `requirements.txt`, or `pyproject.toml`
  with its `dev` extra and `dev` dependency group
- `dependabot.yml`: weekly GitHub Actions updates only; the generated
  `local-validation-python` skill says to add a `pip` entry once a manifest is
  committed (and `uv` instead once `uv.lock` is), since a new repository has no
  manifest for Dependabot to read
- `.python-version`
- `README.md`: project starter with a preferred `uv venv` setup and a
  standard-library `venv` alternative
- `docs/branch-protection-runbook.md`: operational runbook for PRs blocked by required status checks

Dependabot's `pip` updater stops with `Repo must contain a requirements.txt,
setup.py, setup.cfg, pyproject.toml, or a Pipfile.` until a manifest exists
([dependabot-core](https://github.com/dependabot/dependabot-core/blob/a026401a0604a43d12f04dfa4a3557ac0d5bf0bb/python/lib/dependabot/python/file_fetcher.rb),
checked 2026-10-21; GitHub's [options reference](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference)
likewise requires a manifest or lock file for each `package-ecosystem`, checked
2026-10-21), so a new Python repo gets the Actions-only config. After
committing a manifest, opt in deliberately by copying the `pip` entry, with its
semver-major holds on `ruff`, `mypy` and `pytest` and its `dev-dependencies`
group, from the generated `local-validation-python` skill or
[`templates/dependabot-python.yml`](../templates/dependabot-python.yml) into
`.github/dependabot.yml`. That file is a reference snippet; the bootstrapper
never renders it.

## `swift`

CI pipeline for Swift/Xcode projects.

- `pr-title-check.yml`
- `release-please.yml`: test gate → release-please (no deploy); refuses to
  tag a release merge whose own test run failed
- `ci.yml`: runs the `swift-format` lint on every PR; `xcodebuild test` runs
  only on the Release Please merge and on a manual dispatch of
  `release-please.yml`, because macOS runners bill at a multiple of Linux ones
- `test.yml`: `swift-format lint --recursive --strict` (formatting gate) then
  `xcodebuild test` on `macos-26`; scheme set from `--scheme`, destination
  resolved dynamically at CI time from `--destination`; with `--xcodegen`, CI
  installs pinned XcodeGen 2.46.0 and generates the project first
- `dependabot.yml`: weekly GitHub Actions updates
- `.swift-format`: Apple swift-format ruleset (default rules; `AlwaysUseLowerCamelCase`
  left on; disable it deliberately per-repo if wire-format DTOs need snake_case fields)
- `README.md`: project starter with local-development and verification sections
- `docs/branch-protection-runbook.md`: operational runbook for PRs blocked by required status checks

Requires `--scheme`. Destination defaults to `iphone` (an available iPhone
simulator, picked dynamically in CI); pass `--destination ipad` for an iPad
simulator or `--destination macos` for a macOS destination. Pass
`--screenshots` for an app with a screenshot capture lane: it adds the
`screenshot-review` skill and `docs/screenshot-review.md`.

Pass `--xcodegen` when `project.yml` will be the source of truth and generated
`.xcodeproj` output should stay out of git. The generated `AGENTS.md` explains
the local Xcode workflow. Swift package declarations inside XcodeGen manifests
are not supported by Dependabot, so a new Swift repo gets the Actions-only
config; after adding a root `Package.swift` or another supported Swift manifest,
opt in deliberately by copying [`templates/dependabot-swift.yml`](../templates/dependabot-swift.yml)
over `.github/dependabot.yml`. That file is a reference snippet; the
bootstrapper never renders it.

Formatting is enforced from the first commit: `test.yml` fails CI on any
`swift-format lint --recursive --strict` violation, and the generated
`AGENTS.md` tells agents to run
`xcrun swift-format format --recursive --in-place .` after editing Swift files
and to check before pushing.

## `rust`

CI pipeline for Rust crates and workspaces.

- `pr-title-check.yml`
- `release-please.yml`: test gate → release-please (no deploy); refuses to
  tag a release merge whose own test run failed
- `ci.yml`: runs the test suite on every PR
- `test.yml`: `cargo fmt --check`, `cargo clippy -D warnings`, and
  `cargo test` across the workspace; fails with a clear error until a root
  `Cargo.toml` exists
- `dependabot.yml`: GitHub Actions updates only; the generated
  `local-validation-rust` skill says to add a `cargo` entry once `Cargo.toml`
  is committed, since a new repository has no manifest for Dependabot to read
- `.gitignore`: adds Cargo's `/target/` build output
- `README.md`: project starter with rustup setup and the CI commands
- `docs/branch-protection-runbook.md`: operational runbook for PRs blocked by required status checks

Release Please uses the `simple` release type, as for Python and Swift: it
maintains the changelog, tags, and releases but does not edit `Cargo.toml`
versions. The generated `local-validation-rust` skill explains when to move to
the `rust` release type or the `cargo-workspace` plugin.

The bootstrapper does not run `cargo init` or choose a crate layout. The
generated `local-validation-rust` skill tells agents to share one
`CARGO_TARGET_DIR` per repository across worktrees, so each worktree does not
build its own multi-gigabyte `target/`. It lives beside those worktrees and is
deleted with the last of them.

## `simple`

Release Please only, suitable for scripts, docs, or any project without a
test suite.

- `pr-title-check.yml`
- `release-please.yml`: single-job, no test gate
- `dependabot.yml`: GitHub Actions updates only
- `README.md`: concise project starter and navigation guide
- `docs/branch-protection-runbook.md`: operational runbook for PRs blocked by required status checks

## Deployments

The previous provider-deployment flags are rejected as unknown options. The
bootstrapper no longer generates or configures provider deployments. Add a
reviewed, application-owned deployment workflow after choosing a provider; keep
it separate from `release-please.yml`.
