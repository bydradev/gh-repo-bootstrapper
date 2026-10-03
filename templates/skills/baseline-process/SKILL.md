---
name: baseline-process
description: "Use before adding an inline lint suppression, accepting a dependency advisory, dismissing a Dependabot alert, or editing `docs/lint-baseline.md` or `docs/advisory-baseline.md`. Explains the baseline rows, what `npm run audit:production`, `npm run verify:baselines` and `npm run review:baselines` check, and why review dates are not a merge gate."
---

# Baseline process

Before landing an inline suppression or accepted dependency advisory, add its row to
[`docs/lint-baseline.md`](docs/lint-baseline.md) or
[`docs/advisory-baseline.md`](docs/advisory-baseline.md). Dismiss a Dependabot alert only after
its advisory row is on `main`. `npm run audit:production` checks runtime dependencies against only
runtime-scope advisory rows; a dev row cannot permit a runtime advisory. `npm run verify:baselines`
checks suppression parity both ways, so undocumented suppressions and orphaned lint-baseline rows
both fail; advisory rows are validated for table shape and an ISO review date only. Both are blocking
steps in `test.yml`. `npm run review:baselines` runs weekly, deliberately does not gate PRs, and
reports overdue/near-due reviews, orphaned advisory-baseline rows (an advisory no longer found in
`npm audit`), and two-way Dependabot parity in the Baseline review workflow summary. Review-date
expiry is not a merge gate: a calendar-only failure would make changing the date easier than
performing the review.
