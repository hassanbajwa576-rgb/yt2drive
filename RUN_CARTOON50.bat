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
start "" "%PYW%" yt2drive_app.py --find 50 --no-cc --cartoon --schedule 30 --topics "spongebob squarepants funny clip, patrick star funny, squidward funny, mr krabs funny, tom and jerry funny clip, looney tunes bugs bunny, daffy duck funny, road runner wile e coyote, scooby doo funny moments, powerpuff girls funny, phineas and ferb funny, the amazing world of gumball funny, adventure time funny, regular show funny, teen titans go funny, ben 10 funny, dexters laboratory, johnny bravo funny, courage the cowardly dog, fairly oddparents funny, rugrats funny, hey arnold funny, invader zim funny, pink panther cartoon, woody woodpecker, animaniacs, oddbods funny, garfield funny"
