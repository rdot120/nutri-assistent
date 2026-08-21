@echo off
REM ============================================
REM Nutri Assistent - Build Script
REM Gera executavel com PyInstaller
REM ============================================
setlocal enabledelayedexpansion

echo ========================================
echo   Nutri Assistent - Build Script
echo ========================================

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado!
    exit /b 1
)

REM Verificar PyInstaller
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INFO] Instalando PyInstaller...
    pip install pyinstaller
)

REM Limpar builds anteriores
echo [1/5] Limpando builds anteriores...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "NutriAssistent.spec" del "NutriAssistent.spec"

REM Verificar dependencias
echo [2/5] Verificando dependencias...
pip install -r requirements.txt --quiet

REM Gerar icone se nao existir
if not exist "extra\icon.ico" (
    echo [3/5] Gerando icone...
    python generate_icon.py
) else (
    echo [3/5] Icone encontrado.
)

REM Build
echo [4/5] Gerando executavel...
python -m PyInstaller ^
    --name "NutriAssistent" ^
    --windowed ^
    --onefile ^
    --icon "extra\icon.ico" ^
    --add-data "extra\icon.ico;extra" ^
    --add-data "extra\logo.png;extra" ^
    --add-data "config\.env;config" ^
    --hidden-import "customtkinter" ^
    --hidden-import "playwright" ^
    --hidden-import "rapidfuzz" ^
    --hidden-import "httpx" ^
    --hidden-import "bs4" ^
    --hidden-import "openai" ^
    --hidden-import "anthropic" ^
    --hidden-import "ollama" ^
    --collect-all "customtkinter" ^
    --noconfirm ^
    gui\run.py

if errorlevel 1 (
    echo [ERRO] Build falhou!
    exit /b 1
)

REM Verificar resultado
echo [5/5] Verificando...
if exist "dist\NutriAssistent.exe" (
    echo.
    echo ========================================
    echo   Build concluido com sucesso!
    echo   Executavel: dist\NutriAssistent.exe
    echo ========================================
    
    REM Criar atalho no Desktop
    echo Criando atalho no Desktop...
    powershell -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Nutri Assistent.lnk'); $sc.TargetPath = '%CD%\dist\NutriAssistent.exe'; $sc.WorkingDirectory = '%CD%\dist'; $sc.Description = 'Nutri Assistent - Automacao Nutricional'; $sc.Save()"
    echo Atalho criado!
) else (
    echo [ERRO] Executavel nao encontrado!
    exit /b 1
)

echo.
echo Build finalizado!
pause
