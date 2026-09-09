@echo off
REM Created by Tanzim Nasir
REM Copyright (c) 2026 Elite Integrity Services.
REM Developed for Elite Integrity Services by Tanzim Nasir.
REM Unauthorized use by other companies is prohibited.
cd /d "%~dp0"
set PYTHONPATH=%~dp0src
echo Starting Elite DocCon from source (no exe rebuild needed)...
python -m doccon
if errorlevel 1 (
  echo.
  echo If that failed, Python may not be on PATH. Try:
  echo   py -m doccon
  echo.
  pause
)
