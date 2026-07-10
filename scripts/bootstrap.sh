#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

command -v docker >/dev/null 2>&1 || { echo "Docker is required." >&2; exit 1; }
docker compose version >/dev/null

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example; replace development secrets before deployment."
fi

docker compose config --quiet
echo "YeliSport development environment is ready. Run: make up"
