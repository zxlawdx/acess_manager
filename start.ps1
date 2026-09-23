$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Host "[1/4] Criando ambiente virtual..."

    py -3.13 -m venv .venv

    if ($LASTEXITCODE -ne 0) {
        py -m venv .venv
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Não foi possível criar o ambiente virtual."
    }
}

& .\.venv\Scripts\Activate.ps1

Write-Host "[2/4] Instalando dependencias..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Write-Host "[3/4] Coletando arquivos estaticos..."
python manage.py collectstatic --no-tailwind

Write-Host "[4/4] Iniciando ZTE Automatic..."
python manage.py runapp
