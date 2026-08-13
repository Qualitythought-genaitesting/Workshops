@echo off
rem TripSage RAG - one-click launcher (Windows). Double-click this file.
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (where python >nul 2>nul && (set PY=python) || (
  echo Python 3 is required but was not found.
  echo Install it from https://www.python.org/downloads/ ^(tick "Add Python to PATH"^) then run this again.
  pause & exit /b 1))
echo Starting TripSage RAG... your browser will open automatically.
echo If it does not, open the URL printed below. Press Ctrl+C to stop.
%PY% app.py
pause
