@echo off
REM Created by Tanzim Nasir
REM Copyright (c) 2026 Elite Integrity Services.
REM Developed for Elite Integrity Services by Tanzim Nasir.
REM Unauthorized use by other companies is prohibited.
cd /d "%~dp0"
echo Installing PyInstaller and building Elite DocCon.exe in this folder...
python -m pip install -e ".[pack]"
if errorlevel 1 (
  echo pip install failed.
  pause
  exit /b 1
)
python -m PyInstaller --noconfirm --clean --distpath . --workpath build "Elite DocCon.spec"
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)
echo.
echo Built "%~dp0Elite DocCon.exe"
echo Sarah can double-click that file. Token still saves on her PC only.
pause
