<#
.SYNOPSIS
  Recursively traverses an evidence directory, computes SHA-256 hashes, collects metadata,
  and outputs a JSON manifest (hashes_export.json).

.DESCRIPTION
  Designed for forensic-style acquisition:
  - Includes full path, relative path (to evidence root), size, last-write UTC timestamp
  - Adds examiner ID and machine name
  - Writes append-only log lines with timestamps and a test/run ID

.PARAMETER EvidenceRoot
  Root directory containing evidence files.

.PARAMETER ExaminerId
  Human identifier for the examiner (e.g. initials, staff ID).

.PARAMETER OutputJson
  Path where hashes_export.json will be written.

.PARAMETER TestId
  A run identifier to correlate logs across steps (e.g., "CASE123-RUN001").

.EXAMPLE
  pwsh -File .\scripts\ForensicHashPipeline.ps1 `
    -EvidenceRoot .\evidence `
    -ExaminerId "KEITH01" `
    -OutputJson .\out\exports\hashes_export.json `
    -TestId "CASE123-RUN001"
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)]
  [string]$EvidenceRoot,

  [Parameter(Mandatory=$true)]
  [string]$ExaminerId,

  [Parameter(Mandatory=$true)]
  [string]$OutputJson,

  [Parameter(Mandatory=$true)]
  [string]$TestId
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-AppendLog {
  param(
    [Parameter(Mandatory=$true)][string]$LogPath,
    [Parameter(Mandatory=$true)][string]$Message,
    [Parameter(Mandatory=$true)][string]$TestId
  )
  $ts = (Get-Date).ToUniversalTime().ToString("o")
  $line = "$ts`t$TestId`t$Message"
  Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
}

try {
  $evidenceRootFull = (Resolve-Path -LiteralPath $EvidenceRoot).Path
  if (-not (Test-Path -LiteralPath $evidenceRootFull -PathType Container)) {
    throw "EvidenceRoot does not exist or is not a directory: $EvidenceRoot"
  }

  $outDir = Split-Path -Parent $OutputJson
  if (-not (Test-Path -LiteralPath $outDir)) {
    New-Item -ItemType Directory -Path $outDir | Out-Null
  }

  $projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
  $logDir = Join-Path $projectRoot "logs"
  if (-not (Test-Path -LiteralPath $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
  }
  $logPath = Join-Path $logDir "acquisition.log"

  Write-AppendLog -LogPath $logPath -TestId $TestId -Message "START acquisition EvidenceRoot=$evidenceRootFull ExaminerId=$ExaminerId Machine=$env:COMPUTERNAME"

  $files = Get-ChildItem -LiteralPath $evidenceRootFull -File -Recurse -Force

  $items = @()
  foreach ($f in $files) {
    # Compute SHA-256
    $hashObj = Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256
    $rel = $f.FullName.Substring($evidenceRootFull.Length).TrimStart('\','/')

    $items += [PSCustomObject]@{
      full_path_legacy_windows = $f.FullName                 # full path as seen on the machine
      relative_path           = $rel                         # relative to EvidenceRoot
      size_bytes              = $f.Length
      last_write_utc          = $f.LastWriteTimeUtc.ToString("o")
      sha256_hex              = $hashObj.Hash.ToLowerInvariant()
    }
  }

  $manifest = [PSCustomObject]@{
    schema_version = "1.0"
    generated_utc  = (Get-Date).ToUniversalTime().ToString("o")
    examiner_id    = $ExaminerId
    machine_name   = $env:COMPUTERNAME
    evidence_root  = $evidenceRootFull
    item_count     = $items.Count
    items          = $items
  }

  # Write JSON deterministically-ish: ConvertTo-Json output is stable enough for this prototype.
  $json = $manifest | ConvertTo-Json -Depth 6
  Set-Content -LiteralPath $OutputJson -Value $json -Encoding UTF8

  Write-AppendLog -LogPath $logPath -TestId $TestId -Message "WROTE manifest OutputJson=$OutputJson Items=$($items.Count)"
  Write-AppendLog -LogPath $logPath -TestId $TestId -Message "END acquisition OK"
  Write-Host "[OK] Wrote manifest: $OutputJson (items=$($items.Count))"
}
catch {
  Write-Error $_
  try {
    $projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
    $logPath = Join-Path (Join-Path $projectRoot "logs") "acquisition.log"
    Write-AppendLog -LogPath $logPath -TestId $TestId -Message "END acquisition ERROR=$($_.Exception.Message)"
  } catch { }
  exit 1
}
