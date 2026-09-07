@echo off
REM ============================================================================
REM  TripMate Agent Testing Capstone - one-click runner (Windows)
REM
REM  Usage:  run_all.bat            -> classroom build (planted defects ON), full cycle
REM          run_all.bat fixed      -> fixed build (DEFECTS_ENABLED=false), full cycle
REM          run_all.bat server     -> only start the server + open the chat UI
REM          run_all.bat test       -> only run the tests + build the report (server must be up)
REM
REM  Full cycle = create venv, install deps, start server, wait for /health,
REM               run 61 scenarios x 5 runs, build PRD/Test Plan/Execution Report,
REM               fill the Excel workbook, open the UI and the report.
REM ============================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set MODE=%1
if "%MODE%"=="" set MODE=full

echo.
echo  ============================================================
echo   TripMate Agent Testing Capstone  -  Quality Thought
echo   mode: %MODE%
echo  ============================================================
echo.

REM ---- 1. Python ---------------------------------------------------------------
set PY=
where py >nul 2>nul && set PY=py -3
if "%PY%"=="" ( where python >nul 2>nul && set PY=python )
if "%PY%"=="" (
  echo [ERROR] Python 3.10+ was not found. Install it from https://www.python.org/downloads/ - tick "Add python.exe to PATH" - then run this file again.
  pause & exit /b 1
)
%PY% -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" || (echo [ERROR] Python 3.10 or newer is required. & pause & exit /b 1)

REM ---- 2. Virtual environment + dependencies ---------------------------------
if not exist .venv (
  echo [1/6] Creating virtual environment .venv ...
  %PY% -m venv .venv || (echo [ERROR] could not create venv & pause & exit /b 1)
) else (
  echo [1/6] Virtual environment found.
)
call .venv\Scripts\activate.bat
echo [2/6] Installing dependencies (first run may take a minute) ...
python -m pip install --quiet --disable-pip-version-check -r requirements.txt || (echo [ERROR] pip install failed & pause & exit /b 1)

REM ---- 3. Environment ------------------------------------------------------------
if exist .env (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
    if not "%%A"=="" set "%%A=%%B"
  )
)
if "%MODE%"=="fixed" set DEFECTS_ENABLED=false
if "%DEFECTS_ENABLED%"=="" set DEFECTS_ENABLED=true
if "%LLM_PROVIDER%"=="" set LLM_PROVIDER=mock
if "%RUNS%"=="" set RUNS=5
if "%PORT%"=="" set PORT=8000
set TRIPMATE_URL=http://127.0.0.1:%PORT%
if not exist logs mkdir logs
if not exist data mkdir data
if not exist results mkdir results

REM ---- 4. Start server ------------------------------------------------------------
if "%MODE%"=="test" goto tests
echo [3/6] Starting TripMate server on %TRIPMATE_URL%  (LLM_PROVIDER=%LLM_PROVIDER%, DEFECTS_ENABLED=%DEFECTS_ENABLED%) ...
del /q data\tripmate.db 2>nul
start "TripMate Agent Server - close this window to stop" cmd /k ".venv\Scripts\activate.bat && python -m app.server"
set /a tries=0
:waitloop
python -c "import urllib.request,sys; urllib.request.urlopen('%TRIPMATE_URL%/health',timeout=2); sys.exit(0)" >nul 2>nul && goto up
set /a tries+=1
if %tries% GEQ 40 (
  echo [ERROR] server did not start - check the server window
  pause
  exit /b 1
)
timeout /t 1 /nobreak >nul
goto waitloop
:up
echo        server is up.
if not "%MODE%"=="server" goto tests
start "" %TRIPMATE_URL%
echo Chat UI opened. Trace viewer: %TRIPMATE_URL%/traces   API docs: %TRIPMATE_URL%/docs
goto end

:tests
REM ---- 5. Tests -------------------------------------------------------------------
echo [4/6] Running %RUNS% runs of each of the 61 scenarios against %TRIPMATE_URL% ...
python -m pytest
set TEST_RC=%ERRORLEVEL%
echo        pytest exit code %TEST_RC%  (non-zero = some scenarios failed their threshold - expected in the classroom build)

REM ---- 6. Documents + report -----------------------------------------------------
echo [5/6] Building PRD and Test Plan ...
python docs\build_docs.py
echo [6/6] Building Test Execution Report + filled workbook ...
python reports\build_report.py

echo.
echo  ------------------------------------------------------------
echo   Chat UI ............ %TRIPMATE_URL%
echo   Trace viewer ....... %TRIPMATE_URL%/traces
echo   API docs ........... %TRIPMATE_URL%/docs
echo   Report (HTML) ...... reports\Test_Execution_Report.html
echo   Report (Word) ...... reports\Test_Execution_Report.docx
echo   PRD / Test Plan .... docs\PRD_TripMate.docx, docs\Test_Plan_TripMate.docx
echo   Test cases ......... docs\TripMate_Agent_Test_Cases.xlsx, docs\Test_Cases_Executed.xlsx
echo   Raw results ........ results\results.json
echo  ------------------------------------------------------------
start "" "reports\Test_Execution_Report.html"
if not "%MODE%"=="test" start "" %TRIPMATE_URL%

:end
echo.
echo The server keeps running in its own window. Close that window to stop it.
pause
endlocal
