"""Debug cache TBCA."""
import sys
import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from nutrition.tbca import TBCAScraper, TBCAFood

# Check cache
db_path = Path("data/tbca_cache.db")
print(f"Cache exists: {db_path.exists()}")
if db_path.exists():
    conn = sqlite3.connect(str(db_path))
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f"Tables: {tables}")
    for t in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0]
        print(f"  {t[0]}: {count} rows")
    conn.close()

# Test saving
scraper = TBCAScraper(cache_db_path=db_path)
food = TBCAFood(
    code="TEST001",
    name="Teste Banana",
    nutrients={"energia_kcal": {"value_per_100g": 89.0, "unit": "kcal"}}
)
scraper.to_cache(food)

# Check again
conn = sqlite3.connect(str(db_path))
count = conn.execute("SELECT COUNT(*) FROM tbca_foods").fetchone()[0]
print(f"\nAfter save: {count} rows")
rows = conn.execute("SELECT code, name FROM tbca_foods").fetchall()
for r in rows:
    print(f"  {r[0]}: {r[1]}")
conn.close()
