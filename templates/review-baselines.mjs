import { appendFileSync, readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { parseAdvisoryRows, parseLintRows } from "./baseline-table.mjs";

const advisoryBaselinePath = new URL("../docs/advisory-baseline.md", import.meta.url);
const lintBaselinePath = new URL("../docs/lint-baseline.md", import.meta.url);
const now = new Date();
const reviewWindowDays = 30;
const releaseStaleDays = 14;
const apiBase = process.env.GITHUB_API_URL ?? "https://api.github.com";
// The release job of the generated release-please.yml starts with this check.
// While the Release Please App credentials are missing, or not available to the
// run, it warns and the token step and every release step after it are skipped,
// so the run still concludes success without releasing anything. The
// gh-repo-bootstrapper validator checks that its release-please.yml template
// keeps this job id and these two step names in that one job.
const releaseJobName = "release-please";
const releaseCredentialsStep = "Check Release Please credentials";
const releaseTokenStep = "Generate GitHub App token";
// Every state the Dependabot alerts API lists, asked for by name (GitHub REST
// docs, "List Dependabot alerts for a repository", checked 2026-10-20). A row's
// alert may have been dismissed by GitHub's auto-triage rules
// (`auto_dismissed`) or fixed, and Dependabot may raise no alert for a row at
// all; reading only dismissed alerts mistook each of those for a row still
// waiting on a dismissal.
const alertStates = ["auto_dismissed", "dismissed", "fixed", "open"];

// Math.ceil() of a small negative fraction returns -0 (per spec, for
// -1 < x < 0), and -0 < 0 is false, so "less than a day past due" must be
// classified with <= 0, not < 0, or it's silently treated as not-yet-due.
function daysUntil(date) {
  return Math.ceil((date.valueOf() - now.valueOf()) / 86_400_000);
}

function reviewUrgency(daysRemaining, windowDays) {
  if (daysRemaining <= 0) return "past";
  if (daysRemaining <= windowDays) return "upcoming";
  return "ok";
}

function linesForReviewDates(rows, describe) {
  const upcoming = [];
  const past = [];
  for (const row of rows) {
    const reviewAt = new Date(`${row.reviewDate}T00:00:00.000Z`);
    const description = describe(row);
    // An unparseable or impossible date (2026-02-30) would otherwise compare as
    // NaN and read as not due, hiding the row from every review.
    if (
      Number.isNaN(reviewAt.valueOf()) ||
      reviewAt.toISOString().slice(0, 10) !== row.reviewDate
    ) {
      past.push(`${description} (invalid review date)`);
      continue;
    }
    const urgency = reviewUrgency(daysUntil(reviewAt), reviewWindowDays);
    if (urgency === "past") past.push(description);
    else if (urgency === "upcoming") upcoming.push(description);
  }
  return { past, upcoming };
}

async function pagedApi(repository, token, path, collectionKey, label) {
  const values = [];
  let url = `${apiBase}/repos/${repository}/${path}`;
  while (url) {
    const response = await fetch(url, {
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
      },
    });
    if (!response.ok)
      throw new Error(`${label} API returned ${response.status} ${response.statusText}`);
    const body = await response.json();
    const page = collectionKey ? body[collectionKey] : body;
    if (!Array.isArray(page)) throw new Error(`${label} API returned an invalid response`);
    values.push(...page);
    const link = response.headers.get("link") ?? "";
    url = /<([^>]+)>; rel="next"/.exec(link)?.[1] ?? "";
  }
  return values;
}

function dependabotAlerts(repository, token) {
  return pagedApi(
    repository,
    token,
    `dependabot/alerts?state=${alertStates.join(",")}&per_page=100`,
    null,
    "Dependabot",
  );
}

async function releaseWorkflowRuns(repository, token, query) {
  const response = await fetch(
    `${apiBase}/repos/${repository}/actions/workflows/release-please.yml/runs?${query}`,
    {
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
      },
    },
  );
  if (!response.ok)
    throw new Error(`Release Please API returned ${response.status} ${response.statusText}`);
  const body = await response.json();
  if (!Array.isArray(body.workflow_runs))
    throw new Error("Release Please API returned an invalid response");
  return body.workflow_runs;
}

function releaseRunJobs(repository, token, run) {
  if (!Number.isSafeInteger(run.id) || run.id <= 0)
    throw new Error("Release Please API returned a completed run without a run id");
  return pagedApi(
    repository,
    token,
    `actions/runs/${run.id}/jobs?filter=latest&per_page=100`,
    "jobs",
    "Release Please jobs",
  );
}

// What a successful run's jobs show about its release. Every job with both the
// credentials check and the App token step counts: it released only if the
// token step succeeded, and a skipped token step means the credentials were
// missing. A `release-please` job listed as skipped never started. A workflow
// with neither, such as a customised one, is judged as before, by its run's
// conclusion and age.
function releaseEvidence(jobs) {
  const evidence = { released: 0, skipped: 0, notStarted: 0, other: {} };
  for (const job of jobs) {
    const steps = Array.isArray(job?.steps) ? job.steps : [];
    if (job?.name === releaseJobName && job.conclusion === "skipped") {
      evidence.notStarted += 1;
      continue;
    }
    const token = steps.find((step) => step?.name === releaseTokenStep);
    if (!token || !steps.some((step) => step?.name === releaseCredentialsStep)) continue;
    if (token.conclusion === "success") evidence.released += 1;
    else if (token.conclusion === "skipped") evidence.skipped += 1;
    else {
      const conclusion = token.conclusion ?? "unknown";
      evidence.other[conclusion] = (evidence.other[conclusion] ?? 0) + 1;
    }
  }
  evidence.jobs =
    evidence.released +
    evidence.skipped +
    evidence.notStarted +
    Object.values(evidence.other).reduce((sum, count) => sum + count, 0);
  return evidence;
}

function unreleasedJobs({ skipped, notStarted, other }) {
  const parts = [];
  if (skipped)
    parts.push(
      `${skipped} skipped its App token step because the \`RELEASE_PLEASE_CLIENT_ID\` variable or \`RELEASE_PLEASE_APP_KEY\` secret is not set or not available to it`,
    );
  if (notStarted) parts.push(`${notStarted} did not start`);
  for (const [conclusion, count] of Object.entries(other))
    parts.push(`${count} ran an App token step that concluded ${conclusion}`);
  return parts.join("; ");
}

function npmAuditReport() {
  const audit = spawnSync("npm", ["audit", "--json"], { encoding: "utf8" });
  if (audit.error) throw new Error(`unable to run npm audit: ${audit.error.message}`);
  let report;
  try {
    report = JSON.parse(audit.stdout);
  } catch {
    throw new Error(`npm audit did not return valid JSON. ${audit.stderr || audit.stdout}`);
  }
  // A failed audit (for example a registry outage) prints JSON with an
  // `error` object and no vulnerability map. Reading that as an empty audit
  // would report every advisory row as orphaned, or none, so check its shape
  // rather than trusting that npm returned a report.
  if (
    !report ||
    typeof report !== "object" ||
    report.error ||
    typeof report.metadata?.vulnerabilities?.total !== "number" ||
    !report.vulnerabilities ||
    typeof report.vulnerabilities !== "object" ||
    Array.isArray(report.vulnerabilities)
  )
    throw new Error(
      `npm audit returned an incomplete or error response. ${audit.stderr || audit.stdout}`,
    );
  return report;
}

function auditedAdvisoryUrls(report) {
  const urls = new Set();
  for (const vulnerability of Object.values(report.vulnerabilities ?? {}))
    for (const entry of vulnerability.via ?? [])
      if (typeof entry === "object" && typeof entry.url === "string") urls.add(entry.url);
  return urls;
}

function orphanedAdvisoryRows(rows, auditedUrls) {
  return rows
    .filter((row) => !auditedUrls.has(`https://github.com/advisories/${row.ghsa}`))
    .map((row) => `${row.ghsa} (${row.packageName}): ${row.reviewDate}`);
}

// A person's dismissal needs a row, and a row's alert must not stay open. A row
// with no alert has nothing to dismiss, so it is listed but not actionable; the
// orphaned-row check still compares its advisory with `npm audit`.
function parity(rows, alerts) {
  const documented = new Set(rows.map(({ ghsa }) => ghsa));
  const states = new Map();
  for (const alert of alerts) {
    const ghsa = alert?.security_advisory?.ghsa_id;
    if (typeof ghsa !== "string") continue;
    if (!alertStates.includes(alert.state))
      throw new Error(`Dependabot API returned an alert for ${ghsa} with an unexpected state`);
    states.set(ghsa, (states.get(ghsa) ?? new Set()).add(alert.state));
  }
  const hasState = (ghsa, state) => states.get(ghsa)?.has(state) ?? false;
  return {
    undocumentedDismissals: [...states.keys()].filter(
      (ghsa) => hasState(ghsa, "dismissed") && !documented.has(ghsa),
    ),
    rowsWithOpenAlerts: [...documented].filter((ghsa) => hasState(ghsa, "open")),
    rowsWithoutAlerts: [...documented].filter((ghsa) => !states.has(ghsa)),
  };
}

function writeSummary(lines, actionable) {
  const summary = ["## Baseline review", "", ...lines, "", "Baseline review completed."].join("\n");
  console.log(summary);
  if (process.env.GITHUB_STEP_SUMMARY)
    appendFileSync(process.env.GITHUB_STEP_SUMMARY, `${summary}\n`);
  if (actionable) process.exitCode = 1;
}

function completionTimestamp(run) {
  const timestamp = run.completed_at ?? run.updated_at;
  const date = new Date(timestamp);
  if (Number.isNaN(date.valueOf()))
    throw new Error("Release Please API returned a completed run without a completion timestamp");
  return timestamp;
}

function ageInDays(run) {
  const date = new Date(completionTimestamp(run));
  return Math.max(0, Math.floor((now.valueOf() - date.valueOf()) / 86_400_000));
}

function releaseHealth(latest, lastSuccess, evidence) {
  if (!latest)
    return {
      actionable: true,
      line: `- Release pipeline: stale. \`release-please.yml\` has never completed; no successful run exists. A successful run older than ${releaseStaleDays} days is reported as stale.`,
    };

  const latestAt = completionTimestamp(latest);
  const latestAge = ageInDays(latest);
  const latestConclusion = latest.conclusion ?? "unknown";
  if (!lastSuccess)
    return {
      actionable: true,
      line: `- Release pipeline: stale. The latest completed \`release-please.yml\` run concluded ${latestConclusion} at ${latestAt} (${latestAge} days ago); no successful run exists. A successful run older than ${releaseStaleDays} days is reported as stale.`,
    };

  const successAt = completionTimestamp(lastSuccess);
  const successAge = ageInDays(lastSuccess);
  const success = `last successful \`release-please.yml\` run completed successfully at ${successAt} (${successAge} days ago)`;
  if (latestConclusion !== "success")
    return {
      actionable: true,
      line: `- Release pipeline: stale. The latest completed \`release-please.yml\` run concluded ${latestConclusion} at ${latestAt} (${latestAge} days ago); the ${success}. A successful run older than ${releaseStaleDays} days is reported as stale.`,
    };
  if (evidence.jobs && evidence.skipped === evidence.jobs)
    return {
      actionable: true,
      line: `- Release pipeline: not configured. The latest \`release-please.yml\` run (${latestAt}, ${latestAge} days ago) skipped the release because the \`RELEASE_PLEASE_CLIENT_ID\` variable or \`RELEASE_PLEASE_APP_KEY\` secret is not set or not available to it; releases stay skipped until a run can read both.`,
    };
  if (evidence.released < evidence.jobs)
    return {
      actionable: true,
      line: `- Release pipeline: ${evidence.released ? "partly released" : "not released"}. In the latest \`release-please.yml\` run (${latestAt}, ${latestAge} days ago), ${evidence.jobs - evidence.released} of ${evidence.jobs} release job${evidence.jobs === 1 ? "" : "s"} did not release: ${unreleasedJobs(evidence)}.`,
    };
  if (successAge > releaseStaleDays)
    return {
      actionable: true,
      line: `- Release pipeline: stale. The ${success}; a successful run older than ${releaseStaleDays} days is reported as stale.`,
    };
  return {
    actionable: false,
    line: `- Release pipeline: ${success}; stale after ${releaseStaleDays} days.`,
  };
}

async function main() {
  let rows;
  try {
    rows = parseAdvisoryRows(readFileSync(advisoryBaselinePath, "utf8"));
  } catch (error) {
    writeSummary(
      [
        `- Advisory baseline: could not be parsed (${error.message})`,
        "- Dependabot parity: could not be determined because the advisory baseline is unavailable.",
        "- Release pipeline: could not be determined because the advisory baseline is unavailable.",
      ],
      true,
    );
    return;
  }

  const { past, upcoming } = linesForReviewDates(
    rows,
    (row) => `${row.ghsa} (${row.packageName}): ${row.reviewDate}`,
  );
  const lines = [];
  let actionable = false;
  if (past.length) lines.push(`- Overdue advisory reviews:\n  - ${past.join("\n  - ")}`);
  if (past.length) actionable = true;
  if (upcoming.length)
    lines.push(
      `- Advisory reviews due within ${reviewWindowDays} days:\n  - ${upcoming.join("\n  - ")}`,
    );
  if (!past.length && !upcoming.length)
    lines.push(`- Advisory review dates: no rows overdue or due within ${reviewWindowDays} days.`);

  try {
    const orphaned = orphanedAdvisoryRows(rows, auditedAdvisoryUrls(npmAuditReport()));
    if (orphaned.length) {
      lines.push(
        `- Orphaned advisory-baseline rows (advisory not found in \`npm audit\`):\n  - ${orphaned.join("\n  - ")}`,
      );
      actionable = true;
    } else {
      lines.push(
        "- Orphaned advisory-baseline rows: none; every row's advisory appears in `npm audit`.",
      );
    }
  } catch (error) {
    lines.push(`- Orphaned advisory-baseline rows: could not be determined (${error.message})`);
    actionable = true;
  }

  let lintRows = [];
  let lintParsed = true;
  try {
    lintRows = parseLintRows(readFileSync(lintBaselinePath, "utf8"));
  } catch (error) {
    lintParsed = false;
    lines.push(`- Lint baseline: could not be parsed (${error.message})`);
    actionable = true;
  }
  if (lintParsed) {
    const { past: lintPast, upcoming: lintUpcoming } = linesForReviewDates(
      lintRows,
      (row) => `${row.rule} in ${row.file}: ${row.reviewDate}`,
    );
    if (lintPast.length) lines.push(`- Overdue lint reviews:\n  - ${lintPast.join("\n  - ")}`);
    if (lintPast.length) actionable = true;
    if (lintUpcoming.length)
      lines.push(
        `- Lint reviews due within ${reviewWindowDays} days:\n  - ${lintUpcoming.join("\n  - ")}`,
      );
    if (!lintPast.length && !lintUpcoming.length)
      lines.push(`- Lint review dates: no rows overdue or due within ${reviewWindowDays} days.`);
  }

  const { GITHUB_REPOSITORY: repository, GITHUB_TOKEN: token } = process.env;
  if (!repository || !token) {
    lines.push(
      "- Dependabot parity: could not be determined because GITHUB_REPOSITORY or GITHUB_TOKEN is unavailable.",
    );
    lines.push(
      "- Release pipeline: could not be determined because GITHUB_REPOSITORY or GITHUB_TOKEN is unavailable.",
    );
    writeSummary(lines, true);
    return;
  }

  try {
    const result = parity(rows, await dependabotAlerts(repository, token));
    actionable ||= result.undocumentedDismissals.length > 0 || result.rowsWithOpenAlerts.length > 0;
    if (result.undocumentedDismissals.length)
      lines.push(
        `- Dismissed Dependabot alerts without advisory-baseline rows:\n  - ${result.undocumentedDismissals.join("\n  - ")}`,
      );
    if (result.rowsWithOpenAlerts.length)
      lines.push(
        `- Advisory-baseline rows whose Dependabot alert is still open (reassess the row against the alert, scope included, before dismissing the alert citing the row):\n  - ${result.rowsWithOpenAlerts.join("\n  - ")}`,
      );
    if (!result.undocumentedDismissals.length && !result.rowsWithOpenAlerts.length)
      lines.push(
        "- Dependabot parity: every alert a person dismissed has a row, and no row's alert is open.",
      );
    if (result.rowsWithoutAlerts.length)
      lines.push(
        `- Advisory-baseline rows with no Dependabot alert (nothing to dismiss):\n  - ${result.rowsWithoutAlerts.join("\n  - ")}`,
      );
  } catch (error) {
    lines.push(`- Dependabot parity: could not be determined (${error.message})`);
    actionable = true;
  }
  try {
    const [latestRuns, successfulRuns] = await Promise.all([
      releaseWorkflowRuns(repository, token, "status=completed&per_page=1"),
      releaseWorkflowRuns(repository, token, "status=success&per_page=1"),
    ]);
    const latest = latestRuns[0];
    const jobs =
      latest?.conclusion === "success" ? await releaseRunJobs(repository, token, latest) : [];
    const result = releaseHealth(latest, successfulRuns[0], releaseEvidence(jobs));
    lines.push(result.line);
    actionable ||= result.actionable;
  } catch (error) {
    lines.push(`- Release pipeline: could not be determined (${error.message})`);
    actionable = true;
  }
  writeSummary(lines, actionable);
}

await main();
