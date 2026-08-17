@echo off
chcp 65001 >nul
title Nap Mini Knowledge Graph vao Neo4j - Buoi 14

cd /d "D:\01_CONG_VIEC\phan_mem_tra_cuVB\RAG\rag_foundation\buoi_14"

echo ============================================================
echo   NAP MINI KNOWLEDGE GRAPH VAO NEO4J - BUOI 14
echo ============================================================
echo Thu muc: %CD%
echo.
echo Truoc khi chay, dam bao:
echo   - Neo4j Desktop dang mo
echo   - Instance "rag2026" o trang thai RUNNING
echo.
echo Script CHI them du lieu moi, gan nhan lab_session="buoi_14".
echo No KHONG xoa du lieu Buoi 12/13 dang co trong database.
echo.
pause

echo.
echo [1/2] Kiem tra thu vien neo4j ...
python -c "import neo4j" 2>nul
if errorlevel 1 (
    echo     Chua co. Dang cai ...
    python -m pip install neo4j
    echo.
)

echo [2/2] Dang nap ...
echo.
python scripts\load_mini_kg.py

echo.
echo ============================================================
echo Xem bao cao chi tiet tai: outputs\kg_build_report.md
echo ============================================================
echo.
echo Bam phim bat ky de dong cua so.
pause >nul
