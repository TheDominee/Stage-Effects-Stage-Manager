@echo off
REM Double-click this file to start the Local Broadcast Server on Windows.
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel%==0 (
    python local_broadcast_server.py
    goto :end
)

where py >nul 2>nul
if %errorlevel%==0 (
    py local_broadcast_server.py
    goto :end
)

echo Python 3 isn't installed on this computer.
echo Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH" during setup), then run this again.

:end
echo.
pause
