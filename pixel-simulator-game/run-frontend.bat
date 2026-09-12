@echo off
REM Install npm deps if needed and start the Vite dev server.
setlocal EnableExtensions

cd /d "%~dp0frontend"

where npm >nul 2>&1
if errorlevel 1 (
  echo npm is required. Install Node.js from https://nodejs.org/ then re-run.
  exit /b 1
)

echo Installing frontend dependencies ...
call npm install
if errorlevel 1 exit /b 1

echo Starting frontend on http://localhost:5173 ...
call npm run dev
exit /b %ERRORLEVEL%
