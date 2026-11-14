@echo off
cd /d "%~dp0"
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup')+'\YT to Drive worker.lnk'); $s.TargetPath='%~dp0RUN_WORKER.bat'; $s.WorkingDirectory='%~dp0'; $s.WindowStyle=7; $s.Save()"
echo The worker will now start automatically when you sign in to Windows.
pause
