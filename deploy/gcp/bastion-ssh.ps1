# Connect to asanclip-bastion via IAP using Windows OpenSSH (avoids PuTTY/plink failures).
param(
    [int]$LocalPort = 2222,
    [string]$Zone = "europe-west1-b",
    [string]$Project = "asanclip-rag-prod",
    [string]$Instance = "asanclip-bastion",
    [string]$User = "Sahar",
    [string]$KeyFile = "$env:USERPROFILE\.ssh\google_compute_engine"
)

$ErrorActionPreference = "Stop"

function Test-PortListening([int]$Port) {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

if (-not (Test-Path $KeyFile)) {
    throw "Missing SSH key: $KeyFile"
}

if (-not (Test-PortListening $LocalPort)) {
    Write-Host "Starting IAP tunnel on localhost:$LocalPort ..."
    Start-Process -FilePath "gcloud" -ArgumentList @(
        "compute", "start-iap-tunnel", $Instance, "22",
        "--local-host-port=localhost:$LocalPort",
        "--zone=$Zone",
        "--project=$Project"
    ) -WindowStyle Hidden | Out-Null

    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortListening $LocalPort) { break }
        Start-Sleep -Seconds 1
    }
    if (-not (Test-PortListening $LocalPort)) {
        throw "IAP tunnel did not become ready on port $LocalPort"
    }
}

Write-Host "Connecting with OpenSSH to ${User}@127.0.0.1:$LocalPort ..."
& ssh.exe -i $KeyFile -p $LocalPort -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL "$User@127.0.0.1" @args
