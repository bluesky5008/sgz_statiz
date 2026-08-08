@echo off
rem Elevated runner launcher - right-click this file and select "Run as administrator".
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0agent_shell.ps1" -Dir "%~dp0..\output\agent_shell"
echo.
echo [agent_shell exited] If there is an error message above, please report it.
pause
