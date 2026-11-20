#!/bin/sh
set -eu

cd "$(dirname "$0")/../.."
python3 validate_templates.py
python3 -m pytest
node --test templates/*.test.mjs
npx --yes prettier@3.9.9 --config templates/.prettierrc.json --check "templates/*.mjs"
npx --yes eslint@9.39.5 --no-config-lookup --rule '{"no-unused-vars":"error"}' "templates/*.mjs"

md_dir=$(mktemp -d)
trap 'rm -rf "$md_dir"' EXIT
trap 'exit 1' HUP INT TERM
python3 validate_templates.py --render-markdown "$md_dir"
npx --yes markdownlint-cli2@0.23.3 --config markdownlint-generated.jsonc "$md_dir/**/*.md"
npx --yes markdownlint-cli2@0.23.3 --config markdownlint-generated.jsonc \
  "*.md" "docs/**/*.md" ".github/**/*.md" ".agents/**/*.md" "!CHANGELOG.md"
python3 -I .github/scripts/check_public_content.py --range=origin/main..HEAD --files=origin/main..HEAD
