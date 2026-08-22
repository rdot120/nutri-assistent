# Instruções para o agente (opencode)

## Regra principal
- **SEMPRE envie alterações para o GitHub**: depois de qualquer mudança de código, faça commit e `git push` imediatamente. Nunca deixe commits apenas locais.
- Identidade para commits: `Qualihouse <qualihouse@users.noreply.github.com>`

## Estrutura do projeto
- `nutri-assistent\` → **v1** (branch `main`) — NÃO mexer ao trabalhar na v1.1
- `nutri-assistent-v1.1\` → **v1.1** (branch `v1.1`) — versão em desenvolvimento (git worktree da mesma pasta .git)
- `Documents\NutriAssistent-CodigoFonte\` → código-fonte original trazido de outro PC (referência; não é repositório Git)

## Sincronização automática
- Ambas as pastas rodam `auto_sync.py` em background (`pythonw`), commitando e enviando a cada 5 minutos.
- O processo pode morrer ao reiniciar o PC — verificar com `Get-Process pythonw` e reiniciar via `start /min pythonw auto_sync.py` na pasta correspondente se necessário.

## Regras do projeto Nutri Assistent
- Ponto de entrada da GUI: `gui\run.py` (NÃO é o `main.py`, que é ferramenta CLI)
- `config\.env` contém credenciais — NUNCA commitar (já está no `.gitignore`)
- `data\browser_profile\` não deve ser versionado (já ignorado na v1.1; ainda rastreado na v1/main)
- Atalhos na área de trabalho abrem cada versão com seu próprio ambiente:
  - v1: Python do sistema
  - v1.1: `.venv` próprio dentro da pasta
- API USDA: endpoint `/food/changes` não existe na API pública — não reintroduzir chamadas a ele
