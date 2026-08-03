# Run Alembic against production Cloud SQL via bastion IAP tunnel + Cloud SQL Auth Proxy.
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AlembicArgs = @("current")
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Project = "asanclip-rag-prod"
$Zone = "europe-west1-b"
$Instance = "asanclip-bastion"
$SshPort = 2222
$ProxyPort = 54321
$KeyFile = "$env:USERPROFILE\.ssh\google_compute_engine"

function Test-PortListening([int]$Port) {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Ensure-IapTunnel {
    if (Test-PortListening $SshPort) { return }
    Write-Host "Starting IAP SSH tunnel on localhost:$SshPort ..."
    Start-Process -FilePath "gcloud" -ArgumentList @(
        "compute", "start-iap-tunnel", $Instance, "22",
        "--local-host-port=localhost:$SshPort",
        "--zone=$Zone",
        "--project=$Project"
    ) -WindowStyle Hidden | Out-Null
    $deadline = (Get-Date).AddSeconds(45)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortListening $SshPort) { return }
        Start-Sleep -Seconds 1
    }
    throw "IAP SSH tunnel did not become ready on port $SshPort"
}

function Ensure-ProxyForward {
    if (Test-PortListening $ProxyPort) { return }
    Write-Host "Forwarding Cloud SQL Auth Proxy localhost:$ProxyPort through bastion ..."
    Start-Process -FilePath "ssh.exe" -ArgumentList @(
        "-i", $KeyFile,
        "-p", "$SshPort",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=NUL",
        "-N",
        "-L", "${ProxyPort}:127.0.0.1:${ProxyPort}",
        "Sahar@127.0.0.1"
    ) -WindowStyle Hidden | Out-Null
    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortListening $ProxyPort) { return }
        Start-Sleep -Seconds 1
    }
    throw "Cloud SQL proxy forward did not become ready on port $ProxyPort"
}

function Get-ProductionDatabaseUrl {
    $raw = gcloud secrets versions access latest --secret=database-url --project=$Project
    if (-not $raw) { throw "database-url secret is empty" }

    $match = [regex]::Match(
        $raw,
        '^postgresql(?:\+[^:]+)?://([^:]+):([^@]+)@/?([^?]+)'
    )
    if (-not $match.Success) {
        throw "Could not parse database-url secret"
    }

    $user = $match.Groups[1].Value
    $password = [uri]::UnescapeDataString($match.Groups[2].Value)
    $database = $match.Groups[3].Value.TrimStart('/')
    $encodedPassword = [uri]::EscapeDataString($password)

    return "postgresql+psycopg2://${user}:${encodedPassword}@127.0.0.1:${ProxyPort}/${database}"
}

function Show-RedactedUrl([string]$Url) {
    return ($Url -replace '://([^:]+):([^@]+)@', '://$1:***@')
}

Ensure-IapTunnel
Ensure-ProxyForward

$databaseUrl = Get-ProductionDatabaseUrl
Write-Host "Target DATABASE_URL: $(Show-RedactedUrl $databaseUrl)"

Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
$env:DATABASE_URL = $databaseUrl
$env:CLOUDSQL_PROXY_HOST = "127.0.0.1"
$env:CLOUDSQL_PROXY_PORT = "$ProxyPort"

Push-Location $RepoRoot
try {
    $alembic = Join-Path $RepoRoot "venv\Scripts\alembic.exe"
    if (-not (Test-Path $alembic)) {
        throw "Alembic not found at $alembic. Create the venv and install requirements first."
    }
    & $alembic @AlembicArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
