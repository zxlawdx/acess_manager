@echo off
setlocal
cd /d "%~dp0"

set PYTHONNOUSERSITE=1

echo.
echo ============================================================
echo ZTE Automatic - Build Windows
echo ============================================================
echo.

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist package rmdir /s /q package

rem ------------------------------------------------------------
rem Ambiente
rem ------------------------------------------------------------

if not exist .venv (
    py -3.12 -m venv .venv 2>nul || py -m venv .venv
)

call .venv\Scripts\activate.bat

python -m pip install --upgrade pip setuptools wheel "packaging>=24.2"
if errorlevel 1 goto :error

python -m pip install --no-user -r requirements-build.txt
if errorlevel 1 goto :error

rem ------------------------------------------------------------
rem Estáticos
rem ------------------------------------------------------------

python manage.py collectstatic --no-tailwind
if errorlevel 1 goto :error

rem ------------------------------------------------------------
rem Testes antes do empacotamento
rem ------------------------------------------------------------

python -m unittest discover -s tests -v
if errorlevel 1 goto :error

node --check apps\zte_manager\static\js\app.js
if errorlevel 1 goto :error

rem ------------------------------------------------------------
rem PyInstaller
rem ------------------------------------------------------------
rem
rem Ponto importante:
rem config.wsgi -> VelaApp.register_app() -> importlib.import_module()
rem carrega apps.zte_manager.api dinamicamente.
rem
rem Apenas --add-data copia os .py como dados, mas NÃO informa ao
rem PyInstaller que esses módulos e suas dependências devem entrar
rem no PYZ. Foi isso que deixou o pydantic fora do v0.4.3.
rem
rem Por isso usamos --collect-submodules para apps/config e
rem --collect-all nas dependências com imports/metadata dinâmicos.

python -m PyInstaller --noconfirm --clean --onedir --windowed ^
  --name ZTEAutomatic ^
  --hidden-import=config ^
  --hidden-import=config.settings ^
  --hidden-import=config.wsgi ^
  --collect-submodules config ^
  --collect-submodules apps ^
  --collect-all vela ^
  --collect-all webview ^
  --collect-all pydantic ^
  --collect-all pydantic_core ^
  --collect-all cryptography ^
  --collect-all setuptools ^
  --collect-all jaraco.text ^
  --collect-all jaraco.functools ^
  --collect-all jaraco.context ^
  --collect-all more_itertools ^
  --collect-all PyQt5 ^
  --collect-all PyQtWebEngine ^
  --collect-all qtpy ^
  --hidden-import=webview.platforms.qt ^
  --hidden-import=PyQt5.QtWebEngineWidgets ^
  --hidden-import=PyQt5.QtWebEngineCore ^
  --hidden-import=PyQt5.QtWebChannel ^
  --exclude-module=webview.platforms.winforms ^
  --exclude-module=clr ^
  --exclude-module=pythonnet ^
  --add-data "apps;apps" ^
  --add-data "config;config" ^
  --add-data "staticfiles;staticfiles" ^
  --add-data "data;data" ^
  --add-data "docs;docs" ^
  launcher.py

if errorlevel 1 goto :error

rem ------------------------------------------------------------
rem Verificação básica do bundle
rem ------------------------------------------------------------

if not exist "dist\ZTEAutomatic\ZTEAutomatic.exe" (
    echo ERRO: executavel nao encontrado.
    goto :error
)

if not exist "dist\ZTEAutomatic\_internal\apps\zte_manager\templates\index.html" (
    echo ERRO: template principal nao entrou no bundle.
    goto :error
)

if not exist "dist\ZTEAutomatic\_internal\staticfiles\zte_manager\js\app.js" (
    echo ERRO: JavaScript principal nao entrou no bundle.
    goto :error
)

echo.
echo Build concluido em dist\ZTEAutomatic\
exit /b 0

:error
echo.
echo ERRO durante o build.

rem Em CI nao pode pausar esperando teclado.
if /I not "%CI%"=="true" pause

exit /b 1
