@echo off
setlocal
cd /d "%~dp0"
set "PY="
where python >nul 2>&1 && python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY for /f "delims=" %%i in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i"
if not defined PY (echo Python not found. Run RUN.bat first. & pause & exit /b 1)
"%PY%" -m pip install -U yt-dlp -q >nul 2>&1
"%PY%" find_cc.py
echo done> find_done.txt
