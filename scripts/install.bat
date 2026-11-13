@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
if errorlevel 1 (
  echo.
  echo Instalasi gagal. Baca pesan GAGAL di atas.
  pause
  exit /b 1
)
pause
