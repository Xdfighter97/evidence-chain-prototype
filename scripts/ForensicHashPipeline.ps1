<#
.SYNOPSIS
  Recursively hashes evidence files.
.PARAMETER EvidenceRoot
  Root directory containing evidence.
 .PARAMETER OutputJson
  Output path for manifest.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$EvidenceRoot,

    [Paramter(Mandatory=$true)]
    [string]$OutputJson
)

Write-Host "Evidence root: $EvidenceRoot"
Write-Host "Output: $OutputJson"