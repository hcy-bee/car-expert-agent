@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHON_EXE=E:\python-project\PythonProject\.venv\Scripts\python.exe"
"%PYTHON_EXE%" check_env.py
pause
