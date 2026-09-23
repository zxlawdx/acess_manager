@echo off
setlocal
cd /d "%~dp0"

if not exist .venv (
    echo [1/4] Criando ambiente virtual...
    py -3.13 -m venv .venv 2>nul || py -m venv .venv
)

call .venv\Scripts\activate.bat

if errorlevel 1 (
    echo ERRO: nao foi possivel ativar o ambiente virtual.
    pause
    exit /b 1
)

echo [2/4] Instalando dependencias...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERRO: falha ao instalar dependencias.
    pause
    exit /b 1
)

echo [3/4] Coletando arquivos estaticos...
python manage.py collectstatic --no-tailwind
if errorlevel 1 (
    echo ERRO: collectstatic falhou.
    pause
    exit /b 1
)

echo [4/4] Iniciando ZTE Automatic...
python manage.py runapp
