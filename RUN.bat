@echo off
setlocal
cd /d "%~dp0"
title yt2drive

rem ---- find Python (install it if missing) ----
set "PY="
where python >nul 2>&1 && python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY for /f "delims=" %%i in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i"
if not defined PY (
  echo Python not found. Installing Python 3.12 with winget...
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
  if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)
if not defined PY (
  echo Could not install Python automatically. Install it from python.org, then run this again.
  pause & exit /b 1
)

rem ---- install libraries (first run only takes a minute) ----
if not exist ".deps_ok" (
  echo Installing libraries...
  "%PY%" -m pip install --upgrade pip >nul
  "%PY%" -m pip install -r requirements.txt || (echo Library install failed. & pause & exit /b 1)
  echo ok> .deps_ok
)
"%PY%" -m pip install -U yt-dlp -q >nul 2>&1

rem ---- run ----
if not exist links.txt (
  echo Put one video URL per line in links.txt, then run this again.
  echo # one URL per line> links.txt
  notepad links.txt
  exit /b 0
)
"%PY%" yt2drive.py --file links.txt
echo.
echo Done. Links are saved in links.csv
start "" links.csv
pause
