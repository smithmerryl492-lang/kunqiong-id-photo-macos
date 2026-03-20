@echo off
cd /d "%~dp0"
set "PYTHON_EXE=F:\Program Files\Python313\python.exe"
"%PYTHON_EXE%" main.py
if errorlevel 1 pause
