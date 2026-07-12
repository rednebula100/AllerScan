@echo off
setlocal

echo ============================================
echo   AllerScan
echo ============================================
echo.

if "%NEIS_API_KEY%"=="" (
    set /p NEIS_API_KEY=Enter your NEIS Open API key (press Enter to skip):
)
if "%MFDS_API_KEY%"=="" (
    set /p MFDS_API_KEY=Enter your MFDS (food safety) API key (press Enter to skip):
)

echo.
echo [*] Starting AllerScan...
python main.py

pause
