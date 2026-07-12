@echo off
setlocal

echo ============================================
echo   AllerScan Build
echo ============================================
echo.

where pyinstaller >nul 2>nul
if errorlevel 1 (
    echo [ERROR] pyinstaller was not found in PATH.
    echo         Run install.bat first, or: pip install -r requirements.txt
    pause
    exit /b 1
)

echo [*] Generating app icon...
python tools\generate_icon.py
if errorlevel 1 (
    echo [ERROR] Failed to generate assets\icon.ico
    pause
    exit /b 1
)
echo.

echo [*] Running PyInstaller (onefile, windowed)...
pyinstaller AllerScan.spec
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)
echo.

if not exist "dist\AllerScan.exe" (
    echo [ERROR] Build finished but dist\AllerScan.exe was not found.
    pause
    exit /b 1
)

echo ============================================
echo   Build complete: dist\AllerScan.exe
echo ============================================
pause
