# Bump version script (PowerShell)
param(
  [Parameter(Mandatory = $true)][ValidateSet('major','minor','patch')] [string]$part,
  [string]$message = ''
)

$ErrorActionPreference = 'Stop'

$versionFile = Join-Path $PSScriptRoot '..\VERSION'
$changelog = Join-Path $PSScriptRoot '..\CHANGELOG.md'

$current = (Get-Content $versionFile -Raw).Trim()
$tokens = $current -split '\.'
[int]$major = $tokens[0]
[int]$minor = $tokens[1]
[int]$patch = $tokens[2]

switch ($part) {
  'major' { $major++; $minor = 0; $patch = 0 }
  'minor' { $minor++; $patch = 0 }
  'patch' { $patch++ }
}

$newVersion = "$major.$minor.$patch"

# Update VERSION
Set-Content -LiteralPath $versionFile -Value "$newVersion`n" -Encoding UTF8

# Update CHANGELOG (append entry)
$today = Get-Date -Format 'yyyy-MM-dd'
$note = if ($message) { $message } else { 'Updates and improvements' }

$chBody = (Get-Content $changelog -Raw -Encoding UTF8)
$entry = "`n## [$newVersion] - $today`n### Changed`n- $note`n"
Set-Content -LiteralPath $changelog -Value ($chBody + $entry) -Encoding UTF8

# Commit and tag
git add $versionFile $changelog | Out-Null
git commit -m "chore: bump version to v$newVersion" | Out-Null
git tag -a "v$newVersion" -m "v$newVersion" | Out-Null

Write-Output "Bumped to v$newVersion and created tag. Push with: git push origin main && git push origin v$newVersion"


