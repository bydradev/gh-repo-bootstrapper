# gh-repo-bootstrapper

A Python script that creates standardised GitHub repositories: CI
workflows, Release Please, Dependabot, an `AGENTS.md` and skills for coding
agents, and the GitHub settings that hold them together. It keeps existing
repositories in line with later templates too.

- **Five repository types:** `nextjs`, `python`, `swift`, `rust` and
  `simple` (release only), each with its own CI.
- **GitHub settings:** squash-merge only, branch protection on `main`, a
  restricted Actions policy with SHA-pinned actions, and Release Please on its
  own GitHub App.
- **Agent instructions:** a short `AGENTS.md` hub with the safety gates and a
  `## Project specifics` section that belongs to the repository, skills for
  the detailed procedures, and a separate reviewer agent with no edit tools.
- **Updates:** `--check` reports how a repository differs from the current
  templates, and `--adopt` brings it in line without touching what the
  repository owns.

## Requirements

- Python 3.11 or newer. `bootstrap.py` uses the standard library only, so
  nothing needs installing.
- The [GitHub CLI](https://cli.github.com/), signed in (`gh auth login`).
- git.

## Usage

```sh
./bootstrap.py
```

With no arguments the script asks for the repository name, type, owner,
visibility and the type's options, then confirms before creating anything.
A name whose folder already exists and is not empty, or whose path has a
file or a broken symbolic link where a folder belongs, is refused straight
away, before the other questions. Pressing Enter at a numbered question that
has a default, such as the Swift destination, takes it.

Among the questions are the two values Release Please's
[GitHub App](docs/github-settings.md#github-app-for-release-please) needs.
After you confirm, the script creates the repository on GitHub, pushes the
generated files, and applies the [GitHub settings](docs/github-settings.md),
storing those two values with them.

### Flags

| Flag | Description |
|---|---|
| `--name TEXT` | Repository name (lowercase letters, digits, hyphens), or a relative/absolute path ending in one; created in the current directory by default |
| `--type nextjs\|python\|swift\|rust\|simple` | Repository type |
| `--org TEXT` | GitHub org or user (default: authenticated user) |
| `--private` / `--public` | Visibility (default: private) |
| `--postgres` | Add PostgreSQL 16 service to test workflow (nextjs only) |
| `--scheme TEXT` | Xcode scheme name for `xcodebuild test` (swift only) |
| `--destination iphone\|ipad\|macos` | Target destination for `xcodebuild test` (swift only, default: iphone) |
| `--xcodegen` | Generate the Xcode project from `project.yml` in Swift CI |
| `--screenshots` | Add the `screenshot-review` skill and `docs/screenshot-review.md`, for a repository with a screenshot capture lane (nextjs and swift only) |
| `--configure-only` | Apply GitHub config to an existing repo, skip file generation. Leaves branch protection unchanged and asks before changing the Actions policy, pull request creation, Dependabot alerts, secret scanning or CodeQL default setup (see [GitHub settings](docs/github-settings.md)). Cannot be combined with `--dry-run` |
| `--dry-run` | Print all files that would be created without doing anything. The owner lookup is skipped in dry-run: without `--org`, an interactive run asks for the owner, and a `--non-interactive` run uses a placeholder owner, since nothing downstream contacts GitHub. Piping the output to `head` or a pager is fine: the run ends quietly with exit 0 when the reader closes the pipe, and with an error status when a `--non-interactive` run's options are refused |
| `--non-interactive` | Fail instead of prompting for missing options |
| `--check PATH` | Compare an existing local repository with the current templates; read-only, exits 1 on drift (also when the reader of its output closes the pipe early). Needs `--type` and the type options the repository was generated with |
| `--adopt PATH` | Bring an existing local repository in line without contacting GitHub (see [Existing repositories](docs/existing-repositories.md)) |
| `--replace-generated-sections` | With `--adopt`: also replace `AGENTS.md` generated sections whose text differs from the template |

### Examples

```sh
# Fully interactive
./bootstrap.py

# Next.js app: preview files before creating
./bootstrap.py --name my-dashboard --type nextjs --dry-run

# Next.js with PostgreSQL tests in an org
./bootstrap.py --name data-app --type nextjs --postgres --org my-org

# Next.js app with a screenshot capture lane
./bootstrap.py --name my-site --type nextjs --screenshots

# Python library
./bootstrap.py --name my-tool --type python --public

# Rust service or library
./bootstrap.py --name my-service --type rust

# Swift iOS app
./bootstrap.py --name my-app --type swift --scheme MyApp

# Swift macOS app
./bootstrap.py --name my-mac-app --type swift --scheme MyMacApp --destination macos

# Swift macOS app whose Xcode project is generated and not committed
./bootstrap.py --name my-mac-app --type swift --scheme MyMacApp --destination macos --xcodegen

# Simple release-only repo
./bootstrap.py --name docs-site --type simple --org my-org --public

# Apply the GitHub settings to an existing repo
./bootstrap.py --name my-app --type nextjs --configure-only

# Compare an existing local repository with the current templates, then adopt them
./bootstrap.py --check ../my-app --type nextjs
./bootstrap.py --adopt ../my-app --type nextjs
```

### Non-interactive mode

All prompts can be bypassed by combining `--non-interactive` with the
relevant flags. The optional features `--postgres`, `--xcodegen` and
`--screenshots` stay off unless their flag is passed; an interactive run asks
about each, with No as the default. The Release Please App's values are read
from environment variables:

| Environment variable | Used when |
|---|---|
| `RELEASE_PLEASE_CLIENT_ID` | always |
| `RELEASE_PLEASE_APP_KEY` | always |

Example (CI/CD usage):

```sh
export RELEASE_PLEASE_APP_KEY="$(cat path/to/app-key.pem)"
export RELEASE_PLEASE_CLIENT_ID="..."
./bootstrap.py \
  --name my-app \
  --type python \
  --org my-org \
  --private \
  --non-interactive
```

## Repository types

| Type | For | CI | Options |
|---|---|---|---|
| `nextjs` | Next.js applications | production audit and baselines, lint, format, typecheck, unit tests, build, Playwright e2e | `--postgres`, `--screenshots` |
| `python` | Python packages and tools | ruff format check, ruff, mypy, pytest | none |
| `swift` | Xcode apps | `swift-format` lint on every PR; `xcodebuild test` on release merges | `--scheme` (required), `--destination`, `--xcodegen`, `--screenshots` |
| `rust` | crates and workspaces | `cargo fmt --check`, clippy, `cargo test` | none |
| `simple` | scripts, docs, anything without a test suite | none: Release Please only | none |

Every type also gets a README starter, `AGENTS.md` and `CLAUDE.md`, the
agent skills, `docs/current-work.md`, a pull request template, the PR title
check, Release Please and Dependabot. The bootstrapper does not create the
application itself (no `package.json`, `cargo init` or Xcode project) or any
deployment. [Repository types](docs/repository-types.md) lists every file per
type and what each type assumes of the application.

## Existing repositories

`bootstrap.py` generates a repository once; `--check` and `--adopt` bring an
existing local checkout in line with later templates. Neither contacts
GitHub. `--check` is read-only and exits 1 on drift. `--adopt` writes missing
files, updates files nobody edited since an earlier release wrote them (the
template-owned files, which carry a stamp, and the `nextjs` baseline
scripts), rebuilds `AGENTS.md` around the repository's
`## Project specifics`, and keeps a managed block of `.gitignore` (and of
`.prettierignore` in `nextjs`) in step, adding it at the end when it is
missing and leaving every line outside it as it is. It never overwrites a
file the repository edited.
Pass the `--type` and type options the repository was generated with.

Before adopting a new release, read its notes in
[Upgrading](docs/upgrading.md). [Existing repositories](docs/existing-repositories.md)
covers the report, what `--adopt` writes and refuses, and the template-owned
files.

## Documentation

- [Repository types](docs/repository-types.md): the files and CI each type
  gets, its options, and what it assumes of the application.
- [GitHub settings](docs/github-settings.md): what the script configures on
  GitHub, and the GitHub App Release Please runs as.
- [Generated agent layout](docs/agent-layout.md): the `AGENTS.md` hub, the
  skills, the reviewer agents, and why the hub is short.
- [Existing repositories](docs/existing-repositories.md): `--check`,
  `--adopt`, and the template-owned files.
- [Upgrading](docs/upgrading.md): what each release asks of an existing
  repository.
- [Branch protection runbook](docs/branch-protection-runbook.md): unblocking
  a pull request held by required checks or unresolved conversations. Every
  generated repository gets a copy.
- [Development](docs/development.md): working on the bootstrapper, its
  validator and its CI.
- [Current work](docs/current-work.md): dated status and decisions.
- [Changelog](CHANGELOG.md).

## Contributing

Issues and pull requests are welcome, under the
[code of conduct](CODE_OF_CONDUCT.md). Every commit in a pull request needs a
Developer Certificate of Origin sign-off (`git commit -s`). See
[`CONTRIBUTING.md`](CONTRIBUTING.md) for the steps, [Development](docs/development.md)
for the setup and checks, and [`AGENTS.md`](AGENTS.md) for the branch, commit
and release conventions.

## License

`bootstrap.py`, the validator, the tests and the docs are licensed under the
[Apache License 2.0](LICENSE).
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) is adapted from the Contributor
Covenant 3.0 and keeps its CC BY-SA 4.0 licence.

The files under [`templates/`](templates/) are licensed under
[MIT-0](templates/LICENSE) (`SPDX-License-Identifier: MIT-0`). The files
`bootstrap.py` generates from them belong to the repository they are written
into: use, change and relicense them as you like, with no notice or
attribution to keep.
