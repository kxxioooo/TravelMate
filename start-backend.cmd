@echo off
rem TravelMate backend launcher (double-click to run).
rem Real logic lives in start-backend.ps1.
rem -ExecutionPolicy Bypass works around the default "running scripts is disabled" policy.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-backend.ps1" %*
