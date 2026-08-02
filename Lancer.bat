@echo off
chcp 65001 >nul
title Marqueurs XIII
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
if not exist "%PY%" set PY=python
"%PY%" run.py
if errorlevel 1 echo Une erreur est survenue. Copiez le message ci-dessus.
pause
