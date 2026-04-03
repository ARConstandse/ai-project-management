$ErrorActionPreference = "Stop"

docker info *> $null
if ($LASTEXITCODE -ne 0) {
  throw "Docker engine is not running. Start Docker Desktop and retry."
}

Write-Host "Starting PM app container..."
docker compose up --build -d
Write-Host "Started. Open http://127.0.0.1:8000"
