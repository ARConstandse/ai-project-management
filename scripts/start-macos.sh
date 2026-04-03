#!/usr/bin/env bash
set -euo pipefail

docker info >/dev/null 2>&1 || {
  echo "Docker engine is not running. Start Docker and retry."
  exit 1
}

echo "Starting PM app container..."
docker compose up --build -d
echo "Started. Open http://127.0.0.1:8000"
