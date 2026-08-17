@echo off
chcp 65001 >nul
title Buoi 15 - RBAC: Gan tag + Nap Neo4j + Kiem dinh bao mat

cd /d "D:\01_CONG_VIEC\phan_mem_tra_cuVB\RAG\rag_foundation\buoi_14"

echo ============================================================
echo   BUOI 15 - RBAC: chay toan bo pipeline
echo ============================================================
echo Thu muc: %CD%
echo.
echo Truoc khi chay, dam bao:
echo   - Neo4j Desktop dang mo, instance "rag2026" o trang thai RUNNING
echo   - File .env trong buoi_14\ da co du NEO4J_URI/USER/PASSWORD
echo.
echo Script se chay lan luot:
echo   1. assign_security_tags.py  (gan allowed_roles vao chunks_secure.csv)
echo   2. load_secure_kg.py        (nap allowed_roles vao Neo4j - CHI MERGE, KHONG xoa gi)
echo   3. security_audit.py        (kiem tra ro ri du lieu, ghi outputs\security_audit_report.md)
echo.
pause

REM ---------------------------------------------------------------
REM Dung .venv rieng cua buoi 14 neu co (giong chay_demo_buoi14.bat).
REM Neu chua co .venv thi dung Python toan cuc.
REM ---------------------------------------------------------------
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
)

echo.
echo [0/3] Kiem tra thu vien (neo4j, pandas) ...
"%PY%" -c "import neo4j, pandas" 2>nul
if errorlevel 1 (
    echo     Chua du thu vien. Dang cai ...
    "%PY%" -m pip install -r requirements.txt
    echo.
)

echo.
echo [1/3] Gan tag bao mat (assign_security_tags.py) ...
echo ------------------------------------------------------------
"%PY%" scripts\assign_security_tags.py
if errorlevel 1 (
    echo.
    echo [LOI] assign_security_tags.py that bai. Dung lai - xem loi o tren.
    echo Loi cung da duoc ghi vao outputs\error_assign_security_tags_*.txt
    pause
    exit /b 1
)

echo.
echo [2/3] Nap allowed_roles vao Neo4j (load_secure_kg.py) ...
echo ------------------------------------------------------------
"%PY%" scripts\load_secure_kg.py
echo.
echo     (Neu thay "NOT RUN": kiem tra lai Neo4j Desktop da mo va instance
echo      "rag2026" dang RUNNING chua, roi chay lai file .bat nay.)

echo.
echo [3/3] Kiem dinh bao mat (security_audit.py) ...
echo ------------------------------------------------------------
"%PY%" scripts\security_audit.py

echo.
echo ============================================================
echo XONG. Xem bao cao chi tiet tai:
echo   outputs\rbac_kg_load_report.md
echo   outputs\security_audit_report.md
echo ============================================================
echo.
echo Bam phim bat ky de dong cua so.
pause >nul
