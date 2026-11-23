## Cloudflare deployment

These rules are stop-and-ask items.

- Merging a Release Please PR ships to production: `release-deploy.yml`
  deploys the published release while the repository variable
  `CLOUDFLARE_DEPLOY_ENABLED` is `true` (record its last known value in
  `docs/current-work.md`). Never merge one without explicit operator
  authorization for that release.
- Never run `wrangler deploy` (or any npm script that runs it),
  `wrangler versions upload`, `wrangler versions deploy`, `wrangler rollback`,
  `wrangler secret put` or `wrangler secret delete`, for any environment,
  without explicit operator authorization. Secret changes deploy immediately.
  `wrangler deploy --dry-run`, and a wrapping npm script run with
  `-- --dry-run` when the script passes that flag to Wrangler, are exempt:
  they only build and package locally.
- Never install, update or re-add the vendored Cloudflare skills
  (`npx skills add`, `npx skills update`, `npx skills experimental_install`),
  install the Cloudflare plugin, or configure the Cloudflare MCP server
  (`https://mcp.cloudflare.com/mcp`, which reaches the Cloudflare account once
  signed in) on your own. `skills-lock.json` pins the skills to a reviewed
  upstream commit (`ref`). Refresh them only when asked, in a PR that shows
  the diff, by moving that pin. Name each skill `skills-lock.json` lists:

  ```sh
  GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.autocrlf GIT_CONFIG_VALUE_0=false \
    DISABLE_TELEMETRY=1 npx skills@<pinned version> add "cloudflare/skills#<full sha>" \
    --skill <name> [--skill <name> ...] -a claude-code -a codex -y
  ```

- The vendored skills under `.agents/skills/` stay byte-identical to the
  `skills-lock.json` pin. Where one differs from this file, this file governs.
  Record a skill section that does not apply under `## Project specifics`.
- Before posting feedback upstream, as a skill's feedback guide describes,
  redact private code, configuration, credentials, resource identifiers,
  logs and customer data, and get the operator's approval of the exact title
  and body.

