@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
python -m uvicorn main:app --host 127.0.0.1 --port 5000 --workers 1 --proxy-headers >> logs\uvicorn.log 2>&1
