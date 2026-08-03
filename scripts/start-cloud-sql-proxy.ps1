# Start Cloud SQL Auth Proxy, stopping any existing listener on the target port first.
param(
    [string]$Address = "127.0.0.1",
    [int]$Port = 5434,
    [string]$ConnectionName = "asanclip-rag-prod:europe-west1:asanclip-db-prod",
    [switch]$Background
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ProxyExe = Join-Path $RepoRoot "cloud-sql-proxy.exe"

if (-not (Test-Path $ProxyExe)) {
    throw "cloud-sql-proxy.exe not found at $ProxyExe"
}

function Get-ListenerPid([int]$ListenPort) {
    $matches = netstat -ano | Select-String "TCP\s+$Address`:$ListenPort\s"
    foreach ($line in $matches) {
        $pidText = ($line.ToString().Trim() -split "\s+")[-1]
        if ($pidText -match "^\d+$") {
            return [int]$pidText
        }
    }
    return $null
}

function Get-AdcPath {
    if ($env:GOOGLE_APPLICATION_CREDENTIALS -and (Test-Path $env:GOOGLE_APPLICATION_CREDENTIALS)) {
        return $env:GOOGLE_APPLICATION_CREDENTIALS
    }
    $gcloudConfig = gcloud info --format="value(config.paths.global_config_dir)" 2>$null
    if ($gcloudConfig) {
        $adc = Join-Path $gcloudConfig "application_default_credentials.json"
        if (Test-Path $adc) {
            return $adc
        }
    }
    $default = Join-Path $env:APPDATA "gcloud\application_default_credentials.json"
    if (Test-Path $default) {
        return $default
    }
    return $null
}

$existingPid = Get-ListenerPid -ListenPort $Port
if ($existingPid) {
    $owner = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
    if ($owner -and $owner.ProcessName -eq "cloud-sql-proxy") {
        Write-Host "Port $Port is in use by cloud-sql-proxy (PID $existingPid). Stopping it..."
        Stop-Process -Id $existingPid -Force
        Start-Sleep -Seconds 2
    }
    elseif ($owner) {
        throw "Port $Port is in use by $($owner.ProcessName) (PID $existingPid). Free the port or pass -Port with another value."
    }
}

if (Get-ListenerPid -ListenPort $Port) {
    throw "Port $Port is still in use after cleanup."
}

Write-Host "Starting Cloud SQL proxy on ${Address}:$Port for $ConnectionName"

$gcloudConfig = gcloud info --format="value(config.paths.global_config_dir)" 2>$null
if ($gcloudConfig) {
    $env:CLOUDSDK_CONFIG = $gcloudConfig
}

$adcPath = Get-AdcPath
$proxyArgs = @(
    "--gcloud-auth",
    "--address", $Address,
    "--port", "$Port",
    $ConnectionName
)

if ($adcPath) {
    $env:GOOGLE_APPLICATION_CREDENTIALS = $adcPath
    Write-Host "Using gcloud-auth with ADC: $adcPath"
}
else {
    Write-Host "Using gcloud-auth (run: gcloud auth login)"
}

if ($Background) {
    # Windows PowerShell 5.x: child inherits $env: from this process (no -Environment flag).
    $process = Start-Process -FilePath $ProxyExe -ArgumentList $proxyArgs -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 3
    if ($process.HasExited) {
        throw "cloud-sql-proxy exited immediately with code $($process.ExitCode)."
    }
    if (-not (Get-ListenerPid -ListenPort $Port)) {
        throw "cloud-sql-proxy started but port $Port is not listening."
    }
    Write-Host "Proxy running in background (PID $($process.Id))."
    Write-Host "DATABASE_URL example:"
    Write-Host "  postgresql+psycopg2://asanclip_app:PASSWORD@${Address}:$Port/Sale1404"
    exit 0
}

& $ProxyExe @proxyArgs
