@echo off
chcp 65001 >nul
title Demo RAG Hybrid Search - Buoi 14

cd /d "D:\01_CONG_VIEC\phan_mem_tra_cuVB\RAG\rag_foundation\buoi_14"

echo ============================================================
echo   DEMO RAG HYBRID SEARCH - BUOI 14
echo ============================================================
echo Thu muc: %CD%
echo.

REM ---------------------------------------------------------------
REM Dung .venv RIENG cho buoi 14.
REM Ly do: cai thang vao Python toan cuc se ha cap transformers /
REM huggingface_hub, anh huong cac buoi truoc (buoi_09 khong co venh
REM rieng nen dung chung Python toan cuc).
REM ---------------------------------------------------------------
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
"%PY%" -c "import streamlit, rank_bm25, sklearn, bs4" 2>nul
if errorlevel 1 (
    echo     Chua du thu vien. Dang cai vao .venv ^(lan dau mat vai phut^) ...
    "%PY%" -m pip install --upgrade pip >nul
    "%PY%" -m pip install torch --index-url https://download.pytorch.org/whl/cpu
    "%PY%" -m pip install -r requirements.txt
    echo.
)

echo [3/4] Kiem tra corpus ...
if not exist "data\processed\chunks_normalized.csv" (
    echo     Chua co corpus. Dang chuan hoa tu du lieu nguon ...
    "%PY%" scripts\prepare_corpus.py
    echo.
)

echo [4/4] Khoi dong Streamlit ...
echo.
echo Neu cong 8501 ban, Streamlit se doi cong -^> dung dung URL hien o duoi.
echo De DUNG app: bam Ctrl+C trong cua so nay.
echo.

"%PY%" -m streamlit run app.py

echo.
echo App da dung. Bam phim bat ky de dong cua so.
pause >nul
