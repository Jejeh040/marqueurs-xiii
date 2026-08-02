@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
if not exist "%PY%" set PY=python
if not exist logs mkdir logs
"%PY%" run.py --muet >> logs\quotidien.log 2>&1
