@echo off
rem Shares a READ-ONLY copy of the dashboard (cellar hidden) via share.ps1.
title Thai Wine Value Finder - online
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0share.ps1"
pause
