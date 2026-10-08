$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = if ($env:PCIDE_PYTHON) { $env:PCIDE_PYTHON } else { Join-Path $root 'runtime\dev\Scripts\python.exe' }
$env:PCIDE_ROOT = $root
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = Join-Path $root 'src'
$env:PYTHONUTF8 = '1'
$env:TEMP = Join-Path $root 'cache\temp'
$env:TMP = $env:TEMP
& $python -B -m unittest discover -s (Join-Path $root 'tests') -v @args
exit $LASTEXITCODE
