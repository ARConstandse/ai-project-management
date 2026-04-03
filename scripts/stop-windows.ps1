$ErrorActionPreference = "Stop"

docker info *> $null
if ($LASTEXITCODE -ne 0) {
  throw "Docker engine is not running. Start Docker Desktop and retry."
}

Write-Host "Stopping PM app container..."
docker compose down --remove-orphans
Write-Host "Stopped."
