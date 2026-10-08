param(
    [string]$Date = (Get-Date -Format 'yyyy-MM-dd'),
    [switch]$SkipPush
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root
$Git = @('-c', "safe.directory=$Root")
$Excluded = @('cache', 'build', 'outputs', 'runtime', 'downloads', 'sdk', 'third_party', 'assets', 'projects')

function Invoke-Git([string[]]$GitArgs) {
    & git @Git @GitArgs
    if ($LASTEXITCODE -ne 0) { throw "git failed: $($GitArgs -join ' ')" }
}

# The repository .gitignore is the source-of-truth exclusion policy.
Invoke-Git @('add', '-A')
$tracked = (& git @Git ls-files) | Where-Object { $_ }
$bad = @($tracked | Where-Object {
    $p = $_ -replace '\\', '/'
    $Excluded | Where-Object { $p -eq $_ -or $p.StartsWith("$_/") }
})
if ($bad.Count -gt 0) { throw "Excluded paths are tracked: $($bad -join ', ')" }

$status = (& git @Git status --porcelain)
if ($status) {
    Invoke-Git @('commit', '-m', "源代码备份 $Date")
}

$dateBranch = "backup/$Date"
& git @Git show-ref --verify --quiet "refs/heads/$dateBranch"
if ($LASTEXITCODE -ne 0) { Invoke-Git @('branch', $dateBranch, 'main') }
else { Invoke-Git @('branch', '-f', $dateBranch, 'main') }

if (-not $SkipPush) {
    Invoke-Git @('push', 'origin', 'main', $dateBranch)
    Invoke-Git @('push', 'gitee', 'main', $dateBranch)
}

Write-Host "Source backup complete: main and $dateBranch"
