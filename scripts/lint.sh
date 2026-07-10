#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

docker compose run --rm --no-deps api ruff check .
docker compose run --rm --no-deps api mypy app
docker compose run --rm --no-deps ai ruff check .

if command -v flutter >/dev/null 2>&1; then
  (cd apps/mobile && flutter analyze)
else
  echo "Flutter not found; skipped mobile analysis." >&2
fi
