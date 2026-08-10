@echo off
chcp 65001 >nul
title BYC Web Uretim Planlama
cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo Python bulunamadi! Once "3-WEB-KURULUM.bat" calistirin.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   BYC WEB URETIM PLANLAMA v7.4
echo ============================================
echo.
echo Eski sunucu varsa kapatiliyor...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5000" ^| findstr "LISTENING"') do (
    echo   Port 5000 — PID %%a kapatiliyor
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo.
echo Tarayici otomatik acilacak.
echo Bu pencereyi KAPATMAYIN - sunucu burada calisir.
echo.
echo Giris: admin / admin123
echo Mobil: http://[IP-ADRESINIZ]:5000/mobile
echo.
echo Sol menude "Makine Takvimi" OLMAMALI.
echo Baslikta v7.4 gorunmeli.
echo.

start "" "http://localhost:5000"
python web_app.py

if errorlevel 1 (
    echo.
    echo Program acilamadi. Once "3-WEB-KURULUM.bat" calistirin.
    pause
)
