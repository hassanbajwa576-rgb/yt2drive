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
"%PY%" -c "import yt_dlp,googleapiclient,google_auth_oauthlib,requests,tkinter" >nul 2>&1
if errorlevel 1 "%PY%" -m pip install -q -r requirements.txt
set "PYW=%PY:python.exe=pythonw.exe%"
if "%PY%"=="python" set "PYW=pythonw"
start "" "%PYW%" yt2drive_app.py --find 50 --no-cc --compilation --mix-aleks 50 --schedule 30 --topics "funny compilation, funniest fails compilation, try not to laugh compilation, best funny moments compilation, cartoon funny moments compilation, spongebob funny compilation, tom and jerry compilation, looney tunes compilation, gaming funny moments compilation, funny clips compilation, epic fails compilation, funny bloopers compilation, funniest moments of the year, funny dance fails compilation, funny kids moments compilation, funny reactions compilation"
