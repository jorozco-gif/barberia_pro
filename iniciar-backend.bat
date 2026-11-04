@echo off
title Backend - BarberShop Pro (FastAPI)
cd /d "%~dp0src\backend"
echo ===================================================
echo   Iniciando Backend BarberShop Pro en Puerto 8000
echo ===================================================
if not exist "venv\Scripts\activate.bat" (
    echo Creando entorno virtual...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)
echo Verificando base de datos inicial...
python seed.py
echo.
echo Servidor API listo en: http://127.0.0.1:8000
echo Documentacion Swagger:  http://127.0.0.1:8000/docs
echo.
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
pause
