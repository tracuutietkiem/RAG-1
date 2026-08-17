@echo off
chcp 65001 >nul
title Giao dien tim kiem - buoi_09 (Streamlit)

cd /d "D:\01_CONG_VIEC\phan_mem_tra_cuVB\RAG\rag_foundation\buoi_09"

echo ============================================================
echo   KHOI DONG GIAO DIEN TIM KIEM (Streamlit) - buoi_09
echo ============================================================
echo Thu muc: %CD%
echo.

python -c "import streamlit" 2>nul
if errorlevel 1 (
    echo [!] Chua cai streamlit. Dang cai tu requirements.txt ...
    python -m pip install -r requirements.txt
    echo.
)

echo Dang mo trinh duyet tai http://localhost:8501
echo De DUNG app: bam Ctrl+C trong cua so nay.
echo.

python -m streamlit run app.py

echo.
echo App da dung. Bam phim bat ky de dong cua so.
pause >nul
