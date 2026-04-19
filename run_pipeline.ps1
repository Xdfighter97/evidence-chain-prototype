<#
.SYNOPSIS
  One-command reproducible evidence chain pipeline.
  
.DESCRIPTION
  Orchestrates the complete evidence integrity workflow:
  1. Deploy smart contract (if needed)
  2. Acquire evidence hashes (PowerShell)
  3. Encrypt and anchor on-chain (Python)
  4. Verify integrity (Python)

.PARAMETER CaseId
  Case identifier for this run (e.g., "CASE2026-001")

.PARAMETER ExaminerId
  Examiner identifier (e.g., "KEITH01")

.PARAMETER SkipDeploy
  Skip contract deployment (use existing contract from config.json)

.PARAMETER SkipAnchor
  Skip on-chain anchoring (local encryption only)

.EXAMPLE
  .\run_pipeline.ps1 -CaseId "CASE2026-001" -ExaminerId "KEITH01"
  
.EXAMPLE
  .\run_pipeline.ps1 -CaseId "CASE2026-001" -ExaminerId "KEITH01" -SkipDeploy
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)]
  [string]$CaseId,

  [Parameter(Mandatory=$true)]
  [string]$ExaminerId,

  [switch]$SkipDeploy,
  
  [switch]$SkipAnchor
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION LOADING
# ─────────────────────────────────────────────────────────────────────────────

function Load-EnvFile {
  param([string]$Path)
  if (Test-Path $Path) {
    Get-Content $Path | ForEach-Object {
      if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        $name = $Matches[1].Trim()
        $value = $Matches[2].Trim().Trim('"').Trim("'")
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
        Write-Host "  [env] $name = ***" -ForegroundColor DarkGray
      }
    }
  }
}

function Ensure-Key {
  # Generate key if not set
  if (-not $env:EVIDENCE_KEY_B64) {
    $keyBytes = [byte[]]::new(32)
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($keyBytes)
    $env:EVIDENCE_KEY_B64 = [Convert]::ToBase64String($keyBytes)
    Write-Host "[KEY] Generated new encryption key (save this securely!):" -ForegroundColor Yellow
    Write-Host "      $env:EVIDENCE_KEY_B64" -ForegroundColor Cyan
    
    # Append to .env for persistence
    $envPath = Join-Path $ProjectRoot ".env"
    Add-Content -Path $envPath -Value "`nEVIDENCE_KEY_B64=$env:EVIDENCE_KEY_B64"
    Write-Host "[KEY] Saved to .env file" -ForegroundColor Green
  } else {
    Write-Host "[KEY] Using existing encryption key from environment" -ForegroundColor Green
  }
}

function Get-GanachePrivateKey {
  # Default Ganache first account private key (deterministic for reproducibility)
  # In production, this should come from secure storage
  if (-not $env:ETH_PRIVATE_KEY) {
    # Ganache default first account private key (when started with default mnemonic)
    $env:ETH_PRIVATE_KEY = "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d"
    Write-Host "[ETH] Using default Ganache account private key" -ForegroundColor Yellow
  }
}

# ─────────────────────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     BLOCKCHAIN-BACKED EVIDENCE INTEGRITY PIPELINE            ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

$TestId = "$CaseId-$((Get-Date).ToString('yyyyMMdd-HHmmss'))"
Write-Host "[INFO] Case ID    : $CaseId" -ForegroundColor White
Write-Host "[INFO] Examiner   : $ExaminerId" -ForegroundColor White
Write-Host "[INFO] Run ID     : $TestId" -ForegroundColor White
Write-Host ""

# Load .env if exists
$envPath = Join-Path $ProjectRoot ".env"
if (Test-Path $envPath) {
  Write-Host "[CONFIG] Loading .env file..." -ForegroundColor Gray
  Load-EnvFile -Path $envPath
}

# Set pipeline env vars
$env:TEST_ID = $TestId

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: DEPLOY CONTRACT (if needed)
# ─────────────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "STEP 1: Smart Contract Deployment" -ForegroundColor Magenta
Write-Host "────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

if ($SkipDeploy) {
  Write-Host "[SKIP] Using existing contract from config.json" -ForegroundColor Yellow
} else {
  Get-GanachePrivateKey
  
  Write-Host "[DEPLOY] Deploying EvidenceRegistry to Ganache..." -ForegroundColor White
  Push-Location $ProjectRoot
  try {
    python scripts/deploy_contract.py
    if ($LASTEXITCODE -ne 0) { throw "Contract deployment failed" }
  } finally {
    Pop-Location
  }
}

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: EVIDENCE ACQUISITION (PowerShell hashing)
# ─────────────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "STEP 2: Evidence Acquisition (SHA-256 Hashing)" -ForegroundColor Magenta
Write-Host "────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

$evidenceRoot = Join-Path $ProjectRoot "evidence"
$exportJson = Join-Path $ProjectRoot "out\exports\hashes_export.json"

Write-Host "[ACQUIRE] Scanning evidence directory: $evidenceRoot" -ForegroundColor White

Push-Location $ProjectRoot
try {
  pwsh -File scripts/ForensicHashPipeline.ps1 `
    -EvidenceRoot $evidenceRoot `
    -ExaminerId $ExaminerId `
    -OutputJson $exportJson `
    -TestId $TestId
    
  if ($LASTEXITCODE -ne 0) { throw "Evidence acquisition failed" }
} finally {
  Pop-Location
}

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: ENCRYPTION + ANCHORING
# ─────────────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "STEP 3: Encryption + Blockchain Anchoring" -ForegroundColor Magenta
Write-Host "────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

Ensure-Key

if ($SkipAnchor) {
  $env:ANCHOR_ONCHAIN = "0"
  Write-Host "[MODE] Local encryption only (no on-chain anchoring)" -ForegroundColor Yellow
} else {
  $env:ANCHOR_ONCHAIN = "1"
  Get-GanachePrivateKey
  Write-Host "[MODE] Encryption + on-chain anchoring enabled" -ForegroundColor Green
}

Push-Location $ProjectRoot
try {
  python scripts/encrypt_and_hash.py
  if ($LASTEXITCODE -ne 0) { throw "Encryption/anchoring failed" }
} finally {
  Pop-Location
}

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4: VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "STEP 4: Integrity Verification" -ForegroundColor Magenta
Write-Host "────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

if ($SkipAnchor) {
  $env:VERIFY_ONCHAIN = "0"
} else {
  $env:VERIFY_ONCHAIN = "1"
}

Push-Location $ProjectRoot
try {
  python scripts/verify.py
  if ($LASTEXITCODE -ne 0) { throw "Verification failed" }
} finally {
  Pop-Location
}

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                    PIPELINE COMPLETE                         ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "Outputs:" -ForegroundColor White
Write-Host "  • Manifest:   out\exports\hashes_export.json" -ForegroundColor Gray
Write-Host "  • Encrypted:  out\encrypted\*.enc" -ForegroundColor Gray
Write-Host "  • Metadata:   out\metadata\*.meta.json" -ForegroundColor Gray
Write-Host "  • Logs:       logs\" -ForegroundColor Gray
Write-Host ""
Write-Host "Encryption Key (SAVE SECURELY): $env:EVIDENCE_KEY_B64" -ForegroundColor Yellow
Write-Host ""
