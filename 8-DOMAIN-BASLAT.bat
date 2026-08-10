@echo off
chcp 65001 >nul
title BYC - Domain Tuneli (byc.net.tr)
cd /d "%~dp0"

echo.
echo ============================================
echo   BYC DOMAIN TUNELI - byc.net.tr
echo ============================================
echo.

where cloudflared >nul 2>&1
if errorlevel 1 (
    echo [HATA] cloudflared bulunamadi!
    echo.
    echo Kurulum icin PowerShell'de:
    echo   winget install --id Cloudflare.cloudflared
    echo.
    echo Detayli adimlar: deploy\DOMAIN-KURULUM.md
    pause
    exit /b 1
)

netstat -ano | findstr ":5000" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    echo [UYARI] Port 5000 dinlenmiyor!
    echo Once "4-WEB-AC.bat" ile web uygulamasini baslatin.
    echo.
    pause
    exit /b 1
)

echo Web uygulamasi calisiyor.
echo Tunel baslatiliyor...
echo.
echo Site: https://byc.net.tr
echo Bu pencereyi KAPATMAYIN.
echo.

cloudflared tunnel run byc-uretim

if errorlevel 1 (
    echo.
    echo Tunel baslatilamadi. Kontrol edin:
    echo   1. cloudflared tunnel login yapildi mi?
    echo   2. cloudflared tunnel create byc-uretim yapildi mi?
    echo   3. config.yml dosyasi .cloudflared klasorunde mi?
    echo.
    echo Rehber: deploy\DOMAIN-KURULUM.md
    pause
)
