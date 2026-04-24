<#
.SYNOPSIS
    Start both ngrok tunnels (MCP on :8000 and A2A on :8001) from ngrok.yml.

.DESCRIPTION
    Windows equivalent of `make ngrok-all`. Validates the config, then
    runs `ngrok start --all --config ngrok.yml`.

    Prerequisites:
      - ngrok 3.x installed and on PATH (`ngrok --version`).
      - ngrok.yml in the repo root (copy from ngrok.example.yml and fill in
        your authtoken + reserved host — see that file for setup).
      - mcp_server running on 127.0.0.1:8000 (make mcp, or equivalent).
      - a2a_agent running on 127.0.0.1:8001 (make agent, or equivalent).

    Usage:
      pwsh -File scripts/ngrok-all.ps1
      pwsh -File scripts/ngrok-all.ps1 -Config .\custom-ngrok.yml

.NOTES
    See GitHub issue #17 and docs/po_platform_notes.md for why the MCP and
    A2A services MUST have distinct public URLs when registered in a
    Prompt Opinion workspace.
#>
param(
    [string]$Config = "ngrok.yml"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command ngrok -ErrorAction SilentlyContinue)) {
    Write-Error "ngrok CLI not found on PATH. Install from https://ngrok.com/download"
    exit 1
}

if (-not (Test-Path $Config)) {
    Write-Error ("Config file '{0}' not found. Copy ngrok.example.yml to ngrok.yml and edit it." -f $Config)
    exit 1
}

Write-Host ("Validating ngrok config at {0}..." -f $Config)
& ngrok config check --config $Config
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Starting both tunnels (Ctrl-C to stop)..."
& ngrok start --all --config $Config
exit $LASTEXITCODE
