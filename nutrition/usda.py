"""
Scraper USDA FoodData Central.
API REST gratuita para busca de composicao nutricional de alimentos.
https://fdc.nal.usda.gov/api-guide.html
"""
import re
import time
import logging
import sqlite3
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

USDA_BASE = "https://api.nal.usda.gov/fdc/v1"

# Mapeamento USDA nutrient number -> chave normalizada
USDA_NUTRIENT_MAP = {
    "208": "energia_kcal",
    "209": "amido",
    "205": "carboidrato_total",
    "291": "fibra_alimentar",
    "269": "acucares_totais",
    "204": "lipidios_totais",
    "606": "gorduras_saturadas",
    "605": "gorduras_trans",
    "645": "gorduras_monoinsaturadas",
    "646": "gorduras_poliinsaturadas",
    "601": "colesterol",
    "203": "proteina",
    "207": "cinzas",
    "202": "alanina",
    "511": "arginina",
    "512": "acido_aspartico",
    "513": "acido_glutamico",
    "514": "glicina",
    "515": "histidina",
    "516": "isoleucina",
    "517": "leucina",
    "518": "lisina",
    "521": "metionina",
    "519": "fenilalanina",
    "520": "prolina",
    "522": "serina",
    "523": "treonina",
    "524": "triptofano",
    "525": "tirosina",
    "526": "valina",
    "421": "colina",
    "318": "vitamina_a_rae",
    "320": "retinol",
    "321": "beta_caroteno",
    "322": "alfa_caroteno",
    "323": "vitamina_e",
    "325": "vitamina_d2",
    "328": "vitamina_d3",
    "329": "vitamina_d_total",
    "334": "vitamina_b12",
    "430": "vitamina_k",
    "415": "vitamina_b6",
    "418": "vitamina_b12_duplicado",
    "417": "folato",
    "404": "tiamina",
    "405": "riboflavina",
    "406": "niacina",
    "410": "acido_pantotenico",
    "304": "magnesio",
    "305": "fosforo",
    "306": "potassio",
    "307": "sodio",
    "309": "zinco",
    "310": "manganes",
    "311": "cobre",
    "312": "ferro",
    "313": "fluor",
    "314": "selenio",
    "303": "ferro_duplicado",
    "301": "calcio",
    "315": "cromo",
    "316": "molibdenio",
    "317": "selenio_duplicado",
}

# Mapeamento USDA nutrient number -> campo da plataforma
USDA_TO_PLATFORM = {
    "208": "valorEnergetico429",
    "205": "carboidratos429",
    "269": "acucaresTotais429",
    "204": "gordurasTotais429",
    "606": "gordurasSaturadas429",
    "605": "gordurasTrans429",
    "291": "fibraAlimentar429",
    "307": "sodio429",
    "203": "proteinas429",
    "601": "colesterol",
    "645": "gordurasMonoinsaturadas",
    "646": "gordurasPoliInsaturadas",
    "312": "ferro",
    "301": "calcio",
    "309": "zinco",
    "304": "magnesio",
    "305": "fósforo",
    "306": "potassio",
    "310": "manganes",
    "311": "cobre",
    "314": "selenio",
    "313": "fluor",
    "318": "vitaminaA",
    "415": "vitaminaB1",
    "405": "vitaminaB2",
    "406": "vitaminaB3",
    "410": "vitaminaB5",
    "415": "vitaminaB6",
    "417": "vitaminaB9",
    "334": "vitaminaB12",
    "401": "vitaminaC",
    "328": "vitaminaD",
    "323": "vitaminaE",
    "430": "vitaminaK",
    "421": "colina",
}


@dataclass
class USDAFood:
    """Alimento com dados USDA."""
    fdc_id: str
    name: str
    description: str
    food_category: str
    nutrients: dict = None

    def __post_init__(self):
        if self.nutrients is None:
            self.nutrients = {}


class USDAScraper:
    """Scraper da API USDA FoodData Central."""

    def __init__(self, api_key: str = "DEMO_KEY",
                 cache_db_path: Path = None):
        self.api_key = api_key
        self.cache_db_path = cache_db_path
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "NutriAuto/1.0 (contato@example.com)"
        })

    def _request(self, endpoint: str, params: dict = None) -> dict:
        """Faz requisicao a API USDA."""
        url = f"{USDA_BASE}{endpoint}"
        if params is None:
            params = {}
        params["api_key"] = self.api_key

        try:
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code == 429:
                logger.warning("USDA API rate limit, aguardando 1s...")
                time.sleep(1)
                resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error("Erro USDA API: %s", e)
            return {}

    def search(self, query: str, page_size: int = 10,
               data_type: str = "Foundation,SR Legacy") -> list[dict]:
        """
        Busca alimentos no USDA.
        Retorna lista de {fdc_id, description, food_category, data_type}.
        """
        data = self._request("/foods/search", {
            "query": query,
            "pageSize": page_size,
            "dataType": data_type,
        })

        results = []
        for food in data.get("foods", []):
            results.append({
                "fdc_id": str(food.get("fdcId", "")),
                "description": food.get("description", ""),
                "food_category": food.get("foodCategory", ""),
                "data_type": food.get("dataType", ""),
            })
        return results

    def get_food(self, fdc_id: str) -> Optional[USDAFood]:
        """Busca detalhes nutricionais de um alimento."""
        # Verificar cache
        if self.cache_db_path:
            cached = self._from_cache(fdc_id)
            if cached:
                return cached

        data = self._request(f"/food/{fdc_id}")
        if not data:
            return None

        food = USDAFood(
            fdc_id=str(data.get("fdcId", fdc_id)),
            name=data.get("description", ""),
            description=data.get("description", ""),
            food_category=data.get("foodCategory", {}).get("description", "")
                           if isinstance(data.get("foodCategory"), dict)
                           else str(data.get("foodCategory", "")),
            nutrients={},
        )

        # Extrair nutrientes
        for nutrient in data.get("foodNutrients", []):
            nutrient_info = nutrient.get("nutrient", {})
            number = str(nutrient_info.get("number", ""))
            amount = nutrient.get("amount")
            if number and amount is not None:
                food.nutrients[number] = {
                    "name": nutrient_info.get("name", ""),
                    "amount": float(amount),
                    "unit": nutrient_info.get("unitName", ""),
                }

        # Salvar no cache
        if self.cache_db_path:
            self._to_cache(food)

        return food

    def to_platform_fields(self, food: USDAFood) -> dict:
        """
        Converte nutrientes USDA para campos da plataforma.
        Valores por 100g (padrao USDA).
        """
        fields = {}
        for nutrient_num, platform_field in USDA_TO_PLATFORM.items():
            nutrient = food.nutrients.get(nutrient_num)
            if nutrient:
                amount = nutrient.get("amount", 0)
                unit = nutrient.get("unit", "").upper()
                # Converter kJ para kcal se necessario
                if nutrient_num == "208" and unit == "KJ":
                    amount = amount / 4.184
                # Formato brasileiro: virgula como decimal
                if isinstance(amount, float):
                    if amount == int(amount):
                        fields[platform_field] = f"{int(amount)},0"
                    else:
                        fields[platform_field] = f"{amount}".replace(".", ",")
                else:
                    fields[platform_field] = str(amount)
        return fields

    def search_and_match(self, query: str) -> Optional[USDAFood]:
        """Busca e retorna o melhor match para um alimento."""
        results = self.search(query, page_size=5)
        if not results:
            return None

        # Pegar o primeiro resultado mais relevante
        best = results[0]
        return self.get_food(best["fdc_id"])

    def _to_cache(self, food: USDAFood):
        """Salva alimento no cache SQLite."""
        try:
            conn = sqlite3.connect(str(self.cache_db_path))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usda_foods (
                    fdc_id TEXT PRIMARY KEY,
                    name TEXT,
                    description TEXT,
                    food_category TEXT,
                    nutrients_json TEXT,
                    fetched_at REAL
                )
            """)
            conn.execute(
                "INSERT OR REPLACE INTO usda_foods "
                "(fdc_id, name, description, food_category, nutrients_json, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (food.fdc_id, food.name, food.description,
                 food.food_category,
                 json.dumps(food.nutrients, ensure_ascii=False),
                 time.time())
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error("Erro ao salvar cache USDA: %s", e)

    def _from_cache(self, fdc_id: str) -> Optional[USDAFood]:
        """Carrega alimento do cache SQLite."""
        try:
            conn = sqlite3.connect(str(self.cache_db_path))
            row = conn.execute(
                "SELECT * FROM usda_foods WHERE fdc_id = ?",
                (fdc_id,)
            ).fetchone()
            conn.close()
            if row:
                return USDAFood(
                    fdc_id=row[0],
                    name=row[1],
                    description=row[2],
                    food_category=row[3],
                    nutrients=json.loads(row[4]),
                )
        except Exception:
            pass
        return None

    def search_and_fetch(self, query: str, max_results: int = 3) -> list[USDAFood]:
        """Busca e busca detalhes dos top resultados."""
        results = self.search(query, page_size=max_results)
        foods = []
        for r in results:
            food = self.get_food(r["fdc_id"])
            if food:
                foods.append(food)
            time.sleep(0.3)  # Rate limiting
        return foods
