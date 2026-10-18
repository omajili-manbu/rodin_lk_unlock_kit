# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 omajili-manbu
# Get a fresh unlock token and sign it locally with tools/sign_token.py.
#
# This does NOT run `oem unlock` for you. After signing, do the stage/unlock
# immediately, without rebooting or switching slots.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts/get_token_and_sign.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/get_token_and_sign.ps1 -Out unlock_a.sig
#   powershell -ExecutionPolicy Bypass -File scripts/get_token_and_sign.ps1 -Key C:\keys\my_priv.pem
#
param(
    [string]$Out = "unlock.sig",
    [string]$Key = "",
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Get-Command fastboot -ErrorAction SilentlyContinue)) {
    throw "fastboot not found in PATH"
}
if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    throw "$Python not found; install Python 3 or pass -Python <path>"
}

Write-Host "== current slot =="
& fastboot getvar current-slot 2>&1 | ForEach-Object { $_ }

Write-Host "== fastboot oem get_token =="
$tokenOutput = & fastboot oem get_token 2>&1
$tokenOutput | Tee-Object -FilePath token.txt

if (-not (($tokenOutput | Out-String) -match "token")) {
    throw "no token in fastboot output; check the device state"
}

$signArgs = @("tools/sign_token.py", "--token-file", "token.txt", "-o", $Out, "--raw")
if ($Key -ne "") {
    $signArgs += @("-k", $Key)
}

Write-Host "== signing =="
& $Python @signArgs

Write-Host ""
Write-Host "Signature: $Out"
Write-Host "Do this now, without rebooting or switching slots:"
Write-Host "  fastboot stage $Out"
Write-Host "  fastboot oem unlock"
Write-Host "  fastboot oem lks"
Write-Host ""
Write-Host "If anything fails, re-run this script to obtain a fresh token."
