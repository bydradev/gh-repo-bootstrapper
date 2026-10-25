import assert from "node:assert/strict";
import { createServer } from "node:http";
import { chmodSync, copyFileSync, mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, dirname, join } from "node:path";
import { spawn } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";

const scriptsDirectory = dirname(fileURLToPath(import.meta.url));
const columns = [
  "| GHSA | Package | Severity | Scope (runtime/dev) | Why not fixed | Re-check trigger | Review date |",
  "| ---- | ------- | -------- | ------------------- | ------------- | ---------------- | ----------- |",
];
const lintColumns = [
  "| # | Rule | File | Why this is accepted | Review date |",
  "| - | ---- | ---- | ------------------- | ----------- |",
];

function advisoryBaseline(rows) {
  return ["## Accepted advisories", "", ...columns, ...rows].join("\n");
}

function lintBaseline(rows) {
  return ["## Accepted suppressions", "", ...lintColumns, ...rows].join("\n");
}

function auditReportMatching(...ghsaIds) {
  return {
    metadata: { vulnerabilities: { total: ghsaIds.length } },
    vulnerabilities: {
      fixture: {
        via: ghsaIds.map((ghsa) => ({ url: `https://github.com/advisories/${ghsa}` })),
      },
    },
  };
}

function writeFakeNpm(root, scriptBody) {
  const binDir = join(root, "bin");
  mkdirSync(binDir);
  const npmPath = join(binDir, "npm");
  writeFileSync(npmPath, `#!/bin/sh\n${scriptBody}\n`);
  chmodSync(npmPath, 0o755);
  return binDir;
}

function fakeNpmAuditJson(auditReport) {
  return `cat <<'JSON'\n${JSON.stringify(auditReport)}\nJSON\n`;
}

const capturedSuccessfulReleaseRun = {
  id: 30230627141,
  name: "Release Please",
  status: "completed",
  conclusion: "success",
  run_started_at: "2026-07-27T01:47:31Z",
  updated_at: "2026-07-27T01:50:22Z",
  completed_at: null,
};

function successfulRelease(updatedAt = new Date().toISOString()) {
  return { ...capturedSuccessfulReleaseRun, updated_at: updatedAt };
}

function securityTxt(expires = "2099-01-01T00:00:00.000Z") {
  return [
    "Contact: mailto:security@example.com",
    `Expires: ${expires}`,
    "Preferred-Languages: en",
    "Canonical: https://example.com/.well-known/security.txt",
    "",
  ].join("\n");
}

// The release job of the generated release-please.yml as GitHub's jobs API
// lists it. Without the Release Please credentials the token step and the
// steps after it are "completed" with the conclusion "skipped", and there is
// no post step for the token action.
function releaseJob(tokenConclusion) {
  const step = (number, name, conclusion = "success") => ({
    number,
    name,
    status: "completed",
    conclusion,
  });
  return {
    name: "release-please",
    status: "completed",
    conclusion: "success",
    steps: [
      step(1, "Set up job"),
      step(2, "Check Release Please credentials"),
      step(3, "Generate GitHub App token", tokenConclusion),
      step(4, "Refuse to tag an untested release merge", tokenConclusion),
      step(5, "Run googleapis/release-please-action@<sha>", tokenConclusion),
      step(6, "Complete job"),
    ],
  };
}

const testJob = {
  name: "test / build",
  status: "completed",
  conclusion: "success",
  steps: [{ number: 1, name: "Set up job", status: "completed", conclusion: "success" }],
};

// GitHub lists only the alerts in the `state` values asked for; the fixture
// returns every alert when none is given.
function alertsInStates(alerts, state) {
  if (!state || !Array.isArray(alerts)) return alerts;
  const states = state.split(",");
  return alerts.filter((alert) => states.includes(alert.state));
}

function alert(ghsa, state = "dismissed") {
  return { state, security_advisory: { ghsa_id: ghsa } };
}

async function runFixture({
  rows,
  lintRows = [],
  alerts,
  alertPages,
  filterAlertStates = true,
  latestReleaseRuns = [successfulRelease()],
  unfilteredReleaseRuns = latestReleaseRuns,
  successfulReleaseRuns = latestReleaseRuns,
  releaseJobs = [testJob, releaseJob("success")],
  releaseJobPages,
  token = true,
  dependabotStatus = 200,
  releaseStatus = 200,
  jobsStatus = 200,
  auditReport = auditReportMatching("GHSA-aaaa-bbbb-cccc"),
  fakeNpmScript,
  advisoryBaselineContents,
  securityTxtContents,
  securityTxtDirectory = false,
}) {
  const root = mkdtempSync(join(tmpdir(), "review-baselines-"));
  const requests = [];
  const server = createServer((request, response) => {
    const url = new URL(request.url ?? "/", "http://fixture.test");
    requests.push(`${url.pathname}?${url.searchParams}`);
    response.setHeader("content-type", "application/json");
    if (url.pathname === "/repos/bydradev/fixture/dependabot/alerts") {
      response.statusCode = dependabotStatus;
      const served = (page) =>
        filterAlertStates ? alertsInStates(page, url.searchParams.get("state")) : page;
      if (!alertPages) {
        response.end(JSON.stringify(served(alerts)));
        return;
      }
      // Serve one page per request and link to the next, as GitHub does.
      const page = Number(url.searchParams.get("page") ?? "1");
      if (page < alertPages.length) {
        const next = new URL(url.pathname, `http://127.0.0.1:${server.address().port}`);
        next.search = url.search;
        next.searchParams.set("page", String(page + 1));
        response.setHeader("link", `<${next}>; rel="next", <${next}>; rel="last"`);
      }
      response.end(JSON.stringify(served(alertPages[page - 1])));
      return;
    }
    if (url.pathname === "/repos/bydradev/fixture/actions/workflows/release-please.yml/runs") {
      response.statusCode = releaseStatus;
      response.end(
        JSON.stringify({
          workflow_runs:
            url.searchParams.get("status") === "success"
              ? successfulReleaseRuns
              : url.searchParams.get("status") === "completed"
                ? latestReleaseRuns
                : unfilteredReleaseRuns,
        }),
      );
      return;
    }
    if (/^\/repos\/bydradev\/fixture\/actions\/runs\/\d+\/jobs$/.test(url.pathname)) {
      response.statusCode = jobsStatus;
      if (!releaseJobPages) {
        response.end(JSON.stringify({ total_count: releaseJobs.length, jobs: releaseJobs }));
        return;
      }
      const page = Number(url.searchParams.get("page") ?? "1");
      if (page < releaseJobPages.length) {
        const next = new URL(url.pathname, `http://127.0.0.1:${server.address().port}`);
        next.search = url.search;
        next.searchParams.set("page", String(page + 1));
        response.setHeader("link", `<${next}>; rel="next", <${next}>; rel="last"`);
      }
      response.end(
        JSON.stringify({
          total_count: releaseJobPages.flat().length,
          jobs: releaseJobPages[page - 1],
        }),
      );
      return;
    }
    response.statusCode = 404;
    response.end(JSON.stringify({ message: "unexpected fixture request" }));
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  try {
    mkdirSync(join(root, "scripts"));
    mkdirSync(join(root, "docs"));
    for (const file of ["baseline-table.mjs", "review-baselines.mjs"])
      copyFileSync(join(scriptsDirectory, file), join(root, "scripts", file));
    writeFileSync(
      join(root, "docs/advisory-baseline.md"),
      advisoryBaselineContents ?? advisoryBaseline(rows),
    );
    if (securityTxtContents !== undefined || securityTxtDirectory) {
      mkdirSync(join(root, "public/.well-known"), { recursive: true });
      if (securityTxtDirectory) mkdirSync(join(root, "public/.well-known/security.txt"));
      else writeFileSync(join(root, "public/.well-known/security.txt"), securityTxtContents);
    }
    writeFileSync(join(root, "docs/lint-baseline.md"), lintBaseline(lintRows));
    const binDir = writeFakeNpm(root, fakeNpmScript ?? fakeNpmAuditJson(auditReport));
    // Start from the host environment without the variables the script reads,
    // so a developer's own GITHUB_TOKEN or a CI step summary never reaches it.
    const hostEnv = { ...process.env };
    delete hostEnv.GITHUB_TOKEN;
    delete hostEnv.GITHUB_STEP_SUMMARY;
    const child = spawn(process.execPath, [join(root, "scripts/review-baselines.mjs")], {
      cwd: root,
      env: {
        ...hostEnv,
        PATH: `${binDir}${delimiter}${process.env.PATH}`,
        GITHUB_API_URL: `http://127.0.0.1:${port}`,
        GITHUB_REPOSITORY: "bydradev/fixture",
        ...(token ? { GITHUB_TOKEN: "fixture-token" } : {}),
      },
    });
    let output = "";
    for (const stream of [child.stdout, child.stderr])
      stream.on("data", (chunk) => (output += chunk));
    const code = await new Promise((resolve) => child.on("exit", resolve));
    return { code, output, requests };
  } finally {
    await new Promise((resolve) => server.close(resolve));
    rmSync(root, { force: true, recursive: true });
  }
}

const documented =
  "| `GHSA-aaaa-bbbb-cccc` | fixture | high | dev | fixture | fixture | 2099-01-01 |";
const matchingAlert = [alert("GHSA-aaaa-bbbb-cccc")];
const dependabotRequest =
  "/repos/bydradev/fixture/dependabot/alerts?state=auto_dismissed%2Cdismissed%2Cfixed%2Copen&per_page=100";

test("accepts a captured GitHub workflow-run payload and exits zero when healthy", async () => {
  const freshCapturedRun = successfulRelease();
  const { code, output, requests } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    latestReleaseRuns: [freshCapturedRun],
    successfulReleaseRuns: [freshCapturedRun],
  });
  assert.equal(code, 0);
  assert.match(
    output,
    /Orphaned advisory-baseline rows: none; every row's advisory appears in `npm audit`/,
  );
  assert.match(
    output,
    /Dependabot parity: every alert a person dismissed has a row, and no row's alert is open/,
  );
  assert.doesNotMatch(output, /no Dependabot alert/);
  assert.match(
    output,
    /Release pipeline: last successful `release-please\.yml` run completed successfully/,
  );
  assert.match(
    output,
    /security\.txt: none at `public\/\.well-known\/security\.txt`, so there is no expiry to review/,
  );
  assert.match(output, /Baseline review completed/);
  assert.deepEqual(
    requests.filter((request) => request.includes("dependabot/alerts")),
    [dependabotRequest],
  );
  assert.deepEqual(
    requests.filter((request) => request.includes("release-please.yml/runs")),
    [
      "/repos/bydradev/fixture/actions/workflows/release-please.yml/runs?status=completed&per_page=1",
      "/repos/bydradev/fixture/actions/workflows/release-please.yml/runs?status=success&per_page=1",
    ],
  );
});

test("ignores a newer in-progress release run when determining release health", async () => {
  const freshCompletedRun = successfulRelease();
  const { code, output, requests } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    unfilteredReleaseRuns: [{ ...freshCompletedRun, status: "in_progress", conclusion: null }],
    latestReleaseRuns: [freshCompletedRun],
    successfulReleaseRuns: [freshCompletedRun],
  });
  assert.equal(code, 0);
  assert.match(
    output,
    /Release pipeline: last successful `release-please\.yml` run completed successfully/,
  );
  assert.doesNotMatch(output, /Release pipeline: stale/);
  assert.deepEqual(
    requests.filter((request) => request.includes("release-please.yml/runs")),
    [
      "/repos/bydradev/fixture/actions/workflows/release-please.yml/runs?status=completed&per_page=1",
      "/repos/bydradev/fixture/actions/workflows/release-please.yml/runs?status=success&per_page=1",
    ],
  );
});

test("reports both Dependabot parity directions and exits non-zero", async () => {
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: [alert("GHSA-dddd-eeee-ffff"), alert("GHSA-aaaa-bbbb-cccc", "open")],
  });
  assert.equal(code, 1);
  assert.match(
    output,
    /Dismissed Dependabot alerts without advisory-baseline rows:\n {2}- GHSA-dddd-eeee-ffff/,
  );
  assert.match(
    output,
    /Advisory-baseline rows whose Dependabot alert is still open \(reassess the row against the alert, scope included, before dismissing the alert citing the row\):\n {2}- GHSA-aaaa-bbbb-cccc/,
  );
  assert.doesNotMatch(output, /Dependabot parity: every alert a person dismissed has a row/);
});

test("reports a row's open alert even when another alert for it is dismissed", async () => {
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: [alert("GHSA-aaaa-bbbb-cccc"), alert("GHSA-aaaa-bbbb-cccc", "open")],
  });
  assert.equal(code, 1);
  assert.match(output, /whose Dependabot alert is still open[^\n]*\n {2}- GHSA-aaaa-bbbb-cccc/);
});

test("lists a row with no Dependabot alert without failing", async () => {
  const { code, output } = await runFixture({ rows: [documented], alerts: [] });
  assert.equal(code, 0, output);
  assert.match(
    output,
    /Dependabot parity: every alert a person dismissed has a row, and no row's alert is open/,
  );
  assert.match(
    output,
    /Advisory-baseline rows with no Dependabot alert \(nothing to dismiss\):\n {2}- GHSA-aaaa-bbbb-cccc/,
  );
});

test("accepts a row whose alert was auto-dismissed or fixed", async () => {
  for (const state of ["auto_dismissed", "fixed"]) {
    const { code, output, requests } = await runFixture({
      rows: [documented],
      alerts: [alert("GHSA-aaaa-bbbb-cccc", state)],
    });
    assert.equal(code, 0, `${state}: ${output}`);
    assert.match(output, /every alert a person dismissed has a row, and no row's alert is open/);
    assert.doesNotMatch(output, /no Dependabot alert/);
    assert.deepEqual(
      requests.filter((request) => request.includes("dependabot/alerts")),
      [dependabotRequest],
    );
  }
});

test("does not ask for a row for an alert no person dismissed", async () => {
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: [
      ...matchingAlert,
      alert("GHSA-dddd-eeee-ffff", "auto_dismissed"),
      alert("GHSA-gggg-hhhh-iiii", "open"),
      alert("GHSA-jjjj-kkkk-llll", "fixed"),
    ],
  });
  assert.equal(code, 0, output);
  assert.doesNotMatch(output, /Dismissed Dependabot alerts without advisory-baseline rows/);
});

test("reports an alert in an unexpected state as undetermined parity", async () => {
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: [alert("GHSA-aaaa-bbbb-cccc", "unknown")],
    // Served as is: a state the script did not ask for.
    filterAlertStates: false,
  });
  assert.equal(code, 1);
  assert.match(
    output,
    /Dependabot parity: could not be determined \(Dependabot API returned an alert for GHSA-aaaa-bbbb-cccc with an unexpected state\)/,
  );
});

test("reports an advisory-baseline row whose advisory no longer appears in npm audit", async () => {
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    auditReport: auditReportMatching("GHSA-dddd-eeee-ffff"),
  });
  assert.equal(code, 1);
  assert.match(output, /Orphaned advisory-baseline rows \(advisory not found in `npm audit`\)/);
  assert.match(output, /GHSA-aaaa-bbbb-cccc \(fixture\): 2099-01-01/);
});

test("reports orphan detection as unavailable when npm audit fails", async () => {
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    fakeNpmScript: "echo 'not json'\nexit 1\n",
  });
  assert.equal(code, 1);
  assert.match(
    output,
    /Orphaned advisory-baseline rows: could not be determined \(npm audit did not return valid JSON/,
  );
});

test("follows Link-header pagination for Dependabot alerts", async () => {
  const other = documented.replaceAll("GHSA-aaaa-bbbb-cccc", "GHSA-dddd-eeee-ffff");
  const { code, output, requests } = await runFixture({
    rows: [documented, other],
    alertPages: [matchingAlert, [alert("GHSA-dddd-eeee-ffff", "auto_dismissed")]],
    auditReport: auditReportMatching("GHSA-aaaa-bbbb-cccc", "GHSA-dddd-eeee-ffff"),
  });
  assert.equal(code, 0, output);
  assert.match(output, /every alert a person dismissed has a row, and no row's alert is open/);
  assert.doesNotMatch(output, /no Dependabot alert/);
  assert.equal(requests.filter((request) => request.includes("dependabot/alerts")).length, 2);
});

test("reports unavailable credentials as actionable", async () => {
  const { code, output } = await runFixture({ rows: [documented], alerts: [], token: false });
  assert.equal(code, 1);
  assert.match(
    output,
    /could not be determined because GITHUB_REPOSITORY or GITHUB_TOKEN is unavailable/,
  );
  assert.match(output, /Baseline review completed/);
});

test("reports rejected Dependabot API access without claiming healthy parity", async () => {
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: [],
    dependabotStatus: 403,
  });
  assert.equal(code, 1);
  assert.match(output, /Dependabot parity: could not be determined \(Dependabot API returned 403/);
  assert.doesNotMatch(output, /every alert a person dismissed has a row/);
});

test("reports overdue review dates as actionable", async () => {
  const { code, output } = await runFixture({
    rows: [documented.replace("2099-01-01", "2020-01-01")],
    alerts: matchingAlert,
  });
  assert.equal(code, 1);
  assert.match(output, /Overdue advisory reviews/);
  assert.match(output, /Baseline review completed/);
});

test("reports overdue lint review dates as actionable", async () => {
  const { code, output } = await runFixture({
    rows: [documented],
    lintRows: ["| 1 | `no-console` | `e2e/fixture.mjs` | accepted | 2020-01-01 |"],
    alerts: matchingAlert,
  });
  assert.equal(code, 1);
  assert.match(output, /Overdue lint reviews/);
  assert.match(output, /no-console in e2e\/fixture\.mjs: 2020-01-01/);
  assert.match(output, /Baseline review completed/);
});

test("reports a lint review due today as overdue, not upcoming", async () => {
  const today = new Date().toISOString().slice(0, 10);
  const { code, output } = await runFixture({
    rows: [documented],
    lintRows: [`| 1 | \`no-console\` | \`e2e/fixture.mjs\` | accepted | ${today} |`],
    alerts: matchingAlert,
  });
  assert.equal(code, 1);
  assert.match(output, /Overdue lint reviews/);
  assert.doesNotMatch(output, /Lint reviews due within 30 days/);
});

test("reports upcoming lint review dates as informational", async () => {
  const upcomingDate = new Date(Date.now() + 15 * 86_400_000).toISOString().slice(0, 10);
  const { code, output } = await runFixture({
    rows: [documented],
    lintRows: [`| 1 | \`no-console\` | \`e2e/fixture.mjs\` | accepted | ${upcomingDate} |`],
    alerts: matchingAlert,
  });
  assert.equal(code, 0);
  assert.match(output, /Lint reviews due within 30 days/);
  assert.match(output, /no-console in e2e\/fixture\.mjs/);
});

test("reports unavailable release-health access without claiming it healthy", async () => {
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    releaseStatus: 403,
  });
  assert.equal(code, 1);
  assert.match(
    output,
    /Release pipeline: could not be determined \(Release Please API returned 403/,
  );
  assert.doesNotMatch(output, /Release pipeline: last successful/);
});

test("reports a release workflow that has never completed", async () => {
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    latestReleaseRuns: [],
    successfulReleaseRuns: [],
  });
  assert.equal(code, 1);
  assert.match(output, /Release pipeline: stale\. `release-please\.yml` has never completed/);
  assert.match(output, /older than 14 days is reported as stale/);
});

test("reports a successful release run older than the declared stale threshold", async () => {
  const oldRelease = new Date(Date.now() - 15 * 86_400_000).toISOString();
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    latestReleaseRuns: [successfulRelease(oldRelease)],
    successfulReleaseRuns: [successfulRelease(oldRelease)],
  });
  assert.equal(code, 1);
  assert.match(output, /Release pipeline: stale\. The last successful `release-please\.yml` run/);
  assert.match(output, /older than 14 days is reported as stale/);
});

test("reports a failed latest release run as stale and exits non-zero", async () => {
  const { code, output, requests } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    latestReleaseRuns: [{ ...successfulRelease(), conclusion: "failure" }],
    successfulReleaseRuns: [successfulRelease()],
  });
  assert.equal(code, 1);
  assert.match(
    output,
    /Release pipeline: stale\. The latest completed `release-please\.yml` run concluded failure/,
  );
  assert.match(output, /older than 14 days is reported as stale/);
  // Only a successful run's jobs are read.
  assert.deepEqual(
    requests.filter((request) => request.includes("/jobs")),
    [],
  );
});

test("reports a release skipped for missing credentials as not configured", async () => {
  const { code, output, requests } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    releaseJobs: [testJob, releaseJob("skipped")],
  });
  assert.equal(code, 1);
  assert.match(
    output,
    /Release pipeline: not configured\. The latest `release-please\.yml` run \(2\d{3}-[^,]+, 0 days ago\) skipped the release because the `RELEASE_PLEASE_CLIENT_ID` variable or `RELEASE_PLEASE_APP_KEY` secret is not set or not available to it; releases stay skipped until a run can read both\./,
  );
  assert.doesNotMatch(output, /Release pipeline: last successful/);
  assert.deepEqual(
    requests.filter((request) => request.includes("/jobs")),
    ["/repos/bydradev/fixture/actions/runs/30230627141/jobs?filter=latest&per_page=100"],
  );
});

test("reports a skipped release older than the stale threshold as not configured", async () => {
  // Missing credentials are the cause to fix, so they are reported ahead of the age.
  const oldRelease = new Date(Date.now() - 15 * 86_400_000).toISOString();
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    latestReleaseRuns: [successfulRelease(oldRelease)],
    successfulReleaseRuns: [successfulRelease(oldRelease)],
    releaseJobs: [testJob, releaseJob("skipped")],
  });
  assert.equal(code, 1);
  assert.match(
    output,
    /Release pipeline: not configured\. The latest `release-please\.yml` run \(2\d{3}-[^,]+, 15 days ago\)/,
  );
  assert.doesNotMatch(output, /Release pipeline: stale/);
});

test("reports a release whose App token step ran as healthy", async () => {
  const { code, output, requests } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    releaseJobs: [testJob, releaseJob("success")],
  });
  assert.equal(code, 0, output);
  assert.match(
    output,
    /Release pipeline: last successful `release-please\.yml` run completed successfully/,
  );
  assert.doesNotMatch(output, /not configured/);
  assert.equal(requests.filter((request) => request.includes("/jobs")).length, 1);
});

test("reads every page of jobs before judging the release", async () => {
  // The release job is on the second page, after 100 others.
  const filler = Array.from({ length: 100 }, (_, index) => ({
    ...testJob,
    name: `test / ${index}`,
  }));
  const { code, output, requests } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    releaseJobPages: [filler, [releaseJob("skipped")]],
  });
  assert.equal(code, 1);
  assert.match(output, /Release pipeline: not configured/);
  assert.equal(requests.filter((request) => request.includes("/jobs")).length, 2);
});

test("reports a release job that did not start as not released", async () => {
  // A customised release job whose own condition was false: GitHub lists it
  // as skipped, with no steps.
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    releaseJobs: [
      testJob,
      { name: "release-please", status: "completed", conclusion: "skipped", steps: [] },
    ],
  });
  assert.equal(code, 1);
  assert.match(
    output,
    /Release pipeline: not released\. In the latest `release-please\.yml` run \(2\d{3}-[^,]+, 0 days ago\), 1 of 1 release job did not release: 1 did not start\./,
  );
  assert.doesNotMatch(output, /Release pipeline: last successful/);
});

test("reports a run where only some release jobs released as partly released", async () => {
  const second = { ...releaseJob("success"), name: "release-please-docs" };
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    releaseJobs: [testJob, releaseJob("skipped"), second],
  });
  assert.equal(code, 1);
  assert.match(
    output,
    /Release pipeline: partly released\. In the latest `release-please\.yml` run \([^)]+\), 1 of 2 release jobs did not release: 1 skipped its App token step because the `RELEASE_PLEASE_CLIENT_ID` variable or `RELEASE_PLEASE_APP_KEY` secret is not set or not available to it\./,
  );
  assert.doesNotMatch(output, /not configured/);
});

test("reports every release job skipped for missing credentials as not configured", async () => {
  const second = { ...releaseJob("skipped"), name: "release-please-docs" };
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    releaseJobs: [testJob, releaseJob("skipped"), second],
  });
  assert.equal(code, 1);
  assert.match(output, /Release pipeline: not configured/);
});

test("reports an App token step that neither ran nor was skipped as not released", async () => {
  // A customised workflow that lets the token step fail without failing the run.
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    releaseJobs: [testJob, releaseJob("failure")],
  });
  assert.equal(code, 1);
  assert.match(
    output,
    /Release pipeline: not released\. .*1 of 1 release job did not release: 1 ran an App token step that concluded failure\./,
  );
});

test("judges a release workflow without the credentials check by its conclusion", async () => {
  // A customised workflow: a skipped step of another name, and no credentials check.
  const customised = {
    ...releaseJob("success"),
    steps: [
      { number: 1, name: "Set up job", status: "completed", conclusion: "success" },
      { number: 2, name: "Create token", status: "completed", conclusion: "skipped" },
      { number: 3, name: "Generate GitHub App token", status: "completed", conclusion: "skipped" },
      { number: 4, name: "Complete job", status: "completed", conclusion: "success" },
    ],
  };
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    releaseJobs: [testJob, customised],
  });
  assert.equal(code, 0, output);
  assert.match(
    output,
    /Release pipeline: last successful `release-please\.yml` run completed successfully/,
  );
  assert.doesNotMatch(output, /not configured/);
});

test("reports unavailable release jobs without claiming the release healthy", async () => {
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    jobsStatus: 403,
  });
  assert.equal(code, 1);
  assert.match(
    output,
    /Release pipeline: could not be determined\W+Release Please jobs API returned 403/,
  );
  assert.doesNotMatch(output, /Release pipeline: last successful/);
});

test("reports a successful release run without a run id as undetermined", async () => {
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    latestReleaseRuns: [{ ...successfulRelease(), id: undefined }],
  });
  assert.equal(code, 1);
  assert.match(
    output,
    /Release pipeline: could not be determined\W+Release Please API returned a completed run without a run id/,
  );
});

test("reports orphan detection as unavailable when npm audit returns an error response", async () => {
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    auditReport: { message: "request failed, reason: connect ECONNREFUSED", error: {} },
  });
  assert.equal(code, 1);
  assert.match(
    output,
    /Orphaned advisory-baseline rows: could not be determined \(npm audit returned an incomplete or error response/,
  );
  assert.doesNotMatch(output, /Orphaned advisory-baseline rows \(advisory not found/);
});

test("reports an impossible review date as actionable, not healthy", async () => {
  const { code, output } = await runFixture({
    rows: [documented.replace("2099-01-01", "2099-02-30")],
    lintRows: ["| 1 | `no-console` | `e2e/fixture.mjs` | accepted | 2099-13-01 |"],
    alerts: matchingAlert,
  });
  assert.equal(code, 1);
  assert.match(output, /GHSA-aaaa-bbbb-cccc.*\(invalid review date\)/);
  assert.match(output, /no-console in e2e\/fixture\.mjs.*\(invalid review date\)/);
});

test("accepts a clean npm audit with no vulnerabilities", async () => {
  const { output } = await runFixture({
    rows: [],
    alerts: [],
    auditReport: { metadata: { vulnerabilities: { total: 0 } }, vulnerabilities: {} },
  });
  assert.match(
    output,
    /Orphaned advisory-baseline rows: none; every row's advisory appears in `npm audit`/,
  );
});

test("reports a security.txt that expires more than the review window away as informational", async () => {
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    securityTxtContents: securityTxt(),
  });
  assert.equal(code, 0);
  assert.match(output, /security\.txt: Expires 2099-01-01T00:00:00\.000Z, more than 30 days away/);
});

test("reports an expired security.txt as actionable", async () => {
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    securityTxtContents: securityTxt("2020-01-01T00:00:00.000Z"),
  });
  assert.equal(code, 1);
  assert.match(output, /security\.txt: expired\. Expires was 2020-01-01T00:00:00\.000Z/);
  assert.match(output, /Baseline review completed/);
});

test("reports a security.txt that expired less than a day ago as expired, not upcoming", async () => {
  const barelyExpired = new Date(Date.now() - 60 * 60 * 1000).toISOString();
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    securityTxtContents: securityTxt(barelyExpired),
  });
  assert.equal(code, 1);
  assert.match(output, new RegExp(`security\\.txt: expired\\. Expires was ${barelyExpired}`));
  assert.doesNotMatch(output, /security\.txt:.*renew it soon/);
});

test("reports a security.txt expiring within the review window as informational", async () => {
  const soon = new Date(Date.now() + 15 * 86_400_000).toISOString();
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    securityTxtContents: securityTxt(soon),
  });
  assert.equal(code, 0);
  assert.match(
    output,
    new RegExp(`security\\.txt: Expires ${soon}, within 30 days; renew it soon`),
  );
});

test("reports a security.txt without an Expires field as actionable", async () => {
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    securityTxtContents: "Contact: mailto:security@example.com\n",
  });
  assert.equal(code, 1);
  assert.match(output, /^- security\.txt has no Expires field$/m);
});

test("reports a security.txt whose Expires field is not an RFC 3339 date-time as actionable", async () => {
  for (const expires of [
    "next-year",
    "2099-02-30T00:00:00Z",
    "2099-01-01T00:00:00Z trailing",
    "2099-01-01",
    "2099-01-01T24:00:00Z",
    "2099-01-01T00:00:00+24:00",
  ]) {
    const { code, output } = await runFixture({
      rows: [documented],
      alerts: matchingAlert,
      securityTxtContents: securityTxt(expires),
    });
    assert.equal(code, 1, expires);
    assert.match(output, /^- security\.txt Expires field is not an RFC 3339 date-time$/m, expires);
  }
});

test("reads the Expires field name in any case and an offset date-time", async () => {
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    securityTxtContents:
      "Contact: mailto:security@example.com\nexpires: 2099-01-01t02:00:00+02:00\n",
  });
  assert.equal(code, 0);
  assert.match(output, /security\.txt: Expires 2099-01-01T00:00:00\.000Z, more than 30 days away/);
});

test("reports a security.txt with more than one Expires field as actionable", async () => {
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    securityTxtContents: securityTxt() + "Expires: 2098-01-01T00:00:00Z\n",
  });
  assert.equal(code, 1);
  assert.match(output, /^- security\.txt has more than one Expires field$/m);
});

test("reports a security.txt that cannot be read as actionable", async () => {
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    securityTxtDirectory: true,
  });
  assert.equal(code, 1);
  assert.match(output, /security\.txt: could not be read \(/);
});

test("still reports security.txt when the advisory baseline cannot be parsed", async () => {
  const { code, output } = await runFixture({
    rows: [],
    alerts: [],
    advisoryBaselineContents: "not a baseline table",
    securityTxtContents: securityTxt("2020-01-01T00:00:00.000Z"),
  });
  assert.equal(code, 1);
  assert.match(output, /Advisory baseline: could not be parsed/);
  assert.match(output, /security\.txt: expired\. Expires was 2020-01-01T00:00:00\.000Z/);
});

test("still reports security.txt without a GitHub token", async () => {
  const { code, output } = await runFixture({
    rows: [documented],
    alerts: matchingAlert,
    token: false,
    securityTxtContents: securityTxt(),
  });
  assert.equal(code, 1);
  assert.match(output, /security\.txt: Expires 2099-01-01T00:00:00\.000Z, more than 30 days away/);
});
