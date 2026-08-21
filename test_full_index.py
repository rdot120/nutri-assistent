"""Teste completo: listar todas as paginas TBCA + matching."""
import sys
import json
from pathlib import Path

ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from nutrition.tbca import TBCAScraper
from nutrition.matcher import FoodMatcher

db_path = Path("data/tbca_cache.db")

# Limpar cache antigo
if db_path.exists():
    db_path.unlink()

scraper = TBCAScraper(cache_db_path=db_path)

# 1. Buscar todas as paginas de listagem
print("=== Fase 1: Buscando listagem TBCA ===")
all_items = scraper.fetch_all_listings(max_pages=105, delay=0.3)
scraper.save_listing_index(all_items)
print(f"Total: {len(all_items)} alimentos")

# Mostrar amostra
print("\nAmostra (primeiros 10):")
for item in all_items[:10]:
    print(f"  [{item['code']}] {item['name']} ({item['group']})")

# 2. Indexar para matching
print("\n=== Fase 2: Indexando para matching ===")
matcher = FoodMatcher(high_threshold=55.0, medium_threshold=35.0)
matcher.load_tbca_index(all_items)
print(f"Indice: {len(matcher._tbca_names)} alimentos")

# 3. Testar matching
test_names = [
    "ACAI EM PO", "ARROZ INTEGRAL", "FEIJAO CARIOCA", "BANANA PRATA",
    "LEITE INTEGRAL", "ACUCAR REFINADO", "OLEO DE SOJA", "SAL REFINADO",
    "FRANGO INTEIRO", "OVO", "QUEIJO MUSSARELA", "IOGURTE NATURAL",
    "CAFE", "TRIGO", "Milho", "CARNE MOIDA", "PEIXE GRELHADO",
    "MACARRAO", "PAO FRANCES", "MANTEIGA", "CHOCOLATE",
    "SUCO DE LARANJA", "CREME DE LEITE", "MARGARINA",
]

print("\n=== Fase 3: Testes de Matching ===")
matched = 0
for name in test_names:
    result = matcher.match(name)
    if result:
        matched += 1
        print(f"  {name:25s} -> {result.tbca_name[:55]:55s} ({result.confidence:.0f}% {result.match_method})")
    else:
        print(f"  {name:25s} -> SEM MATCH")

print(f"\nResultado: {matched}/{len(test_names)} matches")
