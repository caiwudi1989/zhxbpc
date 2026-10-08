$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$targets = @()
foreach ($folder in @('src', 'tests', 'tools')) {
    $targets += Get-ChildItem -LiteralPath (Join-Path $taskRoot $folder) -Directory -Recurse -Force | Where-Object { $_.Name -in @('__pycache__', 'bin', 'obj') }
}
foreach ($target in ($targets | Sort-Object { $_.FullName.Length } -Descending)) {
    $resolved = $target.FullName
    if (-not $resolved.StartsWith($taskRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Cleanup boundary invalid' }
    if (Test-Path -LiteralPath $resolved) { Remove-Item -LiteralPath $resolved -Recurse -Force }
}
foreach ($relative in @('examples\plugins\native_math\native_math.dll', 'examples\plugins\dotnet_math\Pcide.Example.dll', 'examples\plugins\dotnet_math\Pcide.Example.pdb', 'examples\plugins\dotnet_math\Pcide.Example.deps.json', 'examples\plugins\dotnet_math\Pcide.Example.runtimeconfig.json', 'runtime\modules\dotnet_math\Pcide.Example.pdb')) {
    $target = [IO.Path]::GetFullPath((Join-Path $taskRoot $relative))
    if (-not $target.StartsWith($taskRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Cleanup boundary invalid' }
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Force }
}
