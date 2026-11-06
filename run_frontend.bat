@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem 和 run_backend.bat 用同一个解释器
set "PYTHON_EXE=E:\python-project\PythonProject\.venv\Scripts\python.exe"

echo 启动前端 http://127.0.0.1:8501
"%PYTHON_EXE%" -m streamlit run frontend/app.py
pause
