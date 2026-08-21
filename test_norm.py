"""Debug normalization and base extraction."""
import sys
import sqlite3
import unicodedata
import re
from pathlib import Path

ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

conn = sqlite3.connect(str(Path("data/tbca_cache.db")))
rows = conn.execute("SELECT code, name FROM tbca_index").fetchall()
conn.close()

def norm(s):
    nfkd = unicodedata.normalize("NFKD", s.lower())
    name = "".join(c for c in nfkd if not unicodedata.combining(c))
    name = re.sub(r"[^\w\s]", " ", name)
    return re.sub(r"\s+", " ", name).strip()

def base(name):
    m = re.match(r"^([a-z]+(?:\s+[a-z]+)?)", norm(name))
    return m.group(1) if m else norm(name).split(",")[0].strip()

# Show some key foods
targets = ["acucar", "oleo de soja", "sal", "frango inteiro", "queijo mussa", "leite integral", "trigo"]
for t in targets:
    matches = [(r[0], r[1]) for r in rows if t.lower() in norm(r[1])]
    print(f"\n[{t}] ({len(matches)} matches):")
    for code, name in matches[:5]:
        n = norm(name)
        b = base(name)
        print(f"  {code}: norm='{n}' base='{b}'")
