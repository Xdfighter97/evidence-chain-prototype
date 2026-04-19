<#
.SYNOPSIS
  Resets the evidence chain outputs for a fresh run.

.DESCRIPTION
  Cleans generated artifacts while preserving:
  - Source evidence files
  - Configuration files
  - Scripts and contracts

.PARAMETER KeepLogs
  Preserve log files (default: delete logs too)

.PARAMETER Confirm
  Skip confirmation prompt

.EXAMPLE
  .\reset.ps1
  
.EXAMPLE
  .\reset.ps1 -KeepLogs -Confirm
#>

[CmdletBinding()]
param(
  [switch]$KeepLogs,
  [switch]$Confirm
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "║           EVIDENCE CHAIN - RESET PIPELINE                    ║" -ForegroundColor Yellow
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
Write-Host ""

$dirsToClean = @(
  "out\encrypted",
  "out\metadata", 
  "out\exports"
)

if (-not $KeepLogs) {
  $dirsToClean += "logs"
}

Write-Host "The following directories will be EMPTIED:" -ForegroundColor White
foreach ($dir in $dirsToClean) {
  $fullPath = Join-Path $ProjectRoot $dir
  if (Test-Path $fullPath) {
    $count = (Get-ChildItem $fullPath -Recurse -File -ErrorAction SilentlyContinue).Count
    Write-Host "  • $dir ($count files)" -ForegroundColor Gray
  } else {
    Write-Host "  • $dir (does not exist)" -ForegroundColor DarkGray
  }
}

Write-Host ""
Write-Host "The following will be PRESERVED:" -ForegroundColor Green
Write-Host "  • evidence\* (source evidence files)" -ForegroundColor Gray
Write-Host "  • scripts\* (all scripts)" -ForegroundColor Gray
Write-Host "  • contracts\* (smart contracts)" -ForegroundColor Gray
Write-Host "  • config.json, .env" -ForegroundColor Gray
if ($KeepLogs) {
  Write-Host "  • logs\* (log files)" -ForegroundColor Gray
}
Write-Host ""

if (-not $Confirm) {
  $response = Read-Host "Proceed with reset? [y/N]"
  if ($response -notmatch '^[Yy]') {
    Write-Host "[CANCELLED] No changes made." -ForegroundColor Yellow
    exit 0
  }
}

Write-Host ""
Write-Host "Cleaning..." -ForegroundColor White

foreach ($dir in $dirsToClean) {
  $fullPath = Join-Path $ProjectRoot $dir
  if (Test-Path $fullPath) {
    Remove-Item -Path "$fullPath\*" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  [OK] Cleaned: $dir" -ForegroundColor Green
  } else {
    # Create directory structure
    New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
    Write-Host "  [OK] Created: $dir" -ForegroundColor Green
  }
}

# Ensure directory structure exists
$requiredDirs = @("out\encrypted", "out\metadata", "out\exports", "logs", "evidence\images")
foreach ($dir in $requiredDirs) {
  $fullPath = Join-Path $ProjectRoot $dir
  if (-not (Test-Path $fullPath)) {
    New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
  }
}

Write-Host ""
Write-Host "[DONE] Pipeline reset complete. Ready for fresh run." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Ensure Ganache is running: npx ganache --deterministic" -ForegroundColor Gray
Write-Host "  2. Run pipeline: .\run_pipeline.ps1 -CaseId 'CASE001' -ExaminerId 'USER01'" -ForegroundColor Gray
Write-Host ""
