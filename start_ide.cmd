@echo off
setlocal
set "PCIDE_ROOT=%~dp0"
set "PYTHONPATH=%~dp0src"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONUTF8=1"
set "TEMP=%~dp0cache\temp"
set "TMP=%TEMP%"
if defined PCIDE_PYTHON (
  "%PCIDE_PYTHON%" "%~dp0src\pcide\main.py" %*
) else (
  "%~dp0runtime\dev\Scripts\python.exe" -B "%~dp0src\pcide\main.py" %*
)
exit /b %ERRORLEVEL%
