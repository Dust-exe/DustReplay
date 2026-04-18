@echo off
chcp 65001 >nul
echo DustReplay setup (deps + build)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
