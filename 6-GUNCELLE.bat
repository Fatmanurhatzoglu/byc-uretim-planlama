@echo off
chcp 65001 >nul
title BYC - Guncelleme
cd /d "%~dp0"
echo.
echo Guncelleme kontrol ediliyor...
python -m pip install -r requirements.txt --upgrade
echo.
echo Guncelleme tamamlandi. "4-WEB-AC.bat" ile programi acin.
pause
