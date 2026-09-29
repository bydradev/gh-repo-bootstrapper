<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# This project uses the App Router

Routes live in `app/` or `src/app/`, not the Pages Router (`pages/`). The two
routers are different paradigms with different data-fetching, layout, and
metadata APIs — don't mix them. If this repository's scaffold uses the Pages
Router instead, replace this section.

This section sits outside the `nextjs-agent-rules` markers on purpose:
`next dev` rewrites everything between them, so anything repository-specific
must live out here to survive.

