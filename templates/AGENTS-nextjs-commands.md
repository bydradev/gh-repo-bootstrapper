
## Tooling

Run all checks before pushing:

```sh
npm run lint          # ESLint
npm run format:check  # Prettier
npm run typecheck     # TypeScript
npm test              # unit/integration tests
npm run audit:production  # runtime advisory floor; requires network access
npm run verify:baselines  # lint/advisory baseline parity
npm run build         # Next.js production build
npm run test:e2e      # Playwright e2e
```

`npm run lint:fix` auto-fixes ESLint violations; `npm run format` auto-fixes
Prettier formatting issues.

Always run the relevant checks locally before pushing. For changes that alter browser-facing UI or user interactions, run `npm run test:e2e` locally (or `npm run test:e2e:local` when that script is available) before opening or updating a PR.
