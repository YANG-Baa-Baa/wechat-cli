param(
    [string]$OutputDir = "dist"
)

$ErrorActionPreference = "Stop"

Write-Host "Installing build dependencies..."
python -m pip install --upgrade pip build pyinstaller
python -m pip install -e .

Write-Host "Building wechat-cli.exe..."
python -m PyInstaller `
    --onefile `
    --name wechat-cli `
    --clean `
    --collect-all wechat_cli `
    entry.py

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
Copy-Item -Force "dist\wechat-cli.exe" "$OutputDir\wechat-cli.exe"

Write-Host "Build completed: $OutputDir\wechat-cli.exe"
