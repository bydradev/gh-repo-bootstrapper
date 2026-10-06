---
name: screenshot-review
description: >-
  Use when a change affects tracked screenshots, captured views, or other user-facing visuals, before committing regenerated screenshot assets, or when generating, reviewing, or promoting images from a repository's deterministic capture lane. Covers routing to the repository's own screenshot skill, keeping screenshot generation and visual approval as separate gates, privacy of captured data, image classes and review strength, the complete-set review process, acceptance criteria, promotion safety, and verifying the rendered product.
---

# Screenshot review

Screenshot guidance is capability-conditional: do not assume browser or native
capture tooling exists in this repository. A successful screenshot-generation
workflow proves capture only; it does not approve visual fidelity or privacy.

If `## Project specifics` in `AGENTS.md` names a repository-owned skill, or a
section of one, for screenshot or visual-review work, load it first. It holds
this repository's capability boundaries and procedures, and baseline pointers
where present. Where it is narrower than this skill, it governs.

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

## When the repository has a deterministic capture lane

A capture lane is a repository-provided command that renders fixed, fictional
data into a known set of images. These rules apply only when the repository
has one; its own screenshot skill names the command, configuration, image set,
and current baseline.

### Image classes and review strength

| Image class | Review boundary |
| --- | --- |
| Temporary diagnostic artifact, such as a test-failure capture | Normally untracked; generation alone is not acceptance |
| Visual-regression baseline | Review the image diff and the behavior behind it in the pull request |
| Documentation image | Review visual quality, truthfulness, accessibility, and privacy |
| Tracked asset set | Review every image as below; the repository skill states whether one pass or two fresh-context passes are required |

### Review process

1. Generate a fresh artifact from the intended source commit. For final
   acceptance, prefer the repository's hosted or CI run over a local one.
2. Confirm every configured image exists and that no unexpected file was
   produced.
3. Inspect every image at full resolution for layout, content, accessibility,
   and privacy.
4. Fix product or capture defects in source; never retouch an image to hide
   them.
5. Regenerate the complete set and repeat the review after any fix.
6. For launch-facing images, do a second fresh-context pass against newly
   generated evidence. A second reviewer is preferred; otherwise separate the
   passes with unrelated work or a full validation cycle.
7. Commit accepted images only with the source change that adopts them.

Record the decision, the artifact or run reference, the source commit, the
reviewer or review context, the files reviewed, and any unresolved findings.

### Acceptance criteria

For every image, confirm:

- the configured view, viewport, theme, and full-page behavior are as expected;
- there is no clipping, overflow, overlap, broken truncation, sliced
  navigation, unreadable wrapping, loading artifact, or development chrome;
- values are internally consistent, with no `undefined`, `NaN`, placeholder
  copy, contradictory empty state, or claim that fixture data is live;
- only fictional organizations, people, identifiers, and URLs appear, and no
  real private name, email address, token-shaped value, internal URL, or
  unrelated desktop content is visible;
- text is legible, contrast is credible, focus and hover artifacts are absent,
  and meaning does not rely on color alone; and
- a launch-facing image shows the product with useful composition and no
  error state or development-only presentation.

### Promotion safety

Capture into a temporary location and promote only after every configured
image succeeds. If promotion replaces files one at a time and fails partway,
inspect the diff and the destination set, then rerun the complete capture.
Never treat a partial replacement as an accepted set.
