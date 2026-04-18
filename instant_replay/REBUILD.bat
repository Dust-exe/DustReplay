@echo off
chcp 65001 >nul
echo DustReplay rebuild (PyInstaller one-file)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0rebuild.ps1"
