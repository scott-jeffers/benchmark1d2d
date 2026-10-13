# Requires: gh auth login
# Creates origin, pushes master, prints Pages enablement URL.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

gh auth status
$name = "hydrobench"
$owner = (gh api user --jq .login)
Write-Host "Creating github.com/$owner/$name (private by default; pass --public to gh if desired)"
gh repo create $name --source=. --remote=origin --push --description "Open V&V Benchmarks for Water Solvers"
Write-Host "Enable Pages: Settings → Pages → Source = GitHub Actions (workflow pages.yml)"
Write-Host "Repo: https://github.com/$owner/$name"
