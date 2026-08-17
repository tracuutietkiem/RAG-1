@echo off
chcp 65001 >nul
title Tro ly Tra cuu Van ban (RAG) - dang khoi dong
cd /d "%~dp0"

if not exist "logs" mkdir "logs"

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Tao moi truong ao rieng cho cong cu ...
    python -m venv .venv 1>>"logs\install.log" 2>&1
)
set "PY=.venv\Scripts\python.exe"

"%PY%" -m pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo [2/3] Cai dat thu vien lan dau, co the mat vai phut ...
    echo Xem tien do tai logs\install.log
    "%PY%" -m pip install --upgrade pip 1>>"logs\install.log" 2>&1
    "%PY%" -m pip install torch --index-url https://download.pytorch.org/whl/cpu 1>>"logs\install.log" 2>&1
    "%PY%" -m pip install -r requirements.txt 1>>"logs\install.log" 2>&1
)

echo [3/3] Khoi dong ung dung tai http://localhost:8501 ...
echo Neu Neo4j Desktop dang tat, phan "Graph hints" se hien canh bao vang - khong sao.
"%PY%" -m streamlit run app.py 1>>"logs\app.log" 2>&1

echo.
echo Ung dung da dung. Xem chi tiet loi (neu co) tai logs\app.log
pause
