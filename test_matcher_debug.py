"""Debug do matching - ver nomes TBCA indexados."""
import sys
import json
from pathlib import Path

ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from nutrition.tbca import TBCAScraper, TBCAFood
from nutrition.matcher import FoodMatcher, normalize_food_name, extract_food_base

scraper = TBCAScraper(cache_db_path=Path("data/tbca_cache.db"))

# Carregar do cache
import sqlite3
conn = sqlite3.connect(str(Path("data/tbca_cache.db")))
rows = conn.execute("SELECT code, name, nutrients_json FROM tbca_foods").fetchall()
conn.close()

foods = [TBCAFood(code=r[0], name=r[1], nutrients=json.loads(r[2])) for r in rows]
print(f"Alimentos no cache: {len(foods)}")

for f in foods[:30]:
    norm = normalize_food_name(f.name)
    base = extract_food_base(norm)
    print(f"  [{f.code}] '{f.name}' -> norm='{norm}' base='{base}'")
