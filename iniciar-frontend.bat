@echo off
title Frontend - BarberShop Pro (React + Vite)
cd /d "%~dp0src\frontend"
echo ===================================================
echo   Iniciando Frontend BarberShop Pro en Puerto 5173
echo ===================================================
if not exist "node_modules" (
    echo Instalando paquetes de Node...
    call npm install
)
echo.
echo Abriendo aplicacion web en: http://localhost:5173
echo.
call npm run dev
pause
