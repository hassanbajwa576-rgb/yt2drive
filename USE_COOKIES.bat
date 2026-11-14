@echo off
cd /d "%~dp0"
echo Which browser are you signed in to YouTube with?
echo   1 = Edge   2 = Chrome   3 = Firefox   0 = turn cookies off
set /p C=Choose: 
if "%C%"=="1" (echo edge>cookies_browser.txt)
if "%C%"=="2" (echo chrome>cookies_browser.txt)
if "%C%"=="3" (echo firefox>cookies_browser.txt)
if "%C%"=="0" (del cookies_browser.txt 2>nul)
echo Done. Close the browser first, then restart the app / worker (STOP_WORKER.bat then RUN_WORKER.bat).
pause
