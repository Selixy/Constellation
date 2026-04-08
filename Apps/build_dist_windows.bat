@echo off
setlocal

powershell -ExecutionPolicy Bypass -File "%~dp0build_dist_windows.ps1" %*
if errorlevel 1 (
  echo Build Windows Dist failed.
  exit /b 1
)

echo Build Windows Dist done.
endlocal
