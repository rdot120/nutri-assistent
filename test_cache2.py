"""Debug completo do cache e matching."""
import sys
import sqlite3
import json
from pathlib import Path

ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from nutrition.tbca import TBCAScraper, TBCAFood
from nutrition.matcher import FoodMatcher, normalize_food_name, extract_food_base

db_path = Path("data/tbca_cache.db")

# Limpar cache antigo e recomecar
if db_path.exists():
    db_path.unlink()
    print("Cache antigo removido")

scraper = TBCAScraper(cache_db_path=db_path)

# Buscar alimentos
test_terms = ["arroz", "feijao", "acai", "banana", "leite", "acucar"]
all_foods = []

for term in test_terms:
    foods = scraper.search_and_fetch(term, max_results=2)
    all_foods.extend(foods)
    for f in foods:
        scraper.to_cache(f)
    print(f"'{term}': {len(foods)} alimentos buscados e salvos")

# Verificar cache
conn = sqlite3.connect(str(db_path))
count = conn.execute("SELECT COUNT(*) FROM tbca_foods").fetchone()[0]
rows = conn.execute("SELECT code, name FROM tbca_foods").fetchall()
conn.close()
print(f"\nCache: {count} alimentos")
for r in rows:
    print(f"  {r[0]}: {r[1]}")

# Indexar
matcher = FoodMatcher(high_threshold=55.0, medium_threshold=35.0)

# Usar alimentos buscados
foods_for_index = all_foods if all_foods else [
    TBCAFood(code=r[0], name=r[1], nutrients=json.loads(r[2]))
    for r in rows
]
matcher.load_tbca_index(foods_for_index)

# Mostrar nomes indexados
print(f"\nIndice: {len(matcher._tbca_names)} alimentos")
for entry in matcher._tbca_names[:10]:
    print(f"  [{entry['code']}] '{entry['original']}' -> base='{entry['base']}'")

# Testes
test_names = ["ACAI EM PO", "ARROZ", "BANANA", "LEITE", "ACUCAR"]
print("\n=== Matching ===")
for name in test_names:
    result = matcher.match(name)
    if result:
        print(f"  {name:20s} -> {result.tbca_name[:50]:50s} ({result.confidence:.0f}% {result.match_method})")
    else:
        print(f"  {name:20s} -> SEM MATCH")
