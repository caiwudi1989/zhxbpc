$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = if ($env:PCIDE_PYTHON) { $env:PCIDE_PYTHON } else { Join-Path $root 'runtime\dev\Scripts\python.exe' }
$env:PCIDE_ROOT = $root
$env:PYTHONPATH = Join-Path $root 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
$env:TEMP = Join-Path $root 'cache\temp'
$env:TMP = $env:TEMP
& $python (Join-Path $root 'src\pcide\main.py') @args
exit $LASTEXITCODE
