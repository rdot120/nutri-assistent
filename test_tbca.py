"""Teste rapido do scraper TBCA."""
import sys
import json
from pathlib import Path

ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from nutrition.tbca import TBCAScraper
from config.settings import DATA_DIR

def test():
    scraper = TBCAScraper(cache_db_path=DATA_DIR / "tbca_cache.db")

    # Testar busca
    print("Testando busca TBCA...")
    results = scraper.search("acai")
    print(f"Resultados: {len(results)}")
    for r in results[:5]:
        print(f"  [{r['code']}] {r['name']}")

    if results:
        # Buscar detalhes do primeiro
        print(f"\nBuscando detalhes: {results[0]['name']}...")
        food = scraper.fetch_food(results[0]['url'])
        if food:
            print(f"Codigo: {food.code}")
            print(f"Nome: {food.name}")
            print(f"Grupo: {food.group}")
            print(f"Cientifico: {food.scientific_name}")
            print(f"Nutrientes: {len(food.nutrients)}")
            for key, data in sorted(food.nutrients.items()):
                print(f"  {key}: {data['value_per_100g']} {data['unit']}")

            # Converter para campos da plataforma
            fields = scraper.to_platform_fields(food)
            print(f"\nCampos plataforma: {len(fields)}")
            for field, val in fields.items():
                print(f"  {field} = {val}")

            # Salvar no cache
            scraper.to_cache(food)
            print("\nSalvo no cache")

    print("\nTeste concluido")

if __name__ == "__main__":
    test()
