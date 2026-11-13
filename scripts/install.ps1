[CmdletBinding()]
param(
    [string]$Python = "python"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $Root ".venv"
$ModelDir = Join-Path $Root "models"
$Model = Join-Path $ModelDir "hand_landmarker.task"
$Url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
$Expected = "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"

function Fail([string]$Message) {
    Write-Host "GAGAL: $Message" -ForegroundColor Red
    exit 1
}

try {
    $pyVersion = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
    if ($LASTEXITCODE -ne 0) { Fail "Python tidak ditemukan. Install Python 3.11-3.14 lalu ulangi." }
    Write-Host "Python $pyVersion"
    & $Python -c "import tkinter" 2>$null
    if ($LASTEXITCODE -ne 0) { Fail "Tkinter tidak tersedia. Install Python dengan komponen Tcl/Tk." }

    if (-not (Test-Path $Venv)) { & $Python -m venv $Venv }
    $Py = Join-Path $Venv "Scripts\python.exe"
    & $Py -m pip install --upgrade pip
    & $Py -m pip install -r (Join-Path $Root "requirements.txt")

    New-Item -ItemType Directory -Force $ModelDir | Out-Null
    if (-not (Test-Path $Model)) {
        Write-Host "Mengunduh model MediaPipe..."
        Invoke-WebRequest -Uri $Url -OutFile "$Model.part"
        Move-Item -Force "$Model.part" $Model
    }
    $Hash = (Get-FileHash $Model -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($Hash -ne $Expected) { Remove-Item -Force $Model; Fail "Hash model tidak cocok: $Hash" }

    & $Py (Join-Path $Root "scripts\check_install.py")
    if ($LASTEXITCODE -ne 0) { Fail "Smoke test instalasi gagal." }

    @"
@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python zywtool.py
"@ | Set-Content -Encoding ASCII (Join-Path $Root "run_zywtool.bat")

    $Desktop = [Environment]::GetFolderPath("Desktop")
    $Shortcut = Join-Path $Desktop "ZYWtool.lnk"
    $Shell = New-Object -ComObject WScript.Shell
    $Link = $Shell.CreateShortcut($Shortcut)
    $Link.TargetPath = Join-Path $Root "run_zywtool.bat"
    $Link.WorkingDirectory = $Root
    $Link.Description = "ZYWtool - Fadhil Ghifarion 法迪 for AIT"
    $Link.Save()
    Write-Host "Selesai. Jalankan run_zywtool.bat atau shortcut Desktop ZYWtool." -ForegroundColor Green
}
catch {
    Fail $_.Exception.Message
}
