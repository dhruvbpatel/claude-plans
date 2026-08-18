@echo off
REM Create/reuse a Python venv, install deps, and start the FastAPI server.
setlocal EnableExtensions

cd /d "%~dp0"
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "BACKEND=%ROOT%\backend"

set "PYTHON="
where py >nul 2>&1 && set "PYTHON=py -3"
if not defined PYTHON where python >nul 2>&1 && set "PYTHON=python"
if not defined PYTHON where python3 >nul 2>&1 && set "PYTHON=python3"
if not defined PYTHON (
  echo Python 3 is required. Install it from https://www.python.org/downloads/ then re-run.
  exit /b 1
)

if not exist "%BACKEND%\.venv\Scripts\python.exe" if not exist "%BACKEND%\venv\Scripts\python.exe" (
  echo Creating virtualenv at backend\.venv ...
  %PYTHON% -m venv "%BACKEND%\.venv"
  if errorlevel 1 exit /b 1
)

set "VENV=%BACKEND%\.venv"
if not exist "%VENV%\Scripts\python.exe" set "VENV=%BACKEND%\venv"
if not exist "%VENV%\Scripts\python.exe" (
  echo Failed to create or find a virtualenv under backend\.venv or backend\venv.
  exit /b 1
)

echo Installing backend dependencies ...
"%VENV%\Scripts\python.exe" -m pip install -q -r "%BACKEND%\requirements.txt"
if errorlevel 1 exit /b 1

if not exist "%ROOT%\.env" if exist "%ROOT%\.env.example" (
  copy /Y "%ROOT%\.env.example" "%ROOT%\.env" >nul
  echo Copied .env.example to .env
)

echo Starting API on http://127.0.0.1:8000 ...
cd /d "%BACKEND%"
"%VENV%\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000
exit /b %ERRORLEVEL%
