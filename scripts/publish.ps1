# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 omajili-manbu
# Publish rodin_lk_unlock_kit to GitHub.
#
# Prerequisites:
#   1. gh CLI installed
#   2. gh auth login completed (or GH_TOKEN set)
#   3. run this from the repository root (or let the script cd there)
#
# The signing key in keys/ is intentionally public. If GitHub's secret scanning
# blocks the push, the repository owner can acknowledge it in the GitHub UI.
# Do not obfuscate or rewrite the key to evade the scanner.
#
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$Repo = "omajili-manbu/rodin_lk_unlock_kit"
$Desc = "Offline bootloader unlock kit for Redmi Turbo 4 (rodin): self-built lk images (303/304), public signing key, offline token signer, full write-up."

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) not found: https://cli.github.com/"
}

gh auth status
if ($LASTEXITCODE -ne 0) {
    throw "not logged in. Run: gh auth login"
}

gh repo view $Repo 2>$null | Out-Null
$exists = ($LASTEXITCODE -eq 0)

if ($exists) {
    Write-Host "repo exists, adding remote and pushing..."
    git remote remove origin 2>$null
    git remote add origin "https://github.com/$Repo.git"
    git push -u origin main
} else {
    Write-Host "creating repo and pushing..."
    gh repo create $Repo --public --source . --remote origin --push --description $Desc
}

Write-Host "== topics =="
gh repo edit $Repo `
    --add-topic mediatek `
    --add-topic mtk `
    --add-topic bootloader-unlock `
    --add-topic redmi-turbo-4 `
    --add-topic rodin `
    --add-topic hyperos `
    --add-topic lk `
    --add-topic reverse-engineering `
    --add-topic offline-unlock

Write-Host "== release v1.0.0 =="
gh release create v1.0.0 `
    images/rodin_303_our_lk.img `
    images/rodin_304_our_lk.img `
    images/SHA256SUMS.txt `
    --title "v1.0.0 - rodin 303/304 offline unlock kit" `
    --notes-file CHANGELOG.md

Write-Host ""
Write-Host "Done: https://github.com/$Repo"
