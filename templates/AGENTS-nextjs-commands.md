
## Tooling

Run the checks your change affects before pushing:

```sh
npm run lint          # ESLint
npm run format:check  # Prettier
npm run typecheck     # TypeScript
npm test              # unit/integration tests
npm run audit:production  # runtime advisory floor; requires network access
npm run verify:baselines  # lint/advisory baseline parity
npm run build         # Next.js production build
npm run test:e2e      # Playwright e2e; required for UI or interaction changes
```
