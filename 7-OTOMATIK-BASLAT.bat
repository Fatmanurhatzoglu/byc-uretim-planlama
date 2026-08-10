@echo off
chcp 65001 >nul
title BYC - Windows Servisi Kurulumu
cd /d "%~dp0"

echo.
echo ============================================
echo   BYC - Bilgisayar Acilinca Otomatik Baslat
echo ============================================
echo.
echo Bu script, programi Windows baslangicina ekler.
echo Bilgisayar her acildiginda program otomatik calisir.
echo.

set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set KISAYOL=%STARTUP%\BYC-Uretim-Planlama.bat

echo @echo off > "%KISAYOL%"
echo cd /d "%~dp0" >> "%KISAYOL%"
echo start "" "http://localhost:5000" >> "%KISAYOL%"
echo python web_app.py >> "%KISAYOL%"

echo.
echo Kurulum tamamlandi!
echo Bilgisayar her acildiginda program otomatik baslayacak.
echo.
echo Kaldirma: Su dosyayi silin:
echo %KISAYOL%
echo.
pause
