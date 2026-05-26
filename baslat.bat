@echo off
setlocal
title BSC Forge

REM ============================================================
REM  BSC Forge - Sunucu baslatici
REM  Proje WSL icinde (/home/hasan/bsc-forge) calisiyor.
REM ============================================================

REM ===== 1/2: Tailscale Funnel =====
set "TS=C:\Program Files\Tailscale\tailscale.exe"
if exist "%TS%" goto :ts_ready
where tailscale >nul 2>nul
if errorlevel 1 goto :ts_skip
set "TS=tailscale"

:ts_ready
echo [1/2] Tailscale Funnel ayarlaniyor...
"%TS%" funnel --bg 8000
if errorlevel 1 goto :ts_warn
echo.
echo Funnel aktif. Public URL:
"%TS%" funnel status
echo.
goto :start_backend

:ts_warn
echo.
echo UYARI: Funnel baslatilamadi. Kontrol et:
echo   1) Tailscale system tray'de giris yapildi mi?
echo   2) Admin panelde Funnel feature acik mi?
echo   3) ACL nodeAttrs ile funnel izni verildi mi?
echo.
goto :start_backend

:ts_skip
echo [1/2] Tailscale bulunamadi - sadece yerel calisacak.
echo        Public link icin: https://tailscale.com/download/windows
echo.

:start_backend
REM ===== 2/2: Backend (WSL) =====
where wsl >nul 2>nul
if errorlevel 1 goto :no_wsl

echo [2/2] Frontend build + backend baslatiliyor (WSL)...
echo ============================================================
echo   BSC Forge calisiyor
echo   Yerel:    http://localhost:8000
echo   Public:   yukaridaki Funnel URL
echo   Durdur:   Ctrl+C  veya  bu pencereyi kapat
echo ============================================================
echo.

wsl bash -c "cd /home/hasan/bsc-forge/frontend && echo '--- Frontend derleniyor... ---' && npm run build && echo '--- Backend baslatiliyor... ---' && cd ../backend && source venv/bin/activate && python3 main.py"

echo.
echo Sunucu durdu.
goto :end

:no_wsl
echo HATA: WSL bulunamadi. Windows'ta WSL kurulu olmali.

:end
pause
