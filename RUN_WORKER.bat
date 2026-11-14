@echo off
setlocal
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%LOCALAPPDATA%\Programs\Python\Python312;%PATH%"
if not defined PY (
  echo Python was not found. Run RUN.bat once - it installs Python and the libraries.
  pause
  exit /b 1
)
if not exist worker_config.json (
  echo worker_config.json is missing. Ask Claude for it.
  pause
  exit /b 1
)
"%PY%" -c "import yt_dlp,googleapiclient,google_auth_oauthlib,requests,tkinter" >nul 2>&1
if errorlevel 1 "%PY%" -m pip install -q -r requirements.txt
set "PYW=%PY:python.exe=pythonw.exe%"
if "%PY%"=="python" set "PYW=pythonw"
start "" "%PYW%" yt2drive_worker.py
