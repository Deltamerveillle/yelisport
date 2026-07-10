#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

docker compose run --rm --no-deps -e APP_ENV=test api pytest
docker compose run --rm --no-deps -e APP_ENV=test ai pytest

if command -v flutter >/dev/null 2>&1; then
  (cd apps/mobile && flutter test)
else
  echo "Flutter not found; skipped mobile tests." >&2
fi
