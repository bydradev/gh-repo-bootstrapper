# Security policy

## Reporting a vulnerability

GitHub private vulnerability reporting is the sole security channel for this
repository. Open the repository's **Security** tab and choose **Report a
vulnerability**. Do not open a public issue for anything exploitable or for
information that would make exploitation easier.

A proof of concept may be included in the private advisory when it is needed
to reproduce and confirm the report. A suggested fix is welcome there too. A
fix that is merged follows [`CONTRIBUTING.md`](CONTRIBUTING.md).

The maintainer reads and answers reports as time allows, best effort, with
no set response time, and keeps the reporter updated in the advisory until
the report is fixed or declined.

## Supported versions

Security fixes land on `main` and ship in the next release; earlier releases
get no backports. A repository the bootstrapper created or adopted keeps the
template files it was given, so it has a fixed template only once it runs
`bootstrap.py --check` and `--adopt` from a copy checked out at that
release's tag, as [`docs/upgrading.md`](docs/upgrading.md) describes. The advisory for a fixed
vulnerability is published with the release that fixes it and names that
release.

## Scope

`bootstrap.py` runs locally, on the machine of whoever runs it, under their
own authenticated `gh` CLI session. It has no server component and stores no
credentials. It reads GitHub App secrets from prompts
or environment variables and passes them to `gh` over stdin (never as
command-line arguments, so they stay out of the process list).

The most useful things to report:

- A path where a secret is written to disk, logged, or passed as an argv element.
- A generated workflow that grants more `GITHUB_TOKEN` scope than it needs, is
  triggerable by an untrusted fork PR, or interpolates untrusted input into a
  `run:` block.
- Repository configuration applied by `configure_repo()` that is weaker than
  [GitHub settings](docs/github-settings.md) describes.

Findings in the *generated* templates matter as much as findings in the
bootstrapper: those files are copied into every repository this tool creates.
