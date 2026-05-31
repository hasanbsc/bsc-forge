@echo off
setlocal enabledelayedexpansion
title BSC Forge

REM ============================================================
REM  BSC Forge - Tek tikla baslatici
REM  Public URL: https://bsc-forge.elf-justitia.ts.net
REM
REM  Ilk acilista WSL'ye Tailscale kurulup auth gerekebilir
REM  (pencerede yonergeler basilir). Sonraki acilislar tamamen
REM  otomatiktir.
REM ============================================================

set "TS_WIN=C:\Program Files\Tailscale\tailscale.exe"

REM ===== 1) Windows tarafindaki Funnel kayitlarini temizle =====
REM    Funnel WSL icinde acilir; Windows daemon'a takili eski kayitlar
REM    cakisma yapmasin diye sifirlanir. Node rename'i icin admin panel:
REM    https://login.tailscale.com/admin/machines
if exist "%TS_WIN%" "%TS_WIN%" funnel reset >nul 2>nul

REM ===== 2) WSL var mi? =====
where wsl >nul 2>nul
if errorlevel 1 (
  echo HATA: WSL bulunamadi. Windows'ta WSL kurulu olmali.
  pause
  exit /b 1
)

echo ============================================================
echo   BSC Forge baslatiliyor
echo   Yerel:   http://localhost:8000
echo   Public:  https://bsc-forge.elf-justitia.ts.net
echo   Durdur:  Ctrl+C  veya  bu pencereyi kapat
echo ============================================================
echo.

REM ===== 3) WSL icindeki baslat.sh'i calistir =====
wsl bash /home/hasan/bsc-forge/baslat.sh

echo.
echo Sunucu durdu.
pause
