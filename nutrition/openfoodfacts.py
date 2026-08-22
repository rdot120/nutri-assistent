"""
Fonte Open Food Facts - rotulos reais de produtos industrializados.

API publica e gratuita (sem chave). Prioridade sobre USDA/IA para
produtos de marca, pois traz o valor do ROTULO REAL e nao estimativas.

Politica de uso: maximo ~1 request/segundo com User-Agent identificado.
Docs: https://openfoodfacts.github.io/openfoodfacts-python/
"""
import logging
import re
import time
import unicodedata
from typing import Optional

import requests
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

# Mapa: campo da plataforma <- chaves possiveis no nutriments do OFF
# (valores de mineral/vitamina podem vir em g, mg ou mcg conforme registro)
_NUTRIENT_MAP = {
    "valorEnergetico429": ["energy-kcal_100g"],
    "carboidratos429": ["carbohydrates_100g"],
    "acucaresTotais429": ["sugars_100g"],
    "acucaresAdicionados": ["added-sugars_100g"],
    "proteinas429": ["proteins_100g"],
    "gordurasTotais429": ["fat_100g"],
    "gordurasSaturadas429": ["saturated-fat_100g"],
    "gordurasTrans429": ["trans-fat_100g"],
    "fibraAlimentar429": ["fiber_100g"],
    "colesterol": ["cholesterol_100g"],          # mg
    "sodio429": ["sodium_100g"],                 # g -> mg (x1000)
    "calcio": ["calcium_100g"],                  # mg (as vezes g)
    "ferro": ["iron_100g"],                      # mg
    "magnesio": ["magnesium_100g"],              # mg
    "potassio": ["potassium_100g"],              # mg
    "zinco": ["zinc_100g"],                      # mg
    "vitaminaC": ["vitamin-c_100g"],             # mg
}

_MG_MINERALS = ("calcio", "ferro", "magnesio", "potassio", "zinco",
                "sodio429")


def _strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


class OpenFoodFactsSource:
    """Busca valores nutricionais de rotulo em produtos do OFF."""

    name = "off"
    BASE = "https://world.openfoodfacts.org"
    MIN_INTERVAL = 1.05  # cortesia com o servidor publico

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self._last_request = 0.0
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "NutriAssistent/1.2 "
                          "(automacao nutricional; github.com/rdot120)"
        })

    def is_available(self) -> bool:
        return True

    def _throttle(self):
        elapsed = time.time() - self._last_request
        if elapsed < self.MIN_INTERVAL:
            time.sleep(self.MIN_INTERVAL - elapsed)
        self._last_request = time.time()

    def search_product(self, name: str) -> Optional[dict]:
        """Busca o melhor produto correspondente ao nome.

        Retorna {"fields": {...}, "product_name": ..., "brands": ...,
                 "score": float} ou None.
        """
        self._throttle()
        try:
            resp = self.session.get(
                f"{self.BASE}/cgi/search.pl",
                params={
                    "search_terms": name,
                    "search_simple": 1,
                    "action": "process",
                    "json": 1,
                    "page_size": 10,
                    "fields": "product_name,product_name_pt,brand_owner,"
                              "brands,nutriments",
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.debug(f"OFF erro para '{name}': {e}")
            return None

        products = data.get("products") or []
        best = None
        best_score = 0.0

        query_norm = _strip_accents(name.lower())
        for prod in products:
            pname = (prod.get("product_name_pt")
                     or prod.get("product_name") or "").strip()
            if not pname or not prod.get("nutriments"):
                continue

            candidate = _strip_accents(pname.lower())
            # token_set_ratio tolera ordem e palavras extras da marca
            score = fuzz.token_set_ratio(query_norm, candidate)
            if score > best_score:
                fields = self._map_nutrients(prod["nutriments"])
                if len(fields) >= 6:  # rotulo util precisa de dados minimos
                    best_score = score
                    best = {
                        "fields": fields,
                        "product_name": pname,
                        "brands": prod.get("brands") or "",
                        "score": score,
                    }

        if best and best_score >= 70:
            best["score"] = best_score
            return best
        return None

    def _map_nutrients(self, nutriments: dict) -> dict:
        """Converte nutriments OFF -> campos RDC 429 da plataforma."""
        fields: dict[str, str] = {}
        for target, keys in _NUTRIENT_MAP.items():
            for k in keys:
                val = nutriments.get(k)
                if not isinstance(val, (int, float)) or val <= 0:
                    continue
                num = float(val)
                if target == "sodio429":
                    num *= 1000.0  # OFF guarda sodio em g
                elif target in _MG_MINERALS and num < 5:
                    num *= 1000.0  # veio em g, converte p/ mg
                if target == "valorEnergetico429":
                    num = round(num)
                else:
                    num = round(num, 2)
                fields[target] = (
                    f"{int(num)},0" if num == int(num)
                    else f"{num}".replace(".", ",")
                )
                break
        return fields

    def search_batch(self, names: list[str],
                     gui_callback=None) -> dict[str, Optional[dict]]:
        """Busca varios nomes sequencialmente (com throttle).

        Retorna {nome.lower().strip(): resultado|None}.
        """
        results: dict[str, Optional[dict]] = {}
        found = 0
        for i, name in enumerate(names, 1):
            res = self.search_product(name)
            results[name.lower().strip()] = res
            if res:
                found += 1
            if i % 25 == 0 and gui_callback:
                gui_callback(f"  Rotulos OF: {i}/{len(names)} buscados, "
                             f"{found} encontrados")
        logger.info(f"OFF: {found}/{len(names)} produtos com rotulo util")
        return results
