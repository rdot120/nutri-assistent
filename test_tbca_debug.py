"""Debug completo da busca TBCA."""
import sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup

ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

url = "https://www.tbca.net.br/base-dados/composicao_alimentos.php"
resp = requests.get(url, params={"q": "acai"}, headers=HEADERS, timeout=15)
resp.encoding = "utf-8"

soup = BeautifulSoup(resp.text, "html.parser")

# Salvar HTML para analise
with open("data/tbca_search_debug.html", "w", encoding="utf-8") as f:
    f.write(resp.text)
print(f"HTML salvo: {len(resp.text)} chars")

# Analisar todas as tags com texto
print("\n=== Tags com 'BRC' no texto ===")
for tag in soup.find_all(string=lambda t: t and "BRC" in t):
    parent = tag.parent
    print(f"  <{parent.name}> texto='{tag.strip()[:80]}'")
    if parent.name == "td":
        row = parent.parent
        cells = row.find_all("td")
        print(f"    Row completa: {[c.get_text(strip=True)[:50] for c in cells]}")

# Analisar todos os links
print("\n=== Todos os links 'a' ===")
for a in soup.find_all("a", href=True):
    text = a.get_text(strip=True)
    href = a["href"]
    if text and ("BRC" in text or "int_composicao" in href):
        print(f"  href={href[:80]} text={text[:60]}")
