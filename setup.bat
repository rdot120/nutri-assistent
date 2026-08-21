@echo off
REM ============================================
REM Nutri Assistent - Instalador Automatico
REM Instala e configura TUDO necessario para
REM o programa funcionar em qualquer PC
REM ============================================
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

title Nutri Assistent - Instalador

echo.
echo  ========================================
echo   Nutri Assistent - Instalador Automatico
echo  ========================================
echo.
echo  Este instalador vai configurar:
echo    [1] Python 3.11+ (se necessario)
echo    [2] Dependencias do projeto
echo    [3] Navegador Playwright (chromium)
echo    [4] Ollama + Modelo de IA (opcional)
echo    [5] Atalho no Desktop
echo.
echo  ========================================
echo.

REM ============================================
REM FASE 1: Verificar/Instalar Python
REM ============================================
echo [1/5] Verificando Python...

python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [!] Python nao encontrado!
    echo  [i] Baixando Python 3.11...
    echo.

    REM Baixar Python installer
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\python-installer.exe'}"

    if not exist "%TEMP%\python-installer.exe" (
        echo  [ERRO] Falha ao baixar Python!
        echo  [i] Instale manualmente: https://www.python.org/downloads/
        pause
        exit /b 1
    )

    echo  [i] Instalando Python (pode levar 1-2 minutos)...
    "%TEMP%\python-installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
    timeout /t 5 /nobreak >nul

    REM Verificar novamente
    python --version >nul 2>&1
    if errorlevel 1 (
        echo  [ERRO] Python ainda nao encontrado apos instalacao!
        echo  [i] Reinicie o computador e execute este script novamente.
        pause
        exit /b 1
    )
    del "%TEMP%\python-installer.exe" >nul 2>&1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo  [OK] Python %PYVER% encontrado

REM ============================================
REM FASE 2: Instalar dependencias
REM ============================================
echo.
echo [2/5] Instalando dependencias...

REM Atualizar pip
python -m pip install --upgrade pip --quiet 2>nul

REM Instalar dependencias
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo  [AVISO] Algumas dependencias podem ter falhado
)

REM Instalar playwright
pip install playwright --quiet 2>nul
echo  [OK] Dependencias instaladas

REM ============================================
REM FASE 3: Instalar navegador Playwright
REM ============================================
echo.
echo [3/5] Instalando navegador Playwright...

REM Verificar se ja esta instalado
python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(headless=True); b.close(); p.stop()" >nul 2>&1
if errorlevel 1 (
    echo  [i] Baixando chromium (pode levar 2-5 minutos)...
    python -m playwright install chromium
    if errorlevel 1 (
        echo  [AVISO] Playwright pode precisar de dependencias do sistema
        echo  [i] Execute manualmente: python -m playwright install-deps
    )
) else (
    echo  [OK] Navegador ja instalado
)

REM Instalar dependencias do sistema
python -m playwright install-deps 2>nul

echo  [OK] Playwright configurado

REM ============================================
REM FASE 4: Instalar Ollama (opcional)
REM ============================================
echo.
echo [4/5] Configurando IA Local (Ollama)...

ollama --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  Ollama nao encontrado. Deseja instalar?
    echo  [S] Sim - Instalar Ollama (recomendado, gratuito)
    echo  [N] Nao - Pular (usar Groq online)
    echo.
    set /p OLLAMA_CHOICE="  Resposta (S/N): "

    if /i "!OLLAMA_CHOICE!"=="S" (
        echo  [i] Baixando Ollama...
        powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile '%TEMP%\OllamaSetup.exe'}"

        if exist "%TEMP%\OllamaSetup.exe" (
            echo  [i] Instalando Ollama...
            start /wait "%TEMP%\OllamaSetup.exe"
            del "%TEMP%\OllamaSetup.exe" >nul 2>&1

            REM Verificar instalacao
            ollama --version >nul 2>&1
            if errorlevel 1 (
                echo  [AVISO] Ollama instalado mas nao encontrado no PATH
                echo  [i] Reinicie o computante apos a instalacao
            ) else (
                echo  [OK] Ollama instalado
            )
        ) else (
            echo  [ERRO] Falha ao baixar Ollama
        )
    ) else (
        echo  [i] Pulando Ollama - IA local desabilitada
    )
) else (
    echo  [OK] Ollama ja instalado
)

REM Verificar se Ollama esta rodando e baixar modelo
ollama --version >nul 2>&1
if not errorlevel 1 (
    echo  [i] Verificando se Ollama esta rodando...
    ollama list >nul 2>&1
    if errorlevel 1 (
        echo  [i] Iniciando Ollama...
        start "" ollama serve
        timeout /t 5 /nobreak >nul
    )

    REM Verificar se modelo ja existe
    ollama list 2>nul | findstr "llama3.2" >nul 2>&1
    if errorlevel 1 (
        echo  [i] Baixando modelo de IA (llama3.2 - 2GB)...
        echo  [i] Isso pode levar 5-15 minutos dependendo da internet
        ollama pull llama3.2
    ) else (
        echo  [OK] Modelo llama3.2 ja instalado
    )
)

REM ============================================
REM FASE 5: Criar atalho no Desktop
REM ============================================
echo.
echo [5/5] Criando atalho no Desktop...

REM Copiar executavel para local permanente
set INSTALL_DIR=%LOCALAPPDATA%\NutriAssistent
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

REM Copiar arquivos necessarios
if exist "dist\NutriAssistent.exe" (
    copy "dist\NutriAssistent.exe" "%INSTALL_DIR%\" >nul
    copy "config\.env" "%INSTALL_DIR%\config\" >nul 2>nul
)

REM Criar atalho no Desktop
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Nutri Assistent.lnk'); $sc.TargetPath = '%INSTALL_DIR%\NutriAssistent.exe'; $sc.WorkingDirectory = '%INSTALL_DIR%'; $sc.Description = 'Nutri Assistent - Automacao Nutricional'; $sc.Save()"

echo  [OK] Atalho criado no Desktop

REM ============================================
REM CONCLUSAO
REM ============================================
echo.
echo  ========================================
echo   Instalacao Concluida!
echo  ========================================
echo.
echo  O Nutri Assistent foi instalado em:
echo    %INSTALL_DIR%
echo.
echo  Para usar:
echo    1. Clique no atalho no Desktop
echo    2. Configure sua chave Groq (gratuita)
echo       - Acesse: https://console.groq.com
echo       - Crie uma conta (gratuito)
echo       - Vá em API Keys > Create API Key
echo       - Cole nas Configuracoes do programa
echo    3. Configure seu usuario/senha da plataforma
echo    4. Clique em 'Load Data' e depois 'Start Pipeline'
echo.
echo  Alternativa IA (sem cadastro):
echo    - Groq: Gratuito, 14.000 requisicoes/dia
echo    - Ollama: Local, ilimitado, mas mais lento
echo.
echo  ========================================
echo.
pause
