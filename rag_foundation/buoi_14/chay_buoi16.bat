@echo off
REM ============================================================
REM  BUOI 16 - Bam doi lan vao file nay de chay script danh gia RAG
REM  (Tu dong vao dung thu muc + kich hoat venv + chay script)
REM ============================================================
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python scripts\evaluate_rag_pipeline.py
echo.
echo ============================================================
echo  Script da chay xong (hoac dung lai o loi tren). Nhan phim bat ky de dong.
echo ============================================================
pause
