"""
Nutri Assistent - Instalador Automatico
Instala e configura tudo necessario para o programa funcionar.
"""
import subprocess
import sys
import os
import shutil
import urllib.request
from pathlib import Path

INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", "~")) / "NutriAssistent"
PYTHON_MIN = (3, 10)

def check_python():
    """Verifica se Python esta instalado e na versao minima."""
    print("[1/5] Verificando Python...")
    v = sys.version_info
    if v < PYTHON_MIN:
        print(f"  [ERRO] Python {v.major}.{v.minor} encontrado")
        print(f"  [i] Necessario Python {PYTHON_MIN[0]}.{PYTHON_MIN[1]} ou superior")
        print(f"  [i] Baixe em: https://www.python.org/downloads/")
        return False
    print(f"  [OK] Python {v.major}.{v.minor}.{v.micro}")
    return True

def install_pip_packages():
    """Instala pacotes pip do requirements.txt."""
    print("\n[2/5] Instalando dependencias...")
    
    req_file = Path(__file__).parent / "requirements.txt"
    if not req_file.exists():
        print("  [ERRO] requirements.txt nao encontrado")
        return False
    
    # Atualizar pip
    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
                   capture_output=True)
    
    # Instalar dependencias
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req_file), "--quiet"],
        capture_output=True, text=True
    )
    
    if result.returncode != 0:
        print(f"  [AVISO] Algumas dependencias podem ter falhado")
        print(f"  {result.stderr[:200]}")
    
    print("  [OK] Dependencias instaladas")
    return True

def install_playwright():
    """Instala navegador Playwright."""
    print("\n[3/5] Instalando navegador Playwright...")
    
    # Verificar se ja funciona
    test_cmd = (
        "from playwright.sync_api import sync_playwright; "
        "p = sync_playwright().start(); "
        "b = p.chromium.launch(headless=True); "
        "b.close(); p.stop()"
    )
    result = subprocess.run(
        [sys.executable, "-c", test_cmd],
        capture_output=True
    )
    
    if result.returncode == 0:
        print("  [OK] Navegador ja instalado")
        return True
    
    print("  [i] Baixando chromium...")
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True, text=True
    )
    
    if result.returncode != 0:
        print(f"  [AVISO] Erro: {result.stderr[:200]}")
        return False
    
    # Dependencias do sistema
    subprocess.run([sys.executable, "-m", "playwright", "install-deps"],
                   capture_output=True)
    
    print("  [OK] Playwright configurado")
    return True

def install_ollama():
    """Instala Ollama (opcional)."""
    print("\n[4/5] Configurando IA Local...")
    
    # Verificar se Ollama ja esta instalado
    result = subprocess.run(["ollama", "--version"], capture_output=True)
    if result.returncode == 0:
        print("  [OK] Ollama ja instalado")
    else:
        resp = input("\n  Deseja instalar Ollama? (S/N): ").strip().upper()
        if resp != "S":
            print("  [i] Pulando Ollama")
            return True
        
        print("  [i] Baixe Ollama de: https://ollama.com/download")
        print("  [i] Execute o instalador e volte aqui")
        input("  [i] Pressione ENTER quando terminar...")
    
    # Verificar se esta rodando
    result = subprocess.run(["ollama", "list"], capture_output=True)
    if result.returncode != 0:
        print("  [i] Iniciando Ollama...")
        subprocess.Popen(["ollama", "serve"], creationflags=0x08000000)
        import time
        time.sleep(5)
    
    # Verificar modelo
    result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
    if "llama3.2" not in result.stdout:
        print("  [i] Baixando modelo llama3.2 (2GB)...")
        print("  [i] Isso pode levar 5-15 minutos...")
        subprocess.run(["ollama", "pull", "llama3.2"])
    else:
        print("  [OK] Modelo ja instalado")
    
    return True

def install_files():
    """Copia arquivos para local de instalacao."""
    print("\n[5/5] Instalando arquivos...")
    
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    (INSTALL_DIR / "config").mkdir(exist_ok=True)
    (INSTALL_DIR / "data").mkdir(exist_ok=True)
    (INSTALL_DIR / "logs").mkdir(exist_ok=True)
    
    src_dir = Path(__file__).parent
    
    # Copiar executavel
    exe_src = src_dir / "dist" / "NutriAssistent.exe"
    if exe_src.exists():
        shutil.copy2(exe_src, INSTALL_DIR / "NutriAssistent.exe")
        print(f"  [OK] Executavel copiado")
    else:
        print("  [AVISO] Executavel nao encontrado (execute build.bat primeiro)")
    
    # Copiar .env se nao existir
    env_dst = INSTALL_DIR / "config" / ".env"
    if not env_dst.exists():
        env_src = src_dir / "config" / ".env"
        if env_src.exists():
            shutil.copy2(env_src, env_dst)
    
    # Criar atalho no Desktop
    try:
        import winshell
        from winshell import desktop
        shortcut_path = Path(desktop()) / "Nutri Assistent.lnk"
        
        shell = winshell.CreateObject("WScript.Shell")
        shortcut = shell.CreateShortCut(str(shortcut_path))
        shortcut.Targetpath = str(INSTALL_DIR / "NutriAssistent.exe")
        shortcut.WorkingDirectory = str(INSTALL_DIR)
        shortcut.Description = "Nutri Assistent"
        shortcut.save()
        print(f"  [OK] Atalho criado no Desktop")
    except ImportError:
        # Fallback sem winshell
        ps_cmd = f'''
        $ws = New-Object -ComObject WScript.Shell
        $sc = $ws.CreateShortcut("{Path.home() / 'Desktop' / 'Nutri Assistent.lnk'}")
        $sc.TargetPath = "{INSTALL_DIR / 'NutriAssistent.exe'}"
        $sc.WorkingDirectory = "{INSTALL_DIR}"
        $sc.Save()
        '''
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
        print(f"  [OK] Atalho criado no Desktop")
    
    print(f"  [OK] Instalado em: {INSTALL_DIR}")
    return True

def main():
    print()
    print("  ========================================")
    print("   Nutri Assistent - Instalador Automatico")
    print("  ========================================")
    print()
    
    steps = [
        ("Python", check_python),
        ("Dependencias", install_pip_packages),
        ("Playwright", install_playwright),
        ("Ollama", install_ollama),
        ("Arquivos", install_files),
    ]
    
    for name, func in steps:
        try:
            if not func():
                print(f"\n[ERRO] Falha na etapa: {name}")
                input("Pressione ENTER para continuar...")
        except Exception as e:
            print(f"\n[ERRO] {name}: {e}")
            input("Pressione ENTER para continuar...")
    
    print()
    print("  ========================================")
    print("   Instalacao Concluida!")
    print("  ========================================")
    print()
    print("  Para usar:")
    print("    1. Abra o Nutri Assistent pelo Desktop")
    print("    2. Configure sua chave Groq (gratuita)")
    print("       - console.groq.com")
    print("    3. Configure usuario/senha da plataforma")
    print("    4. Clique em 'Load Data'")
    print()
    print("  ========================================")
    input("\nPressione ENTER para fechar...")

if __name__ == "__main__":
    main()
