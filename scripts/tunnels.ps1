<#
.SYNOPSIS
    Start both tunnels: ngrok for A2A (:8001) and cloudflared for MCP (:8000).

.DESCRIPTION
    Windows equivalent of running `make cf-tunnel` + `make ngrok` in two
    terminals. Launches cloudflared as a background job, then runs ngrok
    in the foreground (Ctrl-C stops ngrok; the cloudflared job is cleaned
    up automatically).

    Prerequisites:
      - ngrok 3.x on PATH      (`ngrok --version`)
      - cloudflared on PATH     (`cloudflared --version`)
      - ngrok.yml in repo root  (copy from ngrok.example.yml + fill in authtoken)
      - mcp_server on 127.0.0.1:8000  (`make mcp` or equivalent)
      - a2a_agent  on 127.0.0.1:8001  (`make agent` or equivalent)

    Usage:
      pwsh -File scripts/tunnels.ps1

.NOTES
    See GitHub issue #17 and docs/po_platform_notes.md for why the MCP and
    A2A services need distinct public URLs when registered in a PO workspace.
#>
param(
    [string]$NgrokConfig = "ngrok.yml"
)

$ErrorActionPreference = "Stop"

# --- preflight ---------------------------------------------------------------
foreach ($tool in @("ngrok", "cloudflared")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Error "$tool not found on PATH. Install it first."
        exit 1
    }
}

if (-not (Test-Path $NgrokConfig)) {
    Write-Error ("ngrok config '{0}' not found. Copy ngrok.example.yml to ngrok.yml and edit it." -f $NgrokConfig)
    exit 1
}

# --- start cloudflared (MCP :8000) in background ----------------------------
Write-Host "`n=== Starting cloudflared tunnel for MCP (:8000) ===`n"
$cfJob = Start-Job -ScriptBlock {
    & cloudflared tunnel --url http://localhost:8000 2>&1
}
Start-Sleep -Seconds 3
Write-Host "cloudflared running as background job $($cfJob.Id)."
Write-Host "Check its output with: Receive-Job $($cfJob.Id)"
Write-Host "Copy the https://*.trycloudflare.com URL + /mcp into PO Server Hub.`n"

# --- start ngrok (A2A :8001) in foreground -----------------------------------
Write-Host "=== Starting ngrok tunnel for A2A (:8001) — Ctrl-C to stop both ===`n"
try {
    & ngrok start --all --config $NgrokConfig
} finally {
    Write-Host "`nStopping cloudflared background job..."
    Stop-Job $cfJob -ErrorAction SilentlyContinue
    Remove-Job $cfJob -Force -ErrorAction SilentlyContinue
}
