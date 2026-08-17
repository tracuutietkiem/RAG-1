@echo off
chcp 65001 >nul
title Dung Tro ly Tra cuu Van ban
echo Dang dung ung dung (cong 8501) ...
set FOUND=0
for /f "tokens=5" %%p in ('netstat -ano ^| findstr :8501 ^| findstr LISTENING') do (
    taskkill /F /PID %%p >nul 2>&1
    set FOUND=1
)
if "%FOUND%"=="1" (
    echo Da dung xong.
) else (
    echo Khong thay ung dung dang chay tren cong 8501.
)
pause
