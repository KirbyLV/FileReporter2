param(
  [Parameter(Mandatory=$true)][string]$Version
)

$ErrorActionPreference = "Stop"

Write-Host "==> Checking git status..."
git fetch --all --tags

# Ensure we're on a branch and clean
git rev-parse --abbrev-ref HEAD | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Not in a git repo" }

git diff --quiet
if ($LASTEXITCODE -ne 0) { throw "Working tree has changes. Commit/stash first." }

# Prevent duplicate tags
$exists = git tag -l $Version
if ($exists) { throw "Tag '$Version' already exists." }

Write-Host "==> Creating annotated tag $Version..."
git tag -a $Version -m "Release $Version"

Write-Host "==> Pushing tag $Version to origin..."
git push origin $Version

Write-Host "==> Done! Tag $Version created and pushed."
