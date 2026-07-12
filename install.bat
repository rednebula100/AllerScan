@echo off
setlocal enabledelayedexpansion

echo ============================================
echo   AllerScan Setup
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    echo         Install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VERSION=%%v
for /f "tokens=1,2 delims=." %%a in ("%PY_VERSION%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)

if %PY_MAJOR% LSS 3 (
    echo [ERROR] Python 3.10+ is required. Found: %PY_VERSION%
    pause
    exit /b 1
)
if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 10 (
    echo [ERROR] Python 3.10+ is required. Found: %PY_VERSION%
    pause
    exit /b 1
)
echo [OK] Python %PY_VERSION% detected.
echo.

echo [*] Installing dependencies...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo.

echo [*] Preparing data directories...
if not exist "data\presets" mkdir "data\presets"
if not exist "data\meals" mkdir "data\meals"
if not exist "data\symptoms" mkdir "data\symptoms"

echo.
echo ============================================
echo   Setup complete!
echo   Run run.bat to start AllerScan.
echo ============================================
pause
