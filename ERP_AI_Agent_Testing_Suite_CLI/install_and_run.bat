@echo off
REM ============================================================
REM  ERP AI Agent Testing Suite – One-Click Installer (Windows)
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo   ERP AI Agent Testing Suite – Installer
echo ============================================================
echo.

REM 1. Check Python
where python >nul 2>&1
if errorlevel 1 (
    echo Python is required. Please install Python 3.9+ from python.org
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do echo Python found: %%i

REM 2. Create venv
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat
echo Virtual environment ready

REM 3. Install deps
echo Installing Python packages...
python -m pip install --upgrade pip -q
pip install -r requirements.txt -q
echo Dependencies installed

REM 4. Configure .env
if not exist "config\.env" (
    copy config\.env.example config\.env >nul
    echo.
    echo ------------------------------------------------------------
    echo   First-time setup: API Key configuration
    echo ------------------------------------------------------------
    echo.
    echo The agent can run in two modes:
    echo   1. MOCK  – deterministic rules (no API key needed)
    echo   2. LLM   – real Large Language Model (needs your API key)
    echo.
    set /p USE_LLM="Do you want to use a real LLM now? (y/N): "
    if /i "!USE_LLM!"=="y" (
        set /p API_KEY="Enter your OpenAI-compatible API key: "
        set /p BASE_URL="Base URL [https://api.openai.com/v1]: "
        if "!BASE_URL!"=="" set BASE_URL=https://api.openai.com/v1
        set /p MODEL="Model name [gpt-4o-mini]: "
        if "!MODEL!"=="" set MODEL=gpt-4o-mini

        (
            echo OPENAI_API_KEY=!API_KEY!
            echo OPENAI_BASE_URL=!BASE_URL!
            echo OPENAI_MODEL=!MODEL!
            echo AGENT_MODE=llm
        ) > config\.env
        echo LLM mode configured. Key saved to config\.env
    ) else (
        echo AGENT_MODE=mock >> config\.env
        echo Running in MOCK mode.
    )
) else (
    echo Existing config\.env found – using it.
)

echo.
echo ============================================================
echo   Launching agent...
echo ============================================================
echo.
echo Type 'help' for sample prompts, 'quit' to exit.
echo.

python app\erp_agent.py
pause
