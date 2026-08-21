"""Teste de parsing da busca TBCA."""
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

# Analisar estrutura da pagina
print("=== Titulo ===")
print(soup.title.string if soup.title else "N/A")

# Procurar tabelas
tables = soup.find_all("table")
print(f"\nTabelas encontradas: {len(tables)}")

# Procurar por links de alimentos
food_links = []
for a in soup.find_all("a", href=True):
    href = a["href"]
    text = a.get_text(strip=True)
    if text and len(text) > 3:
        if "BRC" in text or "int_composicao" in href:
            food_links.append({"text": text, "href": href})

print(f"\nLinks com BRC ou int_composicao: {len(food_links)}")
for link in food_links[:20]:
    print(f"  [{link['text'][:60]}] -> {link['href'][:80]}")

# Procurar por divs com texto de alimentos
print("\n=== Procurando por blocos de resultado ===")
# TBCA pode usar divs ou spans
for div in soup.find_all(["div", "span", "td", "li"]):
    text = div.get_text(strip=True)
    if "BRC" in text and "acai" in text.lower():
        print(f"  Encontrado: {text[:100]}")
        break
