# Start all endpoints in `ngrok.yml` (same as `make ngrok` when that file exists).
# Requires: `ngrok.yml` in repo root (copy from ngrok.example.yml, set agent.authtoken).
# Usage (from repo root):  pwsh -File scripts/ngrok-all.ps1

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ngrokYml = Join-Path $repoRoot "ngrok.yml"

if (-not (Test-Path $ngrokYml)) {
    Write-Error "Missing $ngrokYml — copy ngrok.example.yml to ngrok.yml and set agent.authtoken in that file."
}

Push-Location $repoRoot
try {
    & ngrok start --all --config $ngrokYml
} finally {
    Pop-Location
}
