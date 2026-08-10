@echo off
chcp 65001 >nul
title BYC - Otomatik Yedek
cd /d "%~dp0"
python -c "from backup import yedek_al; print('Yedek alindi:', yedek_al())"
pause
