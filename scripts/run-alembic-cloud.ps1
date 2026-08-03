# Run Alembic against Cloud SQL via the local Auth Proxy (.env settings).
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AlembicArgs = @("current")
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

# Stale shell DATABASE_URL overrides .env and causes wrong host/user (e.g. local postgres).
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue

& (Join-Path $PSScriptRoot "start-cloud-sql-proxy.ps1") -Background | Out-Null

Push-Location $RepoRoot
try {
    & (Join-Path $RepoRoot "venv/Scripts/alembic.exe") @AlembicArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
