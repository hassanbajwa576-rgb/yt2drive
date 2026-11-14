@echo off
wmic process where "commandline like '%%yt2drive_worker.py%%' and name like 'python%%'" call terminate >nul 2>&1
echo Worker stopped.
pause
