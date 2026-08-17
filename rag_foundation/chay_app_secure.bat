@echo off
chcp 65001 >nul
title Demo RAG Secure Search (RBAC) - Buoi 15

cd /d "D:\01_CONG_VIEC\phan_mem_tra_cuVB\RAG\rag_foundation\buoi_14"

echo ============================================================
echo   DEMO RAG SECURE SEARCH (RBAC) - BUOI 15
echo ============================================================
echo Thu muc: %CD%
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Tao moi truong ao rieng cho buoi 14 ...
    python -m venv .venv
    if errorlevel 1 (
        echo [LOI] Khong tao duoc .venv. Kiem tra Python da cai va co trong PATH chua.
        pause
        exit /b 1
    )
    echo.
)

set "PY=.venv\Scripts\python.exe"

echo [2/4] Kiem tra thu vien ...
"%PY%" -c "import streamlit, rank_bm25, sklearn, bs4, pandas" 2>nul
if errorlevel 1 (
    echo     Chua du thu vien. Dang cai vao .venv ^(lan dau mat vai phut^) ...
    "%PY%" -m pip install --upgrade pip >nul
    "%PY%" -m pip install torch --index-url https://download.pytorch.org/whl/cpu
    "%PY%" -m pip install -r requirements.txt
    echo.
)

echo [3/4] Kiem tra corpus bao mat (chunks_secure.csv) ...
if not exist "data\processed\chunks_secure.csv" (
    echo     Chua co. Dang gan tag bao mat truoc ...
    "%PY%" scripts\assign_security_tags.py
    echo.
)

echo [4/4] Khoi dong Streamlit (app_secure.py) ...
echo.
echo Neu cong 8501 ban, Streamlit se doi cong -^> dung dung URL hien o duoi.
echo De DUNG app: bam Ctrl+C trong cua so nay.
echo.

"%PY%" -m streamlit run app_secure.py

echo.
echo App da dung. Bam phim bat ky de dong cua so.
pause >nul
