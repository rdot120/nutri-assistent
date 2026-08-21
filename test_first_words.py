"""Check specific TBCA names."""
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

# Check first words
first_words = {}
for code, name in rows:
    n = norm(name)
    fw = n.split()[0] if n else ''
    if fw not in first_words:
        first_words[fw] = []
    first_words[fw].append((code, name))

# Show key foods
for fw in ['acucar', 'oleo', 'leite', 'carne', 'queijo', 'banana', 'arroz', 'feijao', 'ovo']:
    if fw in first_words:
        print(f"\n{fw} ({len(first_words[fw])} foods):")
        for code, name in first_words[fw][:3]:
            print(f"  {code}: {name}")
    else:
        print(f"\n{fw}: NOT FOUND as first word")

# Check for queijo
print("\n=== queijo foods ===")
for code, name in rows:
    if 'queijo' in norm(name).split(',')[0]:
        print(f"  {code}: {name}")
