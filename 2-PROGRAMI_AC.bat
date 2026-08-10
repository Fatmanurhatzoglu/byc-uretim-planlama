@echo off
chcp 65001 >nul
title BYC Uretim Planlama
cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [HATA] Python bulunamadi!
    echo Once "1-KURULUM.bat" dosyasini calistirin.
    echo.
    pause
    exit /b 1
)

echo Program aciliyor, lutfen bekleyin...
echo.

python main.py
if errorlevel 1 (
    echo.
    echo ============================================
    echo   PROGRAM ACILAMADI - HATA OLUSTU
    echo ============================================
    echo.
    echo Yukaridaki kirmizi hata mesajini okuyun.
    echo Cozemezseniz bu ekranin fotografini
    echo Cursor'a gonderin, yardim edelim.
    echo.
    pause
)
