# Same JSON-RPC as `make mcp-fetch-patient` / `make week2-fhir-smoke` for Windows shells.
# Requires: MCP on http://localhost:8000/mcp
# Env: FHIR_URL, FHIR_TOKEN, PATIENT_ID (and optional MCP_URL)

$ErrorActionPreference = "Stop"
$base = if ($env:MCP_URL) { $env:MCP_URL } else { "http://localhost:8000/mcp" }
if (-not ($base -match "/mcp`$")) { $base = "$($base.TrimEnd("/"))/mcp" }

foreach ($name in @("FHIR_URL", "FHIR_TOKEN", "PATIENT_ID")) {
    $v = [Environment]::GetEnvironmentVariable($name)
    if (-not $v) { Write-Error "Missing env: $name" }
}

$body = @{
    jsonrpc = "2.0"
    id      = 2
    method  = "tools/call"
    params  = @{
        name      = "fetch_patient_context"
        arguments = @{
            patient_id   = $env:PATIENT_ID
            service_code = "72148"
        }
    }
} | ConvertTo-Json -Depth 6 -Compress

$headers = @{
    "Accept"             = "application/json, text/event-stream"
    "Content-Type"       = "application/json"
    "x-fhir-server-url"   = $env:FHIR_URL
    "x-fhir-access-token" = $env:FHIR_TOKEN
}

Write-Host "POST $base"
Invoke-RestMethod -Uri $base -Method Post -Headers $headers -Body $body
