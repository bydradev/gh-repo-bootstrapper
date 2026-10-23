---
name: baseline-process
description: "Use before adding an inline lint suppression, accepting a dependency advisory, dismissing a Dependabot alert, or editing `docs/lint-baseline.md` or `docs/advisory-baseline.md`. Explains the baseline rows, what `npm run audit:production`, `npm run verify:baselines` and `npm run review:baselines` check, and why review dates are not a merge gate."
---

# Baseline process

- **Add a row** to `docs/lint-baseline.md` or `docs/advisory-baseline.md`
  (repository root) before landing an inline suppression or accepted
  dependency advisory. Dismiss a Dependabot alert only after its advisory row
  is on `main`.
- **Auto-triage:** keep the GitHub preset that dismisses low-impact alerts
  for development-scoped dependencies off, so an unfixable development
  advisory stays an open alert until its row exists. Where it is on, nothing
  checks an advisory whose alert it dismissed: record an unfixable one anyway.
- **`npm run audit:production`** checks runtime dependencies against only
  runtime-scope advisory rows; a dev row cannot permit a runtime advisory.
- **`npm run verify:baselines`** checks suppression parity both ways, so
  undocumented suppressions and orphaned lint-baseline rows both fail; it
  checks advisory rows only for table shape and an ISO review date. As
  generated, both commands are blocking steps in `test.yml`.
- **`npm run review:baselines`** runs weekly and deliberately does not gate
  PRs. Its Baseline review workflow summary reports overdue and near-due
  reviews, orphaned advisory rows (an advisory no longer in `npm audit`),
  Dependabot alerts a person dismissed without a row (auto-triage dismissals
  are not checked), and rows whose alert is still open. Reassess such a row
  against its alert, scope included, before dismissing the alert: auto-triage
  can reopen an alert it dismissed, for example when the dependency moves from
  development to production scope (GitHub Docs, *Dependabot auto-triage
  rules*, checked 2026-10-21). A row with no alert is listed but not flagged,
  and a row whose alert auto-triage dismissed or Dependabot marked fixed
  passes: neither has anything to dismiss.
- **Review dates are not a merge gate:** a calendar-only failure would make
  changing the date easier than performing the review.
