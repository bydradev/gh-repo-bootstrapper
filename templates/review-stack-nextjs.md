### Next.js

- **Server and client boundary.** A `"use client"` module imports no
  server-only code or secrets, and server-only modules import `server-only`.
  `NEXT_PUBLIC_*` variables and the `env` key in `next.config.*` are inlined
  into client bundles, so neither holds a secret. Props passed to Client
  Components and Server Action return values reach the browser: pass only the
  fields the client needs.
- **Server Actions and Route Handlers** are public HTTP endpoints: each
  validates its input and checks authorisation itself, not only in
  `proxy.ts`, middleware or the UI.
- **Caching and rendering.** Per-user data is never cached or statically
  rendered for everyone. Revalidation matches how fresh the data must be. A
  static export (`output: "export"`) gains no request-time features.
- **Untrusted content.** `dangerouslySetInnerHTML` and rendered Markdown are
  sanitised; links built from data reject `javascript:` URLs. Server-side
  fetches of user or feed URLs are restricted, and `images.remotePatterns` is
  not a wildcard.
- **React state.** Server-rendered output holds no time, random or
  locale-dependent values that cause hydration mismatches. Effect dependencies
  are complete, and a slow response cannot replace newer state.
- **Indexing.** Changes to `robots.txt`, the sitemap, `noindex` or canonical
  hosts are intended (`public-site-indexing`).
- **Tests and baselines.** `local-validation-nextjs` says which suites run on
  pull requests; as generated, pull requests skip browser E2E, so E2E changes
  need local or `main` evidence. A new row in `docs/lint-baseline.md` or
  `docs/advisory-baseline.md` follows `baseline-process`, and a baseline never
  grows just to pass.
