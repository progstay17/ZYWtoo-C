@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "zywtool.py" %*
  exit /b %errorlevel%
)
where python >nul 2>nul
if errorlevel 1 (
  echo Python tidak ditemukan. Jalankan scripts\install.bat terlebih dahulu.
  exit /b 1
)
python "zywtool.py" %*
