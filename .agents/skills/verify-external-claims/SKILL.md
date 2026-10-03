---
name: verify-external-claims
description: >-
  Use before asserting what a platform, API, dependency, or tool can or cannot do, contradicting the user or repository docs, relying on version-sensitive behaviour (limits, defaults, pricing, deprecations), using external documentation or services, or writing such a claim into a commit, PR, or document. Covers verifying against current primary sources and citing source and date.
---
<!-- gh-repo-bootstrapper: template-owned; sha256=74d40b01b8869ad0b78483518843cadd77f750769f3bc84aac25445e1945eb51 -->

# Verifying external claims

## Recall is not evidence

Training knowledge has a cutoff; the platforms and dependencies this
repository touches do not. A belief formed before the cutoff feels exactly as
certain as one formed from evidence, so confidence is not a signal that
verification can be skipped — prefer running the cheap check to publishing the
hedge, and where a claim must still rest on recall, say so rather than
asserting it flatly.

Verify against a current primary source, rather than relying on recall, for:

- **Any claim about what a platform, API, or dependency can or cannot do.**
  This runs in both directions. A universal negative — "there is no setting
  for that", "the API does not support it" — cannot be established from memory
  or from partial observation. Equally, a capability, flag, default, or
  pricing tier recalled as existing may since have been renamed, deprecated,
  or never shipped at all. Absence of recall is not evidence of absence, and
  presence of recall is not evidence of existence.
- **Any claim that contradicts the user, this repository's documentation, or
  its existing configuration.** Those reflect decisions made with context and
  intent that may not be visible here. Establish the contradiction positively
  before acting on it, and report it as a finding to check rather than a
  correction to apply.
- **Version-sensitive behaviour**: limits, defaults, pricing, deprecations,
  and API shapes for external platforms and dependencies.

When inspecting a system to determine whether it supports something, retrieve
the full response and read it, rather than querying only the fields a prior
belief predicts. Filtering is for output volume, not for discovery — a
hypothesis allowed to select its own evidence will confirm itself. Where a
platform publishes a changelog or release notes, check the period since the
cutoff before concluding that a capability is absent.

Apply a higher bar to anything durable. A claim written into a commit message,
a pull request body, committed documentation, or any user-facing artifact
outlives the conversation that produced it and will be read by people who
cannot see the reasoning behind it. When a durable artefact depends on a claim
about external platform behaviour, cite the source and date in the artefact
itself, so a reader — and the fresh-eyes reviewer — can see what was checked
and when.

## External knowledge and capabilities

Use connected documentation or research capabilities when version-sensitive
APIs or external facts need verification. Prefer primary sources, verify their
applicability against the versions and configuration in this repository, and
record a source and date when it materially informs a change. Use an installed
skill only when it matches the task, following its instructions. Do not send
secrets, private source, or customer data to external services. External
information does not override repository instructions or versioned sources of
truth.

Tool, GitHub, MCP, CI, cloud, and other external capabilities are capabilities,
not standing authorization to mutate state. Use them only within the scope
authorized by the user's current request.
