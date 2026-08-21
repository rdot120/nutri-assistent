"""Teste do food matcher."""
import sys
import json
import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from nutrition.tbca import TBCAScraper, TBCAFood
from nutrition.matcher import FoodMatcher

scraper = TBCAScraper(cache_db_path=Path("data/tbca_cache.db"))

# Buscar mais alimentos para testar matching
test_terms = [
    "arroz", "feijao", "acai", "banana", "leite", "acucar", "oleo", "sal",
    "frango", "ovo", "queijo", "iogurte", "cafe", "trigo", "milho",
    "carne", "peixe", "macarrao", "pao", "manteiga", "creme",
    "chocolate", "suco", "refrigerante", "cerveja",
]
all_foods = []

for term in test_terms:
    print(f"Buscando '{term}'...", end=" ", flush=True)
    foods = scraper.search_and_fetch(term, max_results=2)
    all_foods.extend(foods)
    for f in foods:
        scraper.to_cache(f)
    print(f"{len(foods)} encontrados")

print(f"\nTotal TBCA: {len(all_foods)} alimentos")

# Carregar do cache tambem
conn = sqlite3.connect(str(Path("data/tbca_cache.db")))
rows = conn.execute("SELECT code, name, nutrients_json FROM tbca_foods").fetchall()
conn.close()
cached_foods = [TBCAFood(code=r[0], name=r[1], nutrients=json.loads(r[2])) for r in rows]
print(f"No cache: {len(cached_foods)} alimentos")

# Indexar (usar cache)
matcher = FoodMatcher(high_threshold=60.0, medium_threshold=40.0)
matcher.load_tbca_index(cached_foods)

# Testes de matching
test_names = [
    "ACAI EM PO",
    "ARROZ INTEGRAL",
    "FEIJAO CARIOCA",
    "BANANA PRATA",
    "LEITE INTEGRAL",
    "ACUCAR REFINADO",
    "OLEO DE SOJA",
    "SAL REFINADO",
    "FRANGO INTEIRO",
    "OVO",
    "QUEIJO MUSSARELA",
    "IOGURTE NATURAL",
    "CAFE",
    "TRIGO",
    "Milho",
    "CARNE MOIDA",
    "PEIXE GRELHADO",
    "MACARRAO",
    "PAO FRANCES",
    "MANTEIGA",
]

print("\n=== Testes de Matching ===")
for name in test_names:
    result = matcher.match(name)
    if result:
        print(f"  {name:25s} -> {result.tbca_name[:55]:55s} ({result.confidence:.0f}% {result.match_method})")
    else:
        print(f"  {name:25s} -> SEM MATCH")
