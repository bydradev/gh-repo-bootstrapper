---
name: public-site-indexing
description: "Use before adding or changing `robots.ts`, `robots.txt`, `sitemap.ts` or the sitemap, a page's metadata `robots` setting or `noindex`, the site's hostname or canonical URL, or its AI crawler policy in this Next.js repository. Covers what a public site serves to crawlers, which pages stay out of the index and the sitemap, where AI crawler policy lives, and keeping default and per-deployment hostnames out of search results."
---

# Public-site indexing

These rules apply to a site meant to be found in search. If
`## Project specifics` in `AGENTS.md` names a repository-owned skill for
indexing or search, or says the site is not public, that governs.

A public site serves `robots.txt` and a sitemap from the App Router metadata
files `robots.ts` and `sitemap.ts`. Allow all crawlers and link the sitemap;
disallow only paths with a reason, such as API routes that are not pages. Give
personal or search-result pages `robots: { index: false, follow: true }` in
their metadata, and leave them out of the sitemap.

Keep AI crawler policy in one place: the hosting platform's bot controls when
it has them, otherwise per-bot rules in `robots.ts`.

When the host also serves the site on a default or per-deployment hostname,
turn those hostnames off and send `X-Robots-Tag: noindex, nofollow` on them as
a backstop, so only the canonical domain is indexed. For a static export, make
the CI export check require `out/robots.txt` and `out/sitemap.xml`.
