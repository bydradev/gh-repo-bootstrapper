---
name: screenshot-review
description: >-
  Use when a change affects tracked screenshots, captured views, or other user-facing visuals, or before committing regenerated screenshot assets. Covers keeping screenshot generation and visual approval as separate gates, privacy of captured data, and verifying the rendered product.
---

# Screenshot review

Screenshot guidance is capability-conditional: do not assume browser or native
capture tooling exists in this repository. A successful screenshot-generation
workflow proves capture only; it does not approve visual fidelity or privacy.

**Treat screenshot generation and visual approval as separate gates.** For
changes affecting tracked screenshots or captured views, follow
`docs/screenshot-review.md` (repository root) when this
repository has it; otherwise follow the repository's documented
screenshot-review process when present. A successful
screenshot-generation workflow means only that artifacts were produced; it is
not visual approval. Never capture live or private data, and do not commit
regenerated assets until the required visual and privacy review has passed.

For user-facing changes, verify the rendered or running product in addition to
automated checks; tests alone do not establish visual or interaction quality.
