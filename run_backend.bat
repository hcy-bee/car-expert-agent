@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem 如果你的依赖装在别的虚拟环境，把下面这行改成那个环境的 python.exe
set "PYTHON_EXE=E:\python-project\PythonProject\.venv\Scripts\python.exe"

echo 启动后端 http://127.0.0.1:8000
"%PYTHON_EXE%" -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
pause
