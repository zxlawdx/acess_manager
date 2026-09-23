@echo off
setlocal
cd /d "%~dp0"
set PYTHONNOUSERSITE=1

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist package rmdir /s /q package

if not exist .venv (
    py -3.13 -m venv .venv 2>nul || py -m venv .venv
)

call .venv\Scripts\activate.bat

python -m pip install --upgrade pip setuptools wheel
python -m pip install --no-user -r requirements-build.txt
if errorlevel 1 goto :error

python manage.py collectstatic --no-tailwind
if errorlevel 1 goto :error

python -m PyInstaller --noconfirm --clean --onedir --windowed ^
  --name ZTEAutomatic ^
  --add-data "apps;apps" ^
  --add-data "config;config" ^
  --add-data "staticfiles;staticfiles" ^
  --add-data "data;data" ^
  --add-data "docs;docs" ^
  --collect-all vela ^
  --collect-all PyQt5 ^
  --collect-all PyQtWebEngine ^
  --collect-all webview ^
  --collect-all qtpy ^
  --hidden-import=vela ^
  --hidden-import=vela.core ^
  --hidden-import=vela.core.app ^
  --hidden-import=vela.template_engine ^
  --hidden-import=vela.template_engine.engine ^
  --hidden-import=webview ^
  --hidden-import=webview.platforms.qt ^
  --hidden-import=qtpy ^
  --hidden-import=qtpy.QtCore ^
  --hidden-import=qtpy.QtGui ^
  --hidden-import=qtpy.QtWidgets ^
  --hidden-import=PyQt5 ^
  --hidden-import=PyQt5.QtCore ^
  --hidden-import=PyQt5.QtGui ^
  --hidden-import=PyQt5.QtWidgets ^
  --hidden-import=PyQt5.QtWebEngineWidgets ^
  --hidden-import=PyQt5.QtWebEngineCore ^
  --hidden-import=PyQt5.QtWebChannel ^
  --exclude-module=webview.platforms.winforms ^
  --exclude-module=clr ^
  --exclude-module=pythonnet ^
  launcher.py
if errorlevel 1 goto :error

echo.
echo Build concluido em dist\ZTEAutomatic\
exit /b 0

:error
echo.
echo ERRO durante o build.

rem Em CI nao pode pausar aguardando teclado, senao o job fica preso.
if /I not "%CI%"=="true" pause

exit /b 1
