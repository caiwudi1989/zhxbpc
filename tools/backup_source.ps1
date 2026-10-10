param(
    [string]$Date = (Get-Date -Format 'yyyy-MM-dd'),
    [switch]$SkipPush,
    [int]$PushAttempts = 10
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root
$Git = @('-c', "safe.directory=$Root")
$Excluded = @('cache', 'build', 'outputs', 'runtime', 'downloads', 'sdk', 'third_party', 'assets', 'projects')
$ArchiveDirectory = Join-Path $Root 'backup-archives'
$ArchivePath = Join-Path $ArchiveDirectory "source-$Date.zip"

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

# Create a dated source-only archive. Generated environments, caches, logs,
# temporary files, and previous archives are deliberately excluded.
New-Item -ItemType Directory -Force -Path $ArchiveDirectory | Out-Null
$archiveFiles = Get-ChildItem -LiteralPath $Root -Recurse -File -Force | Where-Object {
    $relative = $_.FullName.Substring($Root.Length + 1) -replace '\\', '/'
    $top = $relative.Split('/')[0]
    $top -notin ($Excluded + @('backup-archives', '.git')) -and
        $_.Extension -notin @('.pyc', '.log', '.tmp', '.bak') -and
        $_.Name -notmatch '^\.DS_Store$'
}
if (Test-Path -LiteralPath $ArchivePath) { Remove-Item -LiteralPath $ArchivePath -Force }
$archiveRelative = @($archiveFiles | ForEach-Object { $_.FullName.Substring($Root.Length + 1) })
if ($archiveRelative.Count -gt 0) { Compress-Archive -LiteralPath $archiveRelative -DestinationPath $ArchivePath -CompressionLevel Optimal }
Invoke-Git @('add', 'backup-archives')
if ((& git @Git status --porcelain)) { Invoke-Git @('commit', '-m', "日期源码压缩备份 $Date") }

$dateBranch = "backup/$Date"
& git @Git show-ref --verify --quiet "refs/heads/$dateBranch"
if ($LASTEXITCODE -ne 0) { Invoke-Git @('branch', $dateBranch, 'main') }
else { Invoke-Git @('branch', '-f', $dateBranch, 'main') }

if (-not $SkipPush) {
    # Each remote receives the current main and the date snapshot. The date
    # branch is intentionally replaced on repeated backups for the same day.
    if ($PushAttempts -lt 1) { throw 'PushAttempts must be at least 1' }
    $pushFailures = @()
    foreach ($remote in @('origin', 'gitee')) {
        $pushed = $false
        for ($attempt = 1; $attempt -le $PushAttempts; $attempt++) {
            try {
                Invoke-Git @('push', $remote, 'main:main', "$dateBranch`:$dateBranch", '--force')
                $pushed = $true
                break
            } catch {
                if ($attempt -ge $PushAttempts) { $pushFailures += "$remote after $PushAttempts attempts: $($_.Exception.Message)"; break }
                Write-Warning "Push to $remote failed (attempt $attempt/$PushAttempts); retrying..."
                Start-Sleep -Seconds 2
            }
        }
        if (-not $pushed -and $pushFailures.Count -eq 0) { $pushFailures += "$remote failed" }
    }
    if ($pushFailures.Count -gt 0) { throw ("Backup push incomplete; no cleanup performed: " + ($pushFailures -join '; ')) }

    foreach ($relative in @('cache/backup', 'cache/backups')) {
        $target = [System.IO.Path]::GetFullPath((Join-Path $Root $relative))
        $cacheRoot = [System.IO.Path]::GetFullPath((Join-Path $Root 'cache'))
        if (-not $target.StartsWith($cacheRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe backup cleanup path: $target" }
        if (Test-Path -LiteralPath $target) {
            $item = Get-Item -LiteralPath $target -Force
            if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { throw "Refusing to clean linked backup path: $target" }
            Remove-Item -LiteralPath $target -Recurse -Force
        }
    }
}

Write-Host "Source backup complete: main and $dateBranch"
