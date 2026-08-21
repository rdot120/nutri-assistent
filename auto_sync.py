"""
Nutri Assistent - Sincronizacao Automatica com GitHub
Roda em background e sincroniza a cada 5 minutos.
"""
import subprocess
import time
import os
import sys
from datetime import datetime

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
SYNC_INTERVAL = 300  # 5 minutos

def run(cmd, capture=True):
    """Executa comando git."""
    result = subprocess.run(
        cmd, shell=True, cwd=REPO_DIR,
        capture_output=capture, text=True
    )
    return result.returncode == 0, result.stdout.strip() if capture else ""

def sync():
    """Sincroniza com GitHub."""
    now = datetime.now().strftime("%H:%M:%S")
    
    # Verificar se ha mudancas
    ok, status = run("git status --porcelain")
    if not ok:
        return False
    
    # Se ha mudancas, commitar e enviar
    if status:
        print(f"[{now}] Mudancas detectadas, enviando...")
        run("git add .")
        run('git commit -m "Auto-sync: atualizacao automatica"')
        ok, _ = run("git push")
        if ok:
            print(f"[{now}] Enviado com sucesso!")
        else:
            print(f"[{now}] Erro ao enviar")
    
    # Sempre puxar atualizacoes
    ok, _ = run("git pull --rebase")
    if ok:
        # Verificar se algo mudou
        ok2, status2 = run("git status --porcelain")
        if ok2 and not status2:
            pass  # Tudo sincronizado
    
    return True

def main():
    print("=" * 50)
    print("  Nutri Assistent - Sincronizacao Automatica")
    print("=" * 50)
    print()
    print("  Sincronizando com GitHub a cada 5 minutos...")
    print("  Pressione Ctrl+C para parar")
    print()
    
    # Sincronizar imediatamente ao iniciar
    print("  Sincronizacao inicial...")
    sync()
    print()
    
    while True:
        try:
            time.sleep(SYNC_INTERVAL)
            sync()
        except KeyboardInterrupt:
            print("\n  Sincronizacao parada.")
            break
        except Exception as e:
            print(f"  Erro: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
