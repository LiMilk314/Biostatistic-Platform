@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch_platform.ps1"
if errorlevel 1 (
    echo Startup did not complete. Review the PowerShell service window and runtime logs.
    pause
)
