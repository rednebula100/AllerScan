@echo off
setlocal

echo ============================================
echo   AllerScan
echo ============================================
echo.

if defined NEIS_API_KEY goto :skip_neis
set /p NEIS_API_KEY=Enter your NEIS Open API key (press Enter to skip):
:skip_neis

if defined MFDS_API_KEY goto :skip_mfds
set /p MFDS_API_KEY=Enter your MFDS (food safety) API key (press Enter to skip):
:skip_mfds

echo.
echo [*] Starting AllerScan...
python main.py

pause
