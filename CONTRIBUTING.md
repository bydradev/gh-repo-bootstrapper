# Contributing

Bug reports, feature requests, questions and pull requests are all welcome.
Everyone taking part follows the [code of conduct](CODE_OF_CONDUCT.md).

## Issues

Open an issue with the form that fits. Describe the behaviour you saw or want;
a suggested fix is welcome too. Please leave out generated files, `.env`
contents, tokens and repository configuration: paths and behaviour are what
help.

Security issues go through private reporting instead; see
[SECURITY.md](SECURITY.md).

## Pull requests

1. For anything bigger than a small fix, open an issue first so the approach
   can be agreed before you write it.
2. Make one change per pull request. Pull requests are squash-merged, and the
   title becomes the changelog entry, so it must be a
   [Conventional Commit](https://www.conventionalcommits.org) subject such as
   `fix: keep the full key when prompting`. A check enforces this.
3. Answer the pull request template's `User-visible:` line with `yes` if a
   release brings the change to users (a `feat`, `fix`, `perf` or `revert`
   title, or a breaking change) or `no` if it does not (`docs`, `chore`,
   `refactor`, `test`, `build` or `ci`). The same check fails when the line is
   missing or disagrees with what Release Please will do with the title and
   body.
4. Run the checks listed under "Tooling" in [AGENTS.md](AGENTS.md) before you
   push, and add or update tests for the behaviour you change.
   [docs/development.md](docs/development.md) covers the setup and what CI
   runs.
5. If an AI tool helped write a commit, add the `Co-Authored-By:` trailer
   that [AGENTS.md](AGENTS.md) describes. You are still responsible for the
   change.

The maintainer reviews every pull request and decides whether it is merged.
Workflows on a first-time contributor's pull request may need the maintainer's
approval before they run.

## Licence of contributions

The repository has three licences, split by path:

- Everything under [`templates/`](templates/) is
  [MIT-0](templates/LICENSE). These files are copied into the repositories
  `bootstrap.py` creates, and MIT-0 lets their owners use them without keeping
  any notice or attribution.
- Everything else is [Apache-2.0](LICENSE), except
  [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md), which is adapted from the
  Contributor Covenant and keeps its CC BY-SA 4.0 licence.

A contribution is made under the licence of the path it changes. Changes
under `templates/` are contributed under MIT-0, changes to `CODE_OF_CONDUCT.md`
under CC BY-SA 4.0, and all other changes under Apache-2.0, as its section 5
provides.

## Forking

All three licences permit forking, modification and redistribution, including
commercially, on their own terms. This file governs only what is merged back.

## Maintainer workflow

[AGENTS.md](AGENTS.md) documents the branch, commit and release conventions the
maintainer and AI assistants follow in this repository. Contributors follow the
same commit and pull request conventions.
