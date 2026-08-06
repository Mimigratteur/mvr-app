@echo off
title Pont MVR <-> Audiveris
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel% neq 0 (
  where py >nul 2>nul
  if %errorlevel% neq 0 (
    echo.
    echo [ERREUR] Python n'est pas installe ou pas dans le PATH.
    echo Installe-le depuis https://www.python.org/downloads/
    echo ^(coche "Add Python to PATH" pendant l'installation^)
    echo puis relance ce fichier.
    pause
    exit /b 1
  )
  py mvr_audiveris_bridge.py
) else (
  python mvr_audiveris_bridge.py
)

pause
