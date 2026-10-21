# Lint Baseline

## What this document covers

This is the baseline for **our own code**: inline suppressions we author, such as
`eslint-disable` and `@ts-expect-error`, and `eslint` configuration comments that turn a rule off,
downgrade it, or change its options for a file. It is deliberately separate from
[`docs/advisory-baseline.md`](advisory-baseline.md), which records accepted third-party dependency
security advisories.

This baseline is mostly self-cleaning when `npm run lint` meets both requirements in the policy
below. ESLint then reports an unused `eslint-disable` directive when the code it covered is removed
or refactored, and that warning fails CI and requires removing both the stale directive and its row
below; without either requirement, a stale baseline row only surfaces at its review date. TypeScript
likewise fails on an unused `@ts-expect-error`, so prefer it to `@ts-ignore`. Nothing reports an
unused `@ts-ignore`, `@ts-nocheck`, or `eslint` configuration comment; those rows stay accurate
only through their review dates. Dependency advisories do not self-clean either; their review triggers belong in `docs/advisory-baseline.md`. Each accepted
suppression below carries a review date for the same reason: the weekly `npm run review:baselines`
surfaces overdue acceptances alongside overdue advisories. Review-date expiry is reported by the
weekly review only and never gates a pull request. The review cadence is six months from acceptance.

## Policy: the baseline is zero

`npm run lint` must run `eslint --max-warnings=0` with unused disable directives reported, which is
the default since ESLint 9 (`reportUnusedDisableDirectives: "warn"`). ESLint 8 reports them only when
asked, such as with `--report-unused-disable-directives`, and a configuration that sets the option to
`"off"` reports none. The bootstrapper does not create `package.json`, so the application scaffold
provides the `lint` script and must include the flag and keep the reporting on; without the flag a
warning does not fail CI. A clean run prints nothing and exits 0. Any warning or error is new work to
investigate; do not hide it in a growing baseline.

When a warning appears:

1. **Fix the code.** This is the normal outcome.
2. **Suppress an unavoidable false positive inline.** Use
   `// eslint-disable-next-line <rule> -- <reason>` and add a row below. The reason is mandatory.

Never turn a rule off globally merely to silence an instance. That removes the tripwire for every
future use of the rule.

## Accepted suppressions

There are currently no accepted inline suppressions.

| # | Rule | File | Why this is accepted | Review date |
| - | ---- | ---- | ------------------- | ----------- |

## Considered alternatives (not adopted)

- **Disable the rule globally**: rejected because it removes the signal for all future code.
- **Ignore the warning without an inline reason**: rejected because the next reader cannot tell an
  intentional exception from an oversight.
