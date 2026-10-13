@echo off
rem TravelMate frontend launcher (double-click to run).
rem Real logic lives in start-frontend.ps1.
rem -ExecutionPolicy Bypass works around the default "running scripts is disabled" policy.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-frontend.ps1" %*
