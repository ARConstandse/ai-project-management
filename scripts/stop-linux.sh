#!/usr/bin/env bash
set -euo pipefail

docker info >/dev/null 2>&1 || {
  echo "Docker engine is not running. Start Docker and retry."
  exit 1
}

echo "Stopping PM app container..."
docker compose down --remove-orphans
echo "Stopped."
