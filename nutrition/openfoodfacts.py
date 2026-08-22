"""Fonte Open Food Facts - rotulos reais de produtos industrializados.

Usa o Search API oficial (search.openfoodfacts.org), filtrando produtos
do Brasil e priorizando os mais populares/completos.
"""
import logging
import re
import time

import requests

logger = logging.getLogger(__name__)

SEARCH_URL = "https://search.openfoodfacts.org/search"
USER_AGENT = ("NutriAssistent/1.2 "
              "(https://github.com/rdot120; contato@qualihouse.com.br)")

# Campos OF -> plataforma
_NUTRI_MAP = {
    "valorEnergetico429": ["energy-kcal_100g", "energy_100g"],  # kcal
    "carboidratos429": ["carbohydrates_100g"],
    "acucaresTotais429": ["sugars_100g"],
    "proteinas429": ["proteins_100g"],
    "gordurasTotais429": ["fat_100g"],
    "gordurasSaturadas429": ["saturated-fat_100g"],
    "fibraAlimentar429": ["fiber_100g"],
    "sodio429": ["sodium_100g"],  # g -> mg
}


def _norm(texto: str) -> str:
    """Normaliza para comparacao de nomes."""
    t = texto.lower().strip()
    t = re.sub(r"[áàâãä]", "a", t)
    t = re.sub(r"[éèêë]", "e", t)
    t = re.sub(r"[íìîï]", "i", t)
    t = re.sub(r"[óòôõö]", "o", t)
    t = re.sub(r"[úùûü]", "u", t)
    t = re.sub(r"[ç]", "c", t)
    return re.sub(r"[^a-z0-9 ]", " ", t)


class OpenFoodFactsSource:
    """Busca rotulos reais no Open Food Facts."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        })
        self._last_request = 0.0

    def _throttle(self):
        elapsed = time.time() - self._last_request
        if elapsed < 1.05:
            time.sleep(1.05 - elapsed)
        self._last_request = time.time()

    def search_product(self, query: str) -> dict | None:
        """Busca um produto e retorna {"fields", "product_name", "brands",
        "score"} ou None se nada confiavel for encontrado."""
        try:
            self._throttle()
            resp = self.session.get(
                SEARCH_URL,
                params={
                    "q": query,
                    "page_size": 8,
                    "countries_tags": "brazil",
                    "sort_by": "popularity_key",
                },
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                logger.debug("OF status %s para '%s'",
                             resp.status_code, query)
                return None
            hits = resp.json().get("hits") or []
        except Exception as exc:
            logger.warning("OF erro '%s': %s", query, exc)
            return None

        q_tokens = set(_norm(query).split())
        # Token principal (marca/produto) precisa constar no nome do hit
        _STOP = {"em", "de", "da", "do", "com", "para", "e"}
        main_tokens = q_tokens - _STOP
        best = None
        for hit in hits:
            name = (hit.get("product_name") or "").strip()
            if not name or len(name) < 3:
                continue
            fields = self._extract_fields(hit.get("nutriments") or {})
            if len(fields) < 6 or "valorEnergetico429" not in fields:
                continue

            n_tokens = set(_norm(name).split())
            if main_tokens and not (main_tokens & n_tokens):
                continue

            # Score: completude + quantidade de campos + sobreposicao de nome
            overlap = (len(q_tokens & n_tokens)
                       / max(1, len(q_tokens))) if q_tokens else 0
            score = (min(1.0, hit.get("completeness") or 0) * 30
                     + min(1.0, len(fields) / 8) * 25
                     + overlap * 45)

            if not best or score > best["score"]:
                brands = ", ".join(hit.get("brands") or [])[:60]
                best = {
                    "product_name": name,
                    "brands": brands,
                    "fields": fields,
                    "score": round(min(score, 100.0), 1),
                }

        if best and best["score"] >= 55:
            return best
        return None

    def _extract_fields(self, nutriments: dict) -> dict:
        """Converte nutriments do OF para campos da plataforma."""
        fields = {}
        for plat_key, of_keys in _NUTRI_MAP.items():
            value = None
            for k in of_keys:
                v = nutriments.get(k)
                if isinstance(v, (int, float)) and v == v:  # nao-NaN
                    value = float(v)
                    break
            if value is None:
                continue
            if plat_key == "valorEnergetico429" \
                    and "energy-kcal_100g" not in nutriments:
                value = value / 4.184  # veio em kJ
            if plat_key == "sodio429":
                value = value * 1000.0  # g -> mg
            fields[plat_key] = f"{value:.1f}".rstrip("0").rstrip(".")
        return fields

    def search_batch(self, names: list[str],
                     gui_callback=None) -> dict[str, dict]:
        """Busca varios produtos. Retorna {nome_normalizado: resultado}."""
        out = {}
        total = len(names)
        for i, name in enumerate(names, start=1):
            res = self.search_product(name)
            if gui_callback and i % 5 == 0:
                gui_callback(f"  Rotulos OF: {i}/{total}...")
            if res:
                out[name.lower().strip()] = res
        return out
