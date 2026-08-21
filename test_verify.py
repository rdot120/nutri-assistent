"""Verify TBCA names are actually correct."""
import sqlite3, unicodedata
conn = sqlite3.connect('data/tbca_cache.db')
rows = conn.execute('SELECT code, name FROM tbca_index').fetchall()
conn.close()

def norm(s):
    import re
    n = unicodedata.normalize('NFKD', s.lower())
    n = ''.join(c for c in n if not unicodedata.combining(c))
    n = re.sub(r'[^\w\s]', ' ', n)
    return re.sub(r'\s+', ' ', n).strip()

# Check if accucar, oleo etc actually exist after normalization
targets = {
    'acucar': 'acucar',
    'oleo': 'oleo',
    'leite integral': 'leite integral',
    'frango inteiro': 'frango inteiro',
    'queijo mussarela': 'queijo mussarela',
}

for label, search in targets.items():
    matches = [(r[0], r[1]) for r in rows if search in norm(r[1])]
    print(f"\n[{label}] ({len(matches)} matches):")
    for code, name in matches[:3]:
        n = norm(name)
        first = n.split(',')[0]
        print(f"  {code}: first_word='{first}' full='{n[:60]}'")
