import sqlite3,unicodedata
conn=sqlite3.connect('data/tbca_cache.db')
rows=conn.execute('SELECT code,name FROM tbca_index').fetchall()
conn.close()
def norm(s):
    import re
    n=unicodedata.normalize('NFKD',s.lower())
    n=''.join(c for c in n if not unicodedata.combining(c))
    return n
for code,name in rows:
    n=norm(name)
    first=n.split(',')[0].strip()
    if first.startswith('acucar') or first.startswith('oleo') or first.startswith('sal') or first.startswith('leite') or first.startswith('queijo') or first.startswith('frango'):
        print(f'{code}: {name}')
