@echo off
chcp 65001 >nul
title BYC Uretim Planlama - Ilk Kurulum
echo.
echo ============================================
echo   BYC Uretim Planlama - ILK KURULUM
echo ============================================
echo.
echo Gerekli dosyalar yukleniyor, lutfen bekleyin...
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [HATA] Python bulunamadi!
    echo.
    echo Python yuklu degil. Su adrese gidin:
    echo https://www.python.org/downloads/
    echo.
    echo Yuklerken "Add Python to PATH" kutucugunu ISARETLEYIN!
    echo.
    pause
    exit /b 1
)

python -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo [HATA] Kurulum basarisiz oldu.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   KURULUM TAMAMLANDI!
echo ============================================
echo.
echo Simdi "2-PROGRAMI_AC.bat" dosyasina cift tiklayin.
echo.
pause
