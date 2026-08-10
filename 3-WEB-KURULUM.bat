@echo off
chcp 65001 >nul
title BYC Web Uretim Planlama - Ilk Kurulum
cd /d "%~dp0"

echo.
echo ============================================
echo   BYC WEB URETIM PLANLAMA - ILK KURULUM
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [HATA] Python bulunamadi!
    echo https://www.python.org/downloads/ adresinden yukleyin.
    echo Kurarken "Add Python to PATH" kutusunu ISARETLEYIN!
    pause
    exit /b 1
)

python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Kurulum basarisiz.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   KURULUM TAMAMLANDI!
echo ============================================
echo.
echo Simdi "4-WEB-AC.bat" dosyasina cift tiklayin.
echo.
pause
